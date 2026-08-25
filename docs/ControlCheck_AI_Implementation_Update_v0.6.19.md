# ControlCheck AI — Implementation Update v0.6.19

**Version:** 0.6.19

**Date:** 2026-08-25

**Status:** Consolidated baseline implemented on `codex/public-beta-v1`; not deployed

**Scope:** Public-beta PR 1 baseline consolidation and production-quality gates

## Objective

Establish one clean baseline for later public-beta work without losing the accepted v0.6.x product behavior or the governed deterministic-ingestion contracts. This update does not implement the public beta.

## Verified consolidated baseline

- The accepted homepage, onboarding, Actions, Governance, Finding Closure, reporting, custom JWT/RBAC, health scoring, and deterministic 20-rule engine remain present.
- Controlled validation remains deterministic: the Golden Positive contract expects 59 true positives with no false positives or false negatives, and the Boundary/Negative contract expects zero findings.
- PostgreSQL persistence tests use a session-scoped `controlcheck_test_<uuid>` database created from a test admin URL and dropped at teardown. Shared developer/application databases are never migration or teardown targets.
- The active Alembic chain includes the additive governed canonical schema and governed analysis metadata revisions on the homepage head.
- Governed workbook ingestion preserves source rows, colliding headers, source coordinates, mapping provenance, project metadata, six canonical domains, and immutable snapshot lifecycle behavior.
- Deterministic analysis loads governed facts from PostgreSQL, fails closed for unavailable domains, and persists ordered executed-rule and skipped-rule provenance.
- Tenant-scoped upload, list, detail, and analysis endpoints use the existing tenant boundary. No legacy production API-key gate was introduced.
- Accepted simplified snapshots remain compatibility-readable; new snapshot writes use governed storage.

## Production failure behavior

- Production configuration rejects an insecure JWT secret, a missing database URL, wildcard/empty CORS, and an unsupported storage backend.
- Serverless production rejects ephemeral local workbook storage. A durable serverless adapter is intentionally deferred rather than simulated with `/tmp`.
- A missing production catalogue fails startup before an application is served.
- The Vercel entrypoint no longer catches import/configuration failure and substitutes a healthy diagnostic application.
- No diagnostic route publishes traceback text, Python paths, current directories, environment-variable names, or import internals.
- Readiness returns `503 not_ready` for database failure without returning connection or exception details.
- Malformed workbook/parser failures return a safe `422`; database/storage failures return a safe `503`; unexpected ingestion failures return a safe `500`.

## CI baseline gates

The CI workflow now requires:

1. Python compilation for `api`, `src`, `tests`, `tools`, and `alembic`;
2. focused production-configuration and serverless-entrypoint tests;
3. the full pytest suite against a live PostgreSQL 16 service and disposable database fixture;
4. an explicit Alembic metadata-drift check;
5. frontend dependency installation with `npm ci` from `package-lock.json`;
6. TypeScript typecheck plus Vite production build; and
7. frontend lint.

## Explicitly deferred

The following approved public-beta design work is not implemented by v0.6.19 and belongs in later governed PRs:

- Clerk email-OTP identity and Clerk-to-personal-workspace mapping;
- private Vercel Blob storage, retention, cleanup, and deletion;
- fair-use quota and abuse controls;
- first-party product telemetry;
- run-level and finding-level feedback;
- billing, pricing, subscriptions, and payments; and
- the public landing/demo/workspace UI defined for the public beta.

The existing Vite/React UI and custom JWT/RBAC remain baseline behavior; they must not be described as the finished public-beta identity or interface.

## Definition of done

- [x] Accepted v0.6.x and deterministic governed-pipeline behavior preserved.
- [x] Production diagnostic false-success path removed.
- [x] Safe production configuration and ingestion error classifications covered test-first.
- [x] Required backend, migration, and frontend CI gates declared.
- [x] Public-beta features explicitly deferred.
- [ ] Public-beta identity, durable Vercel storage, quota, telemetry, feedback, and UI implemented in later PRs.
- [ ] Deployment and public-launch verification completed in a separately approved release.
