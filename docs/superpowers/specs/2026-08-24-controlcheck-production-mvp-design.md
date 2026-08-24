# ControlCheck AI Core: Internal Production MVP

**Status:** Approved design
**Date:** 24 August 2026
**Base:** Phase 4B Core at commit `66d6246`
**Repository:** `EkoSuryaHadi/ControlCheck-AI-Core`

## 1. Objective

Ship the deterministic ControlCheck Core API as a secure internal production service for one organization. The first release protects every business endpoint with one server-managed bearer API key, derives tenant context from server configuration, runs against managed PostgreSQL, stores uploads on a persistent mounted volume, and deploys as one Docker container instance.

This release is a controlled pilot boundary, not the final SaaS identity model. JWT login, multiple organizations, detailed RBAC, frontend, object storage, background workers, and high availability remain later phases.

## 2. Approved Approach

Use a single-organization internal API with a fixed server-side tenant and one bearer API key.

- `/health/live` and `/health/ready` are public and return minimal status only.
- Every `/v1/*` endpoint requires `Authorization: Bearer <key>` in production.
- Production never trusts `X-Organization-ID` as an authorization boundary.
- The organization UUID comes from `CONTROLCHECK_ORGANIZATION_ID`.
- The API key comes from `CONTROLCHECK_API_KEY` and is compared in constant time.
- Development keeps the existing tenant-header behavior so current workflows and tests remain usable.
- The first deployment runs one application replica with a persistent upload volume.
- Managed PostgreSQL is the durable system of record.

Rejected alternatives:

1. Full JWT authentication and RBAC now: appropriate for SaaS, but expands schema, user lifecycle, authorization, and support scope before the pilot proves product value.
2. Public API with only `X-Organization-ID`: fast but not an authentication mechanism and therefore unacceptable for production.
3. Immediate S3-compatible object storage: stronger scaling characteristics, but unnecessary for the first single-instance pilot. A storage interface already exists, so this can follow without changing engine behavior.

## 3. Scope

### 3.1 Included

- Production-aware settings validation.
- Bearer API-key authentication for all `/v1/*` routes.
- Fixed server-side organization context in production.
- Constant-time credential comparison and generic authentication failures.
- Liveness and database/storage readiness endpoints.
- Trusted-host validation.
- Production OpenAPI/docs disablement.
- Strict, opt-in CORS configuration; default is disabled.
- Existing application upload-size enforcement plus documented edge limit.
- Generic production 500 responses with request IDs and server-side logging.
- Non-root Docker image and deterministic startup command.
- Alembic migration execution before application startup.
- GitHub Actions gates for compile, migrations, full tests, Golden 59, and Boundary zero.
- Deployment/runbook documentation and PRD alignment.

### 3.2 Excluded

- Password login, JWT issuance, refresh tokens, user lifecycle, and password reset.
- Complete RBAC and per-project user permissions.
- Multiple customer organizations in one deployed pilot instance.
- Browser-cookie authentication and CSRF workflow.
- Frontend application.
- S3-compatible object storage.
- Distributed rate limiting, multiple API replicas, and background queues.
- Automated database backup implementation; the hosting provider backup policy is documented and verified operationally.

## 4. Architecture

```text
Internal client
  -> HTTPS platform edge
     -> host validation + edge request limit
        -> FastAPI container
           -> bearer API-key dependency
           -> fixed organization context
           -> deterministic engine / snapshot services
              -> managed PostgreSQL
              -> persistent mounted upload volume
```

TLS termination is supplied by the hosting platform. The application does not implement TLS itself and only trusts forwarded proxy information configured by the deployment platform.

## 5. Configuration Contract

`CONTROLCHECK_ENV` accepts `development`, `test`, or `production`. Production startup fails closed when any required value is missing or invalid.

Required in production:

- `CONTROLCHECK_DATABASE_URL`: PostgreSQL SQLAlchemy URL.
- `CONTROLCHECK_UPLOAD_ROOT`: absolute path inside the mounted persistent volume.
- `CONTROLCHECK_CATALOGUE`: existing governed catalogue path.
- `CONTROLCHECK_ORGANIZATION_ID`: UUID of the one authorized organization.
- `CONTROLCHECK_API_KEY`: randomly generated secret of at least 32 characters.
- `CONTROLCHECK_TRUSTED_HOSTS`: comma-separated exact hostnames.

Optional:

- `CONTROLCHECK_MAX_UPLOAD_BYTES`: positive integer; default 25 MiB.
- `CONTROLCHECK_CORS_ORIGINS`: comma-separated exact HTTPS origins. Empty means no CORS middleware.
- `CONTROLCHECK_ENABLE_DOCS`: defaults false in production and true outside production.

Secrets are never logged, returned in API responses, committed to Git, or included in example values that resemble real credentials.

## 6. Authentication and Tenant Boundary

The production authentication dependency parses the standard `Authorization` header using the bearer scheme. Missing, malformed, or incorrect credentials return the same HTTP 401 envelope and `WWW-Authenticate: Bearer`; responses do not reveal which check failed.

The API key is compared with `secrets.compare_digest`. No custom hashing or encryption scheme is introduced. Secret rotation is performed by changing the environment secret and redeploying; a short maintenance window is acceptable for the pilot.

Once authenticated, the dependency returns `TenantContext` using `CONTROLCHECK_ORGANIZATION_ID`. A caller cannot select another organization with a header. Organization IDs in resource paths must match this server-side context, and repository queries retain their existing organization predicates.

The stateless `/v1/audits` endpoint is also protected in production because uploaded workbooks and findings are business-sensitive.

## 7. HTTP and Application Security

- `TrustedHostMiddleware` rejects unknown Host headers in production.
- CORS is absent unless exact origins are configured. Wildcard origins and credentialed wildcard CORS are prohibited.
- `/docs`, `/redoc`, and `/openapi.json` are disabled in production by default.
- FastAPI debug mode and Uvicorn reload are never enabled in the production entrypoint.
- Existing `.xlsx` extension and bounded streaming checks remain. The hosting edge must enforce a request limit no smaller than, and preferably equal to, the application limit.
- Write request models continue to allow only explicit fields.
- SQL access continues through parameterized SQLAlchemy statements.
- Unhandled errors return a generic response with the request ID; stack traces and secrets remain server-side.
- Request logging includes method, normalized route, status, duration, and request ID, but excludes authorization headers, database URLs, workbook bodies, and sensitive query data.

Rate limiting is enforced at the hosting edge for the pilot. An in-process limiter is explicitly excluded because it is not reliable after horizontal scaling.

## 8. Health and Startup

`GET /health/live` proves the process can serve requests. It does not touch dependencies.

`GET /health/ready` performs bounded checks:

- PostgreSQL responds to `SELECT 1`.
- the configured upload directory exists and is writable;
- the configured catalogue file is readable.

It returns HTTP 200 with `{"status": "ready"}` or HTTP 503 with `{"status": "not_ready"}`. It does not expose connection strings, paths, exception messages, table names, or stack traces.

Container startup runs `alembic upgrade head` before Uvicorn. The pilot uses one replica, avoiding concurrent migration runners. A failed migration prevents the application from starting.

## 9. Container and Deployment

The Docker image:

- uses a pinned Python 3.11 slim base image;
- installs only runtime dependencies;
- runs as an unprivileged application user;
- copies governed runtime catalogue/profile data explicitly;
- writes only to the configured upload mount and temporary directory;
- starts Uvicorn without reload or debug;
- exposes one HTTP port and supplies a liveness health check.

The deployment is platform-neutral and can run on Render, Railway, Fly.io, or an equivalent container platform. The initial operational contract requires managed PostgreSQL, TLS at the edge, secret injection, one persistent disk mount, one application replica, and provider-level backup retention.

## 10. CI Release Gates

Every pull request and push to `main` runs:

1. install from the locked project environment;
2. Python compilation;
3. PostgreSQL service startup;
4. `alembic upgrade head` and `alembic check`;
5. the complete test suite;
6. Golden fixture assertion: 59 findings;
7. Boundary fixture assertion: zero findings;
8. Docker image build.

Deployment occurs only from a commit that passes all gates. Secrets are available only to the deployment job and never to pull-request jobs from untrusted forks.

## 11. Error Handling and Auditability

Existing structured application errors remain stable. Authentication errors gain a stable `authentication_required` code. Readiness failures remain deliberately generic.

Every response keeps `X-Request-ID`. A client-supplied request ID is accepted only after validation to a bounded safe format; otherwise the server generates a UUID. Logs use the same ID so an incident can be traced without exposing internal errors to clients.

Finding, analysis, snapshot, and audit-log persistence behavior remains unchanged. Authentication does not change deterministic calculations, evidence, or catalogue identity.

## 12. Testing Strategy

TDD is mandatory for behavior changes.

- Settings tests cover missing secrets, invalid environment, invalid UUID, weak key, non-absolute upload path, trusted hosts, CORS origins, and docs defaults.
- Auth tests prove all `/v1` routes deny missing/invalid keys and accept the configured key.
- Tenant tests prove an authenticated caller cannot override the fixed organization.
- Health tests cover ready and not-ready database/storage/catalogue states without leaking details.
- Middleware tests cover trusted hosts, CORS defaults, docs disablement, generic 500 responses, and request-ID validation.
- Existing 195 tests remain green in development/test mode.
- Docker smoke tests verify container startup and liveness.

## 13. Documentation Alignment

Implementation updates:

- `README.md` with secure local and production startup.
- `.env.example` with placeholders only.
- a production runbook covering deployment, migrations, key rotation, backup verification, rollback, and incident diagnostics.
- PRD v0.5 recording the internal production pilot boundary and explicit RBAC/object-storage deferrals.

Historical PRD, ERD, and rule-catalogue artifacts remain immutable.

## 14. Rollout and Rollback

Rollout sequence:

1. provision managed PostgreSQL and persistent disk;
2. create the fixed organization record and store its UUID as a secret;
3. generate and store the API key in the platform secret manager;
4. deploy to staging and run migrations;
5. execute Golden, Boundary, upload, snapshot, analysis, and evidence smoke tests;
6. deploy the same image digest to production;
7. verify liveness, readiness, and one controlled audit.

Rollback redeploys the previous image digest. Database migrations in this phase are additive or configuration-only; any future destructive migration requires a separate rollback design and verified backup before release.

## 15. Acceptance Criteria

- Production startup fails when required security configuration is missing or weak.
- Public health endpoints reveal no sensitive configuration.
- Every `/v1/*` endpoint returns 401 without the correct bearer key.
- A valid key receives only the fixed server-side organization context.
- Unknown Host values are rejected.
- Production docs and OpenAPI endpoints return 404 by default.
- Readiness returns 503 when PostgreSQL, storage, or catalogue is unavailable.
- The container runs as non-root and starts only after successful migrations.
- CI passes the complete suite, Golden 59, Boundary zero, Alembic drift, and Docker build.
- Existing Phase 4B deterministic outputs and evidence remain unchanged.
- README, runbook, and PRD v0.5 document the production pilot boundary and deferred full RBAC.
