from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .api_models import (
    AnalysisRunListResponse, AnalysisRunResponse, EvidenceListResponse, EvidenceResponse,
    FindingListResponse, FindingResponse, FindingStatusUpdate,
    HealthSnapshotResponse, HealthTrendListResponse,
    ProjectCreate, ProjectListResponse, ProjectResponse, TenantContext,
)
from .application import AnalysisService
from .errors import ControlCheckApplicationError
from .loader import WorkbookSchemaError
from .logging import clear_log_context, configure_logging, get_logger, set_log_context
from .models import AuditResult
from .persistence.repositories import (
    AnalysisRepository, FindingRepository, HealthRepository, OrganizationRepository, ProjectRepository
)

from .persistence.database import create_session_factory
from .service import run_audit
from .settings import PersistenceSettings
from .storage import FileStorage, LocalFileStorage
from .versioning import VersionCompatibilityError

logger = get_logger("api")


DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _default_catalogue() -> Path:
    configured = os.environ.get("CONTROLCHECK_CATALOGUE")
    if configured:
        return Path(configured)
    bundled = Path(__file__).resolve().parents[2] / "data" / "controlcheck_rule_catalogue_v0.1.json"
    return bundled


def create_app(
    catalogue_path: Path | str | None = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    session_factory: sessionmaker[Session] | None = None,
    storage: FileStorage | None = None,
) -> FastAPI:
    configure_logging()
    catalogue = Path(catalogue_path) if catalogue_path else _default_catalogue()
    application = FastAPI(title="ControlCheck Core API", version=__version__)

    @application.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        set_log_context(request_id=request_id)
        start_time = perf_counter()
        logger.info("HTTP %s %s [start]", request.method, request.url.path)
        try:
            response = await call_next(request)
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info("HTTP %s %s [status: %d, duration: %s ms]", request.method, request.url.path, response.status_code, duration_ms)
            return response
        except Exception:
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            logger.exception("HTTP %s %s [unhandled exception, duration: %s ms]", request.method, request.url.path, duration_ms)
            raise
        finally:
            clear_log_context()

    @application.exception_handler(ControlCheckApplicationError)
    async def handle_application_error(request: Request, exc: ControlCheckApplicationError):
        logger.warning(
            "Application error %s (status %d): %s [req_id: %s]",
            exc.code,
            exc.status_code,
            exc.message,
            request.state.request_id,
        )
        error = {
            "code": exc.code,
            "message": exc.message,
            "request_id": request.state.request_id,
        }
        if exc.analysis_run_id is not None:
            error["analysis_run_id"] = str(exc.analysis_run_id)
        return JSONResponse(status_code=exc.status_code, content={"error": error})


    def require_tenant(x_organization_id: str | None = Header(None)) -> TenantContext:
        if x_organization_id is None:
            raise ControlCheckApplicationError(
                "missing_tenant_context", "X-Organization-ID is required", 400
            )
        try:
            org_uuid = UUID(x_organization_id)
            set_log_context(organization_id=str(org_uuid))
            return TenantContext(organization_id=org_uuid)
        except ValueError as exc:
            raise ControlCheckApplicationError(
                "invalid_tenant_context", "X-Organization-ID must be a UUID", 400
            ) from exc


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

    @application.post("/v1/audits", response_model=AuditResult)
    async def audit(file: UploadFile) -> AuditResult:
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            raise HTTPException(415, {"code": "unsupported_file_type"})
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > max_upload_bytes:
                raise HTTPException(413, {"code": "file_too_large", "max_bytes": max_upload_bytes})
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
            limit: int = 50,
            offset: int = 0,
            tenant: TenantContext = Depends(require_tenant),
        ) -> ProjectListResponse:
            require_matching_organization(organization_id, tenant)
            limit = max(1, min(limit, 200))
            offset = max(0, offset)
            with session_factory() as session:
                if OrganizationRepository(session).get(organization_id) is None:
                    raise ControlCheckApplicationError(
                        "organization_not_found", "Organization was not found", 404
                    )
                projects, total = ProjectRepository(session).list_for_organization(
                    organization_id, limit=limit, offset=offset
                )
                return ProjectListResponse(
                    items=[ProjectResponse.model_validate(project) for project in projects],
                    total=total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(projects) < total),
                )

        if storage is not None:
            analysis_service = AnalysisService(session_factory, storage, catalogue)

            @application.post(
                "/v1/projects/{project_id}/analysis-runs",
                response_model=AnalysisRunResponse,
                status_code=201,
            )
            async def create_analysis_run(
                project_id: UUID,
                file: UploadFile,
                x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
                tenant: TenantContext = Depends(require_tenant),
            ) -> AnalysisRunResponse:
                if not file.filename or not file.filename.lower().endswith(".xlsx"):
                    raise ControlCheckApplicationError(
                        "unsupported_file_type", "Only .xlsx workbooks are supported", 415
                    )
                data = bytearray()
                while chunk := await file.read(1024 * 1024):
                    data.extend(chunk)
                    if len(data) > max_upload_bytes:
                        raise ControlCheckApplicationError(
                            "file_too_large",
                            f"Upload exceeds the {max_upload_bytes} byte limit",
                            413,
                        )
                run = analysis_service.run(
                    tenant.organization_id,
                    project_id,
                    file.filename,
                    file.content_type or "application/octet-stream",
                    bytes(data),
                    idempotency_key=x_idempotency_key,
                )
                return AnalysisRunResponse.model_validate(run)

        @application.get(
            "/v1/projects/{project_id}/analysis-runs",
            response_model=AnalysisRunListResponse,
        )
        def list_analysis_runs(
            project_id: UUID,
            limit: int = 50,
            offset: int = 0,
            tenant: TenantContext = Depends(require_tenant),
        ) -> AnalysisRunListResponse:
            limit = max(1, min(limit, 200))
            offset = max(0, offset)
            with session_factory() as session:
                if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                    raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
                runs, total = AnalysisRepository(session).list_runs(
                    tenant.organization_id, project_id, limit=limit, offset=offset
                )
                return AnalysisRunListResponse(
                    items=[AnalysisRunResponse.model_validate(run) for run in runs],
                    total=total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(runs) < total),
                )

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
            status: str | None = None, limit: int = 50, offset: int = 0,
            tenant: TenantContext = Depends(require_tenant),
        ) -> FindingListResponse:
            limit = max(1, min(limit, 200))
            offset = max(0, offset)
            with session_factory() as session:
                if AnalysisRepository(session).get_run(tenant.organization_id, run_id) is None:
                    raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found", 404)
                findings, total = FindingRepository(session).list_for_run(
                    tenant.organization_id, run_id, rule_id=rule_id, severity=severity,
                    category=category, entity_id=entity_id, status=status,
                    limit=limit, offset=offset,
                )
                return FindingListResponse(
                    items=[FindingResponse.model_validate(item) for item in findings],
                    total=total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(findings) < total),
                )


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

        @application.get("/v1/analysis-runs/{run_id}/health", response_model=HealthSnapshotResponse)
        def get_analysis_run_health(
            run_id: UUID,
            tenant: TenantContext = Depends(require_tenant),
        ) -> HealthSnapshotResponse:
            with session_factory() as session:
                if AnalysisRepository(session).get_run(tenant.organization_id, run_id) is None:
                    raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found", 404)
                snapshot = HealthRepository(session).get_by_run(tenant.organization_id, run_id)
                if snapshot is None:
                    raise ControlCheckApplicationError("health_snapshot_not_found", "Health snapshot not found for this run", 404)
                return HealthSnapshotResponse.model_validate(snapshot)

        @application.get("/v1/projects/{project_id}/health-trend", response_model=HealthTrendListResponse)
        def get_project_health_trend(
            project_id: UUID,
            limit: int = 50,
            offset: int = 0,
            tenant: TenantContext = Depends(require_tenant),
        ) -> HealthTrendListResponse:
            limit = max(1, min(limit, 200))
            offset = max(0, offset)
            with session_factory() as session:
                if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                    raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
                items, total = HealthRepository(session).list_trends(
                    tenant.organization_id, project_id, limit=limit, offset=offset
                )
                return HealthTrendListResponse(
                    items=[HealthSnapshotResponse.model_validate(item) for item in items],
                    total=total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(items) < total),
                )


    return application


def create_configured_app() -> FastAPI:
    catalogue = _default_catalogue()
    try:
        settings = PersistenceSettings.from_env()
    except RuntimeError:
        return create_app(catalogue)
    return create_app(
        catalogue,
        session_factory=create_session_factory(settings.database_url),
        storage=LocalFileStorage(settings.upload_root),
    )


app = create_configured_app()
