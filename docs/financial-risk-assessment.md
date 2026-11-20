# Financial risk assessment

Task 04A audit: baseline a588814, feature/financial-integrity. Development implementation of
a new BWP subledger is approved. Historical currency assignment/data conversion, prize-rule
changes and financial API activation remain unapproved. The inventory below records the audit baseline.

## Monetary inventory

| Location | Existing representation/operation | Risk |
|---|---|---|
| app/models.py: Player.balance | SQL Float; default 0.0 | Binary approximation, unbounded/non-finite values, no nonnegative DB check |
| app/models.py: WalletTransaction.amount | SQL Float | Positive/non-finite/type constraints missing; no durable operation key |
| app/models.py: Tournament.entry_fee | Integer, no currency/unit metadata | Whole-major-unit versus minor-unit ambiguity; negative values possible via raw writes |
| app/models.py: TournamentRegistration.contribution | Integer, default zero | Same unit ambiguity; no nonnegative check or reconciliation to fee ledger |
| app/services/wallet.py: deposit/withdraw | float arguments and ORM balance +=/-= amount | Drift, float/bool/non-finite inputs, stale read/lost update and concurrent overdraft risks |
| app/services/wallet.py: commit | Balance change and ledger insert committed together normally | Commit failures lack explicit rollback in this service; service commits unrelated caller work; no idempotency |
| app/services/tournaments.py: distribute_prizes | fee × registrations × float share, round(..., 2), balance += prize | Binary tie behaviour, lost updates, repeated payout, no ledger row; implicit currency/scale |
| app/schemas.py: WalletAmount/PlayerBalanceOut/PlayerOut/WalletTransactionOut | JSON float | Cannot communicate exact decimal intent; finite-money guarantees absent; writes remain disabled |
| app/routes/players.py | legacy numeric reads | Private reads remain protected; legacy numeric API shape must not silently become a new currency |
| app/routes/tournaments.py | entry_fee != 0 blocks registration | Required gate remains; no fee debit route is enabled |
| app/init_db.py and auth registration | legacy player zero defaults | Demo/new-profile zero is not evidence that historical balances can be migrated or currency inferred |
| tests/test_services_tournaments.py | expected float round of 60/30/10 shares | Regression contract must remain unchanged pending approved prize policy |

Elo calculations also use float arithmetic and round(), but they calculate ratings, not money;
they are outside this financial change. Frontend wallet reads display existing numbers without
currency; no financial write controls exist and none will be introduced.

## Current read-only database observations

Original source opened using SQLite URI mode=ro and query_only=ON. integrity_check=ok and
foreign_key_check returned no violations. Counts: 18 players, 16 wallet transactions, 3
tournaments, 4 registrations. No negative balances, nonpositive recorded ledger amounts,
negative fees or negative contributions were found. Decimal(str(value)) signed ledger totals
matched every stored balance. No records were changed. This comparison cannot recover the
original decimal intent from binary floats, establish a currency, prove payment settlement or
prove the absence of past unrecorded/cancelled movements.

## Required controls and limits

A new exact-money foundation needs currency-tagged integer minor-unit storage, Decimal input
validation/arithmetic, bounded nonnegative balances and positive amounts, database integrity
constraints, atomic balance+ledger posting, mandatory unique idempotency keys and reconciliation.
Use conditional updates/transactions rather than read-modify-write; tests must exercise separate
connections and concurrent debits/replays. No direct monetary write should be reachable by HTTP.

Existing internal float services and prize distribution remain legacy risks until a reviewed
conversion/cutover. A new empty foundation must not be portrayed as fixing historical records
or as the authoritative source for existing balances. Neither a matched legacy ledger nor new
wallet reconciliation is a substitute for a balanced general ledger, verified external funding,
refund/chargeback policy, payment-provider reconciliation or regulatory controls.

## Prize behaviour requiring separate approval

The existing pool is entry_fee × registration count, regardless of paid/waived/contribution.
Final standings are transient Python attributes; missing players are skipped; short split lists
use zero shares for later winners. Shares are not constrained to sum to one; independently
rounded shares may leave or exceed the pool; repeated invocation pays again and does not
record ledger entries or a durable distribution marker. These are documented risks, not changes
approved by Task 04A. Preserve the function and its regression test byte-for-byte.

## Conversion review gate

The migration/rounding proposal is in financial-integrity-architecture.md. No existing money is
automatically copied, rounded, re-labelled or repaired. A future conversion requires confirmed
currency/units, a reconciled source manifest, exception review, backups, idempotent provenance,
controlled authoritative-source cutover and an approved rollback plan. Financial API enablement
requires a later, explicit decision after the complete controls have been verified.

## Reproduced stale-session withdrawal defect

A deterministic two-session interleaving on a disposable database opened a player with a
recorded deposit of 100. Both independent ORM sessions cached balance 100. Each then withdrew
80 using the existing service. Both calls succeeded; final stored balance was 20 while signed
ledger total was -60, a difference of 80. This confirms the lost-update/overspend risk; it is
not merely a hypothetical floating-point concern. The experiment did not use the original
database and did not enable an API write. A future conditional balance update must make only
one such debit succeed. The legacy service now refreshes balances under a SQLite writer reservation; sequential stale-session
and simultaneous independent-connection regressions prove only one withdrawal succeeds. No
historical record is changed by this code repair.

## Implemented controls and remaining exposure

The approved new BWP tables enforce exact bounded integer units, valid currency/kind, positive
amounts, nonnegative balances, zero opening balance, ledger arithmetic/sequence, UUID4 key
uniqueness and foreign keys. Ledger UPDATE/DELETE is forbidden; chain inserts must match the
updated wallet. The new service verifies trigger definitions, takes BEGIN IMMEDIATE before reads,
uses conditional updates, and atomically commits balance/sequence/receipt in an owned session.
Reconciliation checks signed totals, continuity and legacy activity without repair.

The legacy wallet adapter's stale-session/overdraw defect is repaired using a locked fresh read
and Decimal arithmetic; exceptions explicitly roll back. It retains Float storage and existing
commit-owning signatures and has no idempotency guarantee. Writes into an exact-wallet player
are refused. Historical precision, unknown currency, legacy fee/contribution checks and prize
distribution risks remain. This is development groundwork, not a production financial activation.

Privileged SQL can still change a bounded wallet balance directly; reconciliation catches a
ledger discrepancy and chain protection rejects further posting. Database administrators can
alter/drop protections, so external audit/backup/security controls remain necessary. SQLite has
one writer at a time; contention returns a bounded retryable error, not an automatic new-key retry.
PostgreSQL is explicitly unsupported by the new migration/service pending row-lock/constraint/
trigger and transaction-retry verification. The architecture document describes those differences.
