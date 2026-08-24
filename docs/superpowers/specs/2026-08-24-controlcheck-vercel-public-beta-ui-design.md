# ControlCheck AI Free Public Beta and Product Validation Design

**Date:** 2026-08-24

**Status:** Approved product direction; implementation pending

**Next governed PRD:** v1.1

**Next governed UI/UX spec:** v0.2

## 1. Decision

ControlCheck AI will launch first as a free public beta that can support real project-control work. The purpose is to measure whether users consume and act on deterministic analysis results before pricing or payment functionality is designed.

The public beta is not measured by registrations alone. Its primary value event is **analysis result used**, defined as at least one of:

- opening finding evidence;
- changing a finding status;
- submitting finding-level or run-level feedback; or
- exporting findings.

The beta keeps the foundational contract: **the deterministic engine calculates; AI may explain only grounded persisted results.** LLMs do not detect findings, calculate metrics, construct evidence, or assign severity.

## 2. Current Baseline

`origin/master` at design time already contains:

- the deterministic 20-rule Python engine;
- PostgreSQL persistence and canonical project-control data;
- health scoring;
- custom JWT authentication and organization/project RBAC;
- an AI assistant layer;
- a React 19 + Vite + TypeScript interface in `frontend/`;
- Vercel hybrid SPA/Python routing through `vercel.json` and `api/index.py`;
- governed PRD versions through v1.0 and UI/UX Design Spec v0.1.

This design evolves that baseline. It does not create a second frontend or regress document numbering to PRD v0.6.

### 2.1 Public-launch blockers found in the current baseline

The current implementation must not be opened to arbitrary public users until these are corrected:

- the login screen contains prefilled demonstration credentials;
- failed backend login falls back to a synthetic authenticated session;
- access token and organization ID are stored in browser `localStorage`;
- browser-supplied organization context is attached to requests;
- the serverless entrypoint forces workbook storage into ephemeral `/tmp/uploads`;
- diagnostic endpoints expose import details and environment-variable names;
- current production settings default CORS to wildcard behavior when unset;
- private durable object storage and retention cleanup are not wired into the Vercel path;
- product-value telemetry, feedback, fair-use limits, and self-service deletion are absent;
- deployment work changed governed backend behavior and tests substantially, so the deterministic and tenant-isolation gates must be freshly re-established.

These are design blockers, not statements that the public beta is already production ready.

## 3. Product Goals

The beta must answer:

1. Can a Project Controls Engineer complete a first useful analysis without assistance?
2. Do users inspect, classify, comment on, or export findings?
3. Do users return with another reporting-period workbook?
4. What is the duration, failure rate, storage footprint, and approximate infrastructure cost per completed analysis?

## 4. Users and Access Modes

### 4.1 Anonymous visitor

An anonymous visitor can view the landing page and open a zero-login interactive demo backed by frozen, sanitized synthetic results. The demo creates no tenant, accepts no upload, and starts no engine run.

### 4.2 Verified beta user

A verified user signs in with an email one-time code and receives one isolated personal workspace. The user can:

- create projects;
- upload governed `.xlsx` workbooks;
- run deterministic analyses;
- review domain readiness, findings, calculations, and evidence;
- update finding status;
- submit feedback;
- export findings to CSV;
- view recent run history and retention dates; and
- delete a workbook or the entire beta workspace.

### 4.3 Product owner

The owner can view a small allowlisted usage and feedback inbox. This narrow operational role does not replace the existing RBAC model and must not expose workbook cells through analytics.

## 5. Scope

### 5.1 In scope

- Existing React/Vite UI evolved into a public landing, demo, and authenticated workspace.
- Existing FastAPI served through the same Vercel project under `/api`.
- Clerk email OTP for public identity.
- Mapping Clerk subjects to isolated existing organizations.
- Neon PostgreSQL for durable application data.
- Private Vercel Blob for original workbook objects.
- Fair-use enforcement, retention, deletion, first-party telemetry, and feedback.
- Findings CSV export.
- Industrial Intelligence visual direction and WCAG 2.2 AA.
- Public-beta security, reliability, migration, smoke, and rollback gates.
- PRD v1.1, UI/UX Design Spec v0.2, README, and public-beta runbook.

### 5.2 Deferred

- Billing, pricing, subscriptions, and payment collection.
- Team invitations and public self-service organization administration.
- Enterprise SSO/SAML.
- Generic column-mapping UI.
- PDF reports.
- Public third-party API keys.
- Unbounded AI usage.
- Customer-accuracy claims based on synthetic fixtures.

## 6. Deployment Architecture

### 6.1 Adopt the existing hybrid Vercel project

The beta uses the current single-project shape:

```text
Browser
  -> Vercel static React/Vite application
  -> same-origin /api/*
  -> api/index.py
  -> FastAPI
       -> Clerk token validation and tenant resolution
       -> Neon PostgreSQL
       -> private Vercel Blob
       -> deterministic ControlCheck engine
```

Keeping one project is the shortest safe path from the actual current code. It avoids a Next.js rewrite and removes cross-project preview coordination. The internal API key is not placed in the browser; public requests use short-lived Clerk session tokens.

### 6.2 Vercel runtime contract

- `api/index.py` is a thin entrypoint only. It must not publish diagnostics, list environment keys, silently replace the configured storage backend, or duplicate application endpoints.
- `/api/*` is stripped exactly once before FastAPI routing.
- SPA filesystem routes fall back to `index.html`; API paths never fall through to the SPA.
- Production settings fail fast at import for missing database, identity, trusted-host, catalogue, storage, and secret configuration.
- The exact platform-provided deployment host may be added to trusted hosts. Wildcard Vercel hosts are forbidden.
- The upload remains limited to 25 MiB.
- Synchronous analysis targets at most 240 seconds, leaving margin beneath the Vercel Hobby function maximum of 300 seconds.

Vercel documents direct FastAPI/Python support and function limits at <https://vercel.com/docs/frameworks/backend/fastapi> and <https://vercel.com/docs/functions/limitations>.

If controlled p95 execution exceeds 180 seconds or observed timeout rate exceeds 1%, queued/background execution becomes mandatory before expanding traffic.

## 7. Authentication and Tenant Isolation

### 7.1 Public identity

Clerk email OTP is the selected public identity path. The existing React Router/Vite application can integrate Clerk without changing frontend frameworks. Clerk session tokens are short lived and sent as bearer tokens to same-origin FastAPI requests.

Relevant official guidance:

- React integration: <https://clerk.com/docs/react/getting-started/quickstart>
- Email verification options: <https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options>
- Manual backend JWT verification: <https://clerk.com/docs/guides/sessions/manual-jwt-verification>
- Current pricing, to be rechecked before launch: <https://clerk.com/pricing>

### 7.2 Backend verification

FastAPI validates:

- permitted algorithm;
- signature against a configured Clerk public key/JWKS;
- issuer;
- authorized party/front-end origin;
- `exp`, `nbf`, and clock skew;
- subject presence.

Validation should be networkless with the configured public key where practical. Invalid or ambiguous credentials fail closed.

### 7.3 Identity mapping

Add a minimal `beta_identities` mapping:

- internal UUID;
- unique Clerk subject;
- unique personal organization ID;
- status;
- terms/privacy version accepted;
- created, last-seen, and deletion timestamps.

On the first verified request, the backend atomically creates one personal organization and the identity mapping. Concurrent first requests converge on the same unique row.

The user's organization is always derived from the verified subject. A browser-provided `X-Organization-ID`, stored organization ID, query parameter, or path alone never authorizes access.

### 7.4 Existing custom auth/RBAC

The existing password/JWT/RBAC code remains available only for migration and controlled internal operation until intentionally retired. Public UI routes do not use prefilled credentials, demo fallback tokens, or browser-persisted long-lived custom JWTs.

The public beta uses personal workspaces. Team invitations and organization role management remain disabled even though related tables/code exist.

### 7.5 Owner access

Owner metrics require a valid Clerk session plus a server-side allowlist of Clerk subjects. This is intentionally narrow and must not evolve into duplicated ad-hoc RBAC.

## 8. Storage, Retention, and Deletion

### 8.1 Storage adapters

- Preserve local storage for development/tests.
- Preserve S3-compatible storage for container deployments where supported.
- Add a private Vercel Blob adapter for the Vercel beta.
- Select storage only through validated configuration; never force `/tmp` as durable storage.
- All production storage adapters must implement the complete protocol: put, delete, exists/readiness, and metadata integrity required by the application.

Vercel private Blob is designed for authenticated user documents: <https://vercel.com/docs/vercel-blob/private-storage>.

### 8.2 Retention

- Original workbook object: seven days after upload.
- Structured project data, findings, evidence, and history: 90 days after last workspace activity.
- User-triggered delete: immediate logical removal, queued physical cleanup, and visible completion state.
- Provider backups may retain data for their documented backup window; the UI and privacy policy must not promise impossible instant backup erasure.

### 8.3 Cleanup

A daily authenticated Vercel Cron runs idempotent bounded cleanup. It:

1. claims eligible records;
2. deletes Blob objects best-effort;
3. records success or retryable failure;
4. removes or anonymizes eligible structured records according to the retention contract; and
5. never resurrects logically deleted data.

## 9. Fair Use and Abuse Controls

Initial configurable beta limits:

- 3 analysis starts per rolling day;
- 10 starts per rolling month;
- one active upload/analysis per user;
- 25 MiB per workbook;
- `.xlsx` extension plus actual workbook/schema validation.

Quota admission is enforced transactionally in PostgreSQL before expensive processing. Infrastructure failures do not consume the successful-run allowance. Repeated invalid uploads use a separate bounded counter. Limit responses use stable `429` errors and a retry timestamp.

## 10. Product Telemetry

### 10.1 Principles

Telemetry is first party and stored in Neon. It measures behavior without copying business data.

Never include:

- filename;
- workbook cells;
- vendor or WBS names;
- evidence field values;
- calculation payloads;
- free-text feedback; or
- secrets/tokens.

### 10.2 Safe event schema

- event UUID and schema version;
- internal identity UUID when authenticated;
- consented anonymous session ID for landing/demo only;
- allowlisted event name;
- optional project/run/finding UUID;
- bounded numeric/categorical properties;
- request ID and server timestamp.

Server-authoritative events are written by the transaction that performs the action. Browser-only events pass a strict allowlist and rate limit.

### 10.3 Events

- `landing_viewed`
- `demo_started`
- `demo_finding_opened`
- `signup_started`
- `signup_completed`
- `project_created`
- `upload_started`
- `upload_validated`
- `analysis_completed`
- `analysis_failed`
- `finding_opened`
- `evidence_opened`
- `finding_status_changed`
- `findings_exported`
- `run_feedback_submitted`
- `finding_feedback_submitted`
- `workspace_returned`
- `data_deletion_requested`

### 10.4 Beta metrics

- unique visitors and demo starts;
- verified users;
- activated users completing a first analysis;
- analysis completion/failure rates;
- p50/p95 duration and storage bytes per run;
- seven-day and 30-day return usage;
- users with at least one `analysis result used` event;
- evidence-open, status-change, feedback, and export rates;
- usefulness, accuracy, and evidence-clarity distributions;
- approximate infrastructure cost per completed run.

No paid-plan decision relies on signups alone.

## 11. Feedback

Feedback is stored separately from telemetry because comments are user content.

- Run usefulness: useful, partly useful, not useful.
- Finding accuracy: accurate, unsure, inaccurate.
- Evidence clarity: clear, partly clear, unclear.
- Optional reason: false positive, missing context, incorrect threshold, unclear source, or recommendation not actionable.
- Optional bounded comment.

The interface explains that feedback does not mutate deterministic results for the current run.

## 12. UI/UX Information Architecture

### 12.1 Public landing

Primary actions are `Try the sample audit` and `Check my workbook`. The landing page explains supported EPC domains, deterministic checks, evidence traceability, data retention, and professional-judgment limitations. Avoid fake chat, decorative KPI tiles, and unsupported accuracy claims.

### 12.2 Anonymous demo

Use frozen, sanitized Golden Positive results and guide the visitor through:

1. project/run summary;
2. one high-severity finding;
3. metrics and deterministic calculation;
4. source evidence; and
5. recommendation/status workflow.

The demo is explicitly synthetic and creates no writable backend state.

### 12.3 Verified workspace

The authenticated shell reuses the current UI foundation but prioritizes the operator workflow:

- projects and latest reporting-period status;
- next action;
- guided workbook upload;
- run summary and domain readiness;
- findings workbench;
- evidence inspector;
- status and feedback actions;
- history, export, retention, and deletion.

AI Assistant and executive presentation features are secondary. They are hidden behind feature flags until groundedness, provider configuration, per-user cost, and failure behavior are verified for public traffic.

### 12.4 Guided upload

Use a full page, not a modal:

1. create/select project;
2. choose workbook and acknowledge retention/privacy;
3. validate type, size, artifact version, and domains;
4. show deterministic progress with safe retry states;
5. open the completed run summary.

### 12.5 Run summary

Prioritize:

- reporting period and run state;
- domain readiness and skipped rules;
- severity distribution;
- critical/high attention list;
- entry to the findings workbench;
- export and feedback.

Health scores must show their formula/inputs and never imply certainty beyond available domain data.

### 12.6 Findings workbench

Desktop uses a master-detail layout:

- filters for severity, domain, status, rule, WBS, vendor, and activity;
- dense list/table with entity, title, severity, domain, and status;
- persistent evidence inspector with metrics, calculation trace, source sheet/rows, business impact, recommendation, feedback, and status controls.

Tablet collapses filters. Mobile uses list-to-detail navigation rather than compressing the desktop table.

### 12.7 History and CSV export

History shows period, run status, finding counts by severity, and result-use actions. CSV export contains stable finding ID, rule, entity, category, severity, status, title, key metrics, impact, and recommendation. Raw workbook rows are excluded by default.

### 12.8 Owner view

The allowlisted owner sees usage funnels, result-use rate, return usage, failures, runtime/storage indicators, and aggregated feedback. The owner view does not expose workbook content as analytics.

## 13. Visual Direction

The approved direction is **Industrial Intelligence**:

- refined light-mode operational surfaces;
- deep navy, cobalt, and cyan from the approved ControlCheck AI logo;
- amber/red reserved for risk and green/teal for healthy states;
- gradients limited to the logo and rare high-value moments;
- engineering-grid alignment, crisp separators, and calm data density;
- full logo on access/onboarding and compact C/check mark in navigation;
- no neon sci-fi dashboard, decorative glow, glassmorphism, generic robot/chip imagery, or repetitive card grids.

The persistent design context is governed in `.impeccable.md` and mirrored in `.github/copilot-instructions.md`.

## 14. Accessibility and Content

- Meet WCAG 2.2 AA.
- Provide keyboard navigation and visible focus.
- Never use color as the only severity/status signal.
- Honor `prefers-reduced-motion`.
- Preserve upload, review, feedback, export, and deletion across responsive layouts.
- Use plain project-control language and actionable errors.
- Show timezone, currency, and unit context.
- State that ControlCheck supports—not replaces—professional judgment.

## 15. Failure Handling

- Blob upload succeeds and database ingestion fails: delete the Blob best-effort and record a safe failure.
- Function terminates during analysis: retain/reconcile a stale run state through an authenticated maintenance job.
- Blob cleanup fails: mark deletion pending and retry without restoring user-visible data.
- Telemetry failure never fails analysis unless required for quota correctness.
- Feedback failure preserves the draft for retry.
- Every API response carries a safe request ID.
- Production exceptions never reveal paths, SQL, tokens, import traces, or environment details.

## 16. Security and Privacy

- Remove login fallback, prefilled production credentials, demo JWT, and browser-authoritative organization state.
- Do not store long-lived tokens in `localStorage`.
- Validate Clerk session tokens and derive tenant context server-side.
- Keep private database, Blob, and identity secrets out of Vite's public environment namespace.
- Disable diagnostic endpoints in production; health responses are minimal.
- Fail closed for missing database, catalogue, storage, auth, trusted host, and secret configuration.
- Use exact origins/hosts; no wildcard production CORS.
- Do not log workbook content or raw tokens.
- Show privacy, retention, and deletion terms before the first real upload.
- Public launch requires an acceptable-use notice and privacy policy reviewed for intended jurisdictions.

## 17. Verification

Before public release:

- audit current `origin/master` changes and establish a trustworthy baseline test count;
- restore/retain exact Golden Positive acceptance: 59 TP, 0 FP, 0 FN, 100% severity and metric agreement;
- restore/retain Boundary/Negative acceptance: zero findings;
- verify deterministic Excel/database parity where canonical persistence is supported;
- test Clerk token validation and concurrent identity provisioning;
- test cross-tenant denial for every project/run/finding/evidence/export/delete path;
- test Blob adapter, quota, retention, deletion, telemetry schema, feedback, and stale-run reconciliation;
- test that no secret or long-lived token appears in the browser bundle/storage;
- run React unit/component tests and Playwright critical journeys;
- run automated accessibility plus keyboard/manual checks;
- build the full hybrid Vercel output and assert API/static routing;
- run preview smoke tests against Neon and private Blob;
- perform application and schema rollback drills.

Critical Playwright journeys:

1. anonymous landing to demo finding/evidence;
2. email OTP to personal workspace;
3. project creation to upload and completed analysis;
4. findings filter, evidence, status, feedback, and CSV export;
5. retention visibility and data deletion;
6. owner feedback/usage view access denial and allowlisted success.

## 18. Deployment and Rollback

1. Provision Clerk, Neon, and private Vercel Blob for preview.
2. Apply reviewed additive Alembic migrations through a direct database URL.
3. Deploy a Vercel Preview of the hybrid application.
4. Run API, UI, security, Golden/Boundary, and end-to-end smoke gates.
5. Seed/bundle frozen anonymous demo artifacts.
6. Verify retention cleanup in dry-run mode.
7. Promote only reviewed deployments.

Rollback promotes the previous Vercel deployment. Public-beta schema changes remain backward compatible with the previous application. Blob and Neon data are not rolled back with application code. Destructive migrations require a separately approved release.

## 19. Documentation Governance

The current repository already contains PRD v1.0. Create new immutable versions:

- `docs/ControlCheck_AI_PRD_v1.1.docx`
- `docs/ControlCheck_AI_UI_UX_Design_Spec_v0.2.docx`

PRD v1.1 must record:

- free public beta and product-usage-validation objective;
- anonymous synthetic demo and verified real-work workspace;
- Vite/React + FastAPI hybrid Vercel deployment;
- Clerk public identity and server-derived personal tenant;
- Neon PostgreSQL and private Vercel Blob;
- fair-use, retention, deletion, telemetry, feedback, and CSV export;
- success metrics based on analysis-result use and return usage;
- public launch blockers and release gates;
- deferral of billing, team self-service, PDF reports, and unbounded AI usage;
- unchanged deterministic-engine quality gates.

UI/UX Spec v0.2 must govern the public landing, synthetic demo, verified workspace, findings/evidence workflow, feedback, retention/deletion, owner metrics, Industrial Intelligence visual system, responsive behavior, and WCAG 2.2 AA.

Historical PRDs and UI specs remain immutable. README and the deployment/public-beta runbook are updated to point to the new governed versions.

## 20. Monetization Decision Gate

Paid-plan design begins only after observed data demonstrates:

- repeated analysis usage;
- meaningful analysis-result use;
- acceptable completion and failure rates;
- strong usefulness/accuracy/evidence feedback;
- known storage and compute cost per completed analysis; and
- clear demand for collaboration, longer retention, higher limits, or reporting features.

Signup count alone is not a monetization signal.
