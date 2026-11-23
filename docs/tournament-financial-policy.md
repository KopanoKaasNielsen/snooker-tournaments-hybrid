# BWP_TOURNAMENT_V1 — approved direction, inactive implementation

Only explicitly created new tournaments can use this immutable policy. Existing tournaments, fees, balances, 50/30/20 descriptions, legacy prize calculations and historical token behaviour are not converted or reinterpreted.

| Topic | Approved rule | Implemented boundary |
|---|---|---|
| Currency / units | BWP, integer thebe, 100 thebe per pula | Explicit BWP; bounded exact integers; bool, float, Decimal and sub-thebe postings rejected by the integer interface |
| Pricing | Explicit new-tournament price; free entries and approved waivers allowed | One immutable fee obligation per owner-consented registration; free/waiver confirmation only |
| Funding | Verified, cleared, posted entry fees plus verified sponsorship | No receiving pool custody/clearing architecture exists; provenance candidates only; cleared/spendable balances fixed at zero |
| Unpaid / waived | Zero contribution | Never count registration expectations or participant wallet balances |
| Tokens | Direction is 10% deduction before prizes | State UNRESOLVED; no asset, token creation, deduction, reserve, token ledger or completion flag |
| Prize weights | 60/30/10 of distributable remainder after future approved token treatment | Pure non-postable previews only; no legacy calculator replacement |
| Fewer winners | Normalise applicable weights: one 100%; two 60/90 and 30/90 | Exact integer quotient plus rational remainder; equal remainder ordered by finishing position |
| Rounding | Largest remainder for prizes | Allocation sums exactly to hypothetical distributable thebe; no binary floats or generic monetary rounding |
| Refunds | Partial reviews; never exceed original remaining principal | Explicit owner-requested review amount; cumulative conservative cap; no automatic percentage or actual refund |
| Pre-start organiser cancellation | Recommend full remaining principal | Immutable recommendation; no automatic request or settlement |
| Authority | Validated locked standings and independent administrator approval | Non-beneficiary, non-proposer approval; corrections require new revision; no financial authority granted |

`allocate_preview` accepts an explicitly hypothetical distributable integer amount and one to three unique consecutive finishing positions. `preview_token_basis` exposes exact rational 10%/90% **scenario bases**, not money deductions or token units. If 90% is fractional thebe it returns no prize allocation rather than choosing an unapproved token rounding rule. Both interfaces are side-effect-free and non-postable.

Examples: 101 distributable thebe with three winners allocates 61/30/10. Five thebe allocates 3/2/0 (the equal second/third remainder goes to second). One thebe with two winners allocates 1/0; 100 thebe with two winners allocates 67/33. A hypothetical gross 101 thebe has a rational token basis of 101/10 thebe and an unresolved 909/10 distributable basis: no rounding, reserve or posting occurs.

The compatibility `Tournament.entry_fee` field remains zero for V1 records because legacy units are undefined. It is not V1 pricing and must not be displayed as authoritative. Internal `TournamentV1Policy.price_minor` is authoritative. Legacy registration and match mutation paths reject V1 tournaments, including HTTP paths that previously interpreted zero as free. Public API schema and existing frontend remain unchanged; there is no V1 HTTP activation.

Activation requires separate approval of token asset/valuation/recipients/custody/rounding/accounting; pool custody and balanced transfers; trusted independent clearing/sponsor evidence; paid-confirmation linkage; refund/recovery rules; payout account/operation types; security and reconciliation review. Until then administrators cannot override any blocker.
