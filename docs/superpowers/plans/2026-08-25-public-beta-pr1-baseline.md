# ControlCheck AI Public Beta PR 1 — Baseline Consolidation

> Execution authority: `docs/superpowers/specs/2026-08-24-controlcheck-vercel-public-beta-ui-design.md`

## Goal

Build a clean, testable baseline for the public beta without losing the accepted v0.6.x product work or the governed canonical-ingestion contracts. This plan stops before Clerk, Blob, quota, telemetry, and public-beta UI implementation.

## Global Constraints

- Work only on `codex/public-beta-v1`, based on `origin/homepage-v3`.
- Preserve the deterministic engine and all controlled ground-truth behavior.
- Preserve Actions, Governance, Finding Closure, reporting, public homepage, onboarding, and v0.6.1–v0.6.18 fixes.
- Reconcile canonical-ingestion behavior from `codex/production-hardening`; do not merge its legacy API-key authentication over the future Clerk design.
- Add tests before every production behavior change and verify RED before GREEN.
- Add new Alembic revisions on the active homepage migration head; do not reuse the obsolete `20260818_0002` revision ID.
- Do not push, merge to `master`, deploy, or perform destructive database operations in this plan.

## Task 1 — Disposable PostgreSQL Test Baseline

**Files:** `tests/persistence/conftest.py`, `tests/conftest.py`, `.github/workflows/ci.yml`, and focused test utilities only.

1. Add a failing fixture-level regression test proving persistence tests never downgrade or mutate the shared `controlcheck` database.
2. Implement a session-scoped disposable database named with a fixed safe prefix plus UUID, created from the local/CI Postgres admin connection and dropped at session teardown.
3. Point Alembic and persistence fixtures exclusively to that disposable database.
4. Make CI start PostgreSQL explicitly and pass the test server URL; ensure local absence still skips persistence tests rather than failing unrelated unit tests.
5. Verify migration upgrade, downgrade/upgrade, metadata drift, persistence tests, then the full backend suite.

## Task 2 — Governed Canonical Schema Reconciliation

**Source contracts:** commits `942c9e6` through `a5a34ba` on `codex/production-hardening`.

**Behavior to preserve:** lossless governed workbook rows, collision-safe headers, mapping boundaries, immutable canonical snapshots, `BIGINT` source row references, and lossless `source_project_name`.

1. Write migration/model contract tests against the active homepage schema and watch them fail for missing governed structures or incompatible column types.
2. Add one additive Alembic revision on the current head, using new table/column names where existing simplified canonical tables overlap.
3. Port the minimum model and repository behavior needed to satisfy the governed contracts without removing homepage tables or v0.6.x migrations.
4. Add compatibility reads for existing simplified snapshots; new writes use governed snapshots.
5. Verify fresh upgrade, upgrade from homepage head, downgrade boundary, metadata drift, and canonical schema tests.

## Task 3 — Canonical Pipeline and Domain Gating

**Source contracts:** commits `d0ab1c0` through `9bfa0e3` on `codex/production-hardening`.

1. Add failing tests for lossless extraction, governed mapping, snapshot failure lifecycle, database-backed engine loading, domain gating, project-name preservation, and tenant-scoped snapshot API.
2. Port extraction and mapping as isolated ingestion modules; preserve original workbook coordinates and header collisions.
3. Persist immutable snapshots transactionally; failures must not leave a valid partial snapshot.
4. Load engine datasets from persisted governed facts and skip rules whose required domains are unavailable, recording deterministic skip metadata.
5. Expose tenant-scoped snapshot/query endpoints without reintroducing the legacy production bearer-key gate.
6. Verify focused tests, all persistence/API tests, and complete engine/ground-truth regression.

## Task 4 — Production Baseline Gates and Documentation

1. Add or restore CI gates for Python compile, full pytest, migration drift, frontend clean install/build/lint, and production configuration tests.
2. Remove false diagnostic success paths from tests; actual startup/configuration errors must fail safely.
3. Update README and implementation status docs to describe the consolidated baseline and record deferred Clerk/Blob/public-beta work.
4. Verify backend full suite, frontend build/lint, clean git diff, and branch-wide review.

## Acceptance Criteria

- Fresh and repeated test runs are independent of developer database history.
- No missing Alembic revision errors occur.
- All homepage-v3 accepted features remain present.
- Governed canonical ingestion contracts and deterministic ground-truth tests pass.
- Frontend production build and lint pass from a clean dependency install.
- No public-beta identity, billing, or deployment changes are introduced in PR 1.
