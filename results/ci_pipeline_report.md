# Task 02B — GitHub Actions CI pipeline report

Branch: `fix/ci-pipeline-triggers`. Parent: `6985d07`.
Workflow: `.github/workflows/ci.yml`, workflow ID `189363310`.

## Task 02C follow-up — 2026-11-20 (current state)

The clean-install blocker recorded below is resolved. Fresh external Python 3.11.15 and
3.12.3 environments each pass all 42 backend tests with warnings treated as errors. Runtime
and development dependency/version lists match across the two interpreters; full resolved
runtime (29 packages) and development (51 packages) pip-audit scans report no known findings.
Migrations, ORM consistency, disposable-copy compatibility, Black and actionlint pass. Frontend
remains 20 passing tests, a passing build, and two unresolved moderate Router advisories.

Task 02B trigger patterns, permissions, concurrency, timeouts and the Node 24 job are retained.
CI now creates an isolated backend virtualenv, installs pinned bootstrap/runtime dependencies,
checks runtime-only imports/startup/API compatibility, then installs requirements-dev and runs
strict tests with a private runner basetemp. Cache inputs cover every requirements/constraints
file. The deprecated Safety check is replaced by pinned pip-audit, and Bandit/pip-audit run in
a separately constrained scanner virtualenv. Scans remain advisory, not blocking gates.

See [the dependency report](dependency_stabilization_report.md) for versions, actual commands,
security sources, candidate failures and final results, and
[dependency management](../docs/dependency-management.md) for installation/lock maintenance.
No hosted run has been executed or observed. Local success supports review and committing;
only a real remote run can establish GitHub-hosted success. The sections below preserve the
Task 02B historical results, not the current dependency state.

## Root cause and outcome

The original `push.branches` filter contained only `main` and `develop`, excluding development
branches from push verification. Pull request filters apply to the target branch and did not
provide push verification for feature/fix/chore branches without a qualifying PR.

The requested triggers and reliability changes are implemented locally. Workflow syntax and
local frontend/migration/format checks pass. **Fresh backend verification is not green:**
a clean dependency install exposes an existing Starlette/python-multipart deprecation
incompatibility. The established environment passes all 42 tests, but a fresh runner is expected
to fail the strict pytest step until that compatibility issue is resolved. No tests were skipped,
assertions weakened, warnings suppressed, application code changed or older dependencies pinned
to conceal it. Trigger activation is ready for review; an all-green hosted pipeline is not claimed.

## Workflow changes

- Push verification: `main`, `develop`, `feature/**`, `fix/**`, `chore/**`,
  `stabilization-phase-2` (nested development branch names are included).
- Pull requests targeting `main` and `develop` retained; `workflow_dispatch` retained.
  GitHub requires the workflow to exist on the default branch for manual-dispatch availability.
- Minimum explicit token scope: `permissions: { contents: read }`. No deployment, PR write,
  secret, OIDC, package-publish or repository-write permission was introduced.
- Concurrency group `${{ github.workflow }}-${{ github.ref }}` with cancellation of superseded
  runs. Runs on different branches/PR refs remain independent. A feature push plus a PR event
  may still create two runs because push and PR refs differ; this preserves both checks.
- Backend matrix remains Python 3.11 and 3.12. Timeout 20 minutes per matrix job.
- Frontend remains Node 24, with unchanged checkout/setup/npm ci/typecheck/Jest/build steps.
  Timeout 15 minutes.
- Pytest runs `python -m pytest -q -W error`, making regressions/warnings blocking. The baseline
  supports it; clean-install incompatibility is reported below rather than ignored.
- Alembic/ORM verification and Black check are unchanged blocking commands.
- Dependency installation is unconditional `python -m pip install -r requirements.txt`:
  missing requirements now fail rather than silently succeeding; removed the unnecessary
  unpinned pip self-upgrade. No application requirements/lockfile versions were changed.
- Bandit/Safety retain their scan commands. Replaced shell `|| true` with explicit
  `continue-on-error: true`, advisory step names and five-minute step timeouts. Actual failing
  step outcomes/logs remain visible, but findings and scanner installation/service errors
  do not fail the job. This also makes scanner installation failures advisory; formerly an
  install failure could block even though the scan command failure was swallowed.

### Pip cache investigation

There were not two active pip caches: the baseline used one separate `actions/cache` step.
Its key omitted Python version and restored broad OS-only prefixes across the matrix. It was
replaced, not supplemented, by `actions/setup-python@v5`'s `cache: pip` and
`cache-dependency-path: requirements.txt`. The built-in key includes interpreter, OS,
architecture and requirements hash. Cache stores pip download/wheel artifacts, not a virtualenv;
each runner still executes dependency installation. No duplicate standalone cache remains.

## Files modified/created

- `.github/workflows/ci.yml`: triggers, permissions, concurrency, cache, timeouts, strict pytest,
  advisory scanner visibility.
- `README.md`: brief CI trigger/verification/advisory scan explanation.
- `.gitignore`: explicitly unignore this report so it can be reviewed/committed normally.
- `results/ci_pipeline_report.md`: this report (created).

No application, test, financial, authentication, dependency declaration or migration history
changes. No commits, pushes, merges, remote dispatches or GitHub settings changes performed.

## Local verification — actual results

Verification used Python 3.12.3 and Node 24.11.1. Python 3.11 was not installed locally; that
matrix entry is preserved but not claimed as locally tested. A fresh temporary Python virtualenv
was created under `/tmp/snooker-ci-02b-uyvskpxh/backend`; scanner tools were installed in a
separate temporary `scanners` environment. The tracked repository virtualenv was not modified.

| Check | Actual result |
|---|---|
| YAML parsing and structural checks | Passed; all six push patterns, PR targets, dispatch, matrix, token scope and frontend steps verified |
| Branch glob examples | Seven included examples and three excluded examples behaved as intended |
| actionlint 1.7.7 | Passed, exit 0, no diagnostics |
| Fresh `python -m pip install -r requirements.txt` | Passed, exit 0; warning that existing pytest-asyncio 0.22.0 is yanked |
| Fresh `python -m pip check` | Passed: no broken requirements |
| Baseline `venv/bin/python -m pytest -q -W error` | 42 passed, zero warnings, exit 0, 23.94 s |
| Fresh `backend/bin/python -m pytest -q -W error` | Failed during conftest import, exit 4: multipart PendingDeprecationWarning becomes an error |
| Fresh diagnostic `backend/bin/python -m pytest -q` | 40 passed, 2 failed, 1 warning, exit 1, 21.58 s |
| Fresh `backend/bin/python -m black --check .` | Passed; 33 files would be unchanged |
| Fresh `backend/bin/python -m scripts.verify_migrations` | Passed: history/heads/current, fresh upgrade, ORM consistency, empty downgrade/re-upgrade |
| `npm ci` | Passed; 439 packages installed, 440 audited; 2 moderate advisories, dependency deprecation notices |
| `npm run typecheck` | Passed |
| `npm run test:ci` | 5 suites passed; 20 tests passed, 0 failed, 9.679 s |
| `npm run build` | Passed; 100 modules, dist/index.html plus CSS/JS, 2.67 s |
| Bandit 1.9.4 `-q -r app` (JSON output for review) | Exit 0; 886 lines, 0 findings, 0 scanner errors |
| Safety 3.8.1 `check -r requirements.txt` | Exit 64; completed scan of 17 declared packages, 2 vulnerabilities reported |
| `git diff --check` | Passed |
| Original `snooker.db` SHA-256 | Unchanged before/after checks |

Actionlint was not on PATH. Downloaded official version 1.7.7 into `/tmp` and verified the
published archive checksum before execution:
`023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757`.
No actionlint binary or virtualenv was added to the repository.

Scanner installation initially hit a TLS fetch failure and prolonged pip backtracking; it was
interrupted and the same initially selected Safety 3.8.1 was installed successfully on retry.
Safety help/startup in the sandbox also failed DNS resolution; a network-enabled actual scan
completed. Safety emitted tool-internal Authlib deprecation warnings and warned that the
legacy `check` command is deprecated. These do not change backend-suite warning counts.

### Fresh-install backend blocker

The established environment contains `python-multipart 0.0.9`; the clean requirements install
resolves `python-multipart 0.0.34`. Pinned FastAPI 0.111.0 resolves Starlette 0.37.2, whose
`starlette/formparsers.py` imports the old `multipart` namespace. The current multipart shim
emits:

```text
PendingDeprecationWarning: Please use `import python_multipart` instead.
```

Strict pytest fails at collection. Even dropping the outer strict flag does not make a clean
suite pass: both parameterizations of
`test_imports_do_not_create_or_mutate_databases` invoke a subprocess with `-W error` and fail
on that third-party import. Their non-mutation assertions were retained.

This is a real dependency compatibility blocker, not a workflow trigger error. The strict
CI gate intentionally remains blocking. Fix via a separately scoped, tested FastAPI/Starlette/
python-multipart compatibility update and repeat clean installs on both Python versions.
Do not blindly downgrade multipart to the old baseline or suppress all warnings. No dependency
upgrade/downgrade or test modification was made in this trigger-focused task. Later CI steps
retain normal success prerequisites and may be skipped when strict pytest fails.

## Security review and limitations

**Neither Bandit nor Safety is an enforced security gate.** Both use `continue-on-error`.
A green job means blocking tests/build/format/migration steps passed, not that these scans
completed successfully or found no issues. Normal step ordering also means scans can be
skipped after an earlier blocking failure. Their output is not uploaded as SARIF or artifacts.

Observed local results:

- Bandit 1.9.4 found no issues in its `app` scope (886 lines); this is not proof of application
  security. It does not replace authentication/financial-integrity review or inspect all
  repository files. Known Task 02 financial/access-control risks remain unchanged.
- Safety 3.8.1 reported Black 24.4.2: CVE-2026-32274, Safety ID 89047, affected range
  `>=24.3.0,<26.3.1` (cache filename path traversal).
- Safety reported pytest 8.2.1: CVE-2025-71176, Safety ID SFTY-20260122-20373, affected
  range `<9.0.3` (temporary-directory denial of service).
- This legacy requirements scan covered 17 declared packages; it is not a complete resolved
  transitive dependency audit. Safety's database coverage/licensing and service availability
  limit conclusions. No authentication or license changes were made.
- npm ci reported two moderate frontend dependency advisories; the existing Task 01/02
  React Router findings were not remediated by this task. No force-upgrade was performed.
- Scanner versions remain unpinned to preserve existing setup; installing scanners into the
  same hosted job environment may alter transitive packages after the blocking tests have run.
  Local review isolated scanners to avoid contamination of the clean backend verification.

Recommended follow-up before introducing blocking gates:

1. Resolve and test the fresh-install backend compatibility problem first.
2. Pin/isolate scanner tooling, select a supported Safety invocation or alternative, and verify
   service/database availability without production credentials. Account for fork PR limits.
3. Review findings and agree severity thresholds, ownership and time-bounded exceptions.
   Remediate flagged packages through explicit dependency-upgrade tasks; no blanket ignores.
4. Preserve scan reports, distinguish tool failures from findings, and then remove advisory
   `continue-on-error` for the agreed blocking scope. Configure branch-protection required
   checks only after successful hosted validation on both Python versions and Node 24.
5. Consider commit-SHA pinning of third-party actions and a resolved Python dependency lock.

## Database preservation and outstanding risks

Before and after implementation:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa  snooker.db
```

Fixtures override request/database URLs before app imports and use `TemporaryDirectory`;
the migration verifier supplies explicit temporary URLs. No production database or application
credentials are required by the workflow. No DB mutations were performed against the original.
No environment secret contents were read or printed.

The current fresh-install failure means hosted backend success must not be assumed. Python
3.11 and hosted runner/caching behavior still require real remote verification. Unpinned
transitive packages and advisory scan tooling remain reproducibility risks; the existing
pytest-asyncio pin is yanked. The original database remains unversioned as documented in Task 02.

## Commit, push and monitor commands — provided only, not executed

Review the fresh-install blocker before deciding whether to push for visibility or remediate
it first. Run from the repository root:

```bash
git diff --check
git diff -- .github/workflows/ci.yml .gitignore README.md
# Task 02B-only paths shown here historically; include the Task 02C files listed in
# results/dependency_stabilization_report.md when staging the combined change.
git add .github/workflows/ci.yml .gitignore README.md results/ci_pipeline_report.md
git commit -m "ci: enable development branch verification"
git push -u origin fix/ci-pipeline-triggers

gh run list --workflow 189363310 --branch fix/ci-pipeline-triggers --limit 10
# Replace RUN_ID with the ID returned above:
gh run watch RUN_ID --exit-status
gh run view RUN_ID --log-failed
```

Optional manual run after pushing, when dispatch is available on the default branch:

```bash
gh workflow run 189363310 --ref fix/ci-pipeline-triggers
```

No remote run was started or observed during this task. The supplied baseline says no remote
runs exist; this report does not claim current remote-run status was independently queried or
that GitHub-hosted CI has passed. Actual success requires a completed remote run after push
and resolution of the documented backend compatibility blocker.

References: [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[setup-python v5 pip cache implementation](https://github.com/actions/setup-python/blob/v5/src/cache-distributions/pip-cache.ts),
[actionlint release](https://github.com/rhysd/actionlint/releases/tag/v1.7.7).
