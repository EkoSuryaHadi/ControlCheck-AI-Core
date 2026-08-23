# ControlCheck AI Implementation Update v0.6.12

**Version:** v0.6.12  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI

## Objective
Prevent stale or expired browser sessions from remaining visually authenticated after JWT expiry.

## Changes
- Added reusable JWT payload decoder and expiry checker.
- Authentication responses containing an already-expired token are rejected.
- Stored tokens are validated before restoring a browser session.
- Malformed stored user JSON now fails closed instead of crashing AuthContext.
- Authenticated state now requires token + user + organization context.
- Active JWT expiry is checked every 30 seconds.
- Expired sessions clear token, user, organization, and current-project state so ProtectedRoute can return the user to login.

## Session Rules
- Missing or invalid `exp` claim is treated as expired.
- Stored session restoration uses a small expiry skew to avoid reviving near-expired tokens.
- Login only accepts a currently valid access token.
- No silent demo authentication fallback is introduced.

## Acceptance Criteria
- Reloading the app with an expired token does not restore the workspace session.
- An active session automatically becomes unauthenticated after token expiry.
- Invalid stored user JSON does not crash the application.
- Protected workspace routes remain inaccessible after session expiry.

## Definition of Done
- JWT expiry helpers implemented.
- AuthContext session restoration and active expiry monitoring hardened.
- Change documented in the same change set.
- Frontend build must pass before Preview sign-off.
