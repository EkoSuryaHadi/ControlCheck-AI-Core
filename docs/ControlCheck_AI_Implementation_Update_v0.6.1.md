# ControlCheck AI — Implementation Update v0.6.1

**Version:** v0.6.1  
**Theme:** Workspace Registration & Auth Session Hotfix  
**Branch:** `homepage-v3`

## 1. Problem

Preview testing identified that a newly registered user could not continue into a newly created workspace.

The first observed UI symptom was a red **Not Found** message after clicking **Create Workspace** in Vercel Preview.

Two separate compatibility issues were identified:

1. the frontend/backend auth response contract did not expose workspace identity consistently;
2. the hosted runtime could enter offline mode when Vercel/Postgres exposed the standard `DATABASE_URL` variable instead of the ControlCheck-specific `CONTROLCHECK_DATABASE_URL` variable.

When the runtime entered offline mode, durable/auth routes such as `/v1/auth/register` were not installed, producing HTTP 404 even though the frontend registration page was available.

## 2. Root Causes

### 2.1 Auth response-contract mismatch

Backend registration behavior:

1. Create user.
2. Create organization when `organization_name` is provided.
3. Add user as `org_admin`.
4. Create access token containing `org_id`, `sub`, `email`, and `role` claims.
5. Return the access/refresh tokens.

Earlier frontend behavior expected `res.org_id` and `res.user_id` as top-level fields and did not decode the JWT claims. This could redirect a successful registration back to login instead of continuing to onboarding.

### 2.2 Hosted database environment mismatch

`ProductionSettings` previously read only:

`CONTROLCHECK_DATABASE_URL`

The Vercel/Postgres/Supabase ecosystem commonly provides:

`DATABASE_URL`

When only `DATABASE_URL` existed, `ProductionSettings.database_url` became empty. `create_configured_app()` then intentionally created an offline application without the persistent registration/login/project routes.

Result:

`POST /api/v1/auth/register` → `404 Not Found`

## 3. Fixes

### 3.1 Database URL resolution

`src/controlcheck/settings.py` now resolves database configuration using:

1. `CONTROLCHECK_DATABASE_URL` — explicit ControlCheck override;
2. `DATABASE_URL` — standard hosted Postgres fallback.

The same resolver is used by both `ProductionSettings` and `PersistenceSettings` so deployment/runtime behavior is consistent.

### 3.2 Auth identity normalization

Added:

`frontend/src/lib/authSession.ts`

The helper:

- validates `access_token` exists;
- decodes JWT payload safely in the browser;
- resolves `org_id` from response or JWT claim;
- resolves user ID from response or JWT `sub`;
- resolves email and role from response or token claims;
- rejects authentication if no workspace organization or user identity can be resolved.

### 3.3 Register flow

`RegisterPage.tsx` now:

1. calls `/v1/auth/register`;
2. normalizes identity from the returned access JWT;
3. persists the real access token, user identity, and organization ID through `AuthContext`;
4. redirects directly to `/onboarding`;
5. displays the backend error message when registration fails.

### 3.4 Login flow

`LoginPage.tsx` now uses the same normalized JWT identity.

The previous fake `org-01` fallback has been removed.

### 3.5 Demo authentication separation

A failed real login no longer silently creates a demo session.

Current behavior:

- failed real login displays an error;
- demo access is available only through the explicit **Enter Demo Workspace** action.

### 3.6 Backend token response compatibility

`TokenResponse` includes optional identity fields:

- `user_id`
- `email`
- `full_name`
- `org_id`
- `role`

JWT claims remain a compatibility source until every auth endpoint explicitly returns all identity fields.

## 4. Automated Tests

Added:

`tests/test_settings_database_url.py`

Coverage:

- `ProductionSettings` accepts a standard `DATABASE_URL` when the ControlCheck-specific variable is absent;
- `CONTROLCHECK_DATABASE_URL` takes precedence when both variables exist;
- `PersistenceSettings` uses the same resolution behavior.

## 5. Acceptance Criteria

v0.6.1 is accepted when:

- [ ] Vercel Preview installs durable auth routes when `DATABASE_URL` is present.
- [ ] `POST /api/v1/auth/register` no longer returns HTTP 404 because of database env-name mismatch.
- [ ] New email + organization can register successfully.
- [ ] User remains authenticated immediately after registration.
- [ ] Correct organization ID is stored in `controlcheck_org_id`.
- [ ] User is routed to `/onboarding` without a second login.
- [ ] Onboarding can create the first project using the real organization ID.
- [ ] Existing account can log in using the real JWT organization claim.
- [ ] Incorrect password displays an authentication error.
- [ ] Incorrect password does not create a demo session.
- [ ] Explicit Demo Workspace access remains intentional/separate.
- [ ] Frontend build/typecheck passes.
- [ ] Backend test suite passes.

## 6. Preview Test Script

Use a new email address for each registration attempt if the previous request may have persisted data.

1. Open `/register` in the Vercel Preview.
2. Enter Full Name.
3. Enter a unique Organization name.
4. Enter a new email address.
5. Enter a password with at least 8 characters.
6. Click **Create Workspace**.
7. Expected: no `Not Found` error.
8. Expected: redirect to `/onboarding`.
9. Create a project code/name.
10. Expected: project creation succeeds under the newly created organization.
11. Logout.
12. Login with the same email/password.
13. Expected: return to the real workspace.
14. Test an incorrect password.
15. Expected: error is shown and no demo login occurs.

## 7. Files Changed

- `src/controlcheck/api_models.py`
- `src/controlcheck/settings.py`
- `tests/test_settings_database_url.py`
- `frontend/src/lib/authSession.ts`
- `frontend/src/pages/auth/RegisterPage.tsx`
- `frontend/src/pages/auth/LoginPage.tsx`
- `docs/ControlCheck_AI_Implementation_Update_v0.6.1.md`

## 8. Deployment Note

This hotfix assumes the Vercel project has either `CONTROLCHECK_DATABASE_URL` or `DATABASE_URL` configured with a reachable PostgreSQL database.

If neither variable exists in the Vercel Preview environment, the application will still operate without durable workspace registration because there is no database to persist users/organizations. In that case the deployment environment must be configured before end-to-end registration testing can pass.

## 9. Release Gate

This is a blocking preview hotfix. v0.7 feature development should continue only after the registration → onboarding → first-project flow is verified successfully in Vercel Preview.
