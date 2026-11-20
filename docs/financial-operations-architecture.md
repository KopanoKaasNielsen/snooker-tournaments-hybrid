# Financial operations architecture (Task 04B)

Financial HTTP mutations stay disabled. No provider adapter or external payment integration is
implemented; the default verifier refuses verification. VERIFIED means a trusted server adapter
has validated evidence/authentication and its operation binding, never that funds have settled.
Only test fixtures simulate successful evidence. No historical money is converted or re-labelled.

## Policy and state machine

An active authenticated wallet owner may request deposit/withdrawal operations for their own
wallet only. Active administrators may request fee/prize operations for another active owner;
organisers have no staff financial powers. All methods validate real access JWT/session state
and reload roles/ownership from the database. No caller-supplied owner or role is accepted.
Admins may inspect operations and reject them, but cannot bypass currency/amount/evidence,
ledger or idempotency controls. Verification/posting require an independent active administrator
who is neither owner nor requester. This conservative internal maker/checker policy adds no HTTP
capability. Current-owner binding and active-account checks apply before funding changes.

PENDING -> VERIFIED -> POSTED. PENDING may become CANCELLED (owner/admin) or REJECTED (admin).
VERIFIED may become REJECTED (admin), but not cancelled. POSTED/REJECTED/CANCELLED are terminal.
Exact retries are no-ops; conflicting intent/verification/terminal retries fail. Cancellation and
rejection do not mean provider refund or reversal. No new reversal/prize-allocation rule exists.

## Storage and atomicity design

Add FinancialOperation with generated UUID4 ID, globally unique UUID4 request key, owner,
requester, wallet, exact positive bounded thebe amount, BWP, kind, lifecycle times, current actor,
immutable digest-only evidence, verifier/poster IDs and unique optional ledger receipt FK.
FinancialOperationAudit stores append-only state events, actor/role and enumerated reason codes,
not raw provider payloads, references, tokens, credentials, arbitrary user text or exception SQL.
Checks/triggers validate intent, states/transitions, ownership, reviewer roles and linked receipts.
No existing table or record is backfilled by the additive revision.

Extract the existing FinancialWalletService posting body into a transaction-participating private
primitive. Its public standalone API still owns a transaction, preserving Task 04A behaviour.
Operation posting uses the same BEGIN IMMEDIATE unit for permission/state checks, the existing
wallet arithmetic/ledger insert, operation POSTED+receipt link and audit insert. There is exactly
one commit and no nested independently committed wallet call. Any failure rolls everything back;
a lost response after commit retries from POSTED and returns the original receipt. The operation
ID is the ledger idempotency key. Public standalone wallet posting refuses keys reserved by
operations; pre-existing standalone ledger rows are not silently adopted into new operations.

Verification adapter work is outside a database writer transaction; intent/state/actor are
checked again before recording VERIFIED. A cancellation/deactivation racing verification wins
if committed first. SQLite writers serialize creation, posting and aborts; no application mutex
or sleep establishes correctness. PostgreSQL remains unsupported pending its separate locking,
trigger and transaction-retry design. Failed rolled-back transitions do not leave false durable
success audit events; operational error monitoring remains necessary.

## Evidence and reconciliation

An internal verifier Protocol accepts a frozen operation binding and bounded opaque reference.
The service accepts no client verification/settlement status or evidence object. A trusted result
must bind operation/wallet/kind/amount/currency exactly, identify the configured provider, contain
canonical event and payload SHA-256 digests and a recent UTC verification-observation time.
Provider/event uniqueness prevents one event funding multiple operations, including aliases.
Only reference digests are persisted. Verified evidence expires for posting after 15 minutes;
expired operations require rejection/new review, not silently renewed verification. No verifier
implementation claims provider settlement. External adapters require separate user approval.

Reconciliation checks operation state/receipt/key/binding and durable audit histories against the
ledger in a consistent read snapshot. Standalone Task 04A entries are reported separately and
never assigned invented operations. Missing/edited operation triggers fail closed. Privileged SQL
is not cryptographic tamper evidence; no reconciliation repairs money or changes state.

## Implemented interfaces and storage

`FinancialOperationService(engine, verifier=None)` accepts **real access-token strings**, not
actor IDs, roles, ownership IDs or client evidence objects. `request`, `get`, `verify`, `post`,
`reject`, `cancel` and `reconcile` validate JWT signature/issuer/audience/expiry and the current
active database user/session on every call. Request keys and generated operation IDs are
canonical UUID4s; ledger idempotency uses the operation ID. Both ID namespaces are reserved
against public standalone wallet posting and conflicting request/ledger keys. The service is
internal: no new HTTP operation endpoints or frontend payment controls are exposed.

Owners may read their current-wallet operations; admins may inspect all operations. Reconciliation
requires an administrator. Deactivation, session revocation, role changes and ownership relinking
are rechecked, including after the verifier boundary. Verification/posted retries still enforce
current reviewer/ownership permission before returning durable results. Staff cancellation and
rejection are abort decisions, not refunds; they cannot alter POSTED records.

Revision `h20261120ops` follows `g20261120fin`. It adds financial_operations and
financial_operation_audit only, with unique request/provider-event/receipt identities, exact thebe
bounds, BWP and state-field CHECKs and foreign keys. Six SQLite triggers enforce initial ownership
and requester policy, immutable intent/evidence, valid state changes, independent reviewers,
matching posted receipts, no deletion and append-only state audit. The audit event/reason pairing
must match the operation's durable state and actor. Trigger definitions are checked inside every
operation transaction, by fresh migration checks and before any disposable-copy stamp. A populated
operation or audit table cannot be downgraded. No historical revision is rewritten.

Evidence fields are provider identifier, canonical provider-event SHA-256 digest, validated
payload digest, request-reference digest, UTC checked-at and verifier ID. References are bounded
printable opaque lookup values, never stored verbatim. A digest is an identifier/integrity aid,
not proof of provider authenticity or settlement. Only a separately approved server adapter may
supply evidence; it must validate signatures/origin, authoritative account/beneficiary mapping,
operation type and amount/currency. No generic client status, arbitrary audit JSON, raw exception
text, payment credential, access token or provider secret is persisted.

Verification observations must be after operation creation and recent (five-minute validation
window, at most five seconds forward clock skew). Verified evidence expires for new postings
after 15 minutes. POSTED means a local ledger transaction committed, not an external payment,
transfer or settlement. Exact retries return original results; differing verified references
cannot overwrite evidence. Canonical provider-event uniqueness spans terminal/rejected operations
as well, so a later refund/reversal needs a separately designed workflow rather than event reuse.

## Checks and limits

Tests use real JWT sessions and SQLite transactions. Passing evidence adapters exist only in
the test file, clearly named as test-only, and are not settlement integration verification.
Tests deterministically interleave creation, verification, posting, conflicting debits and
post-versus-reject races on separate SQLite connections. Verification waits outside the writer
lock; cancellation or deactivation during that wait cannot resurrect an operation. Insert,
operation-update, audit-insert and commit failure/reply-loss scenarios preserve valid durable
states and retry identity. Existing Task 04A concurrency/precision tests remain.

Run both existing wallet reconciliation and operation reconciliation: the latter verifies only
operation/receipt/audit consistency, not wallet balance totals, external funding or settlement.
Standalone Task 04A ledger rows remain visible as unmanaged counts and are not labelled invalid
or converted into invented operation histories. Reconciliation detects receipt-link and audit
history tampering and never repairs them. Missing protections fail closed.

Committed state changes have transactionally durable audit events. Failed/denied attempts roll
back without false success events; this is not a separate durable failed-attempt/security-log
sink. External monitoring, audit retention/tamper evidence and rate limiting must be reviewed
before HTTP activation. Privileged database writers can still tamper with rows or protections;
these controls are not cryptographic payment attestation or defence against compromised server
code/database administration. The private transaction participant is a trusted-code capability,
not an additional public API or an authenticated endpoint.

SQLite BEGIN IMMEDIATE serialises writers; bounded contention uses the existing FinancialBusy
whole-operation/same-key retry rule. The adapter protocol must remain verification-only; external
network calls/capture/transfer/provider credentials are not implemented. PostgreSQL remains
explicitly unsupported; it needs reviewed schema/trigger translation, row locks, unique-key
contention and full-unit serialization/deadlock retries. Existing prize calculations, legacy
wallet records/currency and all financial mutation HTTP denials remain unchanged.

## Development verification

```bash
python -m pytest -q -W error
python -m scripts.verify_migrations --existing-copy-from snooker.db
python -m black --check .
npm run typecheck
npm run test:ci
npm run build
```

Tests/verification use disposable databases and ephemeral auth configuration. The compatibility
command reads the original in SQLite read-only mode and upgrades a separate temporary copy.
See results/financial_operations_implementation_report.md for exact results and limitations.

Pending/verified debits do not reserve a balance or guarantee funds availability. The conditional
wallet update checks funds at POSTED time; competing intents can remain VERIFIED after one debit
uses the available funds. External debit/capture/transfer must not be added to the verification
method; reservations, outbox/delivery recovery, customer consent, refunds and settlement need a
separately approved design before real payment activity. Expired verified events keep their
unique reservation and cannot be silently recycled; an approved recovery/reverification policy
is required before live provider use.
