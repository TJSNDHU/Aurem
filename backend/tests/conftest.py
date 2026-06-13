"""Ensure backend .env is loaded before any test runs."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Default API URL to the FRONTEND's configured backend URL if the
# REACT_APP_BACKEND_URL env var isn't already exported. Hitting the
# external preview URL is critical because middleware/health_probe.py
# returns 204 (instead of the real 401) for every /api/admin/* request
# coming from localhost during the first 90s of boot grace, which made
# the iter 332b D-6/D-7/D-8 negative tests flake during grouped pytest
# runs that triggered hot-reload.
if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe_env = Path("/app/frontend/.env")
    if fe_env.exists():
        for line in fe_env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = (
                    line.split("=", 1)[1].strip()
                )
                break
    os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8001")

# ── iter D-86: central test credentials ──────────────────────────────
# A previous secrets-scrub replaced hardcoded passwords in ~97 test files
# with the literal string "<REDACTED>", silently breaking every login they
# perform (and tripping the brute-force lockout for the whole suite).
# Tests now read AUREM_ADMIN_PASSWORD / AUREM_CUSTOMER_PASSWORD from the
# environment; we hydrate those here from memory/test_credentials.md so
# the secret never lives in the repo's test sources.
def _hydrate_test_credentials():
    if os.environ.get("AUREM_ADMIN_PASSWORD"):
        return
    creds = Path("/app/memory/test_credentials.md")
    if not creds.exists():
        return
    text = creds.read_text()
    import re as _re
    # Passwords appear as table rows: | Password | `...` |
    found = _re.findall(r"\|\s*Password\s*\|\s*`([^`]+)`\s*\|", text)
    if found:
        os.environ.setdefault("AUREM_ADMIN_PASSWORD", found[0])
        if len(found) > 1:
            os.environ.setdefault("AUREM_CUSTOMER_PASSWORD", found[1])


_hydrate_test_credentials()


# ── iter D-86: login-lockout hygiene ─────────────────────────────────
# The full suite logs in hundreds of times; the brute-force guard then
# locks the admin account and every subsequent auth test fails with 429
# ("Account temporarily locked"), poisoning the whole run. Clear the
# persisted attempt ledger once per session so the suite starts clean.
import pytest


@pytest.fixture(scope="session", autouse=True)
def _clear_login_lockouts():
    try:
        from pymongo import MongoClient
        client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
        db = client[os.environ["DB_NAME"]]
        db.failed_login_attempts.delete_many({})
        client.close()
    except Exception:
        pass
    yield
