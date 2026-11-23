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
export AUTH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export AUTH_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
export AUTH_COOKIE_SECURE=false  # development HTTP only
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

Register and sign in using real backend accounts. Dashboard, wallet, profile and settings
routes require a session. Wallet balance/history are restricted to the server-linked player;
there is no arbitrary player selector. Organiser and administrator navigation follows the
current account role; the server independently enforces ownership and tournament assignments.
Settings persistence remains unavailable. Every financial mutation, including fee-bearing
registration, returns an explicit denial until Task 04. Free registration and standings-only
completion remain available to authorised accounts.
See [the current API contract](docs/frontend-api-contract.md),
[security architecture](docs/authentication-security-architecture.md) and
[Task 03 verification report](results/authentication_implementation_report.md).

### Authentication configuration and administrator setup

The quickstart generates a development-only signing key without printing it. Retain a securely
managed key between server restarts if sessions should survive. Never put it in a `VITE_` value,
source control, logs or browser storage. `AUTH_SECRET_KEY` is mandatory; the legacy configuration
placeholder is never used. Access tokens last five minutes; rotating HttpOnly refresh cookies
expire after seven days. Logout, deactivation and role changes revoke sessions immediately.

Production requires HTTPS, explicit `AUTH_ALLOWED_ORIGINS` (comma-separated exact origins),
`AUTH_COOKIE_SECURE=true` (default), and a securely generated signing key delivered by the
host's secret manager. Use same-origin `/api` reverse proxying. `APP_ENV=development` plus
`AUTH_COOKIE_SECURE=false` is only for trusted local HTTP development. Authentication endpoints
require `X-Snooker-Client: web`; the shared frontend client supplies it. Different-site browser
API hosting is unsupported by SameSite=Strict cookies; prefer the same-origin proxy.

On a **new, migrated development database** and with the same auth environment, create the
first administrator explicitly:

```bash
python -m app.auth_cli create-admin --username initial_admin
```

The command prompts for the password twice without echoing it, grants no player ownership, and
does not alter an existing account. Never point this setup command at the preserved original
`snooker.db`. Public registration always grants Player; administrators can assign Organiser and
Administrator roles through `/admin/users/{id}/role` or the administration page. Existing players
remain unclaimed. Existing-player account linking awaits policy approval and has no enabled
endpoint. Administrators assign existing tournaments via
`PUT /admin/tournaments/{id}/organisers` with `{ "user_id": organiserId }`.

For mobile HTTP development add the exact phone-visible frontend origin, for example
`http://192.168.1.20:5173`, to `AUTH_ALLOWED_ORIGINS` before starting FastAPI. Keep requests
through Vite's same-origin `/api` proxy; no backend port exposure is necessary. Without this
explicit origin authentication will be denied. WSL/firewall limitations described above still apply.

Backend tests generate an ephemeral signing key and disposable databases automatically. The
runtime/contract verification script does the same internally; CI needs no production credentials.
The historical unauthenticated OpenAPI snapshot is retained; the new authentication snapshot
is checked separately to make the intentional access-control contract changes reviewable.

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

## Exact-money financial foundation (Task 04A)

The [financial architecture](docs/financial-integrity-architecture.md) implements the approved
new BWP subledger: two decimal places (100 thebe/pula), Decimal arithmetic, bounded integer
minor units, atomic postings, UUID4 idempotency keys and append-only ledger protections.
Historical balances, ledgers, fees and contributions have **unknown currency** and are not
converted or copied. New accounts require explicit BWP and pristine zero-balance/no-history
players. Existing wallet HTTP reads remain on the legacy contract. Every financial mutation
HTTP operation remains disabled, including deposits, withdrawals, entry fees and payouts.

On a **new disposable development database**, the existing init/upgrade commands apply additive
revision `g20261120fin`. No account or credit is seeded. Internal development use after migration:

```python
from decimal import Decimal
from uuid import uuid4
from app.database import make_engine
from app.services.financial_wallets import FinancialWalletService

engine = make_engine("sqlite:////tmp/approved-dev.db")
service = FinancialWalletService(engine)
# player_id must already exist, with no legacy balance or transaction history.
account = service.open_wallet(player_id, currency="BWP")
# Development-only example; not proof of external funding or HTTP activation.
key = str(uuid4())  # retain this SAME key for retries of this operation
receipt = service.post(account.id, kind="deposit", amount=Decimal("1.00"),
                       currency="BWP", idempotency_key=key)
assert service.reconcile()[0].consistent
engine.dispose()
```

Sub-thebe postings and float/bool/string/integer coercions are rejected. Explicit calculation
rounding is separately authorised and HALF_EVEN; existing prize calculations are unchanged.
SQLite BEGIN IMMEDIATE serialises writers before reading balances/idempotency state; bounded
busy failures require retrying the complete unit with the same key. PostgreSQL is explicitly
unsupported by the new service/migration pending schema, row-lock and retry verification.

Read-only diagnostics (never repair, round, create missing files or authorise adoption):

```bash
python -m scripts.audit_legacy_finances --database snooker.db
python -m scripts.reconcile_financial_wallets --database /tmp/approved-dev.db
```

Exit codes are 0 = no findings, 1 = reconciliation/integrity findings, 2 = inspection failure.
The BWP command covers only the new tables; empty wallets do not reconcile historical funds.
See the [risk assessment](docs/financial-risk-assessment.md) and
[implementation report](results/financial_integrity_foundation_report.md). Historical adoption,
financial HTTP activation and prize-rule changes still require separate approval.

## Internal financial operations (Task 04B)

The [operation architecture](docs/financial-operations-architecture.md) adds authenticated internal
PENDING/VERIFIED/POSTED/REJECTED/CANCELLED workflows, UUID4 retry identity, digest-only evidence,
independent administrator review, immutable audit and operation-to-ledger reconciliation. Revision
`h20261120ops` adds two empty tables and six guards; no historical money or prize logic changes.

There are no financial operation HTTP endpoints, provider integrations or enabled deposit,
withdrawal, entry-fee or payout HTTP writes. The default evidence verifier refuses verification.
Passing adapters exist only in tests; VERIFIED is not settlement and POSTED is a local ledger
commit. `FinancialOperationService` methods take real access tokens and enforce current database
identity/role/ownership, including before idempotent replay.

Operation posting uses the existing wallet primitive inside one shared SQLite transaction with
the operation state, receipt link and audit. Failed transactions leave VERIFIED with no posting;
a committed response-loss retry returns the original POSTED receipt. Existing standalone Task
04A entries are counted separately, never assigned invented operations. Run wallet reconciliation
and operation reconciliation for their distinct scopes. See the
[implementation report](results/financial_operations_implementation_report.md). External provider
adapters, financial HTTP writes and historical adoption still need separate approval.

## Tournament financial policy review (Task 04C)

The [audit/architecture](docs/tournament-financial-architecture.md) and
[policy questions](docs/tournament-financial-policy-questions.md) identify a rule mismatch: current
code defaults to 100% to the first winner; its test uses 60/30/10. No checked default/call site establishes 50/30/20, and no
financial 10% token allocation/refund rule is implemented. Those rules need explicit approval.

Revision i20261120tfin adds only immutable POLICY_REQUIRED fee/refund/payout **review identities**
and request history. Amount, currency, financial operation and ledger receipt remain null; no
legacy fee is assumed BWP. Current admins/assigned organisers may record reviews; only admins
reconcile metadata. Core financial services refuse those blocked identifiers as posting keys.
Actual collection, refunds, payouts and token calculations are unavailable, and financial HTTP
writes remain disabled. No provider settlement or automatic completion payout is claimed.
See [the implementation report](results/tournament_financial_implementation_report.md).

### Inactive tournament financial policy (Task 04C Phase 2)

New internal tournaments may explicitly opt into immutable `BWP_TOURNAMENT_V1` BWP/thebe pricing. No existing tournament inherits it. The dedicated pool is non-spendable; paid confirmation, fee collection, sponsorship credits, refunds, tokens and payouts remain blocked. Only free entries, independently approved waivers, eligibility/results reviews and non-postable calculation scenarios are supported internally. All financial HTTP mutations stay disabled.

See [approved policy and activation boundaries](docs/tournament-financial-policy.md), [architecture](docs/tournament-financial-architecture.md), and [remaining policy questions](docs/tournament-financial-policy-questions.md). Revision `j20261120tv1` is additive and refuses populated downgrade; run `python -m scripts.verify_migrations --existing-copy-from snooker.db` to verify fresh migrations and a **disposable read-only-source copy**, never to migrate the original database. The compatibility `entry_fee` field is not authoritative for V1: use the internal policy's explicit `price_minor`; no V1 HTTP API is enabled.
