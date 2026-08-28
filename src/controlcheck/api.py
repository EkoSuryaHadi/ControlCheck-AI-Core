from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker



from . import __version__
from .api_models import (
    AIAskRequest, AIAskResponse, AIConversationListResponse, AIConversationResponse, AIMessageResponse,
    AnalysisRunListResponse, AnalysisRunResponse, EvidenceListResponse, EvidenceResponse,
    DatasetSnapshotListResponse, DatasetSnapshotResponse, DomainStatusResponse,
    FindingListResponse, FindingResponse, FindingStatusUpdate,
    HealthSnapshotResponse, HealthTrendListResponse,
    ProjectCreate, ProjectListResponse, ProjectResponse, TenantContext,
    TokenResponse, UserLogin, UserRegister, UserResponse,
    FeedbackCreate, FeedbackResponse, OwnerMetricsResponse, TelemetryEventCreate,
)
from .ai.assistant import ProjectAIAssistant
from .application import AnalysisService
from .auth import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)
from .errors import ControlCheckApplicationError, InvalidWorkbookError, StorageUnavailableError
from .config import load_catalogue
from .ingestion.profile import load_mapping_profile
from .ingestion.service import SnapshotIngestionService
from .loader import WorkbookSchemaError
from .limits import PUBLIC_BETA_MAX_UPLOAD_BYTES
from .logging import clear_log_context, configure_logging, get_logger, set_log_context
from .metrics import metrics_collector
from .models import AuditResult
from .persistence.repositories import (
    AIRepository, AnalysisRepository, FindingRepository, HealthRepository,
    OrganizationRepository, ProjectRepository, UserRepository,
)
from .persistence.ingestion_repositories import SnapshotRepository
from .persistence.telemetry_repository import TelemetryRepository
from .persistence.models import (
    GovernedDatasetDomainStatusRecord,
    GovernedMappingProfileVersionRecord,
    SourceFileRecord,
)



from .persistence.database import create_session_factory
from .service import run_audit
from .settings import PersistenceSettings, ProductionSettings
from .storage import FileStorage, LocalFileStorage
from .versioning import VersionCompatibilityError

logger = get_logger("api")


DEFAULT_MAX_UPLOAD_BYTES = PUBLIC_BETA_MAX_UPLOAD_BYTES


def _default_catalogue() -> Path:
    configured = os.environ.get("CONTROLCHECK_CATALOGUE")
    if configured:
        return Path(configured)
    data_dir = Path(__file__).resolve().parents[2] / "data"
    v02 = data_dir / "controlcheck_rule_catalogue_v0.2.json"
    if v02.exists():
        return v02
    return data_dir / "controlcheck_rule_catalogue_v0.1.json"



def create_app(
    catalogue_path: Path | str | None = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    session_factory: sessionmaker[Session] | None = None,
    storage: FileStorage | None = None,
    cors_origins: list[str] | None = None,
    trusted_hosts: list[str] | None = None,
) -> FastAPI:
    configure_logging()
    catalogue = Path(catalogue_path) if catalogue_path else _default_catalogue()
    application = FastAPI(title="ControlCheck Core API", version=__version__)

    # Production CORS Middleware
    cors_origins_env = os.environ.get("CONTROLCHECK_CORS_ORIGINS", "*")
    origins = cors_origins or [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    configured_hosts = trusted_hosts or [
        host.strip()
        for host in os.environ.get("CONTROLCHECK_TRUSTED_HOSTS", "*").split(",")
        if host.strip()
    ]
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=configured_hosts or ["*"],
    )

    @application.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        set_log_context(request_id=request_id)
        metrics_collector.inc_active_requests()
        start_time = perf_counter()
        logger.info("HTTP %s %s [start]", request.method, request.url.path)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            
            # Security Headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            
            logger.info("HTTP %s %s [status: %d, duration: %s ms]", request.method, request.url.path, response.status_code, duration_ms)
            return response
        except Exception:
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            logger.exception("HTTP %s %s [unhandled exception, duration: %s ms]", request.method, request.url.path, duration_ms)
            raise
        finally:
            duration_sec = perf_counter() - start_time
            metrics_collector.record_request(request.method, request.url.path, status_code, duration_sec)
            metrics_collector.dec_active_requests()
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

    @application.exception_handler(StorageUnavailableError)
    async def handle_storage_unavailable(request: Request, exc: StorageUnavailableError):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.safe_message,
                    "request_id": request.state.request_id,
                }
            },
        )


    def require_tenant(
        x_organization_id: str | None = Header(None),
        authorization: str | None = Header(None),
    ) -> TenantContext:
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:].strip()
            try:
                payload = decode_token(token)
                org_str = payload.get("org_id")
                if org_str:
                    org_uuid = UUID(org_str)
                    set_log_context(organization_id=str(org_uuid))
                    user_id = None
                    if payload.get("sub"):
                        try:
                            user_id = UUID(str(payload["sub"]))
                        except ValueError:
                            user_id = None
                    return TenantContext(
                        organization_id=org_uuid,
                        user_id=user_id,
                        email=str(payload.get("email")) if payload.get("email") else None,
                        role=str(payload.get("role")) if payload.get("role") else None,
                    )
            except Exception as exc:
                raise ControlCheckApplicationError(
                    "invalid_token", "Authentication token is invalid or expired", 401
                ) from exc

        if x_organization_id is None:
            raise ControlCheckApplicationError(
                "missing_tenant_context", "X-Organization-ID or Authorization header is required", 400
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

    @application.get("/health/live")
    def health_live():
        return {"status": "live", "engine_version": __version__}

    @application.get("/health/ready")
    def health_ready():
        checks = {
            "database": "offline_mode",
            "storage": "unconfigured",
            "catalogue": "loaded" if catalogue.exists() else "missing",
        }
        not_ready = False
        if storage is not None:
            try:
                storage_ready = storage.is_ready()
            except Exception:
                storage_ready = False
            checks["storage"] = "ready" if storage_ready else "unavailable"
            not_ready = not_ready or not storage_ready
        if session_factory is not None:
            try:
                with session_factory() as session:
                    from sqlalchemy import text
                    session.execute(text("SELECT 1"))
                checks["database"] = "connected"
            except Exception:
                checks["database"] = "unreachable"
                not_ready = True
        if not_ready:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "checks": checks},
            )
        return {
            "status": "ready",
            "checks": checks,
            "engine_version": __version__,
        }

    @application.get("/metrics", response_class=PlainTextResponse)
    def prometheus_metrics():
        return metrics_collector.generate_prometheus_output()

    # Static & SPA Frontend Mounting
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not frontend_dist.exists():
        frontend_dist = Path("/app/frontend/dist")

    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            application.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @application.get("/favicon.png", include_in_schema=False)
        def favicon():
            fav = frontend_dist / "favicon.png"
            if fav.exists():
                return FileResponse(fav)
            legacy_fav = Path(__file__).resolve().parent / "web" / "favicon.png"
            return FileResponse(legacy_fav)

        spa_routes = [
            "/dashboard", "/findings", "/findings/{finding_id}", "/data",
            "/assistant", "/reports", "/cost", "/schedule", "/progress",
            "/projects", "/settings", "/login"
        ]
        for route in spa_routes:
            @application.get(route, include_in_schema=False)
            def spa_page():
                return FileResponse(frontend_dist / "index.html")

    web_dir = Path(__file__).resolve().parent / "web"
    if web_dir.exists():
        application.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

        @application.get("/", include_in_schema=False)
        def index():
            return FileResponse(web_dir / "index.html")
    elif frontend_dist.exists() and (frontend_dist / "index.html").exists():
        @application.get("/", include_in_schema=False)
        def index_spa():
            return FileResponse(frontend_dist / "index.html")



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
        except VersionCompatibilityError as exc:
            if catalogue_path is not None:
                raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc
            # Fallback to check if a specific matching catalogue version exists in data/
            try:
                from .loader import load_workbook
                from .config import ThresholdConfig
                from .engine import ControlEngine, RuleContext
                from .rules import ALL_RULES
                dataset = load_workbook(BytesIO(data))
                data_dir = Path(__file__).resolve().parents[2] / "data"
                matching = data_dir / f"controlcheck_rule_catalogue_v{dataset.dataset_version}.json"
                if matching.exists():
                    loaded_cat = load_catalogue(matching)
                    context = RuleContext(catalogue=loaded_cat, thresholds=ThresholdConfig())
                    return ControlEngine(ALL_RULES).run(dataset, context)
            except Exception:
                pass
            raise HTTPException(422, {"code": "incompatible_artifact_versions", "message": "Incompatible workbook and catalogue versions"})
        except WorkbookSchemaError as exc:
            raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc
        except (InvalidWorkbookError, ValidationError) as exc:
            raise HTTPException(
                422,
                {
                    "code": InvalidWorkbookError.code,
                    "message": InvalidWorkbookError.safe_message,
                },
            ) from exc



    if session_factory is not None:
        def record_product_event(
            tenant: TenantContext,
            event_name: str,
            *,
            project_id: UUID | None = None,
            analysis_run_id: UUID | None = None,
            finding_id: UUID | None = None,
            metadata: dict | None = None,
        ) -> None:
            try:
                with session_factory() as session:
                    TelemetryRepository(session).record_event(
                        organization_id=tenant.organization_id,
                        user_id=tenant.user_id,
                        project_id=project_id,
                        analysis_run_id=analysis_run_id,
                        finding_id=finding_id,
                        event_name=event_name,
                        metadata=metadata,
                    )
                    session.commit()
            except Exception:
                logger.warning("Product telemetry could not be persisted", exc_info=True)

        def require_owner(tenant: TenantContext) -> None:
            configured = {
                item.strip().lower()
                for item in os.environ.get("CONTROLCHECK_OWNER_EMAILS", "").split(",")
                if item.strip()
            }
            if tenant.role not in {"org_admin", "owner", "org_owner"} and (not tenant.email or tenant.email.lower() not in configured):
                raise ControlCheckApplicationError("owner_access_required", "Owner access is required", 403)

        @application.post("/v1/auth/register", response_model=TokenResponse, status_code=201)
        def register(payload: UserRegister) -> TokenResponse:
            with session_factory() as session:
                user_repo = UserRepository(session)
                if user_repo.get_by_email(payload.email):
                    raise ControlCheckApplicationError("email_already_registered", "Email is already in use", 409)
                user = user_repo.create_user(
                    email=payload.email,
                    password_hash=hash_password(payload.password),
                    full_name=payload.full_name,
                )
                org_id = None
                role = None
                if payload.organization_name:
                    from .persistence.models import OrganizationRecord
                    slug = payload.organization_name.strip().lower().replace(" ", "-")
                    org = OrganizationRecord(name=payload.organization_name.strip(), slug=slug)
                    session.add(org)
                    session.flush()
                    user_repo.add_org_member(org.id, user.id, role="org_admin")
                    org_id = org.id
                    role = "org_admin"
                session.commit()
                access_tok = create_access_token(user.id, user.email, organization_id=org_id, role=role)
                refresh_tok = create_refresh_token(user.id)
                if org_id is not None:
                    record_product_event(
                        TenantContext(organization_id=org_id, user_id=user.id, email=user.email, role=role),
                        "registration_completed",
                    )
                return TokenResponse(access_token=access_tok, refresh_token=refresh_tok)

        @application.post("/v1/auth/login", response_model=TokenResponse)
        def login(payload: UserLogin) -> TokenResponse:
            with session_factory() as session:
                user_repo = UserRepository(session)
                user = user_repo.get_by_email(payload.email)
                if user is None or not verify_password(payload.password, user.password_hash):
                    raise ControlCheckApplicationError("invalid_credentials", "Invalid email or password", 401)
                from .persistence.models import OrganizationMemberRecord
                from sqlalchemy import select
                membership = session.scalar(
                    select(OrganizationMemberRecord).where(OrganizationMemberRecord.user_id == user.id)
                )
                org_id = membership.organization_id if membership else None
                role = membership.role if membership else None
                access_tok = create_access_token(user.id, user.email, organization_id=org_id, role=role)
                refresh_tok = create_refresh_token(user.id)
                return TokenResponse(access_token=access_tok, refresh_token=refresh_tok)

        @application.post("/v1/telemetry/events", status_code=202)
        def create_telemetry_event(
            payload: TelemetryEventCreate,
            tenant: TenantContext = Depends(require_tenant),
        ) -> dict:
            try:
                with session_factory() as session:
                    if payload.project_id is not None and ProjectRepository(session).get_scoped(tenant.organization_id, payload.project_id) is None:
                        raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
                    if payload.analysis_run_id is not None and AnalysisRepository(session).get_run(tenant.organization_id, payload.analysis_run_id) is None:
                        raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found for this organization", 404)
                    if payload.finding_id is not None and FindingRepository(session).get(tenant.organization_id, payload.finding_id) is None:
                        raise ControlCheckApplicationError("finding_not_found", "Finding was not found for this organization", 404)
                    event = TelemetryRepository(session).record_event(
                        organization_id=tenant.organization_id,
                        user_id=tenant.user_id,
                        project_id=payload.project_id,
                        analysis_run_id=payload.analysis_run_id,
                        finding_id=payload.finding_id,
                        event_name=payload.event_name,
                        metadata=payload.metadata,
                    )
                    session.commit()
                    return {"accepted": True, "event_id": str(event.id)}
            except ValueError as exc:
                raise ControlCheckApplicationError("invalid_telemetry_event", str(exc), 422) from exc

        @application.post("/v1/runs/{run_id}/feedback", response_model=FeedbackResponse, status_code=201)
        def create_run_feedback(
            run_id: UUID,
            payload: FeedbackCreate,
            tenant: TenantContext = Depends(require_tenant),
        ) -> FeedbackResponse:
            with session_factory() as session:
                run = AnalysisRepository(session).get_run(tenant.organization_id, run_id)
                if run is None:
                    raise ControlCheckApplicationError("analysis_run_not_found", "Analysis run was not found", 404)
                feedback = TelemetryRepository(session).add_feedback(
                    organization_id=tenant.organization_id,
                    project_id=run.project_id,
                    analysis_run_id=run.id,
                    user_id=tenant.user_id,
                    rating=payload.rating,
                    comment=payload.comment,
                )
                session.commit()
                record_product_event(tenant, "run_feedback_submitted", project_id=run.project_id, analysis_run_id=run.id)
                return FeedbackResponse.model_validate(feedback)

        @application.post("/v1/findings/{finding_id}/feedback", response_model=FeedbackResponse, status_code=201)
        def create_finding_feedback(
            finding_id: UUID,
            payload: FeedbackCreate,
            tenant: TenantContext = Depends(require_tenant),
        ) -> FeedbackResponse:
            with session_factory() as session:
                finding = FindingRepository(session).get(tenant.organization_id, finding_id)
                if finding is None:
                    raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
                feedback = TelemetryRepository(session).add_feedback(
                    organization_id=tenant.organization_id,
                    project_id=finding.project_id,
                    analysis_run_id=finding.analysis_run_id,
                    finding_id=finding.id,
                    user_id=tenant.user_id,
                    rating=payload.rating,
                    comment=payload.comment,
                )
                session.commit()
                record_product_event(tenant, "finding_feedback_submitted", project_id=finding.project_id, analysis_run_id=finding.analysis_run_id, finding_id=finding.id)
                return FeedbackResponse.model_validate(feedback)

        @application.get("/v1/owner/metrics", response_model=OwnerMetricsResponse)
        def get_owner_metrics(tenant: TenantContext = Depends(require_tenant)) -> OwnerMetricsResponse:
            require_owner(tenant)
            with session_factory() as session:
                return OwnerMetricsResponse.model_validate(TelemetryRepository(session).metrics(tenant.organization_id))

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
                record_product_event(tenant, "project_created", project_id=project.id)
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

        @application.delete("/v1/projects/{project_id}", status_code=204)
        def delete_project(
            project_id: UUID,
            tenant: TenantContext = Depends(require_tenant),
        ) -> None:
            with session_factory() as session:
                if not ProjectRepository(session).delete_scoped(tenant.organization_id, project_id):
                    raise ControlCheckApplicationError("project_not_found", "Project was not found", 404)
                session.commit()

        if storage is not None:
            analysis_service = AnalysisService(session_factory, storage, catalogue)
            mapping_profile = load_mapping_profile(
                catalogue.parent / "controlcheck_mapping_profile_v0.1.json"
            )
            snapshot_ingestion = SnapshotIngestionService(
                session_factory, storage, mapping_profile
            )

            def snapshot_response(
                session: Session, snapshot
            ) -> DatasetSnapshotResponse:
                source = session.scalar(
                    select(SourceFileRecord).where(
                        SourceFileRecord.id == snapshot.source_file_id,
                        SourceFileRecord.organization_id
                        == snapshot.organization_id,
                        SourceFileRecord.project_id == snapshot.project_id,
                    )
                )
                profile_id = getattr(
                    snapshot, "mapping_profile_version_id", None
                )
                profile = (
                    session.get(GovernedMappingProfileVersionRecord, profile_id)
                    if profile_id is not None
                    else None
                )
                statuses = session.scalars(
                    select(GovernedDatasetDomainStatusRecord)
                    .where(
                        GovernedDatasetDomainStatusRecord.organization_id
                        == snapshot.organization_id,
                        GovernedDatasetDomainStatusRecord.project_id
                        == snapshot.project_id,
                        GovernedDatasetDomainStatusRecord.dataset_snapshot_id
                        == snapshot.id,
                    )
                    .order_by(GovernedDatasetDomainStatusRecord.domain)
                ).all()
                return DatasetSnapshotResponse(
                    id=snapshot.id,
                    organization_id=snapshot.organization_id,
                    project_id=snapshot.project_id,
                    source_project_id=snapshot.source_project_id,
                    source_project_name=getattr(
                        snapshot, "source_project_name", None
                    ),
                    dataset_version=snapshot.dataset_version,
                    data_date=snapshot.data_date,
                    mapping_profile_version=(
                        profile.version if profile is not None else None
                    ),
                    mapping_profile_sha256=(
                        profile.sha256 if profile is not None else None
                    ),
                    workbook_sha256=source.sha256 if source is not None else "",
                    status=snapshot.status,
                    row_count_raw=getattr(snapshot, "row_count_raw", None),
                    row_count_canonical=getattr(
                        snapshot, "row_count_canonical", None
                    ),
                    error_count=sum(item.error_count for item in statuses),
                    warning_count=sum(
                        item.warning_count for item in statuses
                    ),
                    domain_statuses={
                        item.domain: DomainStatusResponse.model_validate(item)
                        for item in statuses
                    },
                    created_at=snapshot.created_at,
                    storage_contract=getattr(
                        snapshot, "storage_contract", "governed"
                    ),
                )

            async def read_snapshot_upload(file: UploadFile) -> bytes:
                if not file.filename or not file.filename.lower().endswith(".xlsx"):
                    raise ControlCheckApplicationError(
                        "unsupported_template",
                        "Only .xlsx workbooks are supported",
                        415,
                    )
                data = bytearray()
                while chunk := await file.read(1024 * 1024):
                    data.extend(chunk)
                    if len(data) > max_upload_bytes:
                        raise ControlCheckApplicationError(
                            "snapshot_ingestion_failed",
                            f"Upload exceeds the {max_upload_bytes} byte limit",
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
            ):
                data = await read_snapshot_upload(file)
                try:
                    ingestion = snapshot_ingestion.ingest(
                        tenant.organization_id,
                        project_id,
                        file.filename or "dataset.xlsx",
                        file.content_type or "application/octet-stream",
                        data,
                        force_new=force_new,
                    )
                except ControlCheckApplicationError:
                    raise
                except StorageUnavailableError:
                    raise
                except (InvalidWorkbookError, ValidationError) as exc:
                    raise ControlCheckApplicationError(
                        InvalidWorkbookError.code,
                        InvalidWorkbookError.safe_message,
                        422,
                    ) from exc
                except (SQLAlchemyError, OSError) as exc:
                    raise ControlCheckApplicationError(
                        "snapshot_service_unavailable",
                        "Dataset snapshot service is temporarily unavailable",
                        503,
                    ) from exc
                except Exception as exc:
                    raise ControlCheckApplicationError(
                        "snapshot_ingestion_failed",
                        "Dataset snapshot ingestion failed",
                        500,
                    ) from exc
                snapshot = ingestion.snapshot
                with session_factory() as session:
                    response = snapshot_response(session, snapshot)
                return JSONResponse(
                    status_code=200 if ingestion.outcome == "deduplicated" else 201,
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
                    if (
                        ProjectRepository(session).get_scoped(
                            tenant.organization_id, project_id
                        )
                        is None
                    ):
                        raise ControlCheckApplicationError(
                            "project_not_found",
                            "Project was not found for this organization",
                            404,
                        )
                    snapshots = SnapshotRepository(session).list_scoped(
                        tenant.organization_id, project_id
                    )
                    return DatasetSnapshotListResponse(
                        items=[
                            snapshot_response(session, snapshot)
                            for snapshot in snapshots
                        ]
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
                            "snapshot_not_found",
                            "Dataset snapshot was not found for this project",
                            404,
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
                try:
                    run = analysis_service.run(
                        tenant.organization_id,
                        project_id,
                        file.filename,
                        file.content_type or "application/octet-stream",
                        bytes(data),
                        idempotency_key=x_idempotency_key,
                    )
                except (InvalidWorkbookError, ValidationError) as exc:
                    record_product_event(tenant, "upload_failed", project_id=project_id, metadata={"reason": "invalid_workbook"})
                    raise ControlCheckApplicationError(
                        InvalidWorkbookError.code,
                        InvalidWorkbookError.safe_message,
                        422,
                    ) from exc
                except Exception:
                    record_product_event(tenant, "analysis_failed", project_id=project_id)
                    raise
                record_product_event(tenant, "upload_accepted", project_id=project_id, analysis_run_id=run.id)
                if str(run.status).lower() in {"succeeded", "completed"}:
                    record_product_event(
                        tenant,
                        "analysis_completed",
                        project_id=project_id,
                        analysis_run_id=run.id,
                        metadata={"finding_count": run.finding_count, "rule_count": run.rule_count},
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

        @application.post("/v1/projects/{project_id}/ai/ask", response_model=AIAskResponse)
        def ask_project_ai(
            project_id: UUID,
            payload: AIAskRequest,
            tenant: TenantContext = Depends(require_tenant),
        ) -> AIAskResponse:
            with session_factory() as session:
                project = ProjectRepository(session).get_scoped(tenant.organization_id, project_id)
                if project is None:
                    raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)

                ai_repo = AIRepository(session)
                conv_id = payload.conversation_id
                if conv_id is None:
                    conv = ai_repo.create_conversation(
                        organization_id=tenant.organization_id,
                        project_id=project_id,
                        title=payload.question[:80],
                    )
                    conv_id = conv.id
                else:
                    conv = ai_repo.get_conversation(tenant.organization_id, conv_id)
                    if conv is None:
                        raise ControlCheckApplicationError("conversation_not_found", "Conversation was not found", 404)

                # Record user question
                ai_repo.add_message(conv_id, role="user", content=payload.question)

                # Execute grounded reasoning
                assistant = ProjectAIAssistant(tenant.organization_id, project_id, session)
                result = assistant.ask(payload.question)

                # Record assistant response
                ai_repo.add_message(
                    conv_id,
                    role="assistant",
                    content=result["answer"],
                    tool_calls=result.get("key_evidence"),
                )
                session.commit()

                return AIAskResponse(
                    conversation_id=conv_id,
                    answer=result["answer"],
                    key_evidence=result.get("key_evidence", []),
                    impact=result.get("impact", ""),
                    recommended_action=result.get("recommended_action", ""),
                    confidence=result.get("confidence", "high"),
                    data_caveat=result.get("data_caveat"),
                    evidence_references=result.get("evidence_references", []),
                )

        @application.get("/v1/projects/{project_id}/ai/conversations", response_model=AIConversationListResponse)
        def list_project_ai_conversations(
            project_id: UUID,
            limit: int = 50,
            offset: int = 0,
            tenant: TenantContext = Depends(require_tenant),
        ) -> AIConversationListResponse:
            limit = max(1, min(limit, 200))
            offset = max(0, offset)
            with session_factory() as session:
                if ProjectRepository(session).get_scoped(tenant.organization_id, project_id) is None:
                    raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
                items, total = AIRepository(session).list_conversations(
                    tenant.organization_id, project_id, limit=limit, offset=offset
                )
                return AIConversationListResponse(
                    items=[AIConversationResponse.model_validate(item) for item in items],
                    total=total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(items) < total),
                )

        @application.get("/v1/ai/conversations/{conversation_id}/messages", response_model=list[AIMessageResponse])
        def list_conversation_messages(
            conversation_id: UUID,
            tenant: TenantContext = Depends(require_tenant),
        ) -> list[AIMessageResponse]:
            with session_factory() as session:
                conv = AIRepository(session).get_conversation(tenant.organization_id, conversation_id)
                if conv is None:
                    raise ControlCheckApplicationError("conversation_not_found", "Conversation was not found", 404)
                messages = AIRepository(session).list_messages(conversation_id)
                return [AIMessageResponse.model_validate(m) for m in messages]



    return application


def create_configured_app() -> FastAPI:
    catalogue = _default_catalogue()
    try:
        prod_settings = ProductionSettings.from_env()
    except Exception as exc:
        logger.error("Configuration error on startup: %s", exc)
        raise

    if prod_settings.env == "production" and not catalogue.is_file():
        raise ValueError("Production rule catalogue is missing or unreadable")
    if prod_settings.env == "production":
        try:
            load_catalogue(catalogue)
        except Exception as exc:
            raise ValueError("Production rule catalogue is invalid") from exc

    if not prod_settings.database_url:
        return create_app(catalogue)

    # Storage Backend Selection
    storage: FileStorage
    if prod_settings.storage_backend == "s3":
        from .storage_s3 import S3FileStorage
        storage = S3FileStorage(
            bucket=prod_settings.s3_bucket,
            region=prod_settings.s3_region,
            endpoint_url=prod_settings.s3_endpoint_url,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
    else:
        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        default_upload = "/tmp/uploads" if is_serverless else "var/uploads"
        upload_root = Path(os.environ.get("CONTROLCHECK_UPLOAD_ROOT", default_upload))
        storage = LocalFileStorage(upload_root)

    return create_app(
        catalogue,
        max_upload_bytes=prod_settings.max_upload_bytes,
        session_factory=create_session_factory(prod_settings.database_url),
        storage=storage,
        cors_origins=prod_settings.cors_origins,
        trusted_hosts=prod_settings.trusted_hosts,
    )
