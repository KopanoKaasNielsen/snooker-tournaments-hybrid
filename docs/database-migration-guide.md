# Database setup and migration guide

## Preserve existing data first

Never delete, replace, reset, or point test commands at `snooker.db`. Stop writers before an
operational migration. Record `sha256sum snooker.db` and create a backup with SQLite's backup
API, which includes a consistent view of WAL content. Copying only a live `.db` file may omit
WAL transactions. Store backups outside version control with appropriate permissions.

Example read-only-source backup to a **new, non-existing** path:

```bash
python - <<'PY'
from pathlib import Path
import sqlite3
source = Path('snooker.db').resolve()
target = Path('/tmp/snooker-before-migration.db')
if target.exists():
    raise SystemExit('Choose a new backup filename; refusing to overwrite')
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
    with sqlite3.connect(target) as backup:
        original.backup(backup)
print('Backup created; source was opened read-only')
PY
sha256sum snooker.db /tmp/snooker-before-migration.db
```

The backup's bytes/checksum need not equal the source under every SQLite journal/layout state;
verify integrity and application rows as well. Never log database URLs containing credentials.

## Fresh development database

From the repository root, with Python 3.11/3.12 and requirements installed:

```bash
python3.12 -m venv ~/.venvs/snooker-hybrid
source ~/.venvs/snooker-hybrid/bin/activate
python -m pip install -r requirements/bootstrap.txt
python -m pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:////tmp/snooker-local-dev.db
export APP_ENV=development
python -m app.db_cli init
python -m app.db_cli seed-demo --confirm-demo
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Choose a fresh disposable file for first use. `init` runs migrations only and inserts no demo
records. `seed-demo` is separate and repeatable. It requires `APP_ENV=development`, an explicit
SQLite file URL, `--confirm-demo`, and a database at the migration head. Both development
commands reject the repository's existing `snooker.db` (including resolved aliases).
`python -m app.init_db` delegates to the same guarded CLI for compatibility; it no longer
seeds merely by being imported or invoked without a command. Existing named demo records
are preserved, including balances and ratings. Do not use demo seeding for production.

`.env` is not automatically read by the shared engine/Alembic. Set `DATABASE_URL` in the
process environment or your secret manager/service configuration. The default path remains
`sqlite:///./snooker.db` for existing app compatibility, but running the application no longer
creates its schema or inserts data. Startup requires operators to manage the schema first.

## Alembic commands (disposable database)

```bash
export DATABASE_URL=sqlite:////tmp/snooker-migration-sandbox.db
python -m alembic history
python -m alembic heads
python -m alembic current
python -m alembic upgrade head
python -m alembic check
```

The expected single head is `i20261120tfin`; history contains seven revisions. An empty fresh
schema can be downgraded and rebuilt:

```bash
python -m alembic downgrade base
python -m alembic upgrade head
python -m alembic check
```

**Only perform that downgrade in an empty disposable database.** The corrective revision rejects
populated tables. Historical revisions themselves are preserved and can be destructive if
invoked directly against an old revision: never use downgrade as a production data rollback.
Restore from a reviewed backup/forward fix instead. SQLite online migrations are verified;
full offline `--sql` generation and PostgreSQL migration compatibility are not claimed.

## Existing unversioned database

The preserved `snooker.db` has the six-table pre-authentication schema, but no Alembic version table.
Do not run `upgrade head` on the original: the base revision creates existing tables. Do not
blindly stamp it. No original version adoption was performed during this task.

Run the compatibility verifier first:

```bash
python -m scripts.verify_migrations --existing-copy-from snooker.db
```

This opens the source read-only and uses SQLite backup into a unique temporary directory.
It verifies source-copy integrity, foreign keys and schema equivalence against the pre-authentication
or current ORM metadata. For an unversioned, schema-matched copy it demonstrates direct-upgrade
rejection, explicitly announces stamping **the disposable copy** at the matching baseline
(`e20261119db01` for the six-table original), then upgrades to `i20261120tfin`, runs current/check
and compares all original application rows. Added authentication tables must be empty.
The temporary copy is removed on completion. The original is never stamped.

A future operational adoption requires an operator to review that evidence, stop writers,
back up the target, and explicitly authorize a stamp of the matching schema to the known
revision `e20261119db01`. A stamp only records a version; it does not repair schema or records.
That target-changing step is deliberately not automated here. If the actual schema differs,
or the database is a populated historical revision, do not force it through this path: create
a separately reviewed data migration addressing missing balances, dates and enum semantics.

## Creating future revisions

1. Work on a disposable migrated database; update models and create a new revision with
   `python -m alembic revision --autogenerate -m 'describe change'`.
2. Review every generated operation, data precondition and downgrade. Preserve old revisions.
3. Test fresh upgrades, `alembic check`, and compatibility with representative backed-up data.
4. Review financial changes, time-zone policies and data backfills explicitly before deployment.

Shared metadata is `app.database.Base.metadata` with `app.models` registered. Application and
Alembic both use environment configuration. Programmatic tests may supply an explicit
`Config.attributes['database_url']`; the ini URL is a documented fallback example, not an
override of the shared environment resolver. SQLite migrations use a private FK-disabled
connection for batch DDL and check referential integrity before commit. Failed DDL/version
updates are rolled back. Application connections always enable FKs.

## Regression and CI verification

```bash
python -m pytest -q
python -m black --check .
python -m scripts.verify_migrations
npm run typecheck
npm run test:ci
npm run build
git diff --check
sha256sum snooker.db
```

Backend tests manage their own temporary databases regardless of an inherited `DATABASE_URL`.
The standalone migration verifier also uses explicit temporary URLs, so it is safe to run
without setting an environment variable. Normal production migrations remain manual, explicit
commands against a reviewed target. CI runs tests and fresh migration verification on Python
3.11/3.12, and retains the frontend Node 24 job.

Use the patched formatter and clean external environment documented in
[dependency management](dependency-management.md), rather than reinstalling the old vulnerable
Black pin from the Task 02 baseline. Existing virtualenv files happen to be tracked in this
repository; no untracking or history cleanup was performed during stabilization.

## Financial foundation revision

`g20261120fin` adds two initially empty BWP wallet/ledger tables plus three integrity triggers.
It never backfills existing balances, ledgers, tournament fees or contributions and does not
assume historical currency. The revision and service explicitly support SQLite only.
`verify_migrations` validates fresh upgrade/check/empty roundtrip and installed trigger SQL.
Versioned pre-financial/auth schemas and the six-table pre-authentication original are accepted
only when their schema matches the supported baseline, and upgraded only on disposable copies.
Unversioned current schemas missing required ledger triggers are refused before copy stamping.
Populated financial downgrade is refused, including a zero-balance wallet with no ledger entries.
See the financial architecture for the separately approved adoption procedure still required
before any historical conversion or API activation.

## Financial operation revision

`h20261120ops` creates only financial_operations, financial_operation_audit, constraints/indexes
and six state/audit protections. It never backfills operation IDs onto existing ledger rows.
Populated operations/audit cannot be downgraded; an empty operation schema can be downgraded
to g20261120fin while preserving funded wallets and their ledger. Versioned Task 04A copies are
verified at their matching schema and upgraded on disposable backups only. Missing ledger or
operation triggers are refused before copy stamping. SQLite-only support and the ban on original
snooker.db migration/adoption remain unchanged.

## Policy-blocked tournament reviews

`i20261120tfin` adds only tournament_financial_intents and tournament_financial_requests with
scope/authority/immutability checks. No money/price/currency or operation backfill is performed.
Populated review metadata cannot be downgraded; empty review downgrade preserves funded
wallets and existing operations. Compatible h20261120ops snapshots are rehearsed only on
disposable copies. Required review triggers are checked before any copy stamp and after
fresh upgrade. Do not migrate/stamp the original repository database. Monetary tournament
rules remain unavailable pending the explicit policy questions.
