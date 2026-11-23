# Tournament financial policy questions — approval required

**Phase 2 update:** the approval resolutions at the end of this document and [BWP_TOURNAMENT_V1 policy](tournament-financial-policy.md) supersede the original questions for explicitly opted-in new tournaments. Token treatment, custody/clearing, refund execution and activation remain unresolved. Legacy behaviour stays unchanged.

Baseline d6cb7b5, Task 04C audit. No financial behaviour has been changed.

## Historical Phase 1 questions and findings

The current `app/services/tournaments.py:distribute_prizes` defaults to **100% to the first
winner**, accepts an arbitrary split argument, and computes `entry_fee * registration_count`.
The regression test supplies **60/30/10**, not 50/30/20. No checked default, call site or regression test selects
50/30/20 as the governing rule and no financial 10% token allocation implementation. Authentication tokens are
unrelated. Neither claimed percentage is therefore an established executable business rule.

## Original Phase 1 decision list (resolution below)

1. **Prize rule and funding:** Is 50/30/20 the intended *new* rule? Does it apply to collected
   fees, gross fees due, a net pool after deductions, sponsorship or another funded pool? What
   covers unpaid/waived registrations? Which accounts hold and fund the pool?
2. **Tokens:** What is a token (money, points, transferable asset), its unit/valuation, recipients
   and rounding? Is the 10% deducted before the prize split, funded separately, or something
   else? What denominator is used? Do not infer deduction or create an extra unfunded 10%.
3. **Fee policy:** Confirm new explicitly BWP tournament pricing in thebe, amount approval and
   eligibility timing (registration before/after collection, partial contributions, waivers,
   capacity/deadline rules). Legacy integer fees/contributions have unknown currency/units.
4. **Cancellation/refunds:** Who may cancel a tournament/registration, when, and for what reason?
   Full/partial/no refund, deduction of costs, eligible original POSTED fee, funding account,
   per-fee cap, treatment of external settlement, repeated cancellations and chargebacks?
   Operation CANCELLED/REJECTED does not undo a POSTED fee. Task 04B has no refund operation type.
5. **Ranking/payout authority:** Define authoritative final standings, tie/byes/disqualification,
   matches required complete, unique players/positions, number of eligible winners, result
   corrections and independent financial approval. Completion alone must not authorise payment.
6. **Rounding and remainder:** How are indivisible thebe distributed among winners/tokens,
   including fewer than three winners? Existing float round() is preserved; do not silently
   replace it or choose a remainder allocation rule.
7. **Durable identities and retries:** Should each registration have one fee obligation, each
   original posted fee one refundable principal, and each approved results revision one payout
   schedule? Define replacement/correction policy before allowing new monetary versions.
8. **Evidence:** Which trusted evidence authorises internal fee debits, refunds and pool-funded
   payouts? The production verifier remains unavailable; no client status or admin override may
   manufacture successful proof. No external provider or financial HTTP write is approved.

## Safe work while policy is unresolved

Audit and document existing behaviour; implement policy-neutral durable *blocked* tournament
intent identities and read-only consistency diagnostics only. Fee/refund/payout generation,
amount selection, token allocation, marking registrations paid, refund eligibility and payout
posting remain unavailable. If approval is not supplied, do not manufacture FinancialOperations,
BWP amounts, a pool balance, settlement claims or automatic prize payments. Any safe metadata
layer must preserve the existing operation/wallet authorisation and cannot bypass it.

## Phase 2 approval resolution and remaining questions

Resolved for explicitly opted-in new `BWP_TOURNAMENT_V1` tournaments: BWP/thebe pricing; 60/30/10 normalised largest-remainder prizes; funding only cleared verified posted entry fees and verified sponsorship; unpaid/waived zero; token direction 10% before prizes; explicit partial-refund reviews capped by principal; pre-start organiser cancellation recommends full remaining principal; independent administrator review of a locked results revision. None of these approvals activates money movement or changes legacy tournaments.

Still required before activation:

- What are tokens (asset, value, recipients, custody), and how are fractional-thebe token bases rounded and accounted for? No deduction/reserve can occur yet.
- What account holds tournament funds and which balanced transfer/clearing/sponsorship operation types prove receiving custody? A generic participant fee debit proves neither settlement nor pool credit.
- What evidence establishes cleared funds independently of payer, organiser and client flags? The production verifier remains unavailable.
- Which partial refund percentages or amounts are authorised for each reason? How do player withdrawals, late cancellation, administration costs, chargebacks and recovery work? Who can approve and release rejected review headroom?
- Which explicit tie, disqualification and non-knockout rules apply? Unresolved cases cannot authorise a schedule. How is bracket completeness externally certified beyond recorded matches?
- How are corrected approved results and any future already-posted payout recovered? This implementation only appends reviewed revisions and never posts or overwrites payouts.
- What separately reviewed adoption procedure, if any, can reconcile and denominate historical data? There is no automatic conversion or policy assignment.
