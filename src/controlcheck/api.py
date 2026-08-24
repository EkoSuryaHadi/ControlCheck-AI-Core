from __future__ import annotations

import os
import hashlib
import logging
import re
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .api_models import (
    AnalysisRunListResponse, AnalysisRunResponse, EvidenceListResponse, EvidenceResponse,
    DatasetSnapshotListResponse, DatasetSnapshotResponse, DomainStatusResponse,
    FindingListResponse, FindingResponse, FindingStatusUpdate,
    ProjectCreate, ProjectListResponse, ProjectResponse, TenantContext,
)
from .application import AnalysisService
from .errors import ControlCheckApplicationError
from .ingestion.profile import load_mapping_profile, mapping_profile_sha256
from .ingestion.service import SnapshotIngestionService, _dedupe_key
from .health import check_readiness
from .loader import WorkbookSchemaError
from .models import AuditResult
from .persistence.ingestion_repositories import SnapshotRepository
from .persistence.models import DatasetDomainStatusRecord, MappingProfileVersionRecord, SourceFileRecord
from .persistence.repositories import AnalysisRepository, FindingRepository, OrganizationRepository, ProjectRepository
from .persistence.database import create_session_factory
from .service import run_audit
from .security import build_access_dependency, build_tenant_dependency
from .settings import ApplicationSettings
from .storage import FileStorage, LocalFileStorage
from .versioning import VersionCompatibilityError


DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
logger = logging.getLogger(__name__)


def _default_catalogue() -> Path:
    configured = os.environ.get("CONTROLCHECK_CATALOGUE")
    if configured:
        return Path(configured)
    bundled = Path(__file__).resolve().parents[2] / "data" / "controlcheck_rule_catalogue_v0.1.json"
    return bundled


def create_app(
    catalogue_path: Path | str | None = None,
    max_upload_bytes: int | None = None,
    session_factory: sessionmaker[Session] | None = None,
    storage: FileStorage | None = None,
    settings: ApplicationSettings | None = None,
) -> FastAPI:
    runtime_settings = settings or ApplicationSettings.from_env()
    catalogue = Path(catalogue_path) if catalogue_path else (
        runtime_settings.catalogue_path or _default_catalogue()
    )
    upload_limit = (
        runtime_settings.max_upload_bytes
        if max_upload_bytes is None
        else max_upload_bytes
    )
    docs_enabled = runtime_settings.enable_docs
    application = FastAPI(
        title="ControlCheck Core API",
        version=__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    if runtime_settings.is_production:
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(runtime_settings.trusted_hosts),
        )
    if runtime_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(runtime_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    require_access = build_access_dependency(runtime_settings)
    require_tenant = build_tenant_dependency(runtime_settings)
    application.state.require_access = require_access
    application.state.require_tenant = require_tenant

    @application.middleware("http")
    async def attach_request_id(request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            supplied_request_id
            if SAFE_REQUEST_ID.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(ControlCheckApplicationError)
    async def handle_application_error(request: Request, exc: ControlCheckApplicationError):
        error = {
            "code": exc.code,
            "message": exc.message,
            "request_id": request.state.request_id,
        }
        if exc.analysis_run_id is not None:
            error["analysis_run_id"] = str(exc.analysis_run_id)
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code, content={"error": error}, headers=headers
        )

    if runtime_settings.is_production:
        @application.exception_handler(Exception)
        async def handle_unexpected_error(request: Request, exc: Exception):
            request_id = getattr(request.state, "request_id", str(uuid4()))
            logger.exception("Unhandled request error; request_id=%s", request_id)
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_server_error",
                        "message": "The request could not be completed",
                        "request_id": request_id,
                    }
                },
                headers={"X-Request-ID": request_id},
            )

    def require_matching_organization(path_id: UUID, tenant: TenantContext) -> None:
        if path_id != tenant.organization_id:
            raise ControlCheckApplicationError(
                "tenant_scope_violation",
                "Requested organization does not match tenant context",
                403,
            )

    @application.get("/health")
    def health():
        return {"status": "ok", "engine_version": __version__}

    @application.get("/health/live")
    def health_live():
        return {"status": "live"}

    @application.get("/health/ready")
    def health_ready():
        ready = check_readiness(session_factory, storage, catalogue)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready"},
        )

    @application.post("/v1/audits", response_model=AuditResult)
    async def audit(
        file: UploadFile,
        _access: None = Depends(require_access),
    ) -> AuditResult:
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            raise HTTPException(415, {"code": "unsupported_file_type"})
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > upload_limit:
                raise HTTPException(413, {"code": "file_too_large", "max_bytes": upload_limit})
        try:
            return run_audit(BytesIO(data), catalogue)
        except WorkbookSchemaError as exc:
            raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc
        except VersionCompatibilityError as exc:
            raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc

    if session_factory is not None:
        @application.post(
            "/v1/organizations/{organization_id}/projects",
            response_model=ProjectResponse,
            status_code=201,
        )
        def create_project(
            organization_id: UUID,
            payload: ProjectCreate,
            tenant: TenantContext = Depends(require_tenant),
        ) -> ProjectResponse:
            require_matching_organization(organization_id, tenant)
            with session_factory() as session:
                if OrganizationRepository(session).get(organization_id) is None:
                    raise ControlCheckApplicationError(
                        "organization_not_found", "Organization was not found", 404
                    )
                project = ProjectRepository(session).create(
                    organization_id,
                    payload.code.strip(),
                    payload.name.strip(),
                    payload.currency.upper(),
                )
                session.commit()
                return ProjectResponse.model_validate(project)

        @application.get(
            "/v1/organizations/{organization_id}/projects",
            response_model=ProjectListResponse,
        )
        def list_projects(
            organization_id: UUID,
            tenant: TenantContext = Depends(require_tenant),
        ) -> ProjectListResponse:
            require_matching_organization(organization_id, tenant)
            with session_factory() as session:
                if OrganizationRepository(session).get(organization_id) is None:
                    raise ControlCheckApplicationError(
                        "organization_not_found", "Organization was not found", 404
                    )
                projects = ProjectRepository(session).list_for_organization(organization_id)
                return ProjectListResponse(
                    items=[ProjectResponse.model_validate(project) for project in projects]
                )

        if storage is not None:
            analysis_service = AnalysisService(session_factory, storage, catalogue)
            mapping_profile = load_mapping_profile(
                catalogue.parent / "controlcheck_mapping_profile_v0.1.json"
            )
            snapshot_ingestion = SnapshotIngestionService(
                session_factory, storage, mapping_profile
            )

            def snapshot_response(session: Session, snapshot) -> DatasetSnapshotResponse:
                source = session.get(SourceFileRecord, snapshot.source_file_id)
                profile = session.get(
                    MappingProfileVersionRecord, snapshot.mapping_profile_version_id
                )
                statuses = session.scalars(
                    select(DatasetDomainStatusRecord).where(
                        DatasetDomainStatusRecord.organization_id == snapshot.organization_id,
                        DatasetDomainStatusRecord.project_id == snapshot.project_id,
                        DatasetDomainStatusRecord.dataset_snapshot_id == snapshot.id,
                    ).order_by(DatasetDomainStatusRecord.domain)
                ).all()
                error_count = sum(item.error_count for item in statuses)
                warning_count = sum(item.warning_count for item in statuses)
                return DatasetSnapshotResponse(
                    id=snapshot.id,
                    organization_id=snapshot.organization_id,
                    project_id=snapshot.project_id,
                    source_project_id=snapshot.source_project_id,
                    dataset_version=snapshot.dataset_version,
                    data_date=snapshot.data_date,
                    mapping_profile_version=profile.version if profile else mapping_profile.version,
                    mapping_profile_sha256=profile.sha256 if profile else mapping_profile_sha256(mapping_profile),
                    workbook_sha256=source.sha256 if source else "",
                    status=snapshot.status,
                    row_count_raw=snapshot.row_count_raw,
                    row_count_canonical=snapshot.row_count_canonical,
                    error_count=error_count,
                    warning_count=warning_count,
                    domain_statuses={
                        item.domain: DomainStatusResponse.model_validate(item)
                        for item in statuses
                    },
                    created_at=snapshot.created_at,
                )

            async def read_snapshot_upload(file: UploadFile) -> bytes:
                if not file.filename or not file.filename.lower().endswith(".xlsx"):
                    raise ControlCheckApplicationError(
                        "unsupported_template", "Only .xlsx workbooks are supported", 415
                    )
                data = bytearray()
                while chunk := await file.read(1024 * 1024):
                    data.extend(chunk)
                    if len(data) > upload_limit:
                        raise ControlCheckApplicationError(
                            "snapshot_ingestion_failed",
                            f"Upload exceeds the {upload_limit} byte limit",
                            413,
                        )
                return bytes(data)

            @application.post(
                "/v1/projects/{project_id}/dataset-snapshots",
                response_model=DatasetSnapshotResponse,
            )
            async def upload_dataset_snapshot(
                project_id: UUID,
                file: UploadFile,
                force_new: bool = False,
                tenant: TenantContext = Depends(require_tenant),
            ) -> DatasetSnapshotResponse:
                data = await read_snapshot_upload(file)
                profile_hash = mapping_profile_sha256(mapping_profile)
                duplicate = None
                with session_factory() as session:
                    project = ProjectRepository(session).get_scoped(
                        tenant.organization_id, project_id
                    )
                    if project is not None and not force_new:
                        duplicate = SnapshotRepository(session).find_duplicate(
                            tenant.organization_id,
                            project_id,
                            _dedupe_key(
                                tenant.organization_id,
                                project_id,
                                hashlib.sha256(data).hexdigest(),
                                profile_hash,
                            ),
                        )
                try:
                    snapshot = snapshot_ingestion.ingest(
                        tenant.organization_id,
                        project_id,
                        file.filename or "dataset.xlsx",
                        file.content_type or "application/octet-stream",
                        data,
                        force_new=force_new,
                    )
                except ControlCheckApplicationError:
                    raise
                except Exception as exc:
                    raise ControlCheckApplicationError(
                        "snapshot_ingestion_failed",
                        "Dataset snapshot ingestion failed",
                        422,
                    ) from exc
                with session_factory() as session:
                    response = snapshot_response(session, snapshot)
                from fastapi.responses import JSONResponse as _JSONResponse
                return _JSONResponse(
                    status_code=200 if duplicate is not None and not force_new else 201,
                    content=response.model_dump(mode="json"),
                )

            @application.get(
                "/v1/projects/{project_id}/dataset-snapshots",
                response_model=DatasetSnapshotListResponse,
            )
            def list_dataset_snapshots(
                project_id: UUID,
                tenant: TenantContext = Depends(require_tenant),
            ) -> DatasetSnapshotListResponse:
                with session_factory() as session:
                    if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                        raise ControlCheckApplicationError(
                            "project_not_found", "Project was not found for this organization", 404
                        )
                    snapshots = SnapshotRepository(session).list_scoped(
                        tenant.organization_id, project_id
                    )
                    return DatasetSnapshotListResponse(
                        items=[snapshot_response(session, item) for item in snapshots]
                    )

            @application.get(
                "/v1/projects/{project_id}/dataset-snapshots/{snapshot_id}",
                response_model=DatasetSnapshotResponse,
            )
            def get_dataset_snapshot(
                project_id: UUID,
                snapshot_id: UUID,
                tenant: TenantContext = Depends(require_tenant),
            ) -> DatasetSnapshotResponse:
                with session_factory() as session:
                    snapshot = SnapshotRepository(session).get_scoped(
                        tenant.organization_id, project_id, snapshot_id
                    )
                    if snapshot is None:
                        raise ControlCheckApplicationError(
                            "snapshot_not_found", "Dataset snapshot was not found for this project", 404
                        )
                    return snapshot_response(session, snapshot)

            @application.post(
                "/v1/projects/{project_id}/dataset-snapshots/{snapshot_id}/analysis-runs",
                response_model=AnalysisRunResponse,
                status_code=201,
            )
            def analyze_dataset_snapshot(
                project_id: UUID,
                snapshot_id: UUID,
                tenant: TenantContext = Depends(require_tenant),
            ) -> AnalysisRunResponse:
                run = analysis_service.run_snapshot(
                    tenant.organization_id, project_id, snapshot_id
                )
                return AnalysisRunResponse.model_validate(run)

            @application.post(
                "/v1/projects/{project_id}/analysis-runs",
                response_model=AnalysisRunResponse,
                status_code=201,
            )
            async def create_analysis_run(
                project_id: UUID,
                file: UploadFile,
                tenant: TenantContext = Depends(require_tenant),
            ) -> AnalysisRunResponse:
                if not file.filename or not file.filename.lower().endswith(".xlsx"):
                    raise ControlCheckApplicationError(
                        "unsupported_file_type", "Only .xlsx workbooks are supported", 415
                    )
                data = bytearray()
                while chunk := await file.read(1024 * 1024):
                    data.extend(chunk)
                    if len(data) > upload_limit:
                        raise ControlCheckApplicationError(
                            "file_too_large",
                            f"Upload exceeds the {upload_limit} byte limit",
                            413,
                        )
                run = analysis_service.run(
                    tenant.organization_id,
                    project_id,
                    file.filename,
                    file.content_type or "application/octet-stream",
                    bytes(data),
                )
                return AnalysisRunResponse.model_validate(run)

        @application.get(
            "/v1/projects/{project_id}/analysis-runs",
            response_model=AnalysisRunListResponse,
        )
        def list_analysis_runs(
            project_id: UUID,
            tenant: TenantContext = Depends(require_tenant),
        ) -> AnalysisRunListResponse:
            with session_factory() as session:
                if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                    raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
                runs = AnalysisRepository(session).list_runs(tenant.organization_id, project_id)
                return AnalysisRunListResponse(items=[AnalysisRunResponse.model_validate(run) for run in runs])

        @application.get("/v1/analysis-runs/{run_id}", response_model=AnalysisRunResponse)
        def get_analysis_run(run_id: UUID, tenant: TenantContext = Depends(require_tenant)) -> AnalysisRunResponse:
            with session_factory() as session:
                run = AnalysisRepository(session).get_run(tenant.organization_id, run_id)
                if run is None:
                    raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found", 404)
                return AnalysisRunResponse.model_validate(run)

        @application.get("/v1/analysis-runs/{run_id}/findings", response_model=FindingListResponse)
        def list_findings(
            run_id: UUID, rule_id: str | None = None, severity: str | None = None,
            category: str | None = None, entity_id: str | None = None,
            status: str | None = None, tenant: TenantContext = Depends(require_tenant),
        ) -> FindingListResponse:
            with session_factory() as session:
                if AnalysisRepository(session).get_run(tenant.organization_id, run_id) is None:
                    raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found", 404)
                findings = FindingRepository(session).list_for_run(
                    tenant.organization_id, run_id, rule_id=rule_id, severity=severity,
                    category=category, entity_id=entity_id, status=status,
                )
                return FindingListResponse(items=[FindingResponse.model_validate(item) for item in findings])

        @application.get("/v1/findings/{finding_id}", response_model=FindingResponse)
        def get_finding(finding_id: UUID, tenant: TenantContext = Depends(require_tenant)) -> FindingResponse:
            with session_factory() as session:
                finding = FindingRepository(session).get(tenant.organization_id, finding_id)
                if finding is None:
                    raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
                return FindingResponse.model_validate(finding)

        @application.get("/v1/findings/{finding_id}/evidence", response_model=EvidenceListResponse)
        def get_finding_evidence(finding_id: UUID, tenant: TenantContext = Depends(require_tenant)) -> EvidenceListResponse:
            with session_factory() as session:
                repository = FindingRepository(session)
                if repository.get(tenant.organization_id, finding_id) is None:
                    raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
                evidence = repository.evidence(tenant.organization_id, finding_id)
                return EvidenceListResponse(items=[EvidenceResponse.model_validate(item) for item in evidence])

        @application.patch("/v1/findings/{finding_id}/status", response_model=FindingResponse)
        def update_finding_status(
            finding_id: UUID, payload: FindingStatusUpdate,
            tenant: TenantContext = Depends(require_tenant),
        ) -> FindingResponse:
            with session_factory() as session:
                repository = FindingRepository(session)
                try:
                    finding = repository.update_status(tenant.organization_id, finding_id, payload.status)
                except ValueError as exc:
                    raise ControlCheckApplicationError("invalid_finding_status", "Finding status is invalid", 422) from exc
                if finding is None:
                    raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
                session.commit()
                return FindingResponse.model_validate(finding)

    return application


def create_configured_app() -> FastAPI:
    settings = ApplicationSettings.from_env()
    catalogue = settings.catalogue_path or _default_catalogue()
    if settings.database_url is None:
        return create_app(catalogue, settings=settings)
    return create_app(
        catalogue,
        session_factory=create_session_factory(settings.database_url),
        storage=LocalFileStorage(settings.upload_root),
        settings=settings,
    )


app = create_configured_app()
