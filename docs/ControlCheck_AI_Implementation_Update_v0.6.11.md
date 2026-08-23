# ControlCheck AI Implementation Update v0.6.11

**Version:** v0.6.11  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI

## Objective
Make corrective-action audit identity server authoritative and prevent clients from spoofing tenant or actor information.

## Changes
- Removed client-supplied `actor` from Action create/update request models.
- Action create/update actor is now derived from JWT `sub`.
- Action organization scope is now derived from JWT `org_id`.
- Project action list, finding action list, closure readiness, action create/update, and finding close now require authenticated JWT identity.
- `X-Organization-ID` is no longer authoritative for the corrective-action API surface.
- Action history continues to store the actor, but now records authenticated user identity.

## Security Rules
- `organization_id = JWT.org_id`
- `actor = JWT.sub`
- Client request body cannot override either value.
- Invalid/expired/missing JWT returns authentication failure before action mutation.

## Acceptance Criteria
- A client cannot create an action attributed to another user by sending an `actor` field.
- A client cannot switch action tenant scope by sending a different organization header.
- Action create/update history uses the authenticated user ID.
- Existing authenticated frontend action flows continue to work.

## Definition of Done
- Action API identity model is JWT-authoritative.
- Tenant and actor spoofing paths are removed from action mutation endpoints.
- Change documented in the same change set.
- Backend/frontend deployment validation required before Preview sign-off.
