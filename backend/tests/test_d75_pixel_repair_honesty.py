"""
test_d75_pixel_repair_honesty.py — iter D-75 regression guard.

Pre-D-75, `routers/customer_website_repair_router.py::_run_repair_job`
was theatrical mock code:
  • `delta = rng.randint(24, 38)` → fake random score "improvement"
  • Event templates like "Canary rollout to 10% of traffic complete",
    "SOC 2 audit-chain appended", "42/42 assertions passed",
    "AI Repair engine pushed fix to staging commit {commit}" — none
    of which ever happened.
  • Hardcoded "improvements" array using `lcp * 0.35` math to fake
    a 65% load-speed improvement.
  • The customer's website was NEVER touched. Status ended as
    `completed` with a randomly-elevated `score_after`.

D-75 replaced it with honest behavior:
  • Real audit via `website_audit_service.real_audit()`.
  • Real LLM plan via `services.llm_gateway_v2.route()`
    (DeepSeek V3.1 via OpenRouter — same path as D-73 autonomous
    CTO repair agent).
  • Real email via Resend (best-effort, returns honest error string
    when it fails).
  • Status ends `plan_ready_for_customer`, NEVER `completed`.
  • `score_after` stays `None` — only a customer-triggered re-scan
    can fill it after they apply the plan.

These tests inspect the source (cheap regression guards) plus do one
end-to-end live run against the real backend / real Mongo / real
OpenRouter / real Resend.

Run: PYTHONPATH=/app/backend python3 -m pytest tests/test_d75_pixel_repair_honesty.py -v
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, "/app/backend")


# ─── Source-level regression guards ─────────────────────────────────

def test_no_random_score_delta():
    """`_run_repair_job` must NEVER add a random integer to the scan
    score. Pre-D-75 had `delta = rng.randint(24, 38)`."""
    from routers import customer_website_repair_router as mod
    src = inspect.getsource(mod._run_repair_job)
    assert "rng.randint(24" not in src, (
        "random score delta re-introduced — iter D-75 regression"
    )
    assert "final_score = scan_score + delta" not in src, (
        "score = scan_score + delta pattern re-introduced"
    )
    assert "rng.random()" not in src, (
        "rng.random() back in _run_repair_job — used to be fake commit hashes"
    )


def test_no_fake_deploy_events():
    """The notorious fake events must stay deleted FROM CODE (the
    audit-comment block at the top of the file may legitimately
    mention them as a historical breadcrumb — strip comments first)."""
    from routers import customer_website_repair_router as mod
    src = inspect.getsource(mod)
    # Strip the module docstring + Python comment lines + docstrings
    # inside functions so this test inspects only executable code.
    import re
    # Drop triple-quoted docstrings (greedy across newlines)
    code_only = re.sub(r'"""[\s\S]*?"""', '', src)
    code_only = re.sub(r"'''[\s\S]*?'''", '', code_only)
    # Drop single-line comments
    code_only = "\n".join(
        line for line in code_only.splitlines()
        if not line.lstrip().startswith("#")
    )

    forbidden = (
        "Canary rollout to 10%",
        "SOC 2 audit-chain appended",
        "42/42 assertions passed",
        "Full deploy confirmed",
        "CDN cache invalidated on 4 edges",
        "AI Repair engine pushed fix to staging commit",
        "Compiling Shopify 2026-04 schema package",
        "Sentinel Overwatch",
    )
    for phrase in forbidden:
        assert phrase not in code_only, (
            f"Fake event phrase {phrase!r} present in EXECUTABLE code "
            "(not just historical comment) — D-75 regression. "
            "These events claimed work that never happened."
        )


def test_no_fake_improvements_array():
    """The hardcoded `improvements` array (with `lcp * 0.35` etc) must
    stay deleted. Real improvement is measured by the re-scan, not
    fabricated."""
    from routers import customer_website_repair_router as mod
    src = inspect.getsource(mod)
    forbidden = (
        "Fewer bounces — visitors stay 2-3× longer",
        "Shopify 2026-04 compliant",
        "round(metrics['lcp_s']*0.35,1)",
        "int(metrics['unused_js_kb']*0.32)",
    )
    for phrase in forbidden:
        assert phrase not in src, (
            f"Fake improvements row {phrase!r} re-introduced"
        )


def test_uses_real_audit_and_llm_gateway():
    """Affirmative source check — the honest implementations are wired."""
    from routers import customer_website_repair_router as mod
    src = inspect.getsource(mod._run_repair_job)
    assert "from services.website_audit_service import real_audit" in src, (
        "_run_repair_job no longer calls real_audit — D-75 regression"
    )
    assert "_generate_repair_plan_via_llm" in src, (
        "_run_repair_job no longer calls LLM plan generator"
    )
    # The plan generator must hit llm_gateway_v2
    plan_src = inspect.getsource(mod._generate_repair_plan_via_llm)
    assert "from services.llm_gateway_v2 import route" in plan_src, (
        "_generate_repair_plan_via_llm no longer uses llm_gateway_v2"
    )


def test_status_final_state_is_plan_ready_not_completed():
    """The terminal status MUST be `plan_ready_for_customer`. The old
    fake `completed` claimed work that never happened."""
    from routers import customer_website_repair_router as mod
    src = inspect.getsource(mod._run_repair_job)
    assert '"plan_ready_for_customer"' in src, (
        "terminal status no longer plan_ready_for_customer"
    )
    # And score_after must stay None at the terminal state
    assert '"score_after": None' in src, (
        "score_after is being pre-populated — only re-scan can set this"
    )


def test_honest_disclaimer_in_repair_start_response():
    """`/repair/start` must return the disclaimer telling the customer
    we generate a plan, not deploy code."""
    from routers import customer_website_repair_router as mod
    src = inspect.getsource(mod.repair_start)
    assert "honest_disclaimer" in src, (
        "repair_start no longer surfaces the honest_disclaimer field"
    )
    assert "we do not" in src.lower(), (
        "disclaimer text changed — must explicitly say we don't deploy"
    )


# ─── E2E live test against real backend ──────────────────────────────

def _backend_url() -> str:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


@pytest.fixture(scope="module")
def api_url():
    return _backend_url()


@pytest.fixture(scope="module")
def founder_token(api_url):
    r = httpx.post(
        f"{api_url}/api/platform/auth/login",
        json={"email": "teji.ss1986@gmail.com",
              "password": "Aurem@Founder2026!"},
        timeout=15.0,
    )
    if r.status_code != 200:
        pytest.skip(f"founder login failed: {r.status_code}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def founder_has_website():
    """Ensure the founder's platform_users doc has a website set so
    `/repair/start` can find it. Idempotent."""
    async def _go():
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        await db.platform_users.update_one(
            {"email": "teji.ss1986@gmail.com"},
            {"$set": {"website": "https://aurem.live"}},
        )
    asyncio.run(_go())



def test_repair_start_returns_honest_disclaimer(api_url, founder_token, founder_has_website):
    """Live /repair/start must return the honest disclaimer in its
    response — frontend uses this to set customer expectations."""
    r = httpx.post(
        f"{api_url}/api/customer/website/repair/start",
        headers={"Authorization": f"Bearer {founder_token}",
                 "Content-Type": "application/json"},
        json={},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("ok") is True
    assert body.get("job_id", "").startswith("rep_")
    disclaimer = (body.get("honest_disclaimer") or "").lower()
    assert "we do not" in disclaimer or "do not deploy" in disclaimer, (
        f"disclaimer missing the 'we do not deploy' contract: {disclaimer!r}"
    )



def test_repair_e2e_real_audit_real_llm_real_email(api_url, founder_token, founder_has_website):
    """Full live cycle: start a job, poll until plan_ready, verify
    the OUTPUT shows real LLM provider/model/latency + a real Resend
    email_id OR an honest error string. NO mocks."""
    # Start
    r = httpx.post(
        f"{api_url}/api/customer/website/repair/start",
        headers={"Authorization": f"Bearer {founder_token}",
                 "Content-Type": "application/json"},
        json={},
        timeout=15.0,
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Poll up to 120s, tolerating transient ingress 502s (preview env
    # occasionally hot-reloads mid-test — not a code bug)
    final = None
    started = time.time()
    consecutive_5xx = 0
    while time.time() - started < 120:
        time.sleep(4)
        try:
            s = httpx.get(
                f"{api_url}/api/customer/website/repair/status/{job_id}",
                headers={"Authorization": f"Bearer {founder_token}"},
                timeout=15.0,
            )
        except Exception:
            continue
        if s.status_code >= 500:
            consecutive_5xx += 1
            assert consecutive_5xx < 10, (
                f"backend repeatedly 5xx ({s.status_code}) — real outage"
            )
            continue
        consecutive_5xx = 0
        assert s.status_code == 200, f"unexpected {s.status_code}: {s.text[:200]}"
        body = s.json()
        if body.get("status") in ("plan_ready_for_customer", "failed"):
            final = body
            break
    assert final is not None, "repair job did not complete within 120s"
    assert final.get("status") == "plan_ready_for_customer", (
        f"terminal status {final.get('status')!r} != plan_ready_for_customer"
    )

    # score_after MUST be None — only re-scan sets it
    assert final.get("score_after") is None, (
        f"score_after is {final.get('score_after')!r} — pre-D-75 random delta back"
    )

    # repair_plan must contain ≥1 item with real LLM provider metadata
    plan = final.get("repair_plan") or []
    assert len(plan) >= 1, "repair_plan is empty — LLM never produced output"
    item = plan[0]
    assert item.get("llm_provider"), (
        "plan item missing `llm_provider` — proof it came from a real LLM"
    )
    assert item.get("llm_model"), "plan item missing `llm_model`"
    # latency_ms must be present and > 0 (real network round-trip)
    lat = item.get("llm_latency_ms")
    assert isinstance(lat, (int, float)) and lat > 0, (
        f"plan item has no llm_latency_ms or is 0 — was the LLM actually called?"
    )

    # Email must have either {"ok": True, "email_id": <real-id>} OR
    # an honest error string (NEVER mock-pass).
    email = final.get("email_result") or {}
    if email.get("ok"):
        assert "email_id" in email, (
            "email_result.ok is True but no email_id — looks like a mock pass"
        )
    else:
        # On failure path the `error` must be present and informative
        err = email.get("error", "")
        assert err, "email_result.ok=False but no error string — silent failure"

    # events must NOT contain any of the pre-D-75 fake phrases
    events = final.get("events") or []
    joined = "\n".join(e.get("message", "") for e in events)
    forbidden = ("Canary rollout", "SOC 2 audit-chain",
                 "42/42 assertions", "Full deploy confirmed",
                 "CDN cache invalidated")
    for phrase in forbidden:
        assert phrase not in joined, (
            f"event log contains forbidden fake phrase {phrase!r}"
        )

    # next_step must explicitly tell customer to re-scan
    nxt = (final.get("next_step") or "").lower()
    assert "re-scan" in nxt or "rescan" in nxt, (
        f"next_step doesn't tell the customer to re-scan: {nxt!r}"
    )
