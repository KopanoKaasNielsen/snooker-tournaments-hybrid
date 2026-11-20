# Authenticated frontend/API contract

Task 03 supersedes the public API access rules in Task 01. Exact OpenAPI models, validation,
request bodies and documented success codes are in [authentication-openapi.json](authentication-openapi.json).
The original [backend-openapi.json](backend-openapi.json) remains unchanged as historical evidence.
`python -W error -m scripts.verify_dependency_environment` compares the new snapshot exactly
and checks migrated startup, health and unauthenticated denials in a disposable database.

## Session contract

All browser calls use central Axios, default same-origin `/api` (Vite strips that prefix),
`withCredentials: true`, and `X-Snooker-Client: web`. Explicit trusted Origin checking protects
cookie-based auth operations. Access tokens stay only in memory; refresh tokens stay in
HttpOnly, SameSite=Strict cookies (Secure, `__Host-` in production), never response JSON.
Production must proxy `/api` or explicitly configure the public build-time `VITE_API_BASE_URL`
with a compatible same-site deployment. No secret belongs in Vite variables.

| Method | Route | Request | Success | Access |
|---|---|---|---|---|
| POST | `/auth/register` | `RegisterRequest`: username, password, optional create_player/player_name | 201 `UserOut` | Trusted auth request; always Player role |
| POST | `/auth/login` | `LoginRequest`: username/password | 200 `TokenOut` and refresh cookie | Trusted auth request |
| POST | `/auth/refresh` | No JSON; refresh cookie | 200 `TokenOut`, rotated cookie | Trusted auth request; valid unused refresh token |
| POST | `/auth/logout` | No JSON; cookie or Bearer session | 204, cookie removed | Trusted auth request; idempotent |
| GET | `/auth/me` | None | 200 `UserOut` | Active Bearer session |
| POST | `/auth/me/deactivate` | None | 204, all sessions revoked | Active Bearer session; last-admin safeguard |

`UserOut`: id, normalized username, role, optional player_id, is_active. No password/hash.
`TokenOut`: access_token, token_type=bearer, expires_in=300, user. Refresh tokens rotate and
consumed-token replay revokes the entire session family. Login uses generic 401 for bad/inactive
credentials; registration conflicts return 409; input errors 422 omit raw submitted input.
Registration rejects role, player_id and is_active properties. No account can claim an old
player by supplying a matching name. Unlinked registration (`create_player=false`) is supported.

## Existing protected routes

Every route below requires Bearer authentication. Missing, expired, revoked or inactive sessions
return 401 with WWW-Authenticate. Valid but insufficient permissions return 403. Existing paths,
request models and normal success codes remain; the changes in access and financial writes
are intentional. Health (`GET /health`, 200 `{ "ok": true }`) remains public.

| Method | Route | Body | Success model | Permission |
|---|---|---|---|---|
| GET | `/players/` | None | `Player[]` | Own player only; admin all |
| POST | `/players/` | `PlayerCreate` | `Player` | Administrator; creates unclaimed player |
| GET | `/players/leaderboard` | None | `PublicLeaderboardPlayer[]` | Authenticated; id/name/elo only, no balances |
| GET | `/players/{id}` | None | `Player` | Owner/admin |
| GET | `/players/{id}/elo` | None | `PlayerEloOut` | Owner/admin |
| GET | `/players/{id}/balance` | None | `PlayerBalanceOut` | Owner/admin |
| GET | `/players/{id}/transactions` | None | `WalletTransactionOut[]` | Owner/admin |
| POST | `/players/{id}/deposit` | `WalletAmount` | Disabled | All roles denied |
| POST | `/players/{id}/withdraw` | `WalletAmount` | Disabled | All roles denied |
| GET | `/tournaments/` | None | `Tournament[]` | Authenticated |
| POST | `/tournaments/` | `TournamentCreate` | `Tournament` | Organiser/admin; creator assigned atomically |
| POST | `/tournaments/{id}/register` | `TournamentRegistrationCreate` | Existing registration record | Own player, assigned organiser, admin; free entry only |
| POST | `/tournaments/{id}/complete` | `WinnerCreate[]` | `TournamentResult[]` | Assigned organiser/admin; standings only |
| GET | `/matches/` | None | `Match[]` | Authenticated |
| POST | `/matches/` | `MatchCreate` | `Match` | Assigned tournament organiser/admin |
| POST | `/matches/{id}/result` | `MatchResult` | `Match` | Assigned tournament organiser/admin |

Financial writes return 403 with `detail.code=FINANCIAL_OPERATIONS_DISABLED` for authorised
owners/admins submitting valid payloads. Cross-owner attempts return permission denial;
malformed input may return 422, and missing sessions return 401. No API path withdraws entry
fees or distributes prizes. The legacy service-level financial calculations remain unchanged.
Free registration stores a zero-contribution registration as before.

The transactions route now declares its existing array response; leaderboard intentionally
removes the previously leaked balance field. OpenAPI adds HTTPBearer security and auth/admin
schemas. Framework validation documentation still includes optional ctx/input fields, while the
runtime handler deliberately omits submitted input/context to avoid echoing passwords.
No old snapshot was overwritten to conceal these deliberate changes.

## Administrator operations

All require an active Administrator Bearer session. No public role escalation is possible.

| Method | Route | Body | Success |
|---|---|---|---|
| GET | `/admin/users` | None | 200 `UserOut[]` |
| PUT | `/admin/users/{id}/role` | `RoleChange` | 200 `UserOut`; changed roles revoke sessions |
| POST | `/admin/users/{id}/deactivate` | None | 204, sessions revoked |
| PUT | `/admin/tournaments/{id}/organisers` | `OrganiserAssignment`: user_id | 204; active organiser required |
| DELETE | `/admin/tournaments/{id}/organisers/{user_id}` | None | 204 |
| GET | `/admin/audit-events` | None | 200 latest 100 safe audit records |

Last-active-administrator demotion/deactivation returns 409. Existing-player linking remains
unavailable pending approval. No endpoints for password reset, MFA, email verification,
settings persistence or account reactivation are claimed.

## Frontend integration

Login/register/session restoration call the auth routes above. Profile reads `/auth/me`;
wallet reads only the server-provided own player_id balance/history; dashboard reads tournaments.
Manage creates free tournaments; Administration lists users and updates roles. Navigation and
route guards reflect the authenticated role, while all permissions are enforced independently
on the backend. A failed session restoration leaves the user signed out. Failed logout clears
local credentials, explicitly reports unconfirmed server revocation and offers retry.

A single in-tab refresh handles concurrent requests; safe reads may retry once following 401.
Application mutations are never automatically replayed. Expired sessions clear credentials and
redirect protected pages to login. 403, 429 and network errors have clear messages. Unit tests
mock network calls; backend tests exercise real hashing, tokens and disposable database state.
