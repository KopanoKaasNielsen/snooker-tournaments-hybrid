# Task 02 — Database and migration stabilization report

Date: 2026-11-19. Branch: `feature/database-stabilization`.
Starting commit: `5f330da` (frontend stabilization). Initial worktree was clean.

## Outcome

Database imports and startup no longer create schemas or demo data. Shared configuration,
Alembic metadata, SQLite FK enforcement, request rollback/cleanup, explicit guarded development
setup and repeatable demo seeding are implemented. Fresh migrations and ORM comparison pass.
The original database is unchanged and remains unversioned; only an explicitly announced,
schema-validated disposable copy was stamped during compatibility verification.

## Initial findings

Audited database configuration, all models and schemas, request dependencies, startup, CRUD,
all services/routes, both active revisions, backup migration directory, fixtures/tests,
requirements, README, ignore rules and CI.

- Alembic `current` failed with `ImportError: cannot import name 'DATABASE_URL'`.
  `history` and `heads` could read the graph and showed one head `d27f9a18494f`.
- `database.py`, `models.py` and FastAPI import/startup created tables; model import seeded data.
  Merely inspecting migrations could therefore mutate the configured database.
- Migration history lacked wallet_transactions, player balance/elo, tournament created_at,
  current enum length/names, multiple NOT NULL changes and composite unique constraints.
- The actual `snooker.db` has six ORM-shaped tables with no `alembic_version` table.
- SQLite FK enforcement was not enabled. Session dependencies closed without explicit rollback.
- Demo data was implicit, and the seed test depended on that side effect.
- Black 24.4.2 could not import its compiled `30fcd23745efe32ce681__mypyc` module.
- Requirements listed the same pytest-asyncio pin twice; no dependency upgrades were needed.
- Existing frontend remained stable; no frontend implementation/dependency changes were made.

## Read-only data audit

Original opened using `file:snooker.db?mode=ro` and `PRAGMA query_only=ON`.
No application imports were used to inspect the original.

| Table | Rows |
|---|---:|
| players | 18 |
| tournaments | 3 |
| matches | 1 |
| tournament_registrations | 4 |
| tournament_results | 0 |
| wallet_transactions | 16 |

`integrity_check`: `ok`. `foreign_key_check`: no violations. No negative balances,
non-positive/non-finite ledger amounts, non-finite balances, duplicate registration pairs,
duplicate result positions or duplicate result players were observed. Tournament type observed:
`knockout`; ledger types: `deposit`, `withdrawal`. No individual application records or secret
configuration values are included in this report.

## Architecture decisions

1. `get_database_url()` is the shared configuration source for SQLAlchemy and Alembic.
   Environment-provided `DATABASE_URL` wins over the default relative SQLite file. No implicit
   `.env` loading or credential logging. A programmatic Alembic URL attribute isolates tests.
2. Lazy engines and pure model registration: no schema or seed I/O on import. FastAPI lifespan
   only disposes the engine on shutdown. Production schemas are managed by explicit migrations.
3. Each application SQLite connection enables FKs. Alembic uses a separate FK-disabled
   connection for SQLite batch recreation, validates references before committing and rolls
   back on errors. An explicit BEGIN makes SQLite DDL/version changes transactional.
4. Request sessions explicitly roll back failures and always close. Service commit ownership
   remains unchanged; previously committed financial writes are not magically reversible.
5. Development CLI requires `APP_ENV=development`, an explicit SQLite URL and refuses the
   resolved repository `snooker.db`. Init runs migrations without demo data. Seeding additionally
   requires `--confirm-demo` and migration head; helper callers must supply a session factory.
6. The new corrective revision operates on empty historical tables and refuses populated
   legacy schemas requiring inferred financial/date/enum values. Its downgrade refuses populated
   application data. No historical revision was edited or automatically stamped.
7. Preserve naive UTC storage/API semantics with an aware UTC clock converted to naive UTC;
   replace deprecated Query.get with Session.get and Pydantic class Config with ConfigDict.
   No financial formulas, column precision, historical records or transaction rules changed.
8. Repair pinned Black in place, format active Python and exclude immutable historical revision
   files/backup migration directory. Keep existing frontend CI and add migration verification.

## Migration revision graph

```text
<base>
  -> dd093dfa2ebf
  -> d27f9a18494f
  -> e20261119db01 (head)
```

No missing referenced revisions or multiple heads. Backup directory contains no alternate
revision chain. The omissions were schema evolution missing from history, now represented
by the additive corrective revision.

Historical revision byte preservation, verified against HEAD:

| Revision file | SHA-256 |
|---|---|
| dd093dfa2ebf_fresh_schema_with_created_at.py | f680eb40480cedaeb86769b3ea62213d086a6b80970d8c5743df1f5375df5924 |
| d27f9a18494f_add_scheduled_at_to_matches.py | c479aa193fefe6d7649ae2e70e52904b4b065ea7eecdb58a8f655d40eec92bc3 |

## Files created

- `app/db_cli.py`: guarded explicit development init/demo commands and programmatic migration config.
- `app/time.py`: non-deprecated naive-UTC defaults preserving existing representation.
- `migrations/versions/e20261119db01_align_schema.py`: additive schema correction with data safeguards.
- `scripts/verify_migrations.py`: temporary fresh migration/roundtrip verifier and optional
  read-only-source backup compatibility verification.
- `tests/test_database.py`, `tests/test_migrations.py`: lifecycle, integrity, seeding and real migration tests.
- `pyproject.toml`: Black exclusion of preserved historical files.
- `docs/database-architecture.md`, `docs/database-migration-guide.md`, this report.

## Files modified

- `app/database.py`, `app/dependencies.py`: shared URL, lazy engine, FKs and session cleanup.
- `app/main.py`, `app/models.py`: remove implicit table creation/seeding; lifecycle and UTC defaults.
- `app/init_db.py`: explicit factory, rollback and guarded CLI delegation.
- `app/schemas.py`: ConfigDict with unchanged field contracts.
- `app/crud.py`, `app/routes/players.py`, `app/services/{matches,tournaments,wallet}.py`:
  deprecated API replacements plus formatting; no financial business rule changes.
- `app/core/config.py`, `app/routes/{matches,tournaments}.py`, `app/services/elo.py`:
  Black formatting only; unused old settings remain unused.
- `migrations/env.py`, `alembic.ini`: shared config/metadata, portable script paths, SQLite batch
  and atomic rollback handling; no demo imports.
- `tests/conftest.py`, `tests/test_seed.py`: FK-enabled isolated fixtures and explicit test seeding.
- Existing API/match/tournament tests: replace deprecated Query.get without weakening assertions;
  active tests also formatted by Black (`test_players.py`, `test_tournament_flow.py` included).
- `.github/workflows/ci.yml`: migration verifier added to both Python matrix runs; pinned Black
  check used; frontend job preserved verbatim.
- `requirements.txt`: duplicate identical pytest-asyncio line removed, all versions preserved.
- `.gitignore`: allow this report. `README.md`: migration-driven setup and documentation links.

The same Black wheel was reinstalled with `--force-reinstall --no-deps black==24.4.2`.
Tracked virtualenv wrapper/RECORD artifacts touched by installation were restored byte-for-byte
to their original content; the worktree contains no virtualenv changes. The compiled module
repair remains local. Removing the pre-existing tracked virtualenv is deferred, not performed.

## Actual migration verification

`venv/bin/python -m scripts.verify_migrations --existing-copy-from snooker.db` ran real
Alembic commands in unique temporary directories:

| Operation | Result |
|---|---|
| history | Three revisions, complete linear graph |
| heads | Single e20261119db01 head |
| current before upgrade | Base/unversioned, as expected |
| upgrade head on fresh file | All three revisions applied successfully |
| current after upgrade | e20261119db01 (head) |
| alembic check | No new upgrade operations detected |
| compare_metadata | Empty difference list against ORM |
| downgrade base on empty disposable schema | Passed |
| re-upgrade head / check | Passed / no new operations |
| direct upgrade on unversioned existing-data copy | Refused: players table exists (expected); transaction rolled back |
| explicitly announced stamp of schema-validated disposable copy | Passed; original not stamped |
| current / upgrade head / check after copy adoption | Passed; all application rows/values unchanged |
| populated historical upgrade | Refused by tested preflight; no inferred balances/dates |
| populated head downgrade | Refused; existing balance retained |
| deliberately failed DDL revision | New table and revision changes rolled back |
| stamp attempt with orphan ledger row | Refused; revision update rolled back |
| inconsistent unversioned schema copy | Refused before stamping |

The verifier never changes its source; target must be a new disposable path. Existing-copy
adoption is a compatibility experiment, not operational migration approval. The original
remains unversioned. Offline SQL generation and PostgreSQL migration compatibility are
not claimed; SQLite online migration operations are the verified scope.

## Actual tests and command results

| Command | Result |
|---|---|
| Baseline `venv/bin/python -m pytest -q` | 17 passed, 139 warnings, 14.00 s |
| Baseline `python -m alembic current` with isolated URL | Failed: missing DATABASE_URL import |
| Baseline `python -m black --version` | Failed: missing compiled mypyc module |
| `python -m pip install --force-reinstall --no-deps black==24.4.2` | Passed; no version change |
| `venv/bin/python -m black --check .` | Passed; 33 active files unchanged by final check |
| `venv/bin/python -m pytest -q -W error` | 42 passed, 0 warnings/failures, 23.93 s |
| `venv/bin/python -m pytest -ra` | Final normal warning-visible run: 42 passed, 0 warnings/failures |
| `npm run typecheck` | Passed |
| `npm run test:ci` | 5 suites passed; 20 tests passed, 0 failed |
| `npm run build` | Passed; 100 modules, dist/index.html, CSS and JS assets |
| Migration verifier and existing-copy check | Passed, with expected refusals listed above |
| `git diff --check` | Passed |
| `git status --short` | Reviewed intended source/tests/config/docs changes; no database/virtualenv/frontend changes |
| `sha256sum snooker.db` | Matches initial checksum |

Backend coverage increased from 17 to 42 tests (+25). Existing regression tests retain their
assertions; the seed test now performs the explicit setup its assertion requires. New tests
cover URL configuration, engine laziness, real startup/import non-mutation of absent/existing
temporary files, isolation, rollback/close, FK and unique enforcement, failed seed rollback,
repeatable seeding/value preservation, production/original-database seed guards, revision graph,
real fresh migrations, ORM parity, empty roundtrip, migration/adoption rollback and copy safety.
Frontend remains 20 tests, using mocks as before. GitHub-hosted CI itself has not been run;
workflow syntax/job preservation and the underlying local verification commands were checked.

## Warning counts

| Baseline cause | Before | After |
|---|---:|---:|
| datetime.utcnow defaults/direct calls | 86 | 0 |
| SQLAlchemy Query.get calls | 44 | 0 |
| Pydantic class Config | 7 | 0 |
| FastAPI on_event startup | 2 | 0 |
| Total suite warnings | 139 | 0 |

No warning suppression/filter was added. The final suite also passes with `-W error`.
Alembic's informational message “Will assume non-transactional DDL” describes dialect defaults;
the environment explicitly starts a SQLite transaction, with rollback verified by a failing
DDL revision test. It is not a pytest warning.

## Database preservation evidence

Initial and final original SHA-256:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa
```

Original read-only audit and disposable backup comparisons succeeded. No original schema,
version stamp, demo data, balances or records were changed. All tests/experiments use isolated
temporary files. No live financial operations, authentication, commits, pushes, merges or
historical migration rewrites were performed. No `.env` secrets were read or exposed.

## Outstanding blockers and risks

- Operational adoption of the unversioned original still requires reviewed backup/approval.
  Blind upgrade or stamping is not a repair. Populated historical schemas with missing fields
  need a specific data migration; automatic inference is intentionally blocked.
- Financial risks remain unchanged: FLOAT precision, non-finite/raw invalid writes, no DB
  negative-balance/positive-amount checks, concurrent updates, fee withdrawal committed before
  duplicate-registration rejection, and non-idempotent prize distribution without a ledger
  marker. Request rollback cannot undo a previous service commit. These are documented in
  detail in the architecture guide and require a separately approved financial integrity task.
- Existing API mutations are unauthenticated; authentication/authorisation remains Task 03.
- Currency/rounding/time-zone migration policies remain undefined; no silent conversion made.
- SQLite is verified; other database dialects and offline batch SQL need additional work.
- Existing tracked virtualenv and unused old config module remain repository maintenance debt.
- The Task 01 React Router advisories remain outside this database task; frontend dependencies
  were not changed. Actual CI cloud runs and mobile/browser checks are not claimed.

## Recommendations for Task 03 — Authentication and authorisation

Define the account-versus-player relationship, role/permission matrix and ownership rules before
adding routes/models. Use a new additive migration; never equate a public player ID with a login.
Configure secrets externally and replace/retire the unused legacy settings rather than activating
its placeholder secret. Apply access control to all financial/administrative operations and
verify unauthenticated/forbidden paths with isolated databases. Keep seed users separate from
production accounts. Coordinate an explicitly approved transaction/idempotency and money-precision
remediation task; authentication alone will not fix duplicate fees or duplicate prize payouts.
