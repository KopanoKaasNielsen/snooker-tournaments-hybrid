# Financial integrity foundation

Baseline: a588814, feature/financial-integrity. The proposal was recorded before storage changes;
the user subsequently approved development implementation with **BWP**, scale 2 (100 thebe per
pula), integer minor-unit storage, Decimal arithmetic and no historical adoption/API activation.
This approval does not assign a currency to any historical balance, ledger, fee or contribution.

## Scope and authoritative data

`financial_wallets` and `financial_ledger_entries` form a new, separate BWP subledger. Migration
`g20261120fin` follows `f20261120auth` and creates these initially empty tables and three
ledger-integrity triggers only. Existing columns and rows are untouched. Existing wallet HTTP
reads retain their legacy contract and unknown currency; no UI or API silently switches sources.
No deposit, withdrawal, fee-collection or payout HTTP operation is enabled. Authentication,
player ownership, organiser assignments and administrator permissions are unchanged.

New wallets are opened explicitly for an existing player only when the legacy balance is zero
and there are no legacy ledger rows. Net-zero history still requires separate adoption review.
Only one exact wallet may exist per player. No account or initial credit is created by migration,
seeding, registration, import or startup. BWP must be explicitly supplied on every new operation;
other/absent currency identifiers are rejected. A zero legacy balance is only an empty-state
precondition, not evidence that existing money was denominated in BWP.

## Money policy

New posting boundaries require a finite `Decimal`; float, bool, string and integer coercions
are rejected. Inputs must be positive, exactly representable in thebe and no greater than
90,000,000,000,000.00 pula (9,000,000,000,000,000 minor units). Trailing zero precision such as
Decimal('0.1000') is accepted because it is exactly ten thebe; Decimal('0.001') is rejected.
NaN, infinities, zero, negative amounts, overflow and non-BWP identifiers are rejected.

Money arithmetic uses isolated Decimal contexts; application-wide context changes cannot
alter posting precision or policy. Exact integer SQL arithmetic operates on stored minor units.
SQLite NUMERIC affinity is deliberately avoided because it can store binary REAL values.
Decimal-to-integer conversion is exact and never rounds an accepted posting. `round_calculation`
is a separate, explicit `authorised=True` opt-in helper using ROUND_HALF_EVEN. No posting,
entry-fee collection or existing prize calculation invokes it. Approval for a specific future
calculation still belongs to that business operation; the helper is not an HTTP permission gate.

## Storage and constraints

`financial_wallets`: UUID id, unique player FK, currency CHECK BWP, bounded nonnegative integer
balance_minor, bounded integer sequence, UTC creation time. Sequence zero requires balance zero.
The wallet/currency pair is uniquely constrained for composite ledger references.

`financial_ledger_entries`: receipt UUID, globally unique canonical UUID4 idempotency key,
wallet/currency composite FK, kind (deposit/withdrawal/fee/prize), positive bounded integer
amount_minor, nonnegative bounded before/after balances, positive bounded sequence and UTC time.
CHECK constraints enforce SQLite integer storage classes, BWP, UUID4 key shape, allowed kinds,
ranges and exact per-entry credit/debit arithmetic. Unique wallet/sequence prevents duplicate
positions. Foreign keys prevent orphans; there are no delete cascades that silently erase money.

Three SQLite triggers reject any ledger UPDATE/DELETE and reject inserts that do not match the
wallet's updated sequence/balance or the preceding ledger balance (first entry starts at zero).
The service verifies those trigger definitions inside every transaction and fails closed if they
are missing or changed. The same trigger definitions are attached to metadata-created test schemas; migration tests
compare SQLite's installed SQL to those definitions and exercise the migrated protections.
The additive revision contains its own SQL, independent of future application helper changes.
Downgrade refuses any financial account/entry rows, including zero-balance accounts.

Constraints protect numeric integrity; privileged raw wallet updates can still create a bounded
but unreconciled balance. Reconciliation detects this, and the next posting's chain trigger
refuses it. This is not a cryptographically tamper-evident ledger or protection against a database
administrator dropping triggers, disabling constraints or editing backups.

## Transactional posting and idempotency

`FinancialWalletService(engine)` is internal and SQLite-only. Every call owns a fresh session;
it cannot flush or commit the caller's unrelated session. Writes explicitly start `BEGIN IMMEDIATE`
**before any reads**, including retry lookup. This acquires SQLite's writer reservation before
checking state and avoids a stale deferred read snapshot. A conditional UPDATE atomically changes
balance and sequence only when the result remains in range and nonnegative. One ledger receipt
is flushed and committed in the same unit. Insert, constraint, uniqueness or commit failure rolls
back both balance and receipt; all sessions close. Results are immutable scalar dataclasses,
not ORM objects that need a post-commit query.

Every posting requires a caller-retained canonical UUID4 key. Exact retries return the original
receipt, including its historical after-balance, rather than recalculating a result. Reuse with a
different wallet, amount, kind or currency is rejected (unsupported currency is rejected before
lookup). Global key uniqueness is also enforced by the database. Concurrent identical keys create
one receipt; concurrent conflicting payloads produce one success and one conflict. Future HTTP
integration must authenticate/authorise ownership **before** exposing retry receipts and must
retain the same key across transport retries. UUIDs are retry identities, not access credentials.

There are no automatic write retries. The connection's bounded SQLite busy timeout applies
(default five seconds with the existing engine configuration). A busy/locked failure produces
`FinancialBusy`; retry the complete operation with the same key after contention clears. No
partial balance or reserved key survives that failure. Protected repository snooker.db writes
are refused before connection acquisition, including file-URI and symlink-resolved paths.

## Legacy concurrent-withdrawal repair

The old internal wallet service remains a legacy storage adapter for existing callers/tests,
not the BWP authority. It now obtains SQLite's writer reservation and refreshes cached ORM state
before checking funds. It calculates in Decimal from the legacy numeric representation, retains
Float storage and unknown units/currency, and explicitly rolls back failures. Its existing
commit-owning interface is preserved for compatibility; it still commits caller work and has no
idempotency guarantee. Exact-wallet players are refused by legacy wallet writes to avoid two
wallet services mutating the same player's money. No old row is batch-converted or rounded.
Legacy float arguments remain accepted only by this compatibility adapter, never by new BWP
postings. Legacy Float storage still cannot guarantee exact historical monetary representation.

The prior defect (two cached balances of 100 both withdrawing 80) is covered both sequentially
and using independent simultaneous connections: one debit succeeds, the other is refused;
stored balance and ledger both end at 20. Existing prize distribution is byte-for-byte unchanged.
It bypasses the legacy wallet adapter and still has documented financial risks. If it introduces
legacy activity for an exact-wallet player, new postings refuse further work and reconciliation
reports `legacy_activity_requires_review`; no automatic mirroring/repair is attempted.

## Reconciliation and commands

`service.reconcile()` runs within an explicit, consistent read transaction. It compares every
wallet's balance to signed ledger totals, checks before/after continuity, sequence/count and
currency/arithmetic, and reports legacy activity. It never rounds away discrepancies or repairs
records. The standalone CLI opens the supplied file via `mode=ro`, sets `query_only=ON`, adds
integrity/FK checks, and fails without creating a missing file:

```bash
python -m scripts.reconcile_financial_wallets --database /tmp/approved-dev.db
python -m scripts.audit_legacy_finances --database snooker.db
```

The first covers new BWP accounts only, with exit 0 consistent, 1 findings, 2 inspection failure.
An empty exact-money ledger is not proof that historical funds are reconciled. The second
reports historical unknown-currency values using Decimal string diagnostics without conversion.
No diagnostic verifies external deposits, payment-provider settlement or a double-entry general
ledger. Receipts are subledger records; development credits are not evidence of received funds.

## Deterministic concurrency evidence

Tests hold writer one at its UPDATE after BEGIN IMMEDIATE, observe writer two attempting BEGIN
on a different physical SQLite connection, then release writer one using threading Events.
No sleeps determine success/order. Coverage includes competing withdrawals, independent credits,
identical retry keys and conflicting retry payloads. Legacy tests cache the old balance in both
connections before the fresh locked read. Failure tests inject ledger insertion and commit
errors and assert no partial balance, sequence or key remains. Reconciliation is asserted after
successful races. All files are disposable pytest databases, never the repository database.

## PostgreSQL limitation

The new service and revision explicitly refuse PostgreSQL. SQLite-specific typeof/GLOB CHECKs,
trigger syntax and BEGIN IMMEDIATE are not portable. A PostgreSQL implementation needs a
reviewed additive schema/trigger translation, bigint constraints, row-level SELECT FOR UPDATE
(or a proven conditional UPDATE strategy), safe unique-key contention handling and transaction
retry policy for serialization/deadlock failures. Same-key requests must re-read after locking;
any retry must encompass the entire unit and preserve the key. Independent-wallet PostgreSQL
writes should not be serialised by a database-wide SQLite-style lock. The legacy adapter has a
row-lock branch, but PostgreSQL behaviour was not tested and is not a support claim.

## Historical adoption remains unapproved

1. Confirm currency and original unit interpretation independently for every relevant source.
2. Stop writers, verify backups and rehearse on a disposable consistent copy.
3. Reconcile all balances/ledger amounts, fees/contributions, unknown types, missing entries,
   non-finite/negative values and precision exceptions without inventing money.
4. Produce a deterministic manifest of source IDs/values, proposed exact units, provenance,
   rounding deltas and checksums. Obtain separate approval for that concrete manifest/exceptions.
5. Import idempotently using durable source-record mapping only after approval; verify all totals,
   cut over one authoritative source, retain historical records, and rehearse restore/rollback.
6. Financial API activation, external payment controls, fee atomicity/refunds and durable prize
   distributions require later explicit approval. No role or environment flag bypasses this gate.

## Technical references

- [SQLite storage classes and affinity](https://www.sqlite.org/datatype3.html)
- [Python Decimal](https://docs.python.org/3.12/library/decimal.html)
- [SQLAlchemy transaction scope](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- [SQLite isolation and BEGIN IMMEDIATE](https://www.sqlite.org/isolation.html)
