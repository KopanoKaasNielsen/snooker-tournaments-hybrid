# Snooker Tournament Backend (FastAPI + SQLAlchemy)

Clean architecture for managing snooker tournaments.

## Quickstart
```bash
python3.12 -m venv ~/.venvs/snooker-hybrid
source ~/.venvs/snooker-hybrid/bin/activate
python -m pip install -r requirements/bootstrap.txt
python -m pip install -r requirements-dev.txt
python -m pip check
# Runtime deployments install requirements.txt instead of requirements-dev.txt.

# Use a NEW disposable development database, not the existing snooker.db.
export DATABASE_URL=sqlite:////tmp/snooker-local-dev.db
export APP_ENV=development
python -m app.db_cli init
python -m app.db_cli seed-demo --confirm-demo  # optional demo data

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open http://127.0.0.1:8000/docs

## React frontend

Use Node.js 24 (verified with 24.11.1) and npm 11. The frontend stays in the repository root.

```bash
npm ci
npm run dev
```

Vite listens on `0.0.0.0:5173`. Open http://localhost:5173. `npm start` is equivalent.
Start the backend separately, from the repository root with the Python virtual environment active:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend defaults to the existing `snooker.db` when `DATABASE_URL` is unset. Imports and
startup no longer create tables or seed records. Schema management is explicitly migration-driven.
Do not run fresh migrations against the existing unversioned database. Record its checksum and
back it up via SQLite's read-only-source backup API before any separately approved adoption.

See [database architecture](docs/database-architecture.md) for integrity/financial risks and
[the migration guide](docs/database-migration-guide.md) for backup instructions, fresh setup,
explicit repeatable seeding and existing-copy verification. The shared engine and Alembic read
exported `DATABASE_URL`; neither implicitly loads `.env`. Demo commands require development
mode and reject the repository's existing database.

```bash
python -m scripts.verify_migrations
python -m scripts.verify_migrations --existing-copy-from snooker.db
```

Both commands perform mutations only in temporary databases; the second opens the source
read-only and verifies a disposable backup. The original is not stamped or migrated.

### API configuration

Browser requests default to same-origin `/api`. Vite proxies that prefix to
`http://127.0.0.1:8000`, stripping `/api`. No browser localhost URL is embedded.
Optionally set `VITE_API_BASE_URL` in `.env.local` before starting/building Vite to a different
API base URL. All `VITE_` values are public bundle configuration: never put secrets in them.
Cross-origin deployments require backend CORS configuration. Production hosting must serve
`dist/`, fall back to `index.html` for React routes, and proxy `/api` to FastAPI (or build with
an explicit API base URL). Vite preview does not provide the development API proxy.

### Verification and builds

```bash
npm run typecheck
npm run lint
npm run test:ci
npm run build
npm run preview -- --host 0.0.0.0
source ~/.venvs/snooker-hybrid/bin/activate
python -m pytest -q -W error
```

`lint` currently performs TypeScript checking only, not ESLint. Jest tests mock network
requests and do not prove live backend availability. Backend tests create temporary SQLite
databases automatically and never use `snooker.db`; demo data is seeded explicitly only in tests that require it.
Existing test wallet mutations run only against those temporary databases. The build produces
`dist/index.html` and bundled assets; preview normally listens on port 4173.

### Mobile and WSL networking

On the same trusted LAN, open `http://<Windows-LAN-IP>:5173` on your phone. Keep the backend
on WSL loopback; the Vite proxy forwards requests. WSL2 NAT may require Windows port forwarding
to the current WSL address and a firewall rule for port 5173; localhost forwarding alone does
not guarantee LAN access. Mirrored networking behavior depends on Windows/WSL configuration.
Allow the development port only on trusted networks. Actual mobile access depends on your
host firewall and has to be checked from the device.

### Supported behavior and gaps

Dashboard reads real tournaments. Wallet lets you explicitly choose a public player and reads
balance/history, without financial write controls or an assumed currency. Login, authenticated
profile, saved settings and logout are unavailable because no backend authentication or settings
contract exists. No protected routes are implied. Existing backend financial mutation endpoints
are unauthenticated: review access control before exposing the backend publicly.
See [the API contract](docs/frontend-api-contract.md) and
[stabilization report](results/frontend_stabilization_report.md).

Database stabilization findings and actual verification results are recorded in
[the Task 02 report](results/database_stabilization_report.md).

## Continuous integration

CI runs on pushes to `main`, `develop`, `feature/**`, `fix/**`, `chore/**` and
`stabilization-phase-2`, and on pull requests targeting `main` or `develop`. Manual
`workflow_dispatch` remains enabled (GitHub requires the workflow on the default branch for
dispatch availability). Newer runs cancel superseded runs for the same workflow/ref.

The Python 3.11/3.12 matrix installs requirements, runs pytest with warnings as errors,
verifies fresh Alembic migrations/ORM consistency and checks Black formatting. The Node 24 job
runs `npm ci`, typecheck, Jest and production build. Tests and migration verification use
temporary SQLite databases; no production database or application secrets are needed.

Bandit and pip-audit run in a separate constrained environment and remain **advisory only** via `continue-on-error`: findings, scanner install
failures and scanner service/authentication failures do not fail the job. Review their step
logs; a green workflow does not mean security scans passed. See
[the CI pipeline report](results/ci_pipeline_report.md) for actual local results, security
limitations and commands to push and monitor the first GitHub-hosted run. Local success is
not evidence of a successful remote run. Task 02C resolves the earlier clean-install blocker;
42 backend tests now pass under strict warnings on Python 3.11 and 3.12.

## Python dependencies

Runtime and development requirements are separate and share a complete transitive constraints
file. CI installs `requirements-dev.txt`; production installs `requirements.txt`. Bootstrap
pip/setuptools are pinned too. Use a new external virtualenv rather than the tracked `venv/`.
See [dependency management](docs/dependency-management.md) for exact versions, regeneration,
security sources, isolated audits and clean runtime/development setup, and
[the Task 02C report](results/dependency_stabilization_report.md) for actual results.

```bash
python -W error -m scripts.verify_dependency_environment
python -m scripts.verify_migrations --existing-copy-from snooker.db
```

These commands only migrate disposable databases. The OpenAPI snapshot is preserved; optional
framework validation-error details are distinguished from application contract changes.
