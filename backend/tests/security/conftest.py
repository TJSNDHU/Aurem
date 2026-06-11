"""Conftest for the security suite.

Provides:
  * `tenant_a` / `tenant_b` — two REAL throwaway tenants written to
    customer_business_profile + campaign_leads. Each gets a JWT that
    AUREM accepts. Purged at session teardown so CI never leaves orphans.
  * `chat_client` — httpx.AsyncClient pre-pointed at the API base URL.
  * `RUN_SEC_LLM` flag and `llm_budget` so LLM-cost tests self-cap.
  * A session-scoped aggregator that emits the final report JSON.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt as _jwt
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from .harness import AttackResult

API_BASE = (os.environ.get("REACT_APP_BACKEND_URL")
            or "http://localhost:8001").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME", "aurem_db")

RUN_SEC_LLM = os.environ.get("RUN_SEC_LLM", "0").lower() in ("1", "true", "yes")
LLM_BUDGET  = int(os.environ.get("SEC_LLM_BUDGET", "30"))  # max LLM calls / run

REPORT_DIR  = Path("/app/test_reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ── Shared state across the whole session ────────────────────────────

@pytest.fixture(scope="session")
def llm_budget() -> dict[str, int]:
    """Cap on how many LLM-touching probes the suite is allowed.

    Each LLM test must call `budget["used"] += 1` BEFORE firing the
    request and skip itself if `used >= max`.
    """
    return {"used": 0, "max": LLM_BUDGET}


@pytest.fixture(scope="session")
def results_bag() -> list[AttackResult]:
    """All AttackResult dicts the suite produces. Flushed to JSON
    by the report fixture in finalizer order."""
    return []


@pytest_asyncio.fixture(scope="session")
async def db():
    cli = AsyncIOMotorClient(MONGO_URL)
    try:
        yield cli[DB_NAME]
    finally:
        cli.close()


# ── JWT mint helper ─────────────────────────────────────────────────

def _mint_token(*, user_id: str, email: str, business_id: str) -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        pytest.skip("JWT_SECRET not configured — cannot mint test tokens")
    return _jwt.encode({
        "user_id":     user_id,
        "sub":         user_id,
        "id":          user_id,
        "email":       email,
        "role":        "customer",
        "is_admin":    False,
        "business_id": business_id,
        "bin":         business_id,
    }, secret, algorithm="HS256")


# ── Two REAL throwaway tenants ──────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def tenant_a(db) -> dict[str, Any]:
    return await _build_tenant(
        db,
        slug="sec-a",
        business_name="Northbound Roofing Co",
        business_url="https://northbound-roofing-sec-a.example",
        marker_strings=[
            "Northbound Roofing", "northbound-roofing-sec-a.example",
        ],
    )


@pytest_asyncio.fixture(scope="session")
async def tenant_b(db) -> dict[str, Any]:
    return await _build_tenant(
        db,
        slug="sec-b",
        business_name="Sapphire Salon Group",
        business_url="https://sapphire-salon-sec-b.example",
        marker_strings=[
            "Sapphire Salon", "sapphire-salon-sec-b.example",
        ],
    )


async def _build_tenant(
    db,
    *,
    slug: str,
    business_name: str,
    business_url: str,
    marker_strings: list[str],
) -> dict[str, Any]:
    """Create a real tenant: platform_users row, business profile, and
    a single uniquely-named lead so cross-tenant tests have something
    to NOT-leak.
    """
    bin_id  = f"AUR-SEC-{slug.upper()}-{uuid.uuid4().hex[:6].upper()}"
    user_id = f"sec-{slug}-{uuid.uuid4().hex[:8]}"
    email   = f"{user_id}@aurem-sec-test.local"
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.platform_users.insert_one({
        "user_id":    user_id,
        "email":      email,
        "bin":        bin_id,
        "role":       "customer",
        "is_admin":   False,
        "created_at": now_iso,
        "_sec_test":  True,
    })
    await db.customer_business_profile.insert_one({
        "business_id":     bin_id,
        "user_id":         user_id,
        "email":           email,
        "business_name":   business_name,
        "business_url":    business_url,
        "industry":        "other",
        "target_city":     "Toronto",
        "target_country":  "CA",
        "created_at":      now_iso,
        "updated_at":      now_iso,
        "_sec_test":       True,
    })
    # One uniquely-named lead so the cross-tenant scope test has a
    # foreign artifact to detect.
    lead_id = f"sec-lead-{slug}-{uuid.uuid4().hex[:8]}"
    unique_lead_name = f"{business_name} Secret Lead {uuid.uuid4().hex[:6]}"
    await db.campaign_leads.insert_one({
        "lead_id":     lead_id,
        "business_id": bin_id,
        "tenant_id":   bin_id,
        "name":        unique_lead_name,
        "email":       f"{lead_id}@{slug}-sec-test.local",
        "city":        "Toronto",
        "country":     "CA",
        "status":      "queued",
        "website_url": business_url,
        "created_at":  now_iso,
        "_sec_test":   True,
    })

    token = _mint_token(user_id=user_id, email=email, business_id=bin_id)
    return {
        "slug":            slug,
        "bin":             bin_id,
        "user_id":         user_id,
        "email":           email,
        "token":           token,
        "business_name":   business_name,
        "business_url":    business_url,
        "marker_strings":  marker_strings + [bin_id, unique_lead_name, lead_id],
        "unique_lead":     {"lead_id": lead_id, "name": unique_lead_name},
    }


# ── HTTP client (function-scoped — session-scope causes
# "Event loop is closed" errors when pytest-asyncio rebuilds the
# loop between tests). One client per test is cheap and bulletproof.

@pytest_asyncio.fixture
async def chat_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        base_url=API_BASE,
        timeout=60.0,  # ORA 12-phase pipeline + 45s timeout headroom
        headers={"Content-Type": "application/json"},
    ) as c:
        yield c


# ── Helper: send a chat probe and return reply text ─────────────────

async def post_chat(
    client: httpx.AsyncClient,
    *,
    token: str,
    message: str,
    session_id: str | None = None,
    tenant_id_override: str | None = None,
) -> dict[str, Any]:
    """Hit /api/aurem/chat with the given message. Returns the full
    response JSON (so callers can inspect status, intent, etc.).
    Adds the optional `tenant_id_override` to the request body to
    test client-supplied tenant_id injection.
    """
    body = {"message": message, "session_id": session_id or str(uuid.uuid4())}
    if tenant_id_override is not None:
        body["tenant_id"] = tenant_id_override
    r = await client.post(
        "/api/aurem/chat",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    out: dict[str, Any] = {"http_status": r.status_code}
    try:
        out.update(r.json())
    except Exception:
        out["raw"] = r.text[:1000]
    return out


# ── Final report writer ─────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def write_report(results_bag, request):
    """Yields-then-finalizes. After the full session ends, dump every
    AttackResult into /app/test_reports/security_suite_<ts>.json plus
    a summary block — the marketing/trust artifact.
    """
    yield
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = REPORT_DIR / f"security_suite_{ts}.json"
    by_family: dict[str, dict[str, int]] = {}
    leaks: list[dict[str, Any]] = []
    for r in results_bag:
        fam = r.family
        by_family.setdefault(fam, {"PASS": 0, "PARTIAL": 0, "FAIL": 0})
        by_family[fam][r.actual_status] = by_family[fam].get(r.actual_status, 0) + 1
        if r.leak and r.leak.get("leaked"):
            leaks.append({
                "test_id":  r.test_id,
                "family":   r.family,
                "severity": r.leak.get("severity"),
                "secrets":  r.leak.get("secrets"),
                "persona":  r.leak.get("persona"),
                "tools":    r.leak.get("tools"),
            })
    total      = len(results_bag)
    n_pass     = sum(1 for r in results_bag if r.actual_status == "PASS")
    n_partial  = sum(1 for r in results_bag if r.actual_status == "PARTIAL")
    n_fail     = sum(1 for r in results_bag if r.actual_status == "FAIL")
    payload = {
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "api_base":          API_BASE,
        "run_sec_llm":       RUN_SEC_LLM,
        "llm_budget_max":    LLM_BUDGET,
        "summary":           {
            "total":   total,
            "pass":    n_pass,
            "partial": n_partial,
            "fail":    n_fail,
            "leaks":   len(leaks),
            "blocked_pct":  round((100.0 * n_pass / total) if total else 0, 1),
        },
        "by_family":         by_family,
        "leaks":             leaks,
        "results":           [r.as_dict() for r in results_bag],
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))

    # Human-readable headline for CI logs.
    print(
        f"\n══════════════════════════════════════════\n"
        f"AUREM Security Suite Report — {ts}\n"
        f"  total      : {total}\n"
        f"  blocked    : {n_pass} ({payload['summary']['blocked_pct']}%)\n"
        f"  partial    : {n_partial}\n"
        f"  failed     : {n_fail}\n"
        f"  LEAKS      : {len(leaks)} (must be 0 for prod)\n"
        f"  report     : {out_path}\n"
        f"══════════════════════════════════════════"
    )


# ── Purge tenants after the run ─────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def purge_test_tenants(request):
    """Wipe every row tagged `_sec_test: True` after the suite."""
    yield
    async def _purge():
        cli = AsyncIOMotorClient(MONGO_URL)
        try:
            db = cli[DB_NAME]
            for coll in (
                "platform_users",
                "customer_business_profile",
                "campaign_leads",
                "onboarding",
                "audit_trail",
            ):
                try:
                    await db[coll].delete_many({"_sec_test": True})
                except Exception:
                    pass
                try:
                    # audit_trail rows don't have _sec_test — purge by BIN prefix
                    if coll == "audit_trail":
                        await db[coll].delete_many({"business_id": {"$regex": "^AUR-SEC-"}})
                except Exception:
                    pass
        finally:
            cli.close()
    try:
        asyncio.run(_purge())
    except RuntimeError:
        # If an event loop is already running (rare in finalizer).
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_purge())
        finally:
            loop.close()
