# Task 04B financial operations implementation report

## Scope and baseline

Branch: feature/financial-operations. Baseline: 91914ed, the user-committed Task 04A foundation.
Initial working tree clean. The existing authentication/session/role checks, money policy,
wallet/ledger transactions, reconciliation, migrations, source preservation rules and tests were
inspected before implementation. Baseline contract: 192 backend tests and 33 frontend tests.
Original snooker.db SHA-256 was recorded before changes and verified afterwards.

Implemented authenticated **internal** financial-operation workflows only. No financial HTTP
endpoint, external adapter, real payment confirmation, transfer or settlement integration was
added. Existing deposit, withdrawal, fee and payout HTTP gates remain unchanged. No original
or historical financial record was migrated, stamped, relabelled, copied into an operation or
seeded. Existing prize calculations, currency rules and authentication API contracts are unchanged.
No commits, pushes or merges were performed.

## Models and policy

FinancialOperation contains server-generated unique UUID4 ID, globally unique request key,
immutable owner/requester/wallet, exact positive bounded integer thebe amount, explicit BWP,
kind, status, lifecycle timestamps, verifier/poster/current actor, digest-only evidence and a
unique optional ledger receipt FK. Types match the existing deposit/withdrawal/fee/prize ledger
vocabulary; no prize-allocation or external payout business rule was introduced.

FinancialOperationAudit records immutable transition events, authenticated actor ID/role snapshot,
enumerated reason codes, before/after states and UTC time. It contains no raw references,
credentials, access/refresh tokens, arbitrary user text, provider payloads or exception SQL.
CHECKs/FKs/uniqueness enforce monetary/state/evidence validity; six SQLite triggers protect
ownership/requester policy, transitions/intent/evidence, independent reviewers, receipt matching,
non-deletion and append-only audit. Missing/edited protections fail closed.

| Transition | Authority and conditions |
|---|---|
| Create PENDING deposit/withdrawal | Active authenticated owner of that wallet, including owners with other roles |
| Create PENDING fee/prize | Active administrator acting for another active owner |
| PENDING -> VERIFIED | Independent active admin, current active owner/wallet binding, trusted fresh evidence and no duplicate provider event |
| VERIFIED -> POSTED | Independent active admin; current verifier still active admin; unexpired evidence; atomic wallet/ledger/state/audit transaction |
| PENDING -> CANCELLED | Active owner/admin; exact cancellation retry is a no-op |
| PENDING/VERIFIED -> REJECTED | Active admin; exact rejection retry is a no-op |
| POSTED/REJECTED/CANCELLED | Terminal; no reopening, overwriting intent, refund or reversal |

Service methods take real access-token strings. Existing signature/issuer/audience/expiry,
active-user/session and revocation checks run against database state on every call, before
idempotent results. Owner/role IDs are not accepted from callers. Identity separation forbids
an administrator from verifying/posting their own or self-requested operation. Organisers have
no staff financial powers. Read/reconciliation permissions are enforced independently.

## Evidence boundary

PaymentEvidenceVerifier is a Protocol; the sole application implementation is
UnavailablePaymentVerifier, which always refuses verification. Passing adapters exist only in
tests and are explicitly labelled test-only. Client verified/settled flags and evidence objects
are not accepted as service inputs. A trusted adapter result must exactly bind operation, wallet,
kind, amount and currency, identify the configured provider, carry canonical event/payload
SHA-256 digests and a recent UTC verification observation. A canonical provider/event pair is
unique across all operations, so aliases cannot double-fund another intent. Raw opaque lookup
references are bounded and hashed, never persisted verbatim.

Adapter work occurs outside the writer transaction; current JWT/session, role, ownership,
immutable binding and state are checked again before recording VERIFIED. A racing cancellation,
owner relink/deactivation or reviewer demotion cannot resurrect or verify the pending operation.
Evidence has a five-minute observation window (five-second forward skew allowed) and 15-minute
posting validity. No evidence is silently replaced or renewed. VERIFIED is not settlement;
POSTED means a local ledger unit committed, not an external payment or bank transfer.

## Atomicity, retries and existing wallet reuse

The existing FinancialWalletService posting body was extracted into a private transaction
participant, preserving its public standalone behaviour. Operation posting opens one owned
BEGIN IMMEDIATE transaction before reads, checks current authority/state, calls that existing
money/ledger primitive without a nested commit, sets POSTED/receipt/timestamps and inserts audit.
One commit covers all changes. Insertion/state/audit/commit failure rolls back wallet balance,
sequence, ledger receipt, operation status and audit together. A committed-but-lost response
retries from POSTED and returns the original receipt, rather than posting again.

Client request keys prevent duplicate operations; operation IDs are ledger retry keys. Both
namespaces are reserved against public standalone wallet posting, so that public primitive
cannot create a half-managed receipt or return a receipt without operation-level permissions.
Conflicting intent/key reuse and pre-existing uncoordinated ledger adoption are rejected.
The private participant is trusted server code, not a public or authenticated HTTP entry point.

SQLite writer reservation serialises concurrent requests/posts/aborts. Bounded contention uses
the existing FinancialBusy whole-unit/same-key retry policy. No Python mutex, sleep-based ordering
or automatic new retry key establishes correctness. PostgreSQL remains explicitly unsupported.

## Reconciliation

Authenticated administrator reconciliation reads a consistent snapshot and validates status,
receipt existence/identity/key/amount/type/currency and complete durable audit histories. Wrong
receipt links, missing audit events and ledger entries for non-posted operations are findings;
no repair is attempted. Existing Task 04A standalone entries are counted as unmanaged, not
assigned fabricated operations or labelled invalid solely for predating this workflow.

This is operation-to-ledger reconciliation. Run the existing wallet reconciliation as well for
balance totals, sequence chains and legacy-activity checks; neither proves external settlement.
Committed transitions have durable audit events. Rolled-back/denied attempts do not leave false
success events; separate failed-attempt monitoring/audit retention is still operational work.

## Additive migration and compatibility

```text
<base> -> dd093dfa2ebf -> d27f9a18494f -> e20261119db01
       -> f20261120auth -> g20261120fin -> h20261120ops (single head)
```

h20261120ops adds only financial_operations, financial_operation_audit, their constraints/indexes
and six protections. No existing table is altered/backfilled; all five earlier revisions are
unchanged. Empty operation downgrade/re-upgrade preserves populated Task 04A wallets, ledger
and users. Populated operation/audit downgrade refuses data loss. Fresh history/heads/current,
upgrade/check, empty full downgrade/re-upgrade, ORM equivalence and ledger/operation trigger SQL
are verified. Supported pre-operation versioned copies are schema-matched before upgrade;
unsafe current schemas missing either protection set are refused before copy stamping.

The original six-table database is read only as a SQLite backup source. Only the disposable copy
is explicitly adopted at its matching baseline for compatibility verification; the source is never
stamped or migrated. Tests preserve every row/value of populated g20261120fin data through h
upgrade, empty downgrade and re-upgrade. No operation or provider identity is inferred for old
ledger records.

## Verification results

| Verification | Actual result |
|---|---|
| Python 3.11.15 `python -m pytest -q -W error` | **276 passed**, 0 failures, 0 warnings; **704.32s** |
| Python 3.12.3 `python -m pytest -q -W error` | **276 passed**, 0 failures, 0 warnings; **583.13s** |
| `python -m scripts.verify_migrations --existing-copy-from snooker.db`, both versions | Passed: fresh graph/current/upgrade/check, ORM/ledger/operation triggers, empty roundtrip and disposable-copy row/value preservation |
| `python -m black --check .`, both versions | Passed; **57 files unchanged** |
| `python -m pip check`, both environments | Passed; no broken requirements (nonfatal local pip-cache ownership notice) |
| Runtime-only Python 3.12 `python -W error -m scripts.verify_dependency_environment --runtime-only` | Passed: no dev-only runtime dependency, migrated startup, unchanged auth API snapshot and unauthenticated denials |
| Python 3.11 `python -W error -m scripts.verify_dependency_environment` | Passed: migrated startup and unchanged API contract |
| Runtime-only internal workflow smoke, fresh migrated DB | Passed: real JWT/session ownership, PENDING+one audit, default verifier refusal, posting denial, zero balance/ledger and consistent operation reconciliation; disposable database removed |
| `npm run typecheck` | Passed |
| `npm run test:ci` | **33 passed**, 5 suites; **9.207s** |
| `npm run build` | Passed; Vite 6.4.6, 104 modules, **5.27s**, deployable dist/index.html + assets; JS 241.69 kB (81.00 kB gzip), CSS 1.44 kB |
| actionlint 1.7.7 | Passed, no diagnostics |
| Bandit 1.9.4 `bandit -q -r app` | Passed, no findings |
| pip-audit 2.10.1 of full resolved backend graph | Exit 0, **no known vulnerabilities found** |
| `npm audit --json` | Exit 1, **2 moderate package entries**, 0 high/critical; existing Router advisories remain |
| `git diff --check` | Passed |
| Protected source/history/API/workflow diff | No changes to all five historical revisions, prize/legacy wallet/money/ledger policy, API/auth/security, snapshots, frontend lock/source or workflow |
| Original database checksum | Unchanged; exact evidence below |
| `git status --short` | Only intended new/modified source, tests, migration and docs/report; no publication operation |

Final test count: existing 192 + 82 new operation tests + 2 additive migration tests = **276**.
The final runs used the stable source tree; no Python implementation/test changes were made while
those full suites ran. All financial HTTP mutation-denial regressions continue to pass. Positive
verification cases use test-only adapters, not real provider confirmations. The runtime-only
smoke specifically proves the application default cannot verify/post an unverified operation.
No successful financial HTTP mutation or external financial operation was performed.

An early in-progress run overlapped creation of the new module files: 191 passed/1 failed in
174.58s because the development-CLI subprocess imported financial_operation_models before
operation_schema.py existed. This was not a clean baseline result or hidden success. Once all
modules/migrations were present, the operation target passed 68 tests, then the expanded
operation/migration target passed 98 tests in 171.20s. Final full suites were started only after
the tested source tree was stable; no Python implementation/test changes were made during them.

New automated coverage includes valid authenticated lifecycle, ownership/cross-user denial,
admin/organiser boundaries and self-review refusal, current roles vs forged token role claims,
expired/revoked tokens, invalid/sub-thebe/non-finite/unsupported-currency amounts, conflicting and
concurrent request keys, canonical provider-event alias reuse, malformed/unbound/stale evidence,
raw client verification flags, audit privacy and sanitized provider errors, all terminal states,
verification-boundary deactivation/ownership races, expired evidence, insufficient-funds retry,
operation/audit/commit rollback, committed-reply loss, simultaneous posting of one operation,
competing debit operations, post-versus-reject races, database immutability/state checks,
receipt/audit reconciliation tampering, trigger refusal and additive migration preservation.

All original 192 regressions remain. Existing migration-head expectations include h20261120ops;
the original ledger-trigger query is scoped to its ledger table because six separate operation
triggers now exist, with their own exact SQL checks. No assertions were weakened or warnings
suppressed. Frontend tests mock network transport; real SQLite/JWT tests and runtime-only smoke
are separate internal integration evidence. No real provider/settlement verification is claimed.

## Data and security preservation

Original snooker.db SHA-256 before and after:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa
```

Original data, all historical migrations, prize distribution, legacy wallet adapter, money policy,
ledger protections, API routers/main/security, both API snapshots, frontend source/lock, workflow
and dependency pins are unchanged. The wallet service change is transaction participation/key
reservation only; existing Decimal/integer arithmetic and financial limits are reused. Every
write experiment/test used a disposable database. No secrets or .env contents were printed.

Security scans remain advisory in the unchanged CI workflow; local scanner success is not a
blocking hosted gate or penetration-test claim. No hosted workflow run was performed/claimed.
Existing frontend Router moderate advisories remain and need a separate upgrade. Pip-audit's
artifact-hashing recommendation remains a reproducibility limitation; no vulnerability ignores
or unrelated dependency upgrades were introduced.

## Files created and modified

- `.gitignore`
- `README.md`
- `app/models.py`
- `app/services/financial_wallets.py`
- `docs/database-architecture.md`
- `docs/database-migration-guide.md`
- `scripts/verify_migrations.py`
- `tests/test_migrations.py`
- `app/financial_operation_models.py`
- `app/operation_schema.py`
- `app/payment_verification.py`
- `app/services/financial_operations.py`
- `docs/financial-operations-architecture.md`
- `migrations/versions/h20261120ops_add_financial_operations.py`
- `tests/test_financial_operations.py`
- `results/financial_operations_implementation_report.md` (this report)

## Known limitations and unresolved risks

- No approved external verifier, signature/webhook/account mapping, payment credential storage,
  capture/transfer/refund or settlement orchestration exists. Default verification fails closed.
  External provider integration and every financial HTTP write require separate approval.
- VERIFIED/POSTED never promise settlement. Digest fields alone are not proof of authenticity;
  trusted server adapter validation is a future integration/security review responsibility.
- Expired evidence cannot be silently renewed. Provider-event uniqueness keeps its reservation
  even after rejection; recovery/reverification/refund policies need explicit design before live
  payments, rather than reusing events or manufacturing new confirmations.
- The new internal maker/checker policy is conservative; fee/prize operations require a second
  administrator. There is no role override. Business-specific authority/consent, fraud review,
  payment-method checks, provider retries and settlement evidence remain future work.
- The standalone wallet primitive remains an internal server capability for Task 04A compatibility;
  future HTTP handlers must expose only the authenticated coordinated workflow and must never
  accept client actor/owner/verification objects or call the primitive directly.
- State-change audit is atomic but not a durable rejected-attempt sink, external WORM audit or
  cryptographic tamper evidence. Privileged database/server code can tamper with state/protections.
  Monitoring, retention, failure audit, rate limits and recovery need preactivation review.
- PENDING/VERIFIED debits reserve no funds. Availability is checked only during atomic posting;
  external transfers need separately designed reservations/outbox recovery/consent before approval.
- SQLite serialises all writers. PostgreSQL needs a reviewed schema/trigger translation, row
  locks, unique-key contention and full-unit serialization/deadlock retry strategy; unsupported.
- Historical currency/adoption remains unapproved. Existing Float/prize/legacy risks are not fixed
  by operation intents. Do not import historical funds or change prize behaviour without approval.
- No production deployment, real-device browser/provider E2E or hosted CI success is claimed.

After final local verification, the change is ready for review and user-authorised hosted CI.
Recommended next work is failure/audit/recovery policy and a concrete provider integration design
for separate approval, while preserving the financial HTTP gate and historical-data boundary.
