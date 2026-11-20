# Task 03 authentication design (recorded before implementation)

Baseline: d2a8240 on feature/authentication-authorization. Original database SHA-256:
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa.

## Approval boundary

Existing player ownership is not inferred from a name, username or client-provided player ID.
An approval question is pending: permit administrator-only linking of a verified existing
player to an unlinked account, with a mandatory audit reason, or leave that operation unavailable.
No existing-player linking endpoint will be enabled without that approval. Registration may
create a fresh zero-balance player or leave the account unlinked for manual review. It never
claims existing records. Existing players and tournaments remain unowned/unassigned after migration.

Financial restrictions are already authorized by the task: deposits and withdrawals are denied
for every role, including administrators, until Task 04. Fee-bearing tournament registration is
also denied because the old route commits a wallet withdrawal. Free registration is allowed.
Tournament completion records standings/status only; it does not distribute prizes. No feature
flag or administrator bypass can enable financial writes in this task.

## Proposed additive schema

Historical revisions are immutable. A new revision follows e20261119db01 and adds tables only:

- users: unique normalized username, Argon2id password hash, constrained role (player, organiser,
  administrator), active flag, optional unique player_id FK, UTC creation time.
- auth_sessions: random UUID primary key, user FK, creation/absolute expiry/revocation times.
- refresh_tokens: unique SHA-256 digest of a random opaque token, session FK, creation/expiry
  and consumed times. Plaintext tokens are never persisted.
- tournament_organisers: composite tournament/user PK and FKs, explicit assignments.
- auth_audit_events: event name, success flag, optional actor/user and target IDs, UTC time and
  bounded reason. Never passwords, access tokens, refresh tokens or raw login payloads.
- auth_rate_limits: hashed request bucket IDs, counters and expiration for bounded auth attempts.

No existing player, wallet, tournament, match or financial column is rewritten. Existing data
has no automatic identity assignment. Downgrade is supported when authentication tables are
empty; populated authentication data must not be silently discarded.

## Credentials and sessions

Argon2id: 64 MiB memory, 3 iterations, parallelism 2; per-password random salt and rehash on login
when parameters change. Passwords 15–128 characters. Generic login rejection, dummy hash work
for unknown users, bounded auth request rates, and no raw password logs or persistence.

Access tokens: 5 minute HS256 JWTs with fixed algorithm, issuer, audience, subject, session ID,
issued-at, expiry and unique ID. Required signing key comes only from AUTH_SECRET_KEY, generated
with secrets.token_urlsafe(48); no fallback to the legacy placeholder. Startup fails closed
without secure configuration. Authorization always loads current active user/role/session from
the database; role or ownership claims supplied by browsers are never trusted.

Refresh tokens: random opaque values in HttpOnly SameSite=Strict cookies, Secure in production,
rotated on each refresh, stored only as digests. Absolute session lifetime seven days. Consumed
refresh-token reuse revokes the session family. Logout, deactivation and administrative security
changes revoke sessions; access tokens are checked against session revocation on every request.
Access tokens live only in browser memory, not localStorage/sessionStorage. Refresh/logout use
origin validation plus a required custom request header, with explicit credentialed CORS origins.
Local HTTP cookies are allowed only with explicit development configuration; deployment requires HTTPS.

## Permission matrix

| Operation | Player | Organiser | Administrator |
|---|---|---|---|
| Own current user/profile | Yes | Yes | Yes |
| Another player's private profile/balance/history | No | No | Yes |
| Player listing | Own record | Own record | All records |
| Tournament/match/leaderboard reads | Authenticated | Authenticated | Authenticated |
| Leaderboard wallet balances | Never included | Never included | Never included |
| Create/manage tournament or submit match result | No | Assigned tournaments; creator assigned automatically | Yes |
| Free registration | Own player only | Own player or assigned tournament roster | Yes |
| Fee registration, deposit, withdrawal | Disabled | Disabled | Disabled |
| Complete tournament (standings only) | No | Assigned tournament | Yes |
| Assign organisers, set roles, deactivate others, audit reads | No | No | Yes |

Registration always creates role=player; role/ownership input is forbidden. Initial administrator
creation is an explicit offline command with a hidden password prompt, never public signup.
Last-active-administrator protections prevent accidental loss of administrative access. Non-admin
unauthorized player IDs yield a non-enumerating denial. Authentication failures return 401;
authenticated policy denials return 403, financial denials carry a stable disabled-operation code.

## Frontend and verification plan

Real register/login/logout, refresh-based session recovery, protected routes, role-aware navigation
and expired-session states replace unavailable placeholders. A central client attaches in-memory
Bearer tokens, coordinates a single refresh and never retries a mutation automatically. Wallet
reads only the account's server-reported player ID; no browser player selector grants ownership.
Settings persistence remains unsupported and is described honestly.

Tests will preserve database/service regressions and adapt HTTP tests only for real tokens,
roles and the newly disabled financial routes. Existing deposits used as fixture setup move to
explicit isolated-database setup, not a production bypass. Add tests for credential hashing,
expiry, replay/revocation, deactivation, ownership, organiser scope, administrator operations,
CSRF/origin checks and unchanged balances on denied writes. Verify both Python versions,
frontend checks, migration/metadata parity, disposable-copy compatibility and original checksum.
Old API snapshot remains as history; a separately documented authenticated contract is added.

References: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[PyJWT usage](https://pyjwt.readthedocs.io/en/stable/usage.html),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Implementation and operational limits

The proposed six-table design is implemented by additive revision `f20261120auth` after
`e20261119db01`. No historical file or original record was changed. The first administrator
is provisioned with `python -m app.auth_cli create-admin --username ...` using hidden password
prompts. There are no built-in credentials, demo accounts or automatic administrator grants.
The implemented API and intentional historical contract differences are documented in
[frontend-api-contract.md](frontend-api-contract.md).

The supported backend is SQLite. Authentication request counters use SQLite atomic upserts;
last-administrator removal checks acquire a write transaction before counting. Reverse proxies
must preserve the same-origin deployment and enforce edge request limits/body limits; the app
does not trust client-supplied forwarded IP headers. When all clients share a proxy IP, the
conservative app rate limit is shared, so deployment-specific proxy/rate-limit tuning is needed.

Refresh replay detection deliberately fails closed. In-tab requests share one refresh operation,
but simultaneous refreshes in different tabs can be treated as replay and require signing in
again. Browser-wide refresh coordination is a remaining availability improvement; no replay
exception or grace period weakens revocation. Database access on every protected request
provides immediate session/role revocation. SQLite write contention is a scaling limitation.

Audit rows contain safe event names, actor/target identifiers and bounded reasons, never raw
passwords/tokens or complete request payloads. Authentication success/failure, refresh reuse,
logout, deactivation, role/assignment changes and relevant tournament actions are recorded.
These rows are not a tamper-evident external audit service and do not log every denied resource
read. Session/refresh/audit retention and archival need an operational policy before long-running
production use. Rate buckets are pruned during authentication requests.

Password reset, account reactivation, MFA, breach-password checking, email verification and an
interactive session-management page are outside this task. The current user endpoint and
self/admin deactivation are implemented; deactivation currently uses the API. Initial administrator
provisioning requires trusted server/database access. Signing-key replacement invalidates all
access tokens; rotate/revoke outstanding sessions through a separately reviewed operational
procedure if a key is compromised. HTTPS, XSS prevention, trusted frontend origins, private database
files/backups and secret-manager access remain deployment responsibilities.

Existing React Router moderate advisories remain in the dependency baseline. Login return
navigation accepts only a fixed internal route allowlist, excluding backslash/untrusted redirect
targets; the application does not use SSR hydration. This reduces exposure but is not a library
patch. No unrelated frontend major upgrade was performed. Review the dependency report and
`npm audit` results before deployment. Financial precision, idempotency, reconciliation and payout
integrity remain Task 04 work; the API cannot enable financial writes with a role or configuration
flag. Existing-player linking remains unavailable until the requested policy approval arrives.
