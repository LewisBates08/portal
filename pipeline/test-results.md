# Tester results: urllib3 security finding

Date: 2026-10-27

Overall result: **FAIL**

The source requirement, exact lock pin, installed-package compatibility check,
focused AWS-path test, and vulnerability audits pass. Delivery acceptance is
not complete because this environment could not perform a clean Python 3.13
lock installation, the PostgreSQL-backed backend suite, or the production
container build and scan.

## Specification criteria

| Criterion | Result | Evidence |
|---|---|---|
| Runtime requirement excludes affected urllib3 releases | **PASS** | `backend/requirements.txt` declares `urllib3>=2.8,<3`. |
| Runtime lock uses an exact fixed release | **PASS** | `backend/requirements.lock` pins `urllib3==2.8.0`; no `urllib3==2.7.0` runtime pin remains. |
| Locked urllib3 is compatible with locked botocore | **PASS** | Lock pins `botocore==1.43.93`. Installed botocore metadata declares `urllib3!=2.2.0,<3,>=1.25.4`, which contains 2.8.0. The new dependency-lock regression test passed. |
| Dependency audit has no urllib3 finding | **PASS** | Fresh `pip-audit 2.10.1 --no-deps --disable-pip -r backend/requirements.lock` reported `No known vulnerabilities found`. No other package advisory was reported. |
| Focused AWS path remains compatible | **PASS** | Mail relay boto3/botocore unit tests: 4 passed. Dependency and crypto compatibility tests: 2 passed. |
| Complete release verification against the same dependency state | **FAIL** | Clean Python 3.13 install, PostgreSQL-backed suite, and production container build/runtime/scan were unavailable. |

## Executed checks

| Check | Result | Observed outcome |
|---|---|---|
| Dependency-lock regression | **PASS** | 1 passed. It checks the source range, exact pins, minimum fixed version, and installed botocore metadata. |
| Ruff on the new test | **PASS** | `ruff check` passed; `ruff format --check` reported already formatted. |
| Installed environment consistency | **PASS** | Python 3.14.7 environment: `pip check` reported no broken requirements; installed versions are urllib3 2.8.0 and botocore 1.43.93. |
| Exact-pin vulnerability audit | **PASS** | `pip-audit 2.10.1 --no-deps --disable-pip` reported no known vulnerabilities. The lock is fully pinned, but it is not hash-locked. |
| Normal resolving vulnerability audit | **PASS** | After the sandboxed attempt could not bootstrap its temporary environment, `pip-audit -r backend/requirements.lock` was rerun with approved network access and reported `No known vulnerabilities found`. |
| Focused boto3/botocore mail-relay tests | **PASS** | 4 passed. |
| Backend collection | **PASS** | 88 tests collected, including the new dependency test. |
| Full backend suite | **FAIL** | 36 passed and 48 errored during PostgreSQL fixture setup. TCP access to `127.0.0.1:5432` was denied with `Operation not permitted`; no application assertion caused these 48 errors. |
| Production container build and scan | **FAIL** | Docker and Trivy are unavailable in this environment. Image contents and layers were not verified. |

## Test change

Added `backend/tests/test_dependency_lock.py`. This focused test fails if:

- the declared urllib3 range differs from `>=2.8,<3`;
- urllib3 or botocore is not exactly pinned in the runtime lock;
- the locked urllib3 version is below 2.8.0; or
- installed botocore metadata does not accept the locked urllib3 version.

No application code was changed during this tester stage. The dependency-file
changes being tested were already present in the working tree.

## Commands

```text
.venv/bin/python --version
.venv/bin/pip-audit --version
.venv/bin/python -m pip check
.venv/bin/pip-audit -r backend/requirements.lock
.venv/bin/pip-audit --no-deps --disable-pip -r backend/requirements.lock
```

The normal resolving audit was also run with approved network access:

```text
.venv/bin/pip-audit -r backend/requirements.lock
```

```text
TEST_DATABASE_URL=postgresql+psycopg://portal:test@127.0.0.1:5432/portal_test .venv/bin/pytest -q backend/tests/test_dependency_lock.py
.venv/bin/ruff check backend/tests/test_dependency_lock.py
.venv/bin/ruff format --check backend/tests/test_dependency_lock.py
.venv/bin/python -m pytest -q deploy/mail-relay/test_handler.py
TEST_DATABASE_URL=postgresql+psycopg://portal:test@127.0.0.1:5432/portal_test .venv/bin/pytest -q backend/tests/test_crypto_compatibility.py backend/tests/test_dependency_lock.py
TEST_DATABASE_URL=postgresql+psycopg://portal:test@127.0.0.1:5432/portal_test .venv/bin/pytest --collect-only -q backend/tests deploy/mail-relay/test_handler.py
TEST_DATABASE_URL=postgresql+psycopg://portal:test@127.0.0.1:5432/portal_test .venv/bin/pytest -q backend/tests
```

## Remaining verification required

Before approval, CI or a suitably equipped machine must run all of the
following against the committed lock:

1. Create a clean Python 3.13 environment and install
   `backend/requirements.lock` successfully.
2. Run `python -m pip check` in that clean environment.
3. Run the normal `pip-audit -r backend/requirements.lock` with advisory and
   package-index access.
4. Run the full backend suite against an isolated PostgreSQL database ending
   in `_test`.
5. Build the root production Dockerfile, run its smoke tests and vulnerability
   scan, and inspect the final image for urllib3 2.8.0 and botocore 1.43.93,
   including duplicate Python environments or retained layers.
6. After deployment, verify the target runtime package versions before calling
   the finding deployed or live-verified.
