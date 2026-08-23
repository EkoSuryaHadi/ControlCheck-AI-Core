# ControlCheck AI — Implementation Update v0.6

**Version:** v0.6  
**Theme:** Approval & Escalation Governance  
**Branch:** `homepage-v3`

## 1. Objective

v0.6 upgrades ControlCheck AI from evidence/action closure governance into a management-controlled assurance workflow. The release adds severity-based SLA policy, maker-checker closure approval, role-based closure authority, and escalation records for findings and corrective actions that exceed their required response time.

The core principle is:

> A finding is not closed simply because a user clicks a button. Closure must satisfy evidence, corrective action, approval, and authority rules.

## 2. Governance Flow

The governed closure sequence is:

1. ControlCheck creates a finding from deterministic rules.
2. Evidence is linked to the finding.
3. Corrective actions are created when remediation is required.
4. All corrective actions must be `completed` or `cancelled`.
5. If project policy requires approval for the finding severity, the closure requester submits a closure approval request.
6. A different authorized person reviews the request.
7. The approver must be an `org_admin` or `project_manager`.
8. Maker-checker policy prevents the requester from approving their own request.
9. Only an `org_admin` or `project_manager` can execute final governed closure.
10. The backend revalidates all closure gates before changing the finding to `resolved`.

## 3. Default SLA Policy

Each project has a governance policy. When no custom policy exists, ControlCheck uses:

| Severity | Default SLA | Closure Approval |
|---|---:|---|
| Critical | 3 days | Required |
| Warning | 7 days | Not required by default |
| Observation | 14 days | Not required |

Project managers or organization administrators may change the SLA values from 1 to 365 days and may optionally require approval for warning findings.

## 4. Database Changes

Alembic migration:

`alembic/versions/20260823_0007_approval_escalation_governance.py`

Revision chain:

- Revision: `20260823_0007`
- Down revision: `20260823_0006`

### 4.1 `project_governance_policies`

Stores project-level governance configuration:

- organization_id
- project_id
- critical_sla_days
- warning_sla_days
- observation_sla_days
- require_critical_closure_approval
- require_warning_closure_approval
- updated_at

### 4.2 `finding_closure_approvals`

Stores closure approval requests and decisions:

- organization_id
- project_id
- finding_id
- requested_by
- decision: `pending`, `approved`, `rejected`, `withdrawn`
- decided_by
- decision_note
- requested_at
- decided_at

### 4.3 `governance_escalations`

Stores management escalations:

- finding_id
- optional action_id
- escalation_type: `finding_sla`, `action_overdue`
- severity
- status: `open`, `acknowledged`, `resolved`
- reason
- metadata
- triggered_at
- acknowledged_by / acknowledged_at
- resolved_at

Active duplicate escalations are suppressed by repository logic.

## 5. Maker-Checker Rules

Closure approval is intentionally separated from closure request ownership.

An approval decision is allowed only when:

- the approver is authenticated;
- the approver is not the same user as the requester;
- the approver has `org_admin` or `project_manager` authority.

The backend returns a governance error if maker-checker separation is violated.

## 6. Closure Authority Matrix

| Role | Create Action | Request Approval | Approve / Reject | Final Close | Change Governance Policy | Scan/Acknowledge Escalation |
|---|---|---|---|---|---|---|
| org_admin | Yes | Yes | Yes, except own request | Yes | Yes | Yes |
| project_manager | Yes | Yes | Yes, except own request | Yes | Yes | Yes |
| project_member | Yes / project workflow | Yes | No | No | No | No |
| project_viewer | No management authority | No | No | No | No | No |

Final API enforcement takes precedence over UI visibility.

## 7. Closure Readiness Contract

`GET /v1/findings/{finding_id}/closure-readiness`

The response now includes:

- `evidence_ready`
- `actions_ready`
- `approval_required`
- `approval_ready`
- `approval_decision`
- `approval_id`
- action counters
- `blockers`
- final `can_close`

Final close condition:

```text
can_close = evidence_ready
            AND actions_ready
            AND approval_ready
```

For a Critical finding under the default policy, `approval_ready` is false until an independent authorized approver records `approved`.

## 8. Approval Request Guard

A closure approval cannot be requested prematurely.

Before ControlCheck accepts a request:

- at least one persisted evidence record must exist;
- every corrective action must be `completed` or `cancelled`;
- approval must be required by policy.

Otherwise the API returns `409 approval_request_not_ready` or `409 approval_not_required`.

## 9. API Additions

### Policy

- `GET /v1/projects/{project_id}/governance-policy`
- `PATCH /v1/projects/{project_id}/governance-policy`

### Closure Approval

- `GET /v1/projects/{project_id}/closure-approvals`
- `GET /v1/findings/{finding_id}/closure-approval`
- `POST /v1/findings/{finding_id}/closure-approval`
- `POST /v1/closure-approvals/{approval_id}/decision`

### Escalation

- `POST /v1/projects/{project_id}/governance-escalations/scan`
- `GET /v1/projects/{project_id}/governance-escalations`
- `POST /v1/governance-escalations/{escalation_id}/acknowledge`

### Existing closure endpoint upgraded

- `POST /v1/findings/{finding_id}/close`

Final closure now requires authenticated manager/admin authority and all closure gates.

## 10. Escalation Logic

### Finding SLA breach

A finding escalation is created when an open/acknowledged finding remains unresolved after:

`detected_at + severity SLA`

### Corrective action overdue

An action escalation is created when:

- action status is `open` or `in_review`; and
- action `due_date` is earlier than the current date.

Escalations remain visible until acknowledged/resolved and are designed as management attention records, not transient UI notifications.

## 11. Frontend — Governance Workspace

New route:

`/governance`

The workspace contains:

### Governance scorecards

- Pending Closure Approvals
- Open Escalations
- Critical Escalations
- Critical SLA

### Project Governance Policy

Managers can configure:

- Critical SLA
- Warning SLA
- Observation SLA
- Critical closure approval requirement
- Warning closure approval requirement

### Pending Closure Approval Queue

Managers can:

- open the finding;
- approve closure;
- reject closure.

The backend maker-checker policy still applies if a user attempts to approve their own request.

### Escalation Inbox

Displays:

- severity;
- escalation type;
- reason;
- finding reference;
- triggered date;
- status;
- acknowledge action.

## 12. Finding Detail v2 Changes

Finding Detail now shows five closure readiness dimensions:

1. Evidence
2. Actions
3. Approval
4. Completed Actions
5. Total Actions

When approval is required:

- `Request Closure Approval` is disabled until evidence/action prerequisites are ready;
- a pending request displays `Approval Pending`;
- users can open the Governance queue;
- a rejected request may be submitted again after remediation/review;
- final `Close Finding` remains disabled until approval is ready.

## 13. Serverless Registration

`api/index.py` now registers:

- existing Core API;
- Action Governance routes;
- Approval & Escalation Governance routes.

Diagnostics also verify availability of the auth runtime dependencies `bcrypt` and `jwt`.

## 14. Dependency Alignment

CI identified missing Python dependencies in the backend test environment.

`pyproject.toml` now includes:

- `bcrypt>=4.1`
- `PyJWT>=2.8`
- `python-docx>=1.1` in dev extras

`requirements.txt` now includes:

- `bcrypt>=4.1`
- `PyJWT>=2.8`

This aligns authentication runtime requirements and document-based tests with CI installation behavior.

## 15. Tests

New unit test:

`tests/test_governance_v06.py`

Coverage includes:

- default Critical SLA = 3 days;
- overdue SLA calculation;
- Critical closure approval requirement;
- Warning approval default behavior;
- maker-checker self-approval rejection;
- project member approval rejection;
- project manager approval permission.

Existing v0.5 tests continue to cover evidence/action closure readiness.

## 16. Acceptance Criteria

v0.6 is functionally accepted when all of the following pass:

1. Project governance policy can be read.
2. Authorized manager/admin can update SLA policy.
3. Unauthorized role cannot change governance policy.
4. Critical finding cannot close without evidence.
5. Critical finding cannot close with an open corrective action.
6. Critical finding cannot request approval before evidence/actions are ready.
7. Critical finding with ready evidence/actions can request approval.
8. Requester cannot approve their own closure request.
9. Project member cannot approve a closure request.
10. Project manager/admin can approve another user's request.
11. Approved Critical finding can only be finally closed by manager/admin.
12. Overdue finding creates a finding SLA escalation.
13. Overdue corrective action creates an action escalation.
14. Duplicate active escalation is not recreated.
15. Manager/admin can acknowledge an escalation.
16. Frontend build/typecheck passes.
17. Python test suite passes.
18. Alembic migration upgrades a non-production PostgreSQL database successfully.

## 17. Deployment Checklist

Before merging/deploying v0.6:

1. Confirm GitHub CI is green.
2. Run `alembic upgrade head` against non-production PostgreSQL.
3. Verify tables `project_governance_policies`, `finding_closure_approvals`, and `governance_escalations` exist.
4. Log in as Project Member and Project Manager using separate accounts.
5. Create/identify a Critical finding with persisted evidence.
6. Create and complete/cancel its corrective actions.
7. Request closure approval as User A.
8. Verify User A cannot self-approve.
9. Approve as manager/admin User B.
10. Verify non-manager cannot execute final closure.
11. Close as manager/admin.
12. Create an overdue finding/action test case and run SLA scan.
13. Confirm escalation appears and can be acknowledged.
14. Regression test Dashboard, Findings, Actions, Governance, Cost, Schedule, Progress, AI Assistant, Reports, onboarding, and upload flows.

## 18. v0.7 Direction

Recommended next increment after v0.6 validation:

**Notification & Management Attention Layer**

Potential scope:

- in-app notification center;
- pending approval notification;
- escalation notification;
- approaching-SLA warning before breach;
- daily management digest;
- assignment notifications;
- approval/closure audit timeline;
- optional email/Slack integration when a delivery connector is configured.

v0.7 should consume the governance records created in v0.6 rather than introducing a parallel alert data model.
