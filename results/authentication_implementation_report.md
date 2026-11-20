# Task 03 authentication and authorisation implementation report

## Scope and initial findings

Baseline: branch `feature/authentication-authorization`, HEAD `d2a8240` (the user-committed
CI/dependency stabilisation baseline). Working tree initially clean. Actual baseline backend
verification: **42 passed, zero warnings**. Frontend baseline: 20 tests. Seventeen API operations
had no authentication; player IDs exposed private wallet reads, financial routes were public,
frontend authentication was unavailable, and there were no user/session/assignment tables.
The legacy settings placeholder is unused by the new authentication system.

The database/API/frontend/test architecture and prior CI/dependency report were inspected before
changes. The proposed schema, permissions and approval boundary were recorded in
`docs/authentication-security-architecture.md` before implementation.

## Decisions and approval boundary

- Usernames are unique, normalized lowercase ASCII identifiers (3–64 characters). Passwords
  are 15–128 characters, Argon2id with 64 MiB, 3 iterations, parallelism 2, random salts and
  rehash-on-login. Public signup always grants Player and rejects role/ownership properties.
- Registration creates a fresh zero-balance player or an explicitly unlinked account. It never
  claims a matching existing player. **Existing-player linking is unavailable pending the
  requested administrator-verification/audit policy approval.** No linking endpoint is enabled.
- The first administrator is provisioned offline with a hidden-password CLI; no built-in account,
  placeholder signing secret or public administrator registration exists.
- Five-minute fixed-algorithm HS256 access JWTs are held only in browser memory. Secure,
  HttpOnly, SameSite=Strict refresh cookies rotate, with seven-day absolute sessions. Only
  SHA-256 token digests are persisted. Reuse of a consumed token revokes its session family.
- Authorization loads active users, current roles, ownership and session state from the database
  on every protected request. Logout/deactivation/role changes invalidate sessions immediately.
  Administrator operations protect the last active administrator. Organisers manage assigned
  tournaments; creating a tournament atomically assigns its creator.
- Cookie auth operations require the custom header and trusted origins. Startup rejects absent
  signing keys, absent origins and insecure production cookie/origin configuration. Local HTTP
  is explicitly development-only. Auth attempts have persistent bounded rate counters.
- Deposits, withdrawals and fee-bearing registration are denied for **all roles**, including
  administrators. There is no configuration bypass. Free registration and standings-only
  completion remain supported. Existing financial services/calculations are unchanged.
- Safe audit events record authentication failures/successes, refresh reuse, revocation,
  administrative changes and relevant tournament actions without passwords or tokens.

## Migration graph and data safety

```text
<base> -> dd093dfa2ebf -> d27f9a18494f -> e20261119db01 -> f20261120auth (head)
```

The new revision adds only users, auth_sessions, refresh_tokens, tournament_organisers,
auth_audit_events and auth_rate_limits. Existing players/tournaments remain unclaimed/unassigned.
Empty auth downgrade is supported; populated identity/session/audit/assignment/rate-limit
removal is refused rather than losing security data. Old migration files and migrations_backup
are unchanged. Production schema remains migration-driven; imports/startup do not seed/migrate.

Both Python versions verified history/heads/current, fresh upgrade, `alembic check`, empty
full downgrade/re-upgrade and ORM equivalence. Additional tests verify upgrading a populated
pre-authentication database preserves its player balance, auth-only empty downgrade/re-upgrade,
and populated-auth downgrade rejection. The read-only-source SQLite backup verifier accepts
an exact legacy six-table schema, explicitly adopts **only its disposable copy** at e20261119db01,
upgrades that copy, and checks every original row/value plus empty added tables. Original database
adoption is not performed or silently authorized.

## API and frontend changes

All 17 original operations remain. Health remains public. Other original operations require
Bearer authentication with explicit owner/admin or assigned-organiser checks. Player listing
is restricted to the account's player unless administrator. Leaderboard removes private balance;
transactions declare the existing typed array response. Twelve auth/admin operations bring the
total to 29. Registration/login/refresh/logout/me/deactivation, user roles/deactivation, organiser
assignments and safe audit reads are documented in `docs/frontend-api-contract.md`.

Compared with the historical OpenAPI snapshot, no request body declaration or old operation
was removed. The only existing response declaration changes are leaderboard's deliberate
privacy fix and transactions' explicit array model. OpenAPI no longer includes unreferenced
PlayerOut and includes the dependency-baseline optional framework ValidationError input/ctx;
the runtime validation handler deliberately strips raw input/context to avoid password echo.
Security requirements and auth/admin schemas are additive. `docs/backend-openapi.json` remains
byte-for-byte unchanged; `docs/authentication-openapi.json` is the separate reviewed contract.
The verifier checks the new snapshot exactly instead of overwriting historical evidence.

Frontend now uses actual login/register/refresh/logout/current-user endpoints, protected routes,
role-aware navigation and own-player wallet reads. Manage creates free tournaments;
Administration lists users and changes roles. Axios attaches in-memory Bearer credentials,
coordinates in-tab refresh, retries safe reads once, and never automatically replays a mutation.
Expired sessions clear state and route to login. Failed logout clears local credentials and
explicitly offers retry because server revocation was not confirmed. Settings remain honestly
unavailable. No mock identity or fabricated wallet balance is used in application code.

## Dependencies and CI

Runtime adds argon2-cffi 25.1.0 and PyJWT 2.15.1, with locked bindings 26.2.0, cffi 2.1.1 and
pycparser 3.12. Universal constraints retain all unrelated pins. Existing framework versions
FastAPI 0.163.2, Starlette 1.10.0 and Pydantic 2.12.5 are unchanged. Fresh external development
environments were installed for Python 3.11.15 and 3.12.3; the tracked venv was not modified.
A separate fresh Python 3.12 runtime-only environment proves production imports/startup do not
require pytest, Black or HTTPX. `pip check` passes in all three.

The workflow file is unchanged: development branch triggers, Python 3.11/3.12, Node 24,
strict pytest, migration/API/runtime checks, Black, permissions, timeouts and concurrency remain.
The updated verification scripts generate ephemeral test configuration internally; CI needs no
production key/database. Hosted CI has **not** been run or claimed successful. Security scanning
remains advisory via the existing workflow's continue-on-error settings.

## Actual verification results

External root: `/tmp/snooker-auth-03-8n2r1m06`; no tracked environment used.

| Command/check | Python 3.11.15 | Python 3.12.3 |
|---|---|---|
| Fresh requirements-dev installation | Passed | Passed |
| `python -m pip check` | Passed | Passed |
| `python -m pytest -q -W error` | **90 passed**, 0 failures, 0 warnings; 132.51s | **90 passed**, 0 failures, 0 warnings; 105.54s |
| `python -m black --check .` | Passed, 42 files unchanged | Passed, 42 files unchanged |
| `python -m scripts.verify_migrations --existing-copy-from snooker.db` | Passed | Passed |
| `python -W error -m scripts.verify_dependency_environment` | Passed | Passed |

Additional actual results:

- Fresh Python 3.12 runtime-only installation, pip check and
  `python -W error -m scripts.verify_dependency_environment --runtime-only`: passed.
- `npm run typecheck`: passed.
- `npm run test:ci`: **33 passed**, 5 suites, 0 failures (17.01s).
- `npm run build`: passed; Vite 6.4.6, 104 modules, deployable dist/index.html and assets;
  JS 241.69 kB (81.00 kB gzip), CSS 1.44 kB, build 2.73s.
- actionlint 1.7.7: passed, no diagnostics.
- Bandit 1.9.4 (`bandit -q -r app`): passed, no findings.
- pip-audit 2.10.1 of full resolved development graph in an isolated scanner environment:
  **no known vulnerabilities found**, exit 0. Its hash-hardening notice remains; no ignores used.
- `npm audit --json`: exit 1, **2 moderate package entries**, 0 high/critical. Existing Router
  advisories GHSA-wrjc-x8rr-h8h6 and GHSA-337j-9hxr-rhxg remain; registry offers a major
  react-router-dom 7.18.6 upgrade. No unrelated major upgrade was made. Login return routes
  use a fixed allowlist and the application does not use SSR hydration; these are exposure
  reductions, not a dependency remediation claim.
- Real Vite/FastAPI proxy smoke: HTML/TSX transform, health, unauthenticated denial, registration,
  login, current user, zero balance, disabled deposit, refresh rotation, logout and immediate
  access revocation passed. Used disposable SQLite and ephemeral credentials; both server
  process groups stopped and the database was removed.
- `git diff --check`: passed. Final status contains only intended modifications/new files;
  no commit, push or merge was performed.

Regression coverage retains all 42 pre-authentication backend tests, adapting HTTP setup to
real test accounts/tokens. Previously successful financial HTTP operations now use isolated
service setup where needed; new tests assert the required API denial for every role and
unchanged balances/ledger counts. Free tournament fixtures replace paid API fixtures because
fee-bearing operations are intentionally disabled. Existing tournament/match/service assertions
remain. Migration tests update the expected new head and preserve the historical financial
rollback guard. Profile/Wallet tests now assert the real supported session/ownership contract,
with no fake profile statistics. Settings coverage is retained; added tests exercise login,
registration, guards/navigation, expiry, logout failure/retry and client refresh behavior.
Frontend unit tests mock transport; backend tests exercise real Argon2/JWT/SQLite, and the live
proxy smoke is separate actual integration verification.

Intermediate failures were not hidden: an early backend pass found the migration snapshot helper
assumed every table had id; it was repaired for composite/non-id tables. The first expanded run
was 87 passed/1 failed because a new HTTPS test omitted the origin configuration; test setup was
corrected to exercise the intended safeguard without weakening the assertion. Initial frontend
typecheck rejected the obsolete profile-test shape; tests were aligned to actual UserOut fields.
Sandboxed backend verification stalled and was rerun with the required local execution permission;
the remaining stalled task process was stopped. The first live smoke safely refused occupied port
8000 before starting any server or making requests; the successful retry used backend 18003 and
Vite 15173 with a temporary proxy target override. No existing server was stopped or accessed.

## Preservation evidence

Original snooker.db SHA-256, before and after:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa
```

The original remains unversioned, unstamped and unmigrated. Tests/experiments used temporary
files only; compatibility source access is SQLite read-only. Historical migration files,
backend-openapi.json, tracked environments, package-lock and workflow are unchanged.
No .env contents, signing keys, passwords or refresh tokens were printed or committed.

## Files created and modified

- `.gitignore`
- `README.md`
- `__tests__/App.test.tsx`
- `__tests__/Profile.test.tsx`
- `__tests__/Wallet.test.tsx`
- `__tests__/client.test.ts`
- `app/crud.py`
- `app/main.py`
- `app/models.py`
- `app/routes/matches.py`
- `app/routes/players.py`
- `app/routes/tournaments.py`
- `app/schemas.py`
- `docs/database-architecture.md`
- `docs/database-migration-guide.md`
- `docs/dependency-management.md`
- `docs/frontend-api-contract.md`
- `requirements/constraints.txt`
- `requirements/runtime.in`
- `scripts/verify_dependency_environment.py`
- `scripts/verify_migrations.py`
- `src/App.tsx`
- `src/api/client.ts`
- `src/components/AppLayout.css`
- `src/components/AppLayout.tsx`
- `src/context/AuthContext.tsx`
- `src/pages/Home.tsx`
- `src/pages/Login.tsx`
- `src/pages/Profile.tsx`
- `src/pages/Wallet.tsx`
- `src/types/user.ts`
- `tests/conftest.py`
- `tests/test_api_flow.py`
- `tests/test_migrations.py`
- `tests/test_players.py`
- `tests/test_tournament_flow.py`
- `app/auth_cli.py` (new)
- `app/auth_config.py` (new)
- `app/auth_schemas.py` (new)
- `app/routes/admin.py` (new)
- `app/routes/auth.py` (new)
- `app/security.py` (new)
- `docs/authentication-openapi.json` (new)
- `docs/authentication-security-architecture.md` (new)
- `migrations/versions/f20261120auth_add_authentication.py` (new)
- `src/components/ProtectedRoute.tsx` (new)
- `src/pages/Admin.tsx` (new)
- `src/pages/Manage.tsx` (new)
- `src/pages/Register.tsx` (new)
- `test-utils/auth.tsx` (new)
- `tests/test_authentication.py` (new)
- `tests/test_authorisation.py` (new)
- `results/authentication_implementation_report.md` (this report)

## Outstanding risks and readiness

No local test/build/migration blocker remains. Existing-player linking is deliberately unavailable
pending the explicit approval requested before implementation. Existing accounts cannot claim
historical players; operational adoption of the original database remains separately reviewed.

Security architecture documents remaining production work: trusted HTTPS/reverse proxy and
secret delivery, proxy-aware edge throttling, SQLite contention/scaling, session/audit retention,
MFA/recovery/reactivation policy, secret rotation, and external tamper-evident audit retention.
Refreshes are coordinated within one tab; simultaneous refresh in multiple tabs may trigger
fail-closed replay revocation and require login again. No permissive replay grace was added.
Existing frontend advisories remain and require a dedicated Router upgrade. Live smoke is HTTP
on loopback, not a real-device/HTTPS/browser E2E or production penetration-test claim.

Recommended next work: approve/document existing-player ownership evidence and linking policy;
review Task 03 and run hosted CI after a user-authorized commit/push; then Task 04 must address
financial precision, atomicity, idempotency, ledger reconciliation and prize distribution before
any financial API mutation is enabled. No administrator privilege should bypass that gate.
