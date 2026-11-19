# Database architecture

## Configuration and lifecycle

`app/database.py` is the single runtime configuration source. `get_database_url()` reads
`DATABASE_URL` from the process environment, falling back to `sqlite:///./snooker.db`.
Relative SQLite paths resolve from the working directory. Environment files are not implicitly
loaded by this module or Alembic; export the variable explicitly. URLs are never logged by our
configuration code. The old, unused `app/core/config.py` settings object does not configure
the engine and is not an authentication implementation.

`make_engine()` creates a lazy SQLAlchemy engine. Imports of database, models, application,
seed helpers and development CLI neither connect nor create tables/files nor insert records.
Each SQLite application connection enables `PRAGMA foreign_keys=ON`. No connection pooling,
journal-mode or busy-timeout tuning has been introduced. Production schema management is
exclusively an explicit Alembic operation; startup does not migrate or seed.

`SessionLocal` creates request sessions. `get_db()` is shared by `app.database` and the
compatibility import in `app.dependencies`; failures roll back and all exits close the session.
Services retain ownership of their existing commits. Closing a session rolls back any remaining
uncommitted work; it does not undo earlier service commits. FastAPI lifespan disposes the engine
on shutdown without touching the schema on startup.

## Tables and relationships

| Table | Important columns | Relationships and integrity |
|---|---|---|
| players | id, unique name, rating, elo, FLOAT balance, created_at | Registrations, results and ledger rows; ORM delete-orphan cascades |
| tournaments | id, unique name, date, type, status, best_of, race_to, entry_fee, created_at | Registrations, results, matches; ORM delete-orphan cascades |
| matches | tournament_id, nullable player1_id/player2_id/winner_id, scores, scheduled_at, created_at, completed_at | FKs to tournament and players; nullable second player supports byes |
| tournament_registrations | tournament_id, player_id, paid, waived, contribution | FKs; unique tournament/player pair |
| tournament_results | tournament_id, player_id, position, created_at | FKs; unique tournament/position |
| wallet_transactions | player_id, type, FLOAT amount, timestamp | Player FK; type is deposit/withdrawal/prize/fee |

Database FK constraints protect raw SQL as well as ORM writes on application connections.
ORM cascades are not SQL `ON DELETE CASCADE`: raw parent deletion with referenced children is
rejected. Some domain-level invariants remain service checks rather than database constraints.

Timestamps retain the existing naive-UTC SQLite and API representation. `app/time.py` uses
`datetime.now(timezone.utc).replace(tzinfo=None)` to preserve that representation without
`datetime.utcnow()` deprecations. No stored timestamp was rewritten or assigned a new zone.
The historical uppercase tournament type labels differ from current lowercase enum names.
No populated legacy enum values are automatically converted.

## Migration history

```text
<base>
  -> dd093dfa2ebf  original five-table schema
  -> d27f9a18494f  scheduled_at/completed_at
  -> e20261119db01 corrective schema alignment (single head)
```

The two original revision files are unchanged. There are no missing referenced revision IDs
and no multiple heads. The history nevertheless omitted wallet_transactions, player elo/balance,
tournament created_at, several NOT NULL constraints, both composite unique constraints, and
the current tournament enum representation. The new corrective revision supplies these for
fresh databases. It refuses populated historical schemas instead of inventing omitted financial
values, dates or enum conversions. Populated historic data needs a reviewed data migration.

SQLite alterations use Alembic batch operations. Alembic has a dedicated connection with FK
checks disabled so batch table recreation can operate; `foreign_key_check` runs before commit.
An explicit SQLite `BEGIN` makes DDL/version updates roll back together under sqlite3 legacy
transaction mode. Exceptions roll back and dispose the migration engine. Application engines
keep FK checks enabled. Non-SQLite database URLs are accepted by shared engine configuration,
but the historical enum path and online migration behavior were verified only on SQLite;
do not claim PostgreSQL support without a separate migration test run.

Offline SQL generation of the full corrective SQLite migration is not supported, because batch
reflection and data preflight require an online connection. Empty online downgrade/re-upgrade
is tested. The corrective downgrade rejects populated application tables and populated ledgers
rather than dropping balances or other application data.

## Existing database audit

The source was opened via SQLite URI `mode=ro` and queried with `query_only=ON`.
Observed counts: 18 players, 3 tournaments, 1 match, 4 registrations, 0 results, 16 wallet rows.
`integrity_check` returned `ok`; `foreign_key_check` returned no rows. No negative balances,
non-positive wallet amounts, duplicate registration pairs or duplicate tournament positions
were found. There is no `alembic_version` table. The six-table schema matches current ORM
metadata (also verified on a consistent disposable SQLite backup).

An unstamped schema is not an empty database. Running the base migration over it fails on
existing tables. The repository database has deliberately not been stamped or migrated.
The migration guide describes review and disposable-copy verification before any later adoption.

## Financial and domain risks requiring separate approval

- Balances and ledger amounts remain FLOAT. Binary rounding and concurrent read/modify/write
  updates can lose precision or updates. A Decimal/minor-unit conversion needs an explicit
  currency, rounding and reconciliation policy; no type conversion or calculation changed here.
- Positive amounts are validated by wallet services/API schemas, and normal withdrawals check
  sufficient funds. There are no DB CHECK constraints preventing negative balances, invalid
  transaction types/amounts or non-finite values written through other paths. Finite-number
  validation needs a separately reviewed API/business rule change.
- Tournament registration currently commits the fee withdrawal before checking whether the
  player is already registered. A duplicate request can charge again despite rejection; request
  rollback cannot undo the earlier committed withdrawal. Race conditions also need an atomic
  transaction/idempotency design. The unique pair now protects structural duplicates, not fees.
- `distribute_prizes()` uses transient `final_standings`, directly changes balances, commits,
  and has no durable distribution marker or ledger entries. Repeating it can distribute twice.
  No prize formula, split or payout behavior was changed in this task.
- Results constrain unique positions, but not unique player per tournament; application checks
  do not fully enforce winner membership/score/bye semantics in every service path.
- Historic orphan records would now be rejected by migration FK validation; no automated
  deletion or repair is provided. Current data has none.
- Backend mutation endpoints remain unauthenticated and CORS remains permissive. Access
  control belongs to Task 03; schema stabilization does not make public financial access safe.

## Tests and tooling

Fixtures create a unique temporary directory before application imports, override all request
sessions, explicitly create/drop only the isolated test schema, and enable FK enforcement.
Legacy tests importing `tests.conftest` share the same module/engine. The seed test now calls
`seed_data(TestingSessionLocal)` explicitly; library seeding requires a supplied session factory.
Seed helper errors roll back and sessions close. Sequential re-seeding preserves named records,
including existing balances/ratings, and does not insert duplicates.

New tests cover configuration, lazy imports, isolation, session cleanup/rollback, FKs, unique
registrations, seed rollback/idempotency/guards, actual migrations and metadata comparison,
empty migration roundtrips, populated migration refusal, invalid adoption rollback, and failed
DDL rollback. A separate verifier operates only on temporary databases and optionally on a
read-only backup of an existing database.

The same pinned Black 24.4.2 wheel was reinstalled to repair a missing mypyc compiled module.
No formatter upgrade was required. Active Python files are formatted; historical revisions and
`migrations_backup` are explicitly excluded to preserve their bytes. `requirements.txt` only
removes a duplicate identical pytest-asyncio entry. Frontend dependencies are unchanged.

References: [SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
and [Alembic batch migrations](https://alembic.sqlalchemy.org/en/latest/batch.html).
