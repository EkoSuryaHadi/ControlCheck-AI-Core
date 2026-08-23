# ControlCheck AI — Implementation Update v0.6.1

**Version:** v0.6.1  
**Theme:** Workspace Registration & Auth Session Hotfix  
**Branch:** `homepage-v3`

## 1. Problem

Preview testing identified that a newly registered user could not continue into a newly created workspace.

The backend registration endpoint created the user and organization correctly and embedded `org_id`, `sub`, `email`, and `role` claims inside the access JWT. However, the frontend expected `org_id` and `user_id` as top-level JSON fields in the authentication response.

Because the existing `TokenResponse` only returned token fields, the Register page interpreted the successful registration as an incomplete workspace response and redirected the user back to Login instead of continuing to Onboarding.

## 2. Root Cause

Backend behavior before the fix:

1. Create user.
2. Create organization when `organization_name` is provided.
3. Add user as `org_admin`.
4. Create access token containing `org_id` and user identity claims.
5. Return `access_token` and `refresh_token`.

Frontend behavior before the fix:

- required `res.org_id`;
- required/fell back from `res.user_id`;
- did not decode JWT claims;
- redirected back to login when `res.org_id` was absent.

This was a frontend/backend response-contract mismatch.

## 3. Fix

### 3.1 Auth identity normalization

Added:

`frontend/src/lib/authSession.ts`

The helper:

- validates `access_token` exists;
- decodes JWT payload safely in the browser;
- resolves `org_id` from response or JWT claim;
- resolves user ID from response or JWT `sub`;
- resolves email and role from response or token claims;
- rejects authentication if no workspace organization or user identity can be resolved.

### 3.2 Register flow

`RegisterPage.tsx` now:

1. calls `/v1/auth/register`;
2. normalizes identity from the returned access JWT;
3. persists the real access token, user identity, and organization ID through `AuthContext`;
4. redirects directly to `/onboarding`;
5. displays the backend error message when registration fails.

The obsolete redirect back to Login for successful token responses was removed.

### 3.3 Login flow

`LoginPage.tsx` now uses the same normalized JWT identity.

This removes the previous fallback to fake `org-01` when a valid backend token omitted top-level `org_id`.

### 3.4 Demo authentication separation

Previously, any real login API error could silently authenticate the user into a demo workspace.

That behavior has been removed.

Current behavior:

- failed real login displays an error;
- demo access is available only through the explicit **Enter Demo Workspace** button.

This prevents incorrect credentials from appearing to succeed.

## 4. Backend Contract Improvement

`TokenResponse` has also been extended with optional identity fields:

- `user_id`
- `email`
- `full_name`
- `org_id`
- `role`

The JWT remains the authoritative compatibility source for existing backend responses until all auth endpoints explicitly populate these response fields.

## 5. Acceptance Criteria

v0.6.1 is accepted when:

- [ ] New email + organization can register successfully.
- [ ] User remains authenticated immediately after registration.
- [ ] Correct organization ID is stored in `controlcheck_org_id`.
- [ ] User is routed to `/onboarding` without a second login.
- [ ] Onboarding can create the first project using the real organization ID.
- [ ] Existing account can log in using the real JWT organization claim.
- [ ] Incorrect password displays an authentication error.
- [ ] Incorrect password does not create a demo session.
- [ ] Explicit Enter Demo Workspace still works.
- [ ] Frontend build/typecheck passes.
- [ ] Backend test suite passes.

## 6. Test Script

Use a new email address for each registration attempt while testing the preview environment.

1. Open `/register`.
2. Enter Full Name.
3. Enter a unique Organization name.
4. Enter a new email address.
5. Enter a password with at least 8 characters.
6. Click **Create Workspace**.
7. Expected: redirect to `/onboarding`.
8. Create a project code/name.
9. Expected: project creation succeeds under the newly created organization.
10. Logout.
11. Login with the same email/password.
12. Expected: return to the real workspace.
13. Test an incorrect password.
14. Expected: error is shown and no demo login occurs.
15. Click **Enter Demo Workspace** separately.
16. Expected: demo workspace opens intentionally.

## 7. Files Changed

- `src/controlcheck/api_models.py`
- `frontend/src/lib/authSession.ts`
- `frontend/src/pages/auth/RegisterPage.tsx`
- `frontend/src/pages/auth/LoginPage.tsx`
- `docs/ControlCheck_AI_Implementation_Update_v0.6.1.md`

## 8. Release Note

This is a blocking preview hotfix. v0.7 feature development should continue only after the registration/onboarding flow is verified in Vercel Preview.
