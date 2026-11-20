# Task 02C — Dependency compatibility, security and reproducibility

Date: 2026-11-20. Branch: `fix/ci-pipeline-triggers`. Parent commit: `6985d07`.
Task 02B's uncommitted changes were preserved and extended. No commits, pushes, merges or
remote workflow dispatches were performed.

## Outcome and root cause

Fresh runtime and development environments now work on **Python 3.11.15 and 3.12.3**.
Each passes the existing **42 tests with warnings as errors**, migration/ORM checks and
existing-data-copy compatibility. Frontend retains **20 passing tests**, typecheck and build.
Complete resolved runtime, development and scanner package audits have no known findings;
two existing moderate frontend Router advisories remain, requiring a separate major upgrade.

The old FastAPI 0.111.0/Starlette 0.37.2 graph imported deprecated `multipart`. The old environment
had python-multipart 0.0.9; clean resolution chose 0.0.34, whose namespace shim warned. Strict
collection and both import-safety subprocess tests correctly failed. No warning was suppressed,
installed source patched, test skipped or assertion weakened to repair it.

Audited requirements/config, all application/test imports, scripts, migrations, pre-commit,
legacy task configuration and CI. No active Docker/deployment manifest establishes a need for
asyncpg. The legacy task YAML references Docker and type tooling but is not a verified deployment
configuration; it was not executed (it also contains commit/push commands outside authorization).

## Versions and classification decisions

| Package | Before | Final | Reason |
|---|---|---|---|
| FastAPI | 0.111.0 | 0.163.2, minimal installation | Supported modern framework; patched request-parameter DoS; avoids optional CLI/cloud/template/email extras |
| Starlette | 0.37.2 | 1.10.0 | Multipart/host/path/method security fixes plus compatibility with current AnyIO without deprecated aliases |
| python-multipart | 0.0.9 baseline / 0.0.34 fresh | 0.0.34 explicit | Retain modern parser; no insecure downgrade to hide the import warning |
| Pydantic | 2.7.1 | 2.12.5 | FastAPI requires >=2.9; verified schemas and strict regressions |
| pydantic-core | 2.18.2 direct pin | 2.41.5 transitive constraint | Exact version required by selected Pydantic |
| pydantic-settings | Imported but undeclared | 2.14.2 | Preserve dormant module import; patched nested-secrets advisory |
| annotated-types | 0.7.0 direct | 0.8.0 transitive | Remove redundant direct declaration; fully constrained |
| typing-extensions | 4.15.0 direct | 4.16.0 transitive | Shared complete resolution for framework/typing/plugin requirements |
| Uvicorn[standard] | 0.30.0 | 0.30.0 | Retained; actual HTTP startup verified with locked standard extras |
| SQLAlchemy | 2.0.30 | 2.0.30 | Retained; no financial/schema/migration rewrite |
| Alembic | 1.13.1 | 1.13.1, runtime | Shipped db CLI imports it; migrations unchanged |
| HTTPX | 0.27.0 | 0.27.0, development | Existing async test imports retained |
| HTTPX2 | Absent | 2.16.2, development | Supported current Starlette TestClient; separate import namespace |
| Black | 24.4.2 | 26.10.1 | Verified patched formatter; current advisory-compatible maintenance release |
| pytest | 8.2.1 | 9.0.3 | Verified published fix for temporary-directory advisory |
| pytest-asyncio | 0.22.0, yanked | 1.3.0 | Supports pytest >=8.2,<10 and Python >=3.10; strict async regression passes |
| pytest-cov | 4.1.0 | 4.1.0 | Retained; explicitly exercised with patched pytest |
| isort / mypy | 5.13.2 / 1.10.0 | Unchanged, development | Still referenced by pre-commit/legacy task configuration |
| asyncpg | 0.29.0 | Removed | No imports/async engine or verified PostgreSQL deployment; current DB is sync SQLite |
| sqlalchemy2-stubs | 0.0.2a38 | Removed | 1.4-era stubs conflict with SQLAlchemy 2 native typing; no imports |
| pip bootstrap | 24.0 in fresh venv | 26.3 | Remediate findings in bundled tooling; reproducible bootstrap |
| setuptools bootstrap | 79.0.1 bundled with 3.11 | 84.2.1 | Remediate bootstrap findings, pin equally across both versions |
| pip-audit / Bandit | Ad hoc scanners | 2.10.1 / 1.9.4 | Separate pinned scanner environment/constraints; advisory CI |

The final resolved graphs, including bootstrap tools, have identical package versions across
both tested interpreters: runtime 29 packages; development 51. All versions, including conditional
platform dependencies, are in the generated constraints. No unrelated frontend package changed.

## Security evidence and applicability

Official metadata/release/advisory links and affected ranges are documented in
[dependency management](../docs/dependency-management.md#security-sources-and-limitations).
All audits used pip-audit 2.10.1 installed in an external scanner environment, not in the target.
Targets were exact `pip freeze --all` manifests; `--no-deps --disable-pip` prevented re-resolution
and mixing scanner dependencies into the audited graph. No vulnerability ignores were added.

| Finding | Verified status / remediation |
|---|---|
| Black CVE-2026-32274 / GHSA-3936-cmfr-pm3m / Safety 89047 | >=24.3.0,<26.3.1 affected; 26.3.1 patched. Final 26.10.1 is patched |
| pytest CVE-2025-71176 / GHSA-6w46-j5rx-g56g | <9.0.3 affected; official 9.0.3 release selected; CI also uses private basetemp |
| pytest-asyncio 0.22.0 | Official PyPI says yanked because deprecated functionality lacked reasonable replacements; non-yanked 1.3.0 selected |
| FastAPI GHSA-f56c-v883-vx8r | >=0.123.2,<0.163.2 affected; old 0.111.0 is outside that range, but intermediate upgrades could enter it. Final 0.163.2 is patched |
| Starlette baseline 0.37.2 | Scanner reports 7 distinct advisory alias groups: multipart DoS (fixes 0.40.0/0.47.2), host poisoning (1.0.1), Windows StaticFiles/method dispatch (1.1.0), hostname poisoning (1.3.0), URL-encoded form limits (1.3.1). Final 1.10.0 has no audit findings |
| python-multipart 0.0.9 | Predates multiple official multipart DoS/parser/file-write fixes. Modern 0.0.34 retained; final resolved audit has no finding |
| pydantic-settings candidate 2.12.0 | Audit found CVE-2026-58203/GHSA-4xgf-cpjx-pc3j, >=2.12.0,<2.14.2. Replaced with patched 2.14.2; nested-secrets feature is not used here |
| Python 3.11 bundled setuptools 79.0.1 | Audit found PYSEC-2026-3447 and GHSA-xmj3-9gf7-h52w (patched 83.0.0/84.1.0). Final bootstrap 84.2.1 has no finding |
| Old pip 24.0 | Baseline audit reports 6 distinct alias groups, fixes through 26.2; pinned 26.3 passes final audit |
| Other Black action advisories | Black action parsing issues are outside this workflow's pip invocation. Official GHSA-cg8m-r9f2-5wm2 affects 26.9.0/26.10.0, despite the scanner also reporting it against old Black; applicability was reviewed. Final 26.10.1 avoids those findings too |

The prior clean baseline full graph contained 57 packages. pip-audit returned 32 raw records
in 4 packages (Black, pip, pytest, Starlette), including repeated aliases/records: 17 distinct
per-package alias groups, not 32 unique CVEs. Some scanner applicability was broader than the
official Black advisory. The final result is not obtained by ignoring those records.

Final audit results:

| Graph | Python | Packages | Known findings | Exit |
|---|---|---:|---:|---:|
| Runtime | 3.11 | 29 | 0 | 0 |
| Runtime | 3.12 | 29 | 0 | 0 |
| Development | 3.11 | 51 | 0 | 0 |
| Development | 3.12 | 51 | 0 | 0 |
| Isolated scanners | 3.12 | 33 | 0 | 0 |

Bandit 1.9.4 scanned 885 application lines: zero findings, zero errors, zero skipped tests/nosec
exemptions. Zero findings is scoped to known scanner data/rules at scan time, not a certification.
CI scanners remain advisory via continue-on-error, and can be skipped after earlier failures.
The deprecated Safety check was replaced with supported pip-audit over resolved packages.

## Dependency architecture and reproducibility

- `requirements.txt` includes runtime `.in` declarations and shared transitive constraints.
- `requirements-dev.txt` references runtime requirements plus development declarations.
- `requirements-security.txt` includes its own independent constraints/bootstrap/tools.
- `requirements/bootstrap.txt` pins pip/setuptools; application and scanners use clean external
  environments. No packages were installed into the tracked repository virtualenv.
- uv 0.11.23 generated universal constraints with Python 3.11 as the minimum; actual 3.11/3.12
  runs verify those resolutions. Existing output pins are reused unless a deliberate update is
  requested; versions/markers are reviewed artifacts, with regeneration commands documented.
- This is full version pinning, not artifact-hash locking. Wheel choice, interpreter patch,
  platform ABI and index availability remain reproducibility limits. pip-audit's recommendation
  for hash-pinned manifests was recorded, not hidden.
- Minimal FastAPI avoids unnecessary default extras. Required OpenTelemetry API remains because
  selected FastAPI declares it; no optional SDK/exporter/cloud CLI was requested.

## Actual fresh-environment results

External work root: `/tmp/snooker-deps-02c-lv0pxbk4`. Python 3.12.3 was preinstalled; universal
resolution downloaded CPython 3.11.15, which was then tested rather than claiming it unavailable.
`python311`/`python312` began as runtime-only environments and then received development tools.
`runtime-final311`/`runtime-final312` independently verified the settled final runtime from scratch.

| Command/check | Python 3.11.15 | Python 3.12.3 |
|---|---|---|
| Fresh bootstrap + runtime install | Passed (pip) | Passed (pip) |
| Runtime pip check | Passed | Passed |
| `python -W error -m scripts.verify_dependency_environment --runtime-only` | Passed | Passed |
| Development installation | Passed (pip) | Passed (uv fallback after local pip TLS errors) |
| Development pip check | Passed | Passed |
| `python -m pytest -q -W error` | 42 passed, 0 warnings, 44.29 s | 42 passed, 0 warnings, 39.07 s |
| `python -m black --check .` | Passed | Passed |
| `python -W error -m scripts.verify_dependency_environment` | Passed | Passed |
| `python -m scripts.verify_migrations --existing-copy-from snooker.db` | Passed | Passed |
| Actual Uvicorn HTTP smoke | /health and /tournaments/ HTTP 200 | /health and /tournaments/ HTTP 200 |

HTTP checks ran only against disposable migrated databases; both temporary servers were stopped.
The runtime verifier imports every application module without pytest/Black/HTTPX/HTTPX2 present,
checks lifespan, public empty lists and missing-player 404, and compares the original API snapshot.
No runtime import depends on development-only packages.

`python -m pytest -q -W error --cov=app ...` additionally passed all 42 tests on 3.12 with 88%
application coverage, verifying retained pytest-cov 4.1.0. XML output was outside the repository;
the pre-existing tracked `.coverage` artifact was restored to its exact initial bytes afterward.

Intermediate failures were investigated, not hidden:

- Candidate Starlette 1.3.1 first warned when TestClient fell back to HTTPX. Adding the documented
  HTTPX2 dependency exposed its deprecated AnyIO BlockingPortal alias. Final Starlette 1.10.0
  and HTTPX2 resolve both without changing tests or suppressing warnings.
- Candidate pydantic-settings 2.12.0 and bundled setuptools failed their audits; patched pins
  replaced them and all graphs were audited again.
- Python 3.12 pip wheel downloads repeatedly failed with TLS `DECRYPTION_FAILED_OR_BAD_RECORD_MAC`.
  The same constrained versions installed successfully using uv's transport; pip check and
  strict tests/audits passed afterward. TLS verification was not disabled or bypassed.
- An initial external smoke harness needed its import path corrected; sandboxed asynchronous
  checks stalled and were interrupted/rerun outside the sandbox. The committed ASGI harness now
  models request/disconnect waiting correctly; final runtime/development checks completed.
- Black initially requested formatting of the third historical revision; it was excluded instead
  of modified. Only one existing test blank line changed; AST comparison verified equivalence.

## API compatibility and regression evidence

`docs/backend-openapi.json` was **not overwritten**. The verifier compares all paths/methods,
parameters, request bodies, schemas, responses/status codes, operation metadata and model fields.
The only differences are optional `ctx` and `input` properties in FastAPI's generated
ValidationError documentation. They are explicitly reviewed and normalized only in the verifier;
application schemas are compared exactly. No business response/request contract changed.

Existing wallet deposits/withdrawals, transaction history, tournament registration/completion,
Elo/matches and error scenarios remain covered by the same 42 regression tests, against isolated
fixtures. No live financial operation or financial calculation was changed. No new test assertion
was needed to mask framework differences. Health/list/404 responses were also tested directly
without a development client. The command distinguishes real HTTP smoke from direct ASGI checks.

## Frontend and workflow verification

- `npm ci`: passed; 439 installed, 440 audited, deprecation notices and two moderate advisories.
- `npm run typecheck`: passed.
- `npm run test:ci`: 5 suites / 20 tests passed, 0 failed, 10.859 s.
- `npm run build`: passed, 100 modules, dist/index.html and CSS/JS assets, 2.88 s.
- `npm audit`: exit 1; two moderate Router advisory entries remain. Installed Router 6.30.6 is
  affected by GHSA-wrjc-x8rr-h8h6 (CVE-2026-53669) and GHSA-337j-9hxr-rhxg (CVE-2026-53666).
  Fixed >=7.18.0; npm proposes Router DOM 7.18.6, a major upgrade. No unrelated upgrade was made.
- actionlint 1.7.7: passed against final workflow. YAML structure/matrix/trigger preservation
  checked; no GitHub-hosted run or remote success is claimed.
- `git diff --check`: passed. Original database checksum unchanged.

Task 02B triggers, matrix, Node 24 job, permissions, concurrency and timeouts are preserved.
CI creates its backend virtualenv in runner temp, verifies runtime isolation before adding dev
dependencies, uses pip check and strict pytest, preserves migrations/Black, and adds the API
compatibility check. All requirement/constraint inputs participate in caching. Scanner tools
are isolated and pinned; Bandit and pip-audit remain non-blocking advisory steps.

## Files created and modified

Created:

- `requirements-dev.txt`, `requirements-security.txt`.
- `requirements/{runtime.in,development.in,scanners.in,bootstrap.txt,constraints.txt,scanners-constraints.txt}`.
- `scripts/verify_dependency_environment.py`.
- `docs/dependency-management.md`, this report.

Modified beyond preserved Task 02B changes:

- `requirements.txt`: runtime entry point only.
- `.github/workflows/ci.yml`: isolated locked installs, complete cache paths, private test temp,
  API check and isolated advisory scanners.
- `app/core/config.py`: only the deprecated settings Config conversion; no auth implementation
  or secret behavior changes. Dormant legacy configuration remains unused by the real DB engine.
- `pytest.ini`: explicit pytest-asyncio mode/loop scopes, no warning filters.
- `pyproject.toml`, `.pre-commit-config.yaml`: patched formatter/Python target and preserve all
  historical revisions, including the already committed Task 02 correction.
- `tests/test_tournament_flow.py`: one blank line only, identical AST/assertions.
- `README.md`, `docs/database-migration-guide.md`: external environment and split install guidance.
- `results/ci_pipeline_report.md`: dated Task 02C resolution/current-state addendum while retaining
  actual historical Task 02B failures.
- `.gitignore`: allow new implementation reports.

No other application source, schema, database engine, services, financial logic, frontend source,
package-lock, OpenAPI snapshot or historical migration files were changed.

## Repository environment maintenance audit

Only `venv/` is tracked: 5,726 files, 116,903,317 uncompressed tracked bytes (~111.5 MiB).
`.venv/` is untracked/ignored. This is current-tree logical content, not compressed Git pack
attribution or a promise of reclaimable history space. The tracked pycparser-2.23 dist-info
lacks METADATA, confirming the previous invalid-metadata warning.

Fresh external environments successfully replace it for runtime, development and scanners.
No tracked environment was used as a testing/installation target or removed. The management
guide gives a later, separately reviewed `git rm --cached` procedure that preserves local files;
it was not executed. History cleanup/rewrite is explicitly deferred.

## Data preservation, blockers and readiness

Original SHA-256 before and after:

```text
7de882a4d5bf8f194c5f31f4aabbaed1178879bc7798f58efb7b3ad8205b28fa  snooker.db
```

All database operations were temporary or against a disposable read-only-source backup.
The original remains unstamped/unmigrated. Historical migrations and OpenAPI snapshot match
HEAD byte-for-byte. No credentials or `.env` contents were printed; settings-module verification
ran from a temporary directory. No authentication, financial rules or record changes were made.

There is no remaining local backend clean-install/test/migration/security-audit blocker.
The change is ready for review and an explicit user commit/push followed by real hosted CI
verification. It is not a production-readiness or hosted-success claim. Frontend Router findings,
existing financial/access-control risks, unused placeholder settings, lack of artifact hashes,
interpreter/OS security and vulnerability-database coverage remain limitations. Pytest's official
patched release is used, while upstream shared-temp/TOCTOU discussion still warrants private
temporary directories. No vulnerability ignores or global warning suppression were introduced.
