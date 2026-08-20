from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker


from . import __version__
from .api_models import (
    AIAskRequest, AIAskResponse, AIConversationListResponse, AIConversationResponse, AIMessageResponse,
    AnalysisRunListResponse, AnalysisRunResponse, EvidenceListResponse, EvidenceResponse,
    FindingListResponse, FindingResponse, FindingStatusUpdate,
    HealthSnapshotResponse, HealthTrendListResponse,
    ProjectCreate, ProjectListResponse, ProjectResponse, TenantContext,
    TokenResponse, UserLogin, UserRegister, UserResponse,
)
from .ai.assistant import ProjectAIAssistant
from .application import AnalysisService
from .auth import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)
from .errors import ControlCheckApplicationError
from .loader import WorkbookSchemaError
from .logging import clear_log_context, configure_logging, get_logger, set_log_context
from .models import AuditResult
from .persistence.repositories import (
    AIRepository, AnalysisRepository, FindingRepository, HealthRepository,
    OrganizationRepository, ProjectRepository, UserRepository,
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

    # Production CORS Middleware
    cors_origins_env = os.environ.get("CONTROLCHECK_CORS_ORIGINS", "*")
    origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
                    return TenantContext(organization_id=org_uuid)
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
        if session_factory is not None:
            try:
                with session_factory() as session:
                    from sqlalchemy import text
                    session.execute(text("SELECT 1"))
            except Exception as exc:
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "database": "unreachable", "error": str(exc)},
                )
        return {"status": "ready", "database": "connected" if session_factory else "offline_mode"}


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
        settings = PersistenceSettings.from_env()
    except RuntimeError:
        return create_app(catalogue)
    return create_app(
        catalogue,
        session_factory=create_session_factory(settings.database_url),
        storage=LocalFileStorage(settings.upload_root),
    )


app = create_configured_app()
