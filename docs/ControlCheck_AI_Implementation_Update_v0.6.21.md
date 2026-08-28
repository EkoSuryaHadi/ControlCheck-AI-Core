# ControlCheck AI — Implementation Update v0.6.21

## Fase Beta: Usage Analytics & User Feedback

Public-beta scope now includes first-party, privacy-safe telemetry and lightweight feedback. Product events are stored in Supabase and scoped by organization. Workbook values, cells, vendor names, raw content, and file paths are rejected from event metadata and are never copied into telemetry.

### Delivered

- `product_events` and `finding_feedback` tables with tenant-aware indexes and constraints.
- Alembic migration `20260906_0001_beta_telemetry_feedback`.
- Server-authoritative events for registration, project creation, upload, analysis, finding/evidence usage, and feedback.
- Allowlisted event names and bounded metadata sanitizer.
- Feedback endpoints for runs and findings, with retry-safe frontend controls.
- Owner-only metrics endpoint and frontend dashboard at `/owner/metrics`.

### Metrics

Registrations, active users, projects, accepted uploads, completed analyses, result-use rate, feedback count, useful-feedback rate, and error rate are calculated from persisted events. Telemetry failures are best-effort and do not fail upload or analysis requests.

### PRD alignment

This update formalizes analytics and feedback as part of the public-beta scope. Authentication/RBAC remains intentionally limited to the owner gate required for metrics; full subscription and billing workflows remain deferred.

### Verification

- Event policy tests cover unknown events, sensitive metadata, size limits, and safe scalar metadata.
- Frontend unit tests and production build must pass before promotion.
- Apply the migration in Supabase before enabling the owner dashboard in production.
