# ControlCheck AI — Implementation Update v0.6.22

## AI Insight v1 — Evidence-Grounded Public Beta

AI Insight v1 replaces the dashboard placeholder with a persisted, evidence-grounded summary generated after a deterministic analysis run succeeds. The legacy chat assistant remains hidden and is not part of this release.

### Delivered

- `ai_insights` stores one tenant-scoped insight per analysis run with pending, generating, ready, and failed states.
- Alembic migration `20260907_0002_ai_insights` creates the durable state and run uniqueness constraint.
- The insight input contains only bounded aggregates and deduplicated finding metadata from the selected run. Workbook raw content, sheets, cells, source rows, file paths, and telemetry data are not sent to OpenAI.
- OpenAI output is parsed as JSON, capped, and filtered so it can reference only finding IDs from the current run.
- Analysis completion remains authoritative: AI failure never changes a successful deterministic run into a failed run.
- The dashboard now shows generating, ready, unavailable, and retry states, with links to supporting findings.

### Operational contract

Vercel executes generation best-effort after a completed run. `OPENAI_API_KEY` and `CONTROLCHECK_OPENAI_MODEL` are server-side Vercel environment variables. A failed or pending insight can be retried through the authenticated API. Durable background generation for large asynchronous imports remains deferred with the VPS worker architecture.

### Verification

- Unit tests cover bounded/redacted input, allowed finding references, model JSON parsing, and one insight record per run.
- API tests cover run scope and tenant isolation when PostgreSQL integration tests are available.
- Frontend production build must pass before Vercel promotion.