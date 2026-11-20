# Dependency management

Supported verification targets: CPython 3.11 and 3.12 on Linux/WSL. Node 24/npm use the
unchanged `package-lock.json`. Use an external virtualenv: the repository's `venv/` contains
tracked, incomplete generated files and must not be used as an installation target.

## Architecture

| File | Purpose |
|---|---|
| requirements.txt | Runtime entry point; includes runtime declarations and shared constraints |
| requirements-dev.txt | Includes runtime plus testing/formatting/development declarations |
| requirements-security.txt | Separate scanner entry point; includes patched bootstrap and scanner constraints |
| requirements/runtime.in | Reviewed direct runtime pins |
| requirements/development.in | Reviewed direct development pins |
| requirements/scanners.in | pip-audit and Bandit pins, isolated from application packages |
| requirements/constraints.txt | Generated complete runtime+development version resolution with environment markers |
| requirements/scanners-constraints.txt | Independently generated scanner transitive pins |
| requirements/bootstrap.txt | Exact pip/setuptools versions, including tools bundled by Python venv |

Constraints constrain versions without installing every entry. A runtime-only install does
not install pytest, HTTPX, HTTPX2, Black, mypy or the scanners. Development references the same
runtime graph, so both cannot silently resolve different framework versions. Installed Linux
Python 3.11 and 3.12 development package/version lists matched exactly during verification.

The constraints are version locks, **not artifact hash locks**. They pin all resolved packages
and include platform markers; wheel choice, Python patch version, OS ABI and package-index
availability remain environment-dependent. Do not claim bit-for-bit reproducibility or that
other OS/Python combinations were executed. Future artifact-hash enforcement can be added as
a separate improvement; no hash-checking or vulnerability warnings are suppressed here.

## Install runtime

From the repository root, using a new external environment:

```bash
python3.12 -m venv ~/.venvs/snooker-runtime
source ~/.venvs/snooker-runtime/bin/activate
python -m pip install -r requirements/bootstrap.txt
python -m pip install -r requirements.txt
python -m pip check
python -W error -m scripts.verify_dependency_environment --runtime-only
```

Use `python3.11` instead to verify that interpreter. The verification script creates and migrates
its own temporary database; imports all application modules; checks startup, health, public
lists and missing-player status; and compares the preserved OpenAPI contract. It does not use
HTTPX or pytest. The dormant settings module is imported from a temporary working directory
so no repository `.env` is read. No original database is initialized, seeded, migrated or stamped.

Normal deployment uses an explicitly configured `DATABASE_URL` and separately reviewed
migrations, as described in [the migration guide](database-migration-guide.md). Start with
`uvicorn app.main:app --host 127.0.0.1 --port 8000`. Minimal FastAPI is installed, not its
standard/cloud/CLI extras. Uvicorn's existing standard extras are retained for the documented
reload/server functionality. FastAPI 0.163.2 itself requires OpenTelemetry API, but no exporter,
SDK, cloud CLI, template engine or email validator is pulled in via optional FastAPI extras.

## Install development

After runtime verification, in the same environment (or a new external development env):

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q -W error
python -m black --check .
python -W error -m scripts.verify_dependency_environment
python -m scripts.verify_migrations --existing-copy-from snooker.db
```

The last command opens `snooker.db` read-only, takes a consistent temporary backup and performs
compatibility/adoption experiments only on that disposable copy. Tests use their own temporary
databases and never use production credentials. Retain strict warnings and all 42 tests with their original assertions.
`pytest-cov 4.1.0` was retained and verified with pytest 9.0.3 (42 passing tests, 88% app coverage).
Explicit function loop scopes in `pytest.ini` are configuration for pytest-asyncio 1.x, not
warning filters. No warning suppression was added.

Black 26.10.1 targets Python 3.11 syntax. Historical revision files and migrations_backup are
excluded in both Black configuration and its pre-commit hook. Only one blank line in an
existing test changed under the formatter; its AST remained identical. Do not format history.

If the network interrupts a wheel transfer, retry without disabling TLS verification. An
alternative installer for the same requirements/constraints is:

```bash
uv pip install --python /absolute/path/to/external/env/bin/python -r requirements-dev.txt
```

This alternative was used for a local Python 3.12 Black wheel transfer after pip TLS errors.
The final dependency graph was checked with pip and audited, rather than accepting a different
resolution. Do not patch installed package source or loosen tests to work around dependencies.

## Classification decisions

- FastAPI, Starlette and Pydantic are runtime. Starlette is explicit to enforce the reviewed
  security/compatibility version. python-multipart is modern and explicit; no downgrade to 0.0.9.
- Alembic stays runtime because `app/db_cli.py` and the explicit initialization path import it.
  SQLAlchemy/Uvicorn/Alembic versions remain unchanged where audits and regressions support it.
- Pydantic-core, annotated-types and typing-extensions are resolved transitively and exactly
  constrained, instead of redundant direct declarations which could conflict with Pydantic.
- `pydantic-settings` is now explicitly declared because `app/core/config.py` actually imports
  it. That dormant module's class Config was minimally converted to SettingsConfigDict so it
  imports under strict warnings. It is still not the database configuration source or an auth
  implementation. Its legacy placeholder secret must not be activated for production auth.
- HTTPX 0.27.0 is development-only for existing async tests. HTTPX2 2.16.2 is additionally needed
  for current Starlette TestClient without a deprecation warning. They have distinct import
  namespaces; existing tests were not rewritten or weakened.
- asyncpg was removed: no application/test import or configured async engine uses it; only
  synchronous SQLite is verified. A future PostgreSQL/async task must choose and test its driver.
- sqlalchemy2-stubs was removed: SQLAlchemy 2 ships typing; the legacy stubs target its 1.4 API
  and are incompatible with native SQLAlchemy 2 typing. No source imports them. mypy/isort are
  retained because pre-commit/legacy task configuration references them; their checks were not
  newly made CI gates or claimed clean by this task.

## Refresh constraints deliberately

Reviewed resolver: uv 0.11.23. Use it in a separate tools environment or its standalone binary.
It is not required to install or run the application.

```bash
uv pip compile requirements/runtime.in requirements/development.in \
  --universal --python-version 3.11 --no-emit-index-url --no-emit-index-annotation \
  -o requirements/constraints.txt
uv pip compile requirements/scanners.in \
  --universal --python-version 3.11 --no-emit-index-url --no-emit-index-annotation \
  -o requirements/scanners-constraints.txt
```

Edit direct `.in` pins first; review generated diffs. Existing output pins are normally reused
by uv; request a targeted `--upgrade-package NAME` or deliberate `--upgrade` only when intended.
The bootstrap file is independently reviewed/pinned. Do not add index credentials to output.
Universal resolution is a solver guarantee across markers, not a replacement for actual matrix
tests. During this task uv downloaded Python 3.11.15 for resolution, making both targets locally
available; 3.12.3 was already installed.

## Audit complete resolved graphs

Use a separate scanner environment, never install scanners into the application environment:

```bash
python3.12 -m venv ~/.venvs/snooker-security
~/.venvs/snooker-security/bin/python -m pip install -r requirements-security.txt
# Run freeze using the application environment's Python, including bootstrap packages:
python -m pip freeze --all > /tmp/snooker-resolved.txt
~/.venvs/snooker-security/bin/pip-audit \
  -r /tmp/snooker-resolved.txt --no-deps --disable-pip
~/.venvs/snooker-security/bin/bandit -q -r app
```

`--no-deps --disable-pip` is appropriate only for an already fully resolved, exact freeze: it
avoids re-resolving or mixing the scanner environment into the target. It does not ignore
vulnerabilities. Audit runtime, development and scanners separately. Scan failures/service
availability must be distinguished from a successful zero-finding scan. No blanket ignores.

CI retains Task 02B triggers, Python matrix, Node 24, read-only token scope, timeouts and
concurrency. Cache keys cover root requirements files and all nested `.in`/`.txt` inputs.
Jobs create a fresh backend virtualenv, install bootstrap/runtime and verify runtime isolation,
then add requirements-dev and run pip check, strict pytest (private runner
temp base), API/migrated-startup verification, migrations and Black. Scanner tools have their
own `$RUNNER_TEMP` venv and constraints. Bandit and pip-audit remain **advisory** via
continue-on-error. pip-audit replaces deprecated Safety `check`; no Safety account or production
credentials are required. No hosted success is claimed until an actual remote run completes.

## Security sources and limitations

Verified 2026-11-20 against official metadata/advisories and complete resolved graphs:

- [Black cache path traversal](https://github.com/psf/black/security/advisories/GHSA-3936-cmfr-pm3m):
  CVE-2026-32274, affected >=24.3.0,<26.3.1, fixed 26.3.1. Selected 26.10.1 also avoids
  [later action-version parsing issues](https://github.com/psf/black/security/advisories/GHSA-cg8m-r9f2-5wm2).
  The latter officially affects 26.9.0/26.10.0 and the Black action, not this repository's pip
  invocation; the scanner over-reported it against the older baseline. Advisory applicability
  was reviewed, not blindly counted.
- [pytest advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g) and
  [official 9.0.3 release](https://github.com/pytest-dev/pytest/releases/tag/9.0.3):
  CVE-2025-71176, <9.0.3 affected, fixed release 9.0.3 selected. [Upstream discussion](https://github.com/pytest-dev/pytest/issues/13669) still
  raises shared-temp/TOCTOU concerns; CI uses a runner-private basetemp and local verification
  does not claim every multi-user threat is eliminated.
- [FastAPI request-parameter DoS](https://github.com/fastapi/fastapi/security/advisories/GHSA-f56c-v883-vx8r):
  >=0.123.2,<0.163.2 affected; baseline 0.111.0 is outside that range, but an intermediate
  compatibility-only update could enter it. Selected 0.163.2 is the patched release.
- [Starlette advisories](https://github.com/Kludex/starlette/security/advisories):
  baseline 0.37.2 is affected by multiple multipart/host/method/path issues, including
  [URL-encoded form limits](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq)
  patched in 1.3.1. Selected 1.10.0 is also compatible with current AnyIO without deprecated aliases.
- [python-multipart advisories](https://github.com/Kludex/python-multipart/security/advisories):
  old 0.0.9 predates multiple fixes; modern 0.0.34 is retained and has no known findings in the
  resolved audit. JSON-only current routes do not justify reintroducing an old vulnerable parser.
- [pydantic-settings](https://github.com/pydantic/pydantic-settings/security/advisories/GHSA-4xgf-cpjx-pc3j):
  candidate >=2.12.0,<2.14.2 has nested-secrets symlink escape; patched 2.14.2 selected even
  though this application does not use NestedSecretsSettingsSource.
- [setuptools](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w):
  environment bootstrap is pinned to 84.2.1, avoiding findings in Python 3.11's bundled 79.0.1.
- [pytest-asyncio changelog](https://pytest-asyncio.readthedocs.io/en/stable/reference/changelog.html)
  and [PyPI 0.22.0 metadata](https://pypi.org/pypi/pytest-asyncio/0.22.0/json): 0.22.0 was yanked
  because deprecated functionality lacked reasonable replacement paths; 1.3.0 supports pytest
  >=8.2,<10 and Python >=3.10, covering this matrix.
- [Router redirect advisory](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6) and
  [Router SSR advisory](https://github.com/advisories/GHSA-337j-9hxr-rhxg) remain: installed Router
  6.30.6 is affected; fixed >=7.18.0. npm proposes a major upgrade. No frontend upgrade was made.

Zero pip-audit findings means no known vulnerabilities in that service's database for the
resolved versions at scan time. It is not a security certification. Existing application
financial/access-control risks remain documented separately.

## Tracked environment maintenance

`venv/` has 5,726 tracked files totaling 116,903,317 uncompressed tracked bytes (about 111.5 MiB).
`.venv/` is not tracked. This is current-tree logical content, not an estimate of compressed Git
history reclamation. The old pycparser distribution metadata is invalid; clean external installs
replace the need to repair or reuse it. No tracked environment was removed or modified here.

A later approved maintenance change should first establish an external environment with these
instructions, verify the full suite, confirm ignore rules, review `git ls-files venv .venv`, then
use `git rm -r --cached venv` to untrack generated files while preserving local files. Review
that staged deletion in a dedicated commit. It will not remove existing blobs from history;
any history rewrite needs separate approval and coordination. Do not combine that cleanup with
this dependency task. No such commands were executed.

## Task 03 authentication dependencies

Runtime adds `argon2-cffi==25.1.0` (Argon2id) and `PyJWT==2.15.1` (fixed-algorithm
JWT signing/validation), with locked argon2-cffi-bindings, cffi and pycparser transitive
dependencies in the universal constraints file. Existing framework and development pins
remain unchanged. Both Python matrix versions exercise the same lock; there are no new
development-only imports in runtime authentication. Security scans use the separate tools
environment as before; see the authentication report for actual scan results.
