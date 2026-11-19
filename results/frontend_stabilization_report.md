# Frontend stabilization report

Date: 2026-11-19. Branch: `feature/frontend-stabilization`.

## Initial findings

- Initial git status was clean. No commits, pushes, merges or destructive git operations were performed.
- Audited every source file under `src/` and the sole public HTML file, both existing frontend test files, package/TypeScript/Jest configuration, ignore rules and the existing CI workflow.
- Audited FastAPI main, dependencies, database configuration, all three route modules, models, schemas and backend tests. Generated the actual OpenAPI schema using an isolated database.
- No bundler or usable start script existed. Build only checked types. Dependencies were absent; initial `npm test -- --runInBand` failed with `jest: not found` (exit 127).
- Axios used browser localhost, CRA environment access and cookies. `/auth/login` and `/users/me` do not exist. Settings falsely confirmed persistence. Dashboard fixtures and wallet transactions/balance were fabricated. Mobile CSS hid all navigation.
- Backend imports eagerly seed the database. Initial pytest baseline from a safe `/tmp` working directory failed during collection: `sqlite3.OperationalError: no such table: players` (exit 4). No initial pass count was available.
- Tests previously used root `test.db`; direct imports of `tests.conftest` can create duplicate fixture modules. Migration configuration imports a nonexistent Python `DATABASE_URL` symbol.

## Files created and modified

Created:
- `vite.config.ts`, root `index.html`, `package-lock.json`.
- `__tests__/App.test.tsx`, `Wallet.test.tsx`, `client.test.ts`, `styleMock.cjs`.
- `docs/frontend-api-contract.md`, `docs/backend-openapi.json`, this report.

Modified:
- `package.json`, `tsconfig.json`, `jest.config.ts`: Vite scripts/dependencies, strict config coverage, Jest CSS mocking. TypeScript constrained to 5.6.
- `src/api/client.ts`: configurable same-origin API client, timeout, no cookie credentials, safe error descriptions.
- `src/context/AuthContext.tsx`: honest unavailable identity provider with no unsupported requests or stored credentials.
- `src/pages/{Home,Dashboard,Login,Wallet,Profile,Settings}.tsx`: real read-only requests, loading/empty/error/retry behavior and explicit capability gaps.
- `src/components/AppLayout.css`: retain styling and show wrapping mobile navigation.
- `__tests__/Settings.test.tsx`: retain file and replace false persistence/ranking assumptions with assertions for the actual unsupported behavior. Existing Profile tests retained unchanged and pass.
- `app/database.py`, `app/models.py`, `tests/conftest.py`: configurable database URL, create tables before eager seeding, temporary test databases and shared fixture module identity.
- `.github/workflows/ci.yml`: frontend job using Node 24, npm ci, typecheck, Jest and build; backend job preserved; quoted existing colon-containing step names to make YAML valid.
- `.gitignore`, `README.md`: secrets/artifacts ignored, report explicitly unignored, setup/configuration/testing/networking guidance.

Migrated `public/index.html` to root, adding the module entry script. The old duplicate file is removed; no database file is removed. App routes, entry rendering, auth hook, layout component, NotFound and existing CSS structure were inspected and retained.

## Architecture decisions

- Root Vite application with React plugin, port 5173, host 0.0.0.0 and strict port selection. Aliases match TypeScript and Jest. Vite 6.4.6 / React plugin 4.7.0; React remains 18.3.1, Jest 29.7.0. Vite setup follows [official Vite 6 guidance](https://v6.vite.dev/guide/).
- `VITE_API_BASE_URL` defaults to `/api`. Vite strips `/api` and forwards to loopback FastAPI port 8000. Production reverse proxy configuration is documented. Public Vite configuration contains no secrets.
- No authentication system, route guard, logout or financial write functionality invented. No token/session is stored, and Axios does not send cross-origin credentials. Public player selection is never treated as login.
- Profile keeps its injectable rendering behavior for the existing tests, while the real provider explicitly disables profile availability. Settings has no fake save control.
- Dashboard displays real tournament records. Wallet uses explicit player selection, separate balance/history reads and no assumed currency. Effect cleanup cancels obsolete requests.
- `lint` intentionally remains type checking only. No ESLint claim is made.

## Actual API mapping

| Frontend use | Method and actual backend route | Authentication | Body | Response |
|---|---|---|---|---|
| Dashboard | GET `/tournaments/` | None | None | Tournament array |
| Wallet selection | GET `/players/` | None | None | Player array |
| Selected balance | GET `/players/{player_id}/balance` | None | None | `{player_id, balance}` |
| Selected history | GET `/players/{player_id}/transactions` | None | None | `{id,type,amount,timestamp}[]` |

See the contract and checked-in OpenAPI for all 14 paths, methods, request bodies and exact schemas. Only these four backend operations are used by the UI; smoke verification also reads `/health`. Unsupported auth/profile requests were removed. HTTP 401 gets an access-denied explanation; network failures offer retry without exposing response internals.

## Missing capabilities

No authentication, current-user profile, settings persistence, logout, notification preferences, favourite cue, email, world ranking, currency metadata, sponsorship/ticket revenue or live venue readiness contract exists. No successful integration is claimed for these features. Backend deposit, withdrawal and tournament financial mutation routes exist but are not invoked by this frontend.

## Actual verification results

| Command/check | Actual result |
|---|---|
| Initial `npm test -- --runInBand` | Failed: Jest not installed, exit 127 |
| Initial isolated backend pytest | Collection failed: missing players table, exit 4 |
| First backend run after isolation change | 9 passed, 8 failed: duplicate conftest engines; repaired |
| Sandboxed backend run | Stalled in TestClient; interrupted; rerun outside sandbox |
| `npm ci` | Passed; dependency deprecation notices and 2 moderate advisories |
| `npm run typecheck` | Passed, strict TypeScript |
| `npm run test:ci` | 5 suites passed, 20 tests passed, 0 failed |
| `npm run build` | Passed; 100 modules; dist/index.html plus CSS and JS assets |
| `venv/bin/python -m pytest -q -o faulthandler_timeout=15` | 17 passed, 0 failed; 139 existing deprecation warnings |
| `git diff --check` | Passed |
| `git status --short` | Reviewed; only intended source/config/test/docs changes; no database changes |
| `npm audit --json` | 2 moderate React Router advisories; no high/critical advisories |
| CI YAML parse | Passed; jobs `test` and `frontend` |
| Server shutdown verification | Both ports 5173 and 8000 refused connections (111) |
| Local Black check on changed Python files | Could not run: installed Black fails importing `30fcd23745efe32ce681__mypyc` |

The sandboxed port-closure check was denied socket access; its approved rerun confirmed both ports closed. The first sandboxed npm audit failed DNS resolution; the approved network-enabled rerun produced the advisory results. Installation required network-enabled execution. No automatic force-upgrade was used.

Frontend tests mock requests. They cover Home/application rendering, navigation, unknown routes and home recovery, unsupported login/profile/settings, dashboard loading/empty/data/error/retry, preserved Profile states, wallet loading/error/retry/zero balance/empty history and wallet-request failure, plus client defaults/network/401/server error handling. Auth success, guards and logout tests do not apply to an unsupported backend mechanism.

Live read-only smoke checks, using `/tmp/snooker-smoke.db` rather than existing data:
- Vite ready in 336 ms on port 5173.
- GET `/`, `/profile`, `/src/index.tsx`, `/src/App.tsx`: HTTP 200 with HTML or transformed JavaScript as appropriate.
- GET `/api/health`, `/api/tournaments/`, `/api/players/`, `/api/players/1/balance`, `/api/players/1/transactions`: HTTP 200 through Vite proxy. Health true, seeded tournament/player records, balance 0.0 and empty history observed.
- Temporary Vite and Uvicorn servers stopped with interrupt; Uvicorn confirmed shutdown complete. No live deposits/withdrawals were performed. Financial mutations in regression tests were isolated.

## Data preservation and security

`snooker.db` SHA-256 before and after verification:
`7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa`.
No secrets from `.env` were read or printed. Lockfile is retained and unignored; dependencies, build/coverage files, temporary files and secret environment files are ignored. No tracked database was removed.

## Remaining issues

- npm audit identifies React Router advisories GHSA-wrjc-x8rr-h8h6 and GHSA-337j-9hxr-rhxg. Proposed remediation is a major upgrade to Router 7.18.6. This application uses fixed links and no SSR hydration, but the dependency findings remain and require a planned upgrade.
- Backend mutation endpoints are public and CORS is permissive. Access control requires a separately approved backend task before public deployment.
- Alembic's existing import mismatch is documented; migrations were not run or rewritten against application data.
- Backend deprecations and the local broken Black installation remain; backend CI was preserved, not claimed to have run on GitHub.
- No browser automation tool was available. DOM behavior was tested with jsdom and server modules with HTTP; no actual browser console or phone/Windows firewall check is claimed. WSL LAN forwarding remains host-dependent.
- No persistent notification/account features are provided. API responses are statically typed, without runtime schema validation.

## Recommended next task

Define the backend authentication/access-control contract and restrict financial operations before exposing the application. Separately repair Alembic configuration, update Router with migration tests, and verify real browser/mobile access on the target WSL host.
