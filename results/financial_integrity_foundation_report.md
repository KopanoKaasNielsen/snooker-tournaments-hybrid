# Task 04A financial integrity foundation — implementation report

## Scope, approval and baseline

Branch feature/financial-integrity; baseline a588814. The proposal/risk assessment/read-only
legacy diagnostic were prepared before monetary storage changes. The user then explicitly
approved development implementation for BWP, scale 2 (100 thebe/pula), integer minor-unit
storage, Decimal arithmetic, rejection of sub-thebe postings and HALF_EVEN only for explicit
calculations. Historical currency assignment/adoption, prize-rule changes and financial HTTP
activation were not approved and were not performed.

Original backend baseline: 90 passing tests; preapproval diagnostic work increased this to
99 passing tests on both Python 3.11/3.12. Existing frontend baseline: 33 passing tests. All
existing assertions remain, apart from expected migration-head updates; no security control,
warning check or financial denial was weakened. No dependency upgrade or frontend source
change was required. Existing external Python environments were used, not the tracked venv.

## Initial findings and decisions

Legacy Player.balance/WalletTransaction.amount use Float; tournament fees/contributions have
unknown integer units and no currency. Wallet read/modify/write permitted lost updates;
prize distribution uses float shares/round(), directly updates balances and lacks durable
ledger/payout identity. The read-only source check found no current imbalance, but a disposable
stale-session experiment accepted two withdrawals of 80 from an opening 100, leaving stored
balance 20 and signed ledger -60. That defect required an actual repair, not merely new tables.

The new BWP foundation is separate from legacy data. It never copies, re-labels, rounds or
synchronises historical records. Opening an account requires an explicitly supplied BWP and a
pristine player with zero legacy balance and no legacy ledger history. Net-zero history still
requires approved adoption. Authentication registration does not automatically open wallets.
Existing wallet HTTP reads retain their legacy numeric/unknown-currency contract.

## Implementation

- `app/money.py`: strict finite Decimal boundary, explicit BWP, exact conversion to/from thebe,
  positive posting validation and 9,000,000,000,000,000 minor-unit bound. Floats, bools, strings,
  integers, non-finite/negative/zero/overflow/sub-thebe postings are rejected. Isolated contexts
  resist changes to the caller's Decimal precision/traps/rounding. Explicit authorised HALF_EVEN
  calculation helper is separate; neither posting nor existing prize code uses it.
- `FinancialWallet`: UUID, unique player FK, BWP, bounded integer balance/sequence, zero opening
  balance, creation time and composite wallet/currency unique identity.
- `FinancialLedgerEntry`: immutable receipt UUID, globally unique canonical UUID4 operation key,
  composite wallet/currency FK, valid signed kind, positive integer amount, before/after balances,
  sequence and UTC time. Checks enforce storage classes, bounds, BWP, key shape, arithmetic
  and unique wallet sequence. No ledger delete cascades exist.
- Three SQLite triggers reject ledger UPDATE/DELETE and enforce insertion continuity/matching
  updated wallet state. Service transactions verify their installed definitions and fail closed
  if missing/edited. Metadata test schemas install the same definitions; migration SQL is
  independently frozen in the new revision and compared/exercised in tests.
- `FinancialWalletService`: private fresh sessions; BEGIN IMMEDIATE before any reads; conditional
  nonnegative/bounded balance+sequence update and ledger insert committed together. Constraint,
  insertion or commit errors roll back both. Results are immutable dataclasses, with no fragile
  post-commit fetch. Caller session work cannot be flushed or committed by this service.
- Idempotency: exact repeated payload returns the original receipt and original after-balance;
  different wallet/amount/kind payload with the same key is rejected. Unsupported currencies
  are rejected before lookup. Database key uniqueness is independent of service checks.
- Busy/locked SQLite writes fail with FinancialBusy, no partial posting/key reservation. Retry
  the complete operation using the same key; no automatic new-key or partial-unit retry exists.
- The legacy wallet adapter now obtains a writer reservation and refreshes cached balances before
  checking funds, calculates with Decimal, and explicitly rolls back errors. Existing Float
  storage, unknown currency/scale and return/commit interface remain for compatibility. It
  refuses writes to exact-wallet players. This repairs the original stale-session withdrawal
  defect without bulk conversion or changes to prize calculations.
- New reconciliation reads a consistent snapshot, compares balance with signed ledger totals,
  checks chain/sequence/currency and reports legacy activity; no automatic repair. The standalone
  exact-money CLI uses mode=ro/query_only, adds integrity/FK checks and never creates a missing
  source. The earlier standalone legacy audit remains currency-agnostic and read-only.

## Migration details

```text
<base> -> dd093dfa2ebf -> d27f9a18494f -> e20261119db01
       -> f20261120auth -> g20261120fin (single head)
```

`migrations/versions/g20261120fin_add_exact_money.py` creates only financial_wallets,
financial_ledger_entries, their constraints/indexes and three integrity triggers. It performs
no backfill or old-table alteration. Populated financial downgrade is refused even for an empty
zero-balance wallet. Empty downgrade/re-upgrade is supported. SQLite-only guard explicitly
rejects an unverified PostgreSQL migration.

Both versions verify history/heads/current, fresh upgrade, alembic check, empty full roundtrip,
ORM consistency and installed trigger SQL. Tests populate pre-financial players, ledger rows,
fees, contributions and auth accounts, prove every old value survives upgrade, then prove empty
financial downgrade preserves that dataset. Populated financial rollback is refused. Existing
six-table original and supported pre-financial/auth copies are validated at their matching
baseline, then upgraded only in disposable backups; current schemas missing triggers are refused
before copy stamping. The source database is always opened read-only and never stamped.

## Concurrency and failure evidence

Tests use real independent SQLite connections and Events, not sleeps to choose ordering.
Writer one is held at its UPDATE after taking BEGIN IMMEDIATE; writer two's BEGIN attempt is
observed on a different physical connection, then writer one is released.

| Case | Required asserted outcome |
|---|---|
| BWP 100.00, simultaneous withdrawals 80.00/80.00 | One receipt, one InsufficientFunds; balance/ledger both 20.00; two total entries including initial credit |
| Concurrent identical key/payload credits | Same receipt ID/result; exactly one ledger entry |
| Concurrent same key/different amounts | One credit, one IdempotencyConflict; no second credit |
| Concurrent 0.10/0.20 credits | Both retained; exact balance 0.30 and two entries |
| Two legacy sessions each cache 100, then withdraw 80 | One succeeds, second refused; balance and signed legacy ledger both 20 |
| Independent simultaneous legacy cached withdrawals | Same result; both starting caches confirmed 100 and two physical connections confirmed |
| Locked writer | FinancialBusy, no partial unit; same key succeeds once after release |
| Ledger insert or commit failure | Balance/sequence/receipt/key all roll back; key can retry |
| Direct ledger UPDATE/DELETE or discontinuous append | Database rejects change; no partial wallet update survives transaction rollback |
| Bounded direct wallet tampering | Reconciliation flags mismatch; no repair; subsequent posting chain rejects the mismatch |
| Missing/edited integrity protections | Service refuses the unit; unsafe unversioned copy is not stamped |

These are subledger/atomicity controls, not evidence of external funds received, provider
settlement, double-entry accounting or an authorised prize payout. The test results below
confirm these assertions on both supported interpreters.

## Actual verification results

| Command/check | Actual result |
|---|---|
| Python 3.11.15 `python -m pytest -q -W error` | **192 passed**, 0 failed, 0 warnings; **355.41s** |
| Python 3.12.3 `python -m pytest -q -W error` | **192 passed**, 0 failed, 0 warnings; **291.26s** |
| `python -m scripts.verify_migrations --existing-copy-from snooker.db`, Python 3.11/3.12 | Both passed: fresh graph/current/upgrade/check, empty downgrade/re-upgrade, ORM/trigger verification and copy row preservation |
| `python -m black --check .`, both interpreters | Passed; **51 files unchanged** |
| `python -m pip check`, both development environments | Passed, no broken requirements |
| `python -W error -m scripts.verify_dependency_environment`, both versions | Passed; migrated startup, unchanged auth API snapshot and unauthenticated denials |
| Runtime-only Python 3.12 verification (`--runtime-only`), final source | Passed; no pytest/Black/HTTPX required by production imports/startup |
| `npm run typecheck` | Passed (Node 24.11.1 / npm 11.7.0) |
| `npm run test:ci` | **33 passed**, 5 suites; **8.381s** |
| `npm run build` | Passed; 104 modules; **2.96s**; dist/index.html plus JS 241.69 kB (81.00 kB gzip), CSS 1.44 kB |
| actionlint 1.7.7 | Passed, no diagnostics |
| Bandit 1.9.4 (`bandit -q -r app`), final source | Passed, no findings |
| pip-audit 2.10.1 of full resolved backend environment | Exit 0; **no known vulnerabilities found** |
| `npm audit --json` | Exit 1; **2 moderate package entries**, 0 high/critical; existing Router advisories remain |
| Runtime-only migrated CLI/service smoke | Passed; exact 100.00 credit/80.00 debit, idempotent retry, denied overdraft, balance/ledger both 20.00 and two entries |
| Read-only CLI exit paths | Exit 0 consistent; exit 1 detects deliberately tampered disposable balance without repair; exit 2 missing file without creating it |
| `python -m scripts.audit_legacy_finances --database snooker.db` | Exit 0, no findings, unknown currency retained, source unchanged |
| Original source/prize/history checksums | Unchanged; exact evidence below |
| `git diff --check` | Passed |
| `git status --short` | Only intended source/tests/docs/new migration/report modifications; no Git publication operations |

The final matrix contains all original 90 backend regressions, 9 earlier read-only diagnostic
cases, 33 monetary-policy cases, 57 financial service/constraint/concurrency cases and 3 new
migration cases: 192 total. Existing tournament/match/prize/authentication/role/ownership and
financial-denial assertions pass. New money tests and smoke commands use disposable databases.
Frontend tests mock transport; backend tests use actual SQLite/Decimal/Argon2/JWT components;
the runtime-only command is separate integration evidence. No successful financial HTTP mutation occurred; denial tests sent requests only to disposable test databases.

Security scans remain advisory in the unchanged CI workflow (continue-on-error); a green job
would not enforce them. Current local pip-audit has no known backend findings; no blanket
ignores were introduced. Existing Router advisories GHSA-wrjc-x8rr-h8h6 and
GHSA-337j-9hxr-rhxg remain; npm suggests a major Router upgrade. No unrelated upgrade was made.
Pip-audit's notice recommending hashed dependency artifacts remains a reproducibility limitation.
No hosted workflow run was claimed or triggered.

Intermediate results/failures are retained honestly:

- The first money/service/migration target run passed 92 tests.
- A later target run was 62 passed/1 failed: a new test used dict(CursorResult) rather than
  explicit result rows. Fixing that inspection with .all() preserved all trigger assertions;
  its focused rerun passed.
- A patch-generation command initially used system Python without SQLAlchemy and failed before
  editing files; it was rerun successfully with the verified external environment.
- I edited the trigger helper while the first full matrix was active. Cached old app modules
  combined with the new verifier caused three ImportErrors: 187 passed/3 failed on Python 3.12
  (280.52s) and 187 passed/3 failed on Python 3.11 (348.00s). Those are invalid final verification
  runs, not hidden successes. Both final suites were rerun against a stable source tree, with
  no further Python changes during their execution.
- Missing-trigger safeguards passed their focused two-test check before the final runs.

## Original database and history preservation

Before/after original snooker.db SHA-256:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa
```

Read-only diagnostics report integrity OK, no FK violations, 18 players, 16 legacy ledger rows,
3 tournaments, 4 registrations and no current findings. Currency remains unknown. No original
row, table, migration stamp or seed was changed. Original prize service and all four historical
migration files match their initial SHA-256 checksums. API routers/main/security, both OpenAPI
snapshots, package lock, CI workflow and tracked environments are unchanged. No secrets or .env
contents were exposed. Tests/experiments wrote only disposable databases. No financial HTTP
mutation was performed; no commit, push or merge was performed.

## Files created and modified

- `.gitignore`
- `README.md`
- `app/models.py`
- `app/services/wallet.py`
- `docs/database-architecture.md`
- `docs/database-migration-guide.md`
- `scripts/verify_migrations.py`
- `tests/test_migrations.py`
- `app/financial_schema.py`
- `app/money.py`
- `app/services/financial_wallets.py`
- `docs/financial-integrity-architecture.md`
- `docs/financial-risk-assessment.md`
- `migrations/versions/g20261120fin_add_exact_money.py`
- `results/financial_integrity_foundation_report.md`
- `scripts/audit_legacy_finances.py`
- `scripts/reconcile_financial_wallets.py`
- `tests/test_financial_wallets.py`
- `tests/test_legacy_financial_audit.py`
- `tests/test_money.py`

## Outstanding risks and next work

- Historical adoption remains unapproved. Confirm actual currency/units/provenance, reconcile
  a source manifest and exceptions, verify backups, obtain separate conversion approval and
  rehearse idempotent source mapping, authoritative cutover and restore. Do not assume BWP.
- Legacy Float storage/raw checks, commit-owning non-idempotent compatibility calls and existing
  prize distribution risks remain. Prize function still uses float shares, can repeat payouts,
  bypasses wallet/ledger, and has no durable payout marker; it was intentionally not changed.
  If it creates legacy activity for an exact-wallet player, the new foundation stops further postings and reports it.
- SQLite serialises all writers. Contention/scaling need operational handling; tests do not
  establish multi-host throughput or power-loss durability beyond SQLite transaction guarantees.
- PostgreSQL requires a separately reviewed schema/trigger translation, row locks/conditional
  update strategy, unique-key contention and full-unit serialization/deadlock retries retaining
  the key. The new foundation explicitly refuses PostgreSQL; the legacy branch is unverified.
- Direct privileged SQL can create reconciled-looking or bounded corrupted data; these controls
  are not cryptographic tamper evidence. Access controls, external audit, backup/recovery,
  retention and monitoring remain deployment requirements.
- The new service is internal and not an HTTP authorisation boundary. Future endpoints must
  authenticate/authorise wallet ownership before any operation or receipt lookup, validate
  real funding/payment-provider evidence, and retain idempotency identity across retries.
- Fees/registrations/refunds/payout orchestration, external settlement, reconciliation automation
  and prize distribution integrity require subsequent work. ALL financial HTTP writes remain
  disabled without a feature-flag or administrator bypass.
- Two moderate frontend dependency entries remain; hosted CI is unverified. Neither financial
  production readiness nor financial API activation is claimed.

After clean final local verification, this is ready for code review and user-authorised hosted
CI verification. Recommended next work is a separately approved historical reconciliation/adoption
plan and financial orchestration/payment/payout controls, while preserving the HTTP mutation gate.
