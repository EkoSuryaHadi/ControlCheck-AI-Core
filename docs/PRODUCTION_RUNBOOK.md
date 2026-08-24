# ControlCheck Core Internal Production Runbook

This runbook governs the first internal, single-organization production pilot. The release runs as a single replica backed by managed PostgreSQL and one persistent upload volume. JWT, complete RBAC, object storage, public multi-tenancy, and frontend deployment remain out of scope.

## Production boundary

- Every `/v1/*` request requires `Authorization: Bearer <key>`.
- The tenant UUID comes only from `CONTROLCHECK_ORGANIZATION_ID`.
- `X-Organization-ID` is development-only and cannot override the production tenant.
- `/health/live` and `/health/ready` are public and return minimal status only.
- API docs are disabled by default. CORS is absent unless exact HTTPS origins are configured.
- Workbook files must remain on a persistent mounted volume; do not scale beyond a single replica during this pilot.

## Provider prerequisites

Before Deployment, prepare:

1. A managed PostgreSQL 16 database with TLS required, automated backups enabled, and credentials held in the provider's secret manager.
2. A persistent volume mounted at `/var/lib/controlcheck/uploads` and writable by UID/GID `10001`.
3. An HTTPS hostname and reverse proxy or managed ingress. Terminate TLS before the application and forward the original hostname.
4. A random API key of at least 32 characters and one fixed organization UUID.
5. The reviewed image digest produced by the successful `main` CI workflow.

## Required configuration

Start from `.env.example`, replacing every placeholder. Store real values only in the deployment platform's secret/configuration service.

| Variable | Requirement |
|---|---|
| `CONTROLCHECK_ENV` | Exactly `production`. |
| `CONTROLCHECK_DATABASE_URL` | Managed PostgreSQL URL using the `postgresql+psycopg` driver. |
| `CONTROLCHECK_UPLOAD_ROOT` | Absolute mounted path; `/var/lib/controlcheck/uploads` is the container default contract. |
| `CONTROLCHECK_CATALOGUE` | Readable catalogue path, normally `/app/data/controlcheck_rule_catalogue_v0.2.json`. |
| `CONTROLCHECK_ORGANIZATION_ID` | Fixed pilot organization UUID. |
| `CONTROLCHECK_API_KEY` | Random secret of at least 32 characters. |
| `CONTROLCHECK_TRUSTED_HOSTS` | Comma-separated exact API hostnames; no wildcard. Put the health-check host first. |
| `CONTROLCHECK_CORS_ORIGINS` | Optional comma-separated exact HTTPS origins. Empty by default. |
| `CONTROLCHECK_ENABLE_DOCS` | `false` for production. |
| `CONTROLCHECK_MAX_UPLOAD_BYTES` | Positive byte count; default `26214400` (25 MiB). |
| `PORT` | Listener port; default `8000`. |

## Deployment

1. Deploy to staging using the same managed-service classes, mount path, and environment contract as production.
2. Pin the reviewed image by immutable digest. Configure exactly one replica.
3. Mount the persistent upload volume and verify ownership for UID/GID `10001`.
4. Inject configuration and secrets. Never bake them into the image or commit them to Git.
5. Start the container. Its entrypoint applies Alembic migrations before starting Uvicorn.
6. Confirm `GET /health/live` returns `{"status":"live"}` and `GET /health/ready` returns `{"status":"ready"}`.
7. Confirm `/docs` is 404, an unauthenticated `/v1/audits` request is 401, and an authenticated controlled upload succeeds.
8. Promote the same image digest to production and repeat the checks.

## Alembic migrations

The container runs `alembic upgrade head` once before the API starts. For a controlled manual migration, use the same image and production database secret in a one-off job:

```text
alembic upgrade head
alembic current
```

Before promotion, CI must report one linear head and `alembic check` must report no new upgrade operations. Never apply the readable SQL files under `docs/` directly; Alembic is the executable schema authority.

## Controlled release smoke tests

Run Golden and Boundary fixtures only in CI or a staging environment approved for synthetic data. The release gates are:

- Golden Positive: 59 TP, 0 FP, 0 FN, 100% precision and recall.
- Boundary / Negative: zero findings and strict evaluation success.
- Production HTTP: live 200, ready 200, missing bearer key 401, docs 404.
- Persistence: a controlled project, snapshot, analysis run, finding list, and evidence lookup remain organization-scoped.

Do not present controlled-fixture results as customer accuracy on unseen projects.

## API key rotation

1. Generate a new random key of at least 32 characters in the secret manager.
2. Schedule a short maintenance window because this pilot supports one active key.
3. Update `CONTROLCHECK_API_KEY` and restart the single replica.
4. Verify the new key succeeds and the old key returns 401.
5. Revoke and remove the old secret from the deployment platform and operator workstations.
6. Record the rotation time and responsible operator without recording either key.

If a key is suspected compromised, rotate immediately, inspect request IDs and access logs, and treat all activity since the last known-safe time as potentially unauthorized.

## Backup verification

Managed backups are incomplete until restoration is tested.

1. Confirm automated PostgreSQL backups and point-in-time recovery are enabled.
2. Confirm the persistent workbook volume is included in a separate backup or snapshot policy.
3. At least monthly, restore the database and upload volume into an isolated environment.
4. Verify database records that reference stored workbook keys can read the matching restored files.
5. Run readiness, one controlled persisted analysis, and evidence retrieval against the restore.
6. Record recovery-point and recovery-time observations and delete the isolated restore safely.

## Rollback

Application rollback uses the previous known-good image digest:

1. Stop new uploads and record the failing release digest and request IDs.
2. Determine whether the release applied a database migration. Do not run a downgrade unless that exact downgrade was reviewed and tested.
3. Redeploy the previous image as one replica with the existing persistent volume and database.
4. Verify live, ready, authentication, and one read-only persisted query.
5. Re-enable uploads only after data compatibility is confirmed.

If a forward-only schema change prevents application rollback, keep traffic disabled and perform a reviewed forward fix. Restore from backup only when data integrity cannot be recovered safely in place.

## Incident diagnostics

1. Capture the UTC time, response status, safe `X-Request-ID`, image digest, and affected endpoint. Never copy API keys or database URLs into tickets.
2. Check `/health/live`. If it fails, inspect container scheduling and process logs.
3. Check `/health/ready`. If it fails, inspect managed PostgreSQL reachability, persistent-volume mount/permissions, and catalogue availability without exposing details to the caller.
4. Search application and ingress logs by request ID. Production responses intentionally omit stack traces.
5. For repeated authentication failures, rotate the key if compromise is plausible.
6. For storage/database disagreement, stop uploads, preserve both systems, and reconcile keys before changing records.
7. Record the resolution, affected data window, and required regression test.

## Pilot limitations and escalation

Keep a single replica because uploads use a local persistent filesystem. Scaling, rolling multi-replica deployment, JWT/RBAC, S3-compatible object storage, customer self-service, and frontend access require a later approved phase and a PRD update before implementation.
