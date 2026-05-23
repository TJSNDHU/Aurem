# AUREM DEV SKILL: testing — Testing Standards
## Context
Loaded when ORA is asked to write tests, run tests, check coverage,
or verify a change. These rules are non-negotiable in AUREM.

## Trigger intent
Keywords: test, pytest, coverage, e2e, mock, fixture, regression,
"write tests", "verify", "did it work".

## Owner Agent
ORA. NEVER declare a task complete without `run_pytest` AND
`check_coverage` passing.

---

## The 6 Non-Negotiable Rules

### Rule 1 — 80% line coverage minimum on NEW code
- `check_coverage` returns a real percentage.
- < 80% → add tests OR justify in writing why a branch cannot
  be tested. NEVER lower the bar.
- The bar applies to the new/changed file, not the global average.

### Rule 2 — Mock ALL external APIs in unit tests
- Stripe, Twilio, Retell, Resend, GitHub, Brightbean — every one of
  them gets `respx` mocks or `monkeypatch` stubs.
- Real API calls in unit tests are a Tier-3 fire-the-engineer offense:
  they burn money, leak credentials, and break offline.
- The ONE exception: smoke tests (Rule 4 below) — explicitly labelled
  `@pytest.mark.smoke` so they can be deselected in CI.

### Rule 3 — Use `REACT_APP_BACKEND_URL`, NEVER `http://localhost:8001`
- localhost bypasses the K8s ingress, which means `/api` routing
  isn't exercised. The test passes on localhost but the real route
  is broken in production.
- Read the URL from env in conftest:
  ```python
  API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
  ```
- The fallback to localhost is only for true unit tests that don't
  hit the network.

### Rule 4 — `data-testid` on every interactive UI element
- Buttons, links, inputs, modals, dropdowns, menus, cards, anything
  the user can interact with or that displays critical info.
- Naming: kebab-case, describes the element's function not its style.
- Example: `data-testid="lead-card-{id}"`, `data-testid="login-submit-btn"`.
- Playwright E2E and the testing agent both depend on these.

### Rule 5 — `check_coverage` after EVERY session
- Before `finish`, run `check_coverage` on what you changed.
- If coverage dropped vs the previous run → add tests. NEVER ship
  a regression in coverage.
- Pattern in the test report: percent up or flat = green, percent
  down = blocker.

### Rule 6 — One regression test per bug fix
- Every bug fix gets a `test_iter{N}_{descr}.py` with at least 1
  test that fails BEFORE the fix and passes AFTER.
- No bug fix without a regression test. No exceptions.
- The test prevents recurrence (we've had 4+ recurrences of the
  `.env` corruption bug because there was no regression test for it).

---

## Test layout conventions

```
/app/backend/tests/
├── conftest.py                    # shared fixtures (db, async client)
├── test_iter{N}_{descr}.py        # iter-stamped test file
└── fixtures/                      # static JSON / .env.test files
```

## Standard fixture pattern

```python
# /app/backend/tests/conftest.py
import os, pytest, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

@pytest.fixture
def api_url() -> str:
    return os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()
```

## Common pytest invocations

```bash
# Run a specific iter's tests
cd /app/backend && python -m pytest tests/test_iter331a*.py -q --tb=short

# Skip the one known-failing pre-existing test
python -m pytest tests/ -q --tb=line \
  --deselect tests/test_accurate_scout.py::test_channel_gating_medium_phone_allows_whatsapp_not_call

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=term-missing -q
```

## Anti-patterns

- `assert response.status_code in (200, 201, 204)` — pick one. Vague
  assertions hide bugs.
- `time.sleep(2)` to wait for async work → use `await asyncio.wait_for`
  or `tenacity.retry`. Sleeps are flaky.
- `try: ... except: pytest.skip()` — that's hiding failures, not
  testing.
- `pytest.mark.skip` without a clear reason + ticket. Don't disable
  tests; fix or delete them.
- Tests that change state for other tests (no teardown). Always reset
  what you create.
