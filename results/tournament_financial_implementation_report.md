# Task 04C Phase 2 — approved policy implementation report

## Current status

Implemented inactive, explicit `BWP_TOURNAMENT_V1` policy orchestration for newly created tournaments only. No default policy, historical adoption, financial HTTP route, actual posting, token creation/deduction/reserve, refund execution, sponsorship credit or prize payment is enabled. The Phase 1 report is preserved below as historical audit evidence; its pre-approval statements do not describe current Phase 2 approval status.

## Baseline and findings

Branch `feature/tournament-financial-orchestration`; HEAD `d6cb7b5`. Phase 1 changes were already uncommitted and have been preserved. Its preceding verification recorded 304 strict backend tests per Python version and 33 frontend tests. Phase 2 collected 323 backend tests, retaining all 304 and adding 19 focused tests. Original database initial SHA-256: `7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa`.

Inspected the Phase 1 review identities, Task 04B operations/evidence boundary, Task 04A atomic wallet/ledger services, legacy tournament registration/completion/match/prize paths, migrations and tests. A generic POSTED fee debit cannot prove receiving tournament custody or cleared settlement. There is no pool transfer, sponsorship or refund operation type. These gaps are blockers, not reasons to bypass the existing maker/checker or evidence controls. Legacy fee/balance currency is unknown and remains untouched.

## Implemented, preview-only and blocked behaviour

- **Implemented metadata workflows:** explicit new tournament plus immutable policy/pool; BWP exact integer-thebe price; independent eligibility attestation; owner consent; capacity/deadline checks; one nominal fee obligation; pending paid registrations; free/independently waived confirmations; durable globally reserved request identities; atomic retries/rollback; immutable posted-debit provenance references; sponsorship evidence review without an amount/settlement claim; principal-capped owner partial refund reviews; pre-start organiser cancellation recommendation; reviewed knockout match results; locked versioned standings; independent non-proposer/non-beneficiary administrator approval; reconciliation diagnostics.
- **Calculation-only:** pure integer/rational 60/30/10 largest-remainder allocator, normalised for one/two winners, finishing-position remainder tie-break; rational hypothetical 10% token basis with no fractional-thebe rounding choice; one immutable, explicitly hypothetical non-postable scenario schedule per approved results revision. Scenario amounts are never interpreted as funded pool amounts.
- **Blocked:** paid confirmation/collection, transfers, pool credit, sponsor posting, monetary schedules/payouts, refunds, tokens and every financial HTTP mutation. `monetary_action` authenticates and denies even administrators. Existing generic operations keep their original trusted-evidence and independent-authorisation boundaries; V1 never invokes them to post.
- **Unresolved:** token definition/value/recipients/custody/rounding/accounting; receiving custody/clearing and balanced operation types; sponsor evidence; refund reason/percentage/recovery/charges/chargebacks; tie/disqualification/non-knockout rules; full bracket completeness certification beyond recorded matches; financial activation and historical adoption.

## Architecture and migration

Four new tables: `tournament_v1_policies`, `tournament_pool_accounts`, `tournament_v1_records` (typed immutable facts), `tournament_v1_requests` (actor/action/payload-bound receipts). Money-related values and foreign identities are relational; JSON is restricted by service methods to evidence digests and immutable review/calculation snapshots. Existing FinancialOperation and ledger schemas are unchanged. Pool cleared/spendable fields are constrained to zero; observed posted debit provenance is a diagnostic, never spendable funding or participant-wallet aggregation.

Additive revision `j20261120tv1` follows `i20261120tfin`. It creates four tables, indexes, constraints and eleven SQLite triggers, assigns no policy to existing tournaments and performs no data conversion. Populated downgrade refuses before deleting any object. Full graph: `dd093dfa2ebf -> d27f9a18494f -> e20261119db01 -> f20261120auth -> g20261120fin -> h20261120ops -> i20261120tfin -> j20261120tv1` (one head). All earlier revision files are preserved.

New writes reuse the guarded Task 04A/04B `BEGIN IMMEDIATE` transaction. Semantic duplicates reuse facts, distinct retry keys remain bound, changed payloads/actors/actions conflict, and failed request persistence rolls back registration/obligation changes. Event-controlled tests hold one writer, observe a second independent connection attempting `BEGIN IMMEDIATE`, then release it: concurrent registration retry yields one obligation; competing partial-refund reviews cannot exceed original principal. No sleep-based race assertions are used.

Legacy calculations and tournament data remain unchanged. Conditional guards reject V1 tournaments in old registration/match/completion/prize helpers. V1's compatibility `Tournament.entry_fee=0` is explicitly not authoritative pricing; the immutable policy price is authoritative. No new HTTP API or frontend monetary flow exists. Public OpenAPI snapshots are not replaced.

## Verification

Both final full strict backend suites completed successfully against the final Python implementation. Commands used external environments, never the tracked repository environment. **323 passed on each interpreter, 0 failed, 0 warnings, no skips: all 304 existing tests retained plus 19 new tests.**

| Check | Actual result |
|---|---|
| Python 3.12.3 full `pytest -q -W error --basetemp /tmp/snooker-v1-final-py312` | Exit 0; **323 passed, 0 failed, 0 warnings**, 1236.94s (20m36s) |
| Python 3.11.15 full `pytest -q -W error --basetemp /tmp/snooker-v1-final-py311` | Exit 0; **323 passed, 0 failed, 0 warnings**, 1493.49s (24m53s) |
| Python 3.11 / 3.12 `python -m scripts.verify_migrations --existing-copy-from snooker.db` | Both exit 0: one head `j20261120tv1`; fresh upgrade, ORM consistency, empty downgrade/re-upgrade, all four trigger families, disposable-copy upgrade and row/value preservation |
| Python 3.11 / 3.12 `python -m black --check .` | Both exit 0; 68 files unchanged; historical migrations not reformatted |
| Python 3.11 / 3.12 `python -m pip check` | Both exit 0; no broken requirements (sandbox cache-location warnings, not backend test warnings) |
| Python 3.11 / 3.12 `python -W error -m scripts.verify_dependency_environment` | Both exit 0 outside sandbox; reviewed authentication OpenAPI snapshot exactly unchanged; migrated startup, health and unauthenticated denials pass |
| Runtime-only Python 3.12 `python -W error -m scripts.verify_dependency_environment --runtime-only` | Exit 0 outside sandbox; imports/startup require no development packages |
| `npm ci` | Exit 0 on outside-sandbox retry; lockfile retained |
| `npm run typecheck` | Exit 0 |
| `npm run test:ci` | Exit 0; 5 suites, 33 tests passed, 0 failed |
| `npm run build` | Exit 0; 104 modules; deployable `dist/index.html`, CSS 1.44 kB and JS 241.69 kB |
| Bandit 1.9.4 `bandit -q -r app` | Exit 0; no findings |
| pip-audit 2.10.1 against complete external dev environment `pip freeze --all`, using `--no-deps --disable-pip` | Exit 0 after network-enabled retry; no known vulnerabilities found; scanner recommends hashed locks |
| `npm audit --json` | Exit 1 for findings, not a pass: 2 moderate package entries (`react-router`, `react-router-dom`), no high/critical entries |
| actionlint 1.7.7 | Exit 0; all existing jobs/triggers retained; backend timeout raised from 20 to 35 minutes for the expanded strict schema suite; no hosted workflow success claimed |
| `git diff --check` | Exit 0 at verification checkpoints; repeated after final report |
| Original database SHA-256 | Unchanged at repeated checkpoints; final checksum recorded below |

Full backend commands use `/tmp/snooker-auth-03-8n2r1m06/py312/bin/python` and `/tmp/snooker-auth-03-8n2r1m06/py311/bin/python`, each wrapped with `timeout 2400`. Final application Python code was frozen before both full suites started. The runtime-only interpreter is `/tmp/snooker-auth-03-8n2r1m06/runtime312/bin/python`.

Initial focused verification found a real preview retry defect (JSON lists versus in-memory tuples); canonical JSON comparison fixed it. New tests also corrected exception-class expectations to the actual denial/error contracts without weakening assertions. The first focused run had 10 passed/3 failed; the second had 14 passed/1 failed. A later focused run completed 18 V1 checks before its sandbox TestClient startup stalled; it was interrupted (exit 130), not reported as a pass. A timeout diagnostic confirmed the event-loop portal wait. The same HTTP denial test passed outside the sandbox (1 passed in 3.37s). The successful full outside-sandbox regression results above supersede these development runs.

Sandbox `npm ci` failed with esbuild `spawnSync ... EPERM`; the authorised outside-sandbox clean-install/check chain succeeded. Initial sandbox security scans failed DNS access; authorised network-enabled retries produced the actual audit outcomes above. Three sandbox runtime checks timed out (exit 124) after disposable migrations, during asynchronous startup; their outside-sandbox reruns passed. These environmental failures were not hidden or treated as application successes.

Remaining npm advisories: [GHSA-wrjc-x8rr-h8h6](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6), open redirect, and [GHSA-337j-9hxr-rhxg](https://github.com/advisories/GHSA-337j-9hxr-rhxg), SSR hydration constructor injection. npm proposes a major Router upgrade (7.18.6); no unrelated frontend upgrade was made. Existing CI security scans remain **advisory**, not blocking gates. Zero findings from a scanner are not a production security certification.

## Files and scope

New Phase 2 implementation: `app/tournament_v1_models.py`, `app/tournament_v1_schema.py`, `app/tournament_prize_preview.py`, `app/services/tournament_v1.py`, additive `j20261120tv1` migration, `tests/test_tournament_v1.py`, `docs/tournament-financial-policy.md`.

Updated model registration, shared review key reservation, V1-only legacy-path guards (`app/crud.py`, `app/services/matches.py`, `app/services/tournaments.py`), migration verifier/head assertions, backend CI timeout headroom, README, architecture/policy-question documentation and this report. Prior Phase 1 model/service/schema/migration/test/docs and shared operation/wallet key guards remain present. No dependency upgrade, historical migration rewrite, financial business-rule change to legacy paths, commit, push or merge was performed.

## Remaining risks and activation requirements

This is review infrastructure, not a payment system. A consistent review report does not prove external settlement or custody. SQLite serialises all writers; PostgreSQL requires a reviewed locking/trigger port. Database-owner privileges can remove triggers; services fail closed on changed/missing triggers, but least-privilege deployment remains necessary. Match/bracket completeness requires staff evidence; omitted intended matches cannot be inferred from nonexistent rows. Unsupported tie/disqualification cases require policy approval rather than an automatic rule. Refund review headroom is conservative and has no rejection-release workflow. Old reviewed revisions can be reported stale/superseded without deleting their audit history.

Future activation needs separately approved token and custody/clearing policies, supported balanced financial operation types, trusted provider evidence, an independently reviewed funded-pool/paid-confirmation/payout/refund contract, and security/reconciliation review. No production activation is recommended in this task.

## Final preservation evidence and Git status

Original `snooker.db` SHA-256 before and after all implementation/tests is identical:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa
```

The source was read only for checksum and SQLite backup compatibility verification; migrations, adoption stamps, seeding and all financial test postings affected disposable databases only. No original rows were relabelled, converted or migrated. No production server was started; test clients and verification lifespans closed. No commit, push or merge was performed. `git diff --check` returned 0 after verification; actionlint returned 0 after the CI timeout edit. Hosted CI has not been run or claimed passed.

Final branch: `feature/tournament-financial-orchestration`; HEAD remains `d6cb7b5`. The working tree contains 28 modified/untracked paths, including preserved Phase 1 work:

```text
 M .github/workflows/ci.yml
 M .gitignore
 M README.md
 M app/crud.py
 M app/models.py
 M app/services/financial_operations.py
 M app/services/financial_wallets.py
 M app/services/matches.py
 M app/services/tournaments.py
 M docs/database-architecture.md
 M docs/database-migration-guide.md
 M scripts/verify_migrations.py
 M tests/test_migrations.py
?? app/services/tournament_financials.py
?? app/services/tournament_v1.py
?? app/tournament_financial_models.py
?? app/tournament_financial_schema.py
?? app/tournament_prize_preview.py
?? app/tournament_v1_models.py
?? app/tournament_v1_schema.py
?? docs/tournament-financial-architecture.md
?? docs/tournament-financial-policy-questions.md
?? docs/tournament-financial-policy.md
?? migrations/versions/i20261120tfin_add_tournament_review_identities.py
?? migrations/versions/j20261120tv1_add_inactive_explicit_tournament_v1_.py
?? results/tournament_financial_implementation_report.md
?? tests/test_tournament_financials.py
?? tests/test_tournament_v1.py
```

Ready for code/policy review and subsequent commit/hosted CI verification by the user. **Not ready for financial activation.** Token/custody/clearing/refund execution policies and the two moderate frontend dependency entries remain outstanding.

---

# Historical Phase 1 report (preserved)

# Task 04C tournament financial implementation report

## Status and approval boundary

**Implemented: audited rules, policy questions, immutable policy-blocked review identities,
key reservation and read-only consistency diagnostics. Monetary tournament orchestration is
NOT implemented or approved.** Fee collection, refund eligibility/amounts, payout scheduling,
50/30/20 prize allocation and 10% token allocation remain blocked pending explicit decisions.
An approval question was submitted after the audit and before implementing any monetary rule.
No reply/approval was received; absence of a response was not treated as approval.

This is the safe, policy-neutral part of Task 04C, not a claim that tournament financial
behaviour or real-money workflows are complete. The required outstanding decisions are in
`docs/tournament-financial-policy-questions.md`.

## Baseline and inspection

Branch feature/tournament-financial-orchestration, baseline d6cb7b5. Initial working tree clean.
The preceding verified baseline has 276 backend tests and 33 frontend tests. Tournament/model/
registration/match/prize services, HTTP CRUD, financial-operation/wallet/evidence architecture,
shared guards, tests, migrations, docs and repository references were inspected before changes.
No .env contents or credentials were printed.

Read-only original SQLite inspection: integrity OK, zero FK violations; 18 players, 3 tournaments,
1 match, 4 registrations, 0 results and 16 ledger rows. All three tournaments are PENDING; all
four registrations have paid=0 and waived=0. These observations do not establish currency,
settlement, eligibility or an available prize pool. Original checksum evidence is below.

## Actual rules and ambiguities

| Area | Current executable behaviour / gap |
|---|---|
| Fees | Legacy integer entry_fee has unknown currency/units. HTTP rejects every nonzero fee. Free registration alone proceeds under current ownership/assignment/admin checks. |
| Contributions | paid/waived/contribution exist, default false/false/zero, but do not gate helpers or determine the legacy pool. No partial-payment/waiver/deadline/capacity policy exists. |
| Refunds/cancellation | CANCELLED enum exists, but no tournament/registration cancellation/refund workflow, eligibility/cap/funding rule or original-fee linkage exists. Operation CANCELLED is not reversal of a posted fee. |
| Legacy pool | entry_fee × every registration; no actual-collection, paid, waived, contribution, custody or reconciliation logic. |
| Claimed 50/30/20 | No checked default/call site/test establishes it as policy (the generic helper accepts arbitrary splits). Function defaults to (1.0,) = 100% to first winner; existing test passes (0.6,0.3,0.1). These were preserved, not replaced. |
| Claimed 10% tokens | No financial token allocation/asset/unit/recipient/funding implementation found. Auth tokens are unrelated. No deduction from the pool was inferred. |
| Existing prizes | Transient final_standings, arbitrary shares, float round(...,2), missing-player skip, zero later shares if split short, direct legacy balance credits; no ledger/idempotency marker. Repeats can pay again. |
| Registration duplicates | CRUD/service check plus unique tournament/player pair. No cancellation state or payment-backed eligibility. |
| Completion | Registered winner IDs, unique positions 1–4, rejects COMPLETED; permits empty/incomplete standings and the same player in multiple positions. Stores results/status only, no payout. |
| Match route | CRUD overwrites results without participant/score/registration checks, marks tournament completed when existing winners are non-null; does not derive authoritative standings. |
| Separate Elo helper | Checks winner membership/repeat result, but is not the route path and lacks complete bye handling. First-round shuffled knockout generation is not a complete ranking algorithm. |
| Authority | Tournament assignment/admin is not independent financial maker/checker approval or trusted payment evidence. Existing Task 04B rules remain intact. |

Approval is needed for prize rule priority, pool funding, token definition/denominator/deduction,
new explicit BWP pricing and eligibility, cancellation/refund rules/provenance, authoritative
rankings/corrections, rounding/remainders and payment evidence. No such rule was silently chosen.

## Implemented safe architecture

`TournamentFinancialIntent` represents an immutable review aggregate for an existing registration
(FEE/REFUND) or persisted result (PAYOUT). Every row stays POLICY_REQUIRED, with amount, currency,
FinancialOperation and receipt NULL by CHECK constraint. UUID4 IDs, foreign keys, source bindings,
semantic uniqueness and a SHA-256 source fingerprint are durable. A review is not an obligation,
refund entitlement, payable winner or approval. One review per context does not select a future
maximum number of instalments/refunds/payout versions.

`TournamentFinancialRequest` independently binds every distinct UUID4 request key to its actor,
role snapshot and aggregate. A different key returning an existing aggregate is still recorded;
that key cannot later be reused for a different context. Exact retries add no duplicate rows.
Conflicting reuse fails. Six triggers protect context/authority and immutable intent/history.
Service transactions verify their definitions before work.

`TournamentFinancialService` reuses FinancialOperationService's guarded transaction, which reuses
FinancialWalletService's owned SQLite BEGIN IMMEDIATE/rollback/original-DB protection. Real JWT/
session validation and current tournament admin/assigned-organiser checks precede replay. Wallet
ownership alone grants no tournament-review authority. Financial reconciliation requires admin.
No client amount/currency/actor override or status promotion is supported.

Both core financial services reject blocked review IDs/request keys as monetary identifiers.
The new layer never calls operation request/verification/posting or legacy prize distribution.
create_operation/post_intent/allocate_tokens explicitly deny unapproved rules, including for
admins. Existing maker/checker, trusted evidence, BWP arithmetic and atomic posting regressions
remain. No callback is wired to registration, cancellation, match completion or prize payment.

Metadata reconciliation compares source fingerprints/request history and checks for improper
FinancialOperation/ledger activity using blocked identifiers. It diagnoses duplicate/unregistered
rankings, position anomalies, completed-without-standings, invalid winners/negative scores and
unfinished completed matches. It never edits results, allocates funds or silently chooses ties.
prize_pool/token_allocation stay None, policy_required=True and monetary_flow_ready=False even
when metadata is consistent. Unrelated generic operations cannot be attributed to tournaments
without approved provenance; a funded financial-pool reconciliation is not claimed.

## Additive migration

```text
<base> -> dd093dfa2ebf -> d27f9a18494f -> e20261119db01
       -> f20261120auth -> g20261120fin -> h20261120ops
       -> i20261120tfin (single head)
```

The new revision creates only tournament_financial_intents, tournament_financial_requests,
constraints/indexes and six protections; all six historical revisions are unchanged. No original
column/row is altered or backfilled, and no monetary or token operation is generated. Populated
review downgrade refuses data loss. An empty review schema can downgrade/re-upgrade while
preserving existing funded wallets, operations, audit and users. Tests verify populated h data
row-for-row through i migration/empty rollback and preserve pending review metadata on refused
rollback. Known-version copy verification supports h as a baseline and validates all three sets
of financial/review trigger SQL. Original data is opened read-only; any explicit verification
stamp affects only a disposable copy.

## Actual verification results

| Verification | Actual result |
|---|---|
| Python 3.11.15 `python -m pytest -q -W error` | **304 passed**, 0 failures, 0 warnings; **969.35s** |
| Python 3.12.3 `python -m pytest -q -W error` | **304 passed**, 0 failures, 0 warnings; **798.85s** |
| Both versions: `python -m scripts.verify_migrations --existing-copy-from snooker.db` | Passed: fresh graph/current/upgrade/check, empty roundtrip, ORM and all financial/review trigger SQL, source-copy row/value preservation |
| Both versions: `python -m black --check .` | Passed; **62 files unchanged** |
| Runtime-only Python 3.12 `python -W error -m scripts.verify_dependency_environment --runtime-only` | Passed: no dev-only runtime imports, migrated startup, unchanged authenticated API snapshot and unauthenticated denials |
| Python 3.11 runtime/API verification | Passed, unchanged contract |
| Runtime-only review smoke | Passed: real JWT, three blocked identities, exact retry, null money/currency/bindings, zero operations/ledger, token/post denial and consistent metadata; legacy fee/unpaid flag unchanged; disposable DB removed |
| `npm run typecheck` | Passed |
| `npm run test:ci` | **33 passed**, 5 suites; **8.516s** |
| `npm run build` | Passed; 104 modules; **3.03s**, dist/index.html and deployable assets; JS 241.69 kB (81.00 kB gzip), CSS 1.44 kB |
| Bandit 1.9.4 | Passed, no findings |
| pip-audit 2.10.1, full resolved backend graph | Exit 0; **no known vulnerabilities found** |
| `npm audit --json` | Exit 1; **2 existing moderate Router package entries**, 0 high/critical; no unrelated upgrade |
| actionlint 1.7.7 | Passed, no diagnostics |
| Protected source/history/API/workflow diff | No change to all six historical revisions, legacy prize/match/registration rules, money/auth/evidence contracts, frontend source/lock or CI workflow |
| `git diff --check` | Passed |
| Original checksum/integrity/FK checks | Unchanged checksum, integrity OK, no FK violations |
| `git status --short` | Only intended new/modified source/tests/docs/migration/report; no publication operations |

Final count is 276 existing + 26 new policy-neutral review tests + 2 new migration tests = **304**.
No verification test/build/migration command failed during this task. npm audit's nonzero result
is explicitly retained above; pip-audit's recommendation to hash dependency artifacts remains.
Security scans remain advisory in the unchanged workflow. Hosted CI was not run or claimed;
local matrix timings reflect parallel SQLite workloads and hosted job timing remains unverified.
No dependency upgrade or global warning filter was introduced.

Focused tests passed before final full runs: 26 new review tests in 54.57s; all 18 migration
tests in 43.91s. Final full runs were started after source/tests/migration implementation was
stable; no Python source or tests were modified while they ran. No test assertions were weakened,
warning suppression added, or old financial/security tests removed. Existing migration-head and
failure-test references were updated for the additive revision only.

New tests exercise all three blocked identities, exact/different-key/concurrent retries,
conflicting context keys, current roles/assignments/revocation, no admin policy bypass, no amount/
currency override, core operation/wallet key refusal, old-operation non-adoption, immutable source
changes, invalid standings/matches, repeated completion without financial operations, metadata
rollback/retry, DB monetary/promotion refusal, trigger protection and additive migration safety.
Positive new tests assert no FinancialOperation or ledger creation; existing Task 04B tests still
simulate trusted evidence only in test fixtures. No real payment/settlement verification occurred.

## Preservation evidence

Original snooker.db SHA-256 before and after:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa
```

All writes used disposable databases. Original source was never migrated, stamped, seeded,
converted or relabelled. Legacy prize calculations/tests, tournament/match CRUD/routes, legacy
wallet adapter, monetary arithmetic, auth/security, existing ledger/operation triggers and models,
all historical migrations, API snapshots, frontend source/lock and workflow are unchanged.
The two existing financial service changes add blocked-key reservation only. No provider
integration, fake successful confirmation, financial HTTP activation, commit, push or merge.

## Files created and modified

- `.gitignore`
- `README.md`
- `app/models.py`
- `app/services/financial_operations.py`
- `app/services/financial_wallets.py`
- `docs/database-architecture.md`
- `docs/database-migration-guide.md`
- `scripts/verify_migrations.py`
- `tests/test_migrations.py`
- `app/services/tournament_financials.py`
- `app/tournament_financial_models.py`
- `app/tournament_financial_schema.py`
- `docs/tournament-financial-architecture.md`
- `docs/tournament-financial-policy-questions.md`
- `migrations/versions/i20261120tfin_add_tournament_review_identities.py`
- `tests/test_tournament_financials.py`
- `results/tournament_financial_implementation_report.md` (this report)

## Outstanding blockers and next action

Explicit prize/token/fee/refund/payout policy remains the blocker for actual tournament monetary
orchestration. Confirm the intended new split versus observed defaults/test, token meaning and
whether/how it affects the pool, funded pool custody/conservation, new BWP pricing/eligibility,
refund provenance and amounts, authoritative rankings/revisions and rounding/remainder rules.
The full question list is in the policy document; no field default or admin flag answers it.

After policy approval, design concrete monetary intent versions/line items linked atomically to
Task 04B operations, independently authorised posting, fee/refund provenance and funded pool
reconciliation. Do not reuse an unrelated generic fee or assume legacy scalar currency. External
provider integration and all financial HTTP writes remain separately unapproved.

Legacy direct prize repetition/float risks and weak match/ranking validation remain deliberately
unchanged. Diagnostics do not repair them. Current reconciliation covers metadata only, not a
monetary prize pool or external settlement. SQLite-only writer serialisation, privileged database
or server tampering, audit retention/monitoring, historical adoption and existing Router advisories
remain limitations. No hosted CI, production readiness or complete Task 04C monetary workflow
success is claimed. Safe groundwork is ready for review; policy decisions are required next.
