# Tournament financial orchestration — audited architecture

**Current Phase 2 status:** explicit new-tournament `BWP_TOURNAMENT_V1` review workflows and non-postable previews are implemented. All financial activation remains blocked. The audit and approval-boundary text below records the Phase 1 baseline for legacy tournaments; the Phase 2 section and [current policy](tournament-financial-policy.md) supersede its outstanding policy choices for new opt-in tournaments.

Baseline d6cb7b5; branch feature/tournament-financial-orchestration. Initial original database
SHA-256: 7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa.
Financial rules below are observations, not approval to change calculations or activate writes.

## Phase 1 audit: legacy rules (preserved)

- Tournament.entry_fee is an integer with no currency/unit metadata. Registration has paid=False,
  waived=False, contribution=0 defaults, unique tournament/player and FKs. Those flags and
  contribution are not used to calculate the existing pool or gate the registration helpers.
- Authenticated HTTP registration permits owner, assigned organiser or administrator, but all
  nonzero fees are explicitly denied. Free registration uses CRUD; duplicate pairs are rejected.
  No registration deadline/capacity/status/payment-eligibility policy is implemented.
- There is a CANCELLED tournament enum, but no cancellation/refund workflow, eligibility rule,
  refund operation type or durable original-fee/refund association. Cancelling a FinancialOperation
  is not reversing a posted ledger amount. No historical refund policy can be inferred.
- Legacy distribute_prizes defaults to split (1.0,), uses entry_fee × every registration,
  transient tournament.final_standings, arbitrary supplied shares and Python float round(..., 2).
  Missing players are skipped; later winners get zero if splits are short. There is no paid/waived/
  contribution deduction, durable pool custody, ledger entry, idempotency or payout marker.
  Repeating it can credit balances again. Existing test explicitly exercises 60/30/10.
- No checked default/call site establishes 50/30/20; the generic helper can accept arbitrary
  splits, which does not establish the policy. No financial 10% token allocation was found. The product request
  introduces unresolved policy questions; authentication token code is not token allocation.
- CRUD completion requires registered winner IDs and unique positions between 1 and 4 and
  rejects an already COMPLETED status. It accepts empty/incomplete winner lists and can put
  the same player in different positions. DB uniqueness protects positions, not player ranking.
  Completion stores results/status only and does not call prize distribution or create operations.
- HTTP match-result CRUD overwrites scores/winner without participant/score/registration checks;
  once all existing matches have a non-null winner it marks the tournament COMPLETED. It does
  not derive durable final rankings. The separate Elo service validates winner membership and
  rejects repeat results, but is not the route's CRUD path and has incomplete bye handling.
- Knockout generation shuffles registrations and creates the first round/byes; no authoritative
  complete-bracket/league ranking algorithm or payout-approved result version is implemented.
- Tournament permission (assigned organiser/admin) is not independent financial maker/checker
  approval. Task 04B requires current JWT/session/ownership, independent active administrators,
  trusted evidence, exact BWP and an atomic operation/ledger/audit unit. Those controls stay intact.

## Approval boundary

See tournament-financial-policy-questions.md. No assumption that legacy prices are BWP, that
50/30/20 supersedes existing code, or that tokens reduce the prize pool is permitted. The
existing prize function/tests and all financial HTTP denials remain unchanged. No successful
external payment evidence is manufactured. Monetary flow implementation awaits explicit rules.

## Safe implementation scope

A policy-neutral metadata layer may identify FEE, REFUND and PAYOUT *intents* without creating
money or deciding eligibility. Such intents remain POLICY_REQUIRED, have no inferred amount,
currency, operation or posted ledger receipt, and cannot be posted. Immutable semantic identities
and unique request keys make retries/concurrent recording safe. Repeated tournament completion
must have no automatic financial side effects. Diagnostics report incomplete/corrupt rankings
and pool uncertainty; they do not repair historical results or infer payable winners.

Any future activation must atomically bind approved intent/price/results/refund provenance to a
Task 04B FinancialOperation and use its existing shared wallet transaction, independent reviewer,
trusted evidence, global idempotency and audit. Separate commits or an admin force flag are not
acceptable. Pool custody/conservation, refunds, tokens, result revisions and rounding require
explicit policy before implementing that monetary layer. Existing core operations/ledger remain
unmanaged by this proposed tournament metadata layer until an approved binding design exists.

## Implemented safe layer (no monetary policy approval received)

Revision i20261120tfin follows h20261120ops and adds two initially empty metadata tables:
`tournament_financial_intents` and `tournament_financial_requests`. Intent kind is FEE, REFUND or
PAYOUT; state is permanently POLICY_REQUIRED. Amount, currency, FinancialOperation and receipt
fields must be NULL by database CHECK. Immutable triggers prohibit promotion, rebinding or
removal. There is no token-allocation record because token meaning is not defined.

A review aggregate identifies an existing registration (fee/refund review) or result row (payout
review). One aggregate per kind/source identity is **not** a policy limiting future instalments,
partial refunds or payout revisions; that monetary design is undecided. No eligibility, refund
entitlement or payable winner is asserted. Each distinct UUID4 request has a separate immutable
receipt so even a second key returning the same aggregate stays permanently bound to its actor
and context. Conflicting reuse fails; concurrent requests use the shared SQLite writer transaction.

TournamentFinancialService reuses Task 04B's guarded transaction and real JWT/session validation,
then requires current administrator or assigned organiser authority. Monetary reconciliation
requires administrator. Ownership of a wallet alone is not permission to review a tournament.
No client roles/actor IDs or amount/currency overrides are accepted. Every request is checked
against current scope/assignment before idempotent replay. The original repository DB write
protection and all wallet/operation integrity checks remain in force.

Registration/result context is verified by foreign keys plus insert triggers, and the initial
source fingerprint includes the raw legacy fee/contribution representation, flags, status and
ranking as applicable. This is hashing provenance, not unit conversion or a currency claim.
Source changes flag the immutable review as stale rather than silently changing financial intent.
Six triggers protect scope/request authority and append-only metadata. Their SQL is verified in
migrations and service transactions. Populated review downgrade refuses data loss.

The existing wallet and operation services reserve review IDs/request keys against monetary use.
Neither create_operation, post_intent nor allocate_tokens can proceed: they raise a clear
TournamentPolicyRequired error after access checks. No callback is wired to registration,
match reporting, completion or cancellation. Repeated completion/review requests create no
FinancialOperations or ledger entries. Financial HTTP writes and trusted evidence controls are
unchanged; no organiser/admin override exists.

## Diagnostics and limits

Read-only metadata reconciliation compares review provenance and request histories and checks
for any financial activity improperly using blocked identifiers. It reports missing/changed
source metadata, duplicate ranked players, unregistered rankings, position anomalies, empty
completed standings, invalid match winners/negative scores and unfinished completed matches.
It does not repair winners, implement a ranking algorithm, decide ties or assert payout approval.
The prize pool and token allocation remain explicitly undefined (None), with policy_required=True
and monetary_flow_ready=False even when metadata is consistent.

Generic Task 04B operations and existing ledger entries cannot be attributed to tournaments
without approved provenance rules. No arbitrary fee operation is treated as a tournament fee,
no refund is mapped to a deposit/prize type, and no existing financial record is adopted.
Current reconciliation is therefore **blocked-review consistency**, not a funded prize-pool or
settlement reconciliation. Future actual flows need approved pricing/currency, pool custody and
conservation, original-fee refund provenance, immutable authoritative results/versions, rounding,
token funding and independent verification/posting in the same transaction. No such rule was
chosen to make tests pass.

All existing legacy prize calculations and APIs remain unchanged. Their documented validation,
repeated payout and float risks still exist in legacy internal code; the new layer never calls
that payout function. PostgreSQL remains unsupported by the shared financial services and this
revision. Privileged database/server tampering, audit retention and full financial policy need
separate review. The policy approval question is pending; absence of a reply is not approval.

## Phase 2: explicitly opted-in, inactive BWP policy

`TournamentV1Service.create_tournament` is the only supported policy assignment path. It atomically creates a new tournament, immutable `BWP_TOURNAMENT_V1` policy, organiser assignment, non-spendable pool account and request receipt. There is no attach-existing method, default policy, backfill, historical currency inference, or financial HTTP route. Legacy tournaments retain the Phase 1 blocked review identities and existing calculations. Legacy mutation services deny V1 tournaments before registration, match changes, completion or prize calculation can bypass the new workflow.

Four additive tables separate explicit pricing/policy (`tournament_v1_policies`), a dedicated pool identity (`tournament_pool_accounts`), typed immutable facts (`tournament_v1_records`) and globally bound idempotency receipts (`tournament_v1_requests`). Fact kinds identify eligibility, registration, fee obligation, confirmation, waiver, posted-debit reference, sponsorship review, cancellation, refund review, match-result change, locked results revision, independent approval and non-postable schedule preview. Parent foreign keys, scoped uniqueness, amount constraints and SQLite triggers protect these relationships. Financial-operation and ledger references are relational, unique and immutable; JSON holds reviewed evidence digests and result/calculation snapshots, never credentials. Facts and request receipts are audit history, not payment instructions.

All writes share the Task 04A/04B guarded transaction boundary, reserve the SQLite writer with `BEGIN IMMEDIATE`, reauthenticate the real session, check current assignment/ownership, and commit facts, legacy registration/match state and request receipt together. An error rolls everything back. Distinct retries retain their request receipts but reuse semantic identities. A reused key with different actor, action or payload is rejected. V1 identities cannot become operation or wallet posting keys. No V1 service calls the financial operation verifier or poster. The production verifier remains unavailable and fails closed; successful evidence adapters exist only in tests.

### Registration and provenance

Independent staff attest a linked active player's eligibility with an evidence digest. The owner consents through their own authenticated registration call; no caller-selected owner identifier is trusted for consent. Capacity includes pending reservations, so unpaid registration cannot overbook a tournament. Registration closes at its UTC deadline. Each registration has exactly one nominal BWP/thebe fee obligation. Free entries confirm immediately. An independent administrator can approve a full waiver before the deadline; free and waived entries contribute zero. Paid entries stay pending even after a fee intent or a reviewed posted debit exists.

The existing wallet ledger records a debit but has no receiving tournament custody account, balanced transfer, clearing evidence or sponsorship operation type. Consequently a reviewed posted fee is only a provenance candidate: its owner, amount, BWP currency, original consent time, receipt, operation status and independent reviewer must match. It is explicitly **not cleared pool funding**. A sponsorship review records an evidence digest without an amount or successful settlement claim. Observed debit totals are diagnostics; cleared and spendable pool balances remain zero by database constraint. Participant wallet balances and registration counts never calculate the pool. Paid confirmation, fee collection, sponsor credit, pool transfer and all monetary postings remain blocked pending an approved custody/clearing architecture and activation review.

### Results, corrections and previews

V1 currently supports reviewed knockout results, with best-of-three decisive scores, explicitly represented byes and confirmed members. Locking requires all recorded matches to be completed through the internal result workflow. The service reconstructs elimination order, verifies the final winner and runner-up, and requires a decisive third-place match for more than three entrants. Three entrants have one remaining third-place member. Ties, inconsistent scores, inactive/relinked owners, eliminated players returning and missing results fail closed. Disqualification/tie resolution rules are not inferred; unsupported cases require further policy review. Scheduling a correct and complete bracket is still a staff responsibility; the workflow cannot infer omitted intended matches that were never recorded.

A revision freezes membership, match snapshots, finishing positions, proposing actors and evidence digest. An independent, non-beneficiary active administrator must approve the latest unchanged revision. Completion does not authorise payment. Corrections need an explicit correction evidence digest and a new locked revision/approval; previous reviews and schedules are never overwritten. A single durable **scenario schedule** per approved revision holds a hypothetical distributable amount and exact allocations, marked `postable=false`, with no operation, receipt or financial amount binding. Other what-if scenarios use the pure calculator. Any monetary schedule remains blocked because token treatment and pool clearing are unresolved.

### Refund review boundaries

Owner-requested partial review amounts are explicit positive integer thebe linked to an original reviewed posted fee. All review requests cumulatively consume at most the original principal; this is conservative review headroom, not reserved money or an actual refund. No automatic amount/percentage selection, refund operation, settlement or credit exists. Organiser cancellation before commencement records a recommendation of the full remaining principal but creates no refund request or money movement. Player withdrawal, late cancellation, charges, recovery, chargebacks and release of rejected review headroom remain unresolved.

### Reconciliation, migrations and activation

Reconciliation checks nominal obligations, legacy registration drift, operation/receipt bindings, cumulative review amounts, results revisions, preview conservation and forbidden money-key reuse. It reports stale/superseded revisions for review rather than repairing data; they remain immutable history. Wallet and Task 04B operation reconciliation remain independently required. Review consistency does not establish fund custody or payment readiness.

Revision `j20261120tv1`, following `i20261120tfin`, creates only the four new tables, indexes, constraints and eleven SQLite triggers. It assigns no existing tournament and converts no data. Downgrade refuses before removing anything if any new table is populated. Copy verification recognises the previous 18-table schema as an explicit verification-only disposable adoption baseline. The application source database is never stamped or migrated.

These safeguards are SQLite-specific. `BEGIN IMMEDIATE` serialises database writers; PostgreSQL requires reviewed account/operation row locking, uniqueness/retry handling and equivalent trigger enforcement before support. Raw database owners can remove triggers; trigger-presence checks fail closed but are not a substitute for restrictive deployment credentials. No new permission bypass or security-scanner suppression is introduced.
