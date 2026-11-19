# Snooker Tournament Backend (FastAPI + SQLAlchemy)

Clean architecture for managing snooker tournaments.

## Quickstart
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

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
source venv/bin/activate
python -m pytest -q
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
