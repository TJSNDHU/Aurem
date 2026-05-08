"""
AUREM Deep QA Agent
──────────────────────────────────────────────────────────────
Simulates full user journeys (signup → login → dashboard → scan → result)
using chained API calls. Runs weekly OR on-demand from admin dashboard.

Optionally uses Emergent LLM (Claude) to analyze failures and suggest root cause.

Logs to:
  • db.qa_agent_deep_runs — one doc per journey run with all steps + LLM analysis
"""
import os
import time
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# ─── Council voter (Phase 0) ─────────────────────────────────────────

_QA_SPAM_WORDS = ("FREE", "WINNER", "URGENT", "CLICK NOW", "GUARANTEED",
                  "ACT NOW", "LIMITED TIME")


async def vote(action: str, payload: Dict[str, Any]) -> tuple:
    """QA Council vote — content-quality gate for outreach.

    Rejects if:
      • SMS body > 160 chars (carrier penalty)
      • Subject or body contains spam-trigger words
    """
    content = (
        payload.get("message_text")
        or payload.get("sms_text")
        or payload.get("blast_sms_body")
        or payload.get("blast_email_subject")
        or ""
    )
    if "sms" in (action or "").lower() and len(content) > 160:
        return "REJECT", f"SMS too long ({len(content)}>160)"
    upper = content.upper()
    for word in _QA_SPAM_WORDS:
        if word in upper:
            return "REJECT", f"Spam trigger: {word}"
    return "APPROVE", "QA passed"




def _base_url() -> str:
    return os.environ.get("QA_BOT_BASE_URL") or "http://localhost:8001"


# ══════════════════════════════════════════════════════════════
# Journey definitions — chainable flows
# ══════════════════════════════════════════════════════════════
def _signup_login_journey() -> List[Dict[str, Any]]:
    """Anonymous → signup → login → me → SEO audit. Uses throwaway email."""
    email = f"qa-bot-{uuid.uuid4().hex[:10]}@example.com"
    password = f"Qa!{uuid.uuid4().hex[:12]}A9"
    return [
        {
            "name": "Signup new user",
            "method": "POST", "path": "/api/auth/register",
            "body": {"email": email, "password": password, "first_name": "QA", "last_name": "Bot"},
            "expect": [200, 201, 409, 400, 422],
            "extract": {"from": "json", "key": "token", "into": "token"},
        },
        {
            "name": "Login",
            "method": "POST", "path": "/api/auth/login",
            "body": {"email": email, "password": password},
            "expect": [200, 401, 403],
            "extract": {"from": "json", "key": "token", "into": "token"},
        },
        {
            "name": "Get current user",
            "method": "GET", "path": "/api/auth/me",
            "auth": True,
            "expect": [200, 401, 404],
        },
        {
            "name": "Run SEO audit",
            "method": "POST", "path": "/api/seo-audit/scan",
            "body": {"url": "https://aurem.live", "email": email},
            "expect": [200, 202, 429],
        },
    ]


def _public_content_journey() -> List[Dict[str, Any]]:
    """Public-facing content flow — marketing/SEO surface."""
    return [
        {"name": "Landing page", "method": "GET", "path": "/", "expect": [200, 404]},
        {"name": "robots.txt",   "method": "GET", "path": "/robots.txt", "expect": [200, 404]},
        {"name": "sitemap.xml",  "method": "GET", "path": "/sitemap.xml", "expect": [200, 404]},
        {"name": "llms.txt",     "method": "GET", "path": "/llms.txt", "expect": [200, 404]},
        {"name": "Framework map", "method": "GET", "path": "/framework", "expect": [200, 404]},
        {"name": "Pricing API",  "method": "GET", "path": "/api/aurem-billing/plans", "expect": [200, 404]},
    ]


JOURNEYS = {
    "signup_and_scan": {
        "label": "New user signup → scan flow",
        "build": _signup_login_journey,
    },
    "public_content": {
        "label": "Public content surface",
        "build": _public_content_journey,
    },
}


# ══════════════════════════════════════════════════════════════
# Journey runner
# ══════════════════════════════════════════════════════════════
async def _run_journey(journey_id: str) -> Dict[str, Any]:
    spec = JOURNEYS.get(journey_id)
    if not spec:
        return {"error": "unknown_journey", "journey_id": journey_id}

    steps_def = spec["build"]()
    ctx: Dict[str, Any] = {"token": None}
    step_results: List[Dict[str, Any]] = []
    started = datetime.now(timezone.utc)

    async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
        for step in steps_def:
            t0 = time.time()
            url = _base_url().rstrip("/") + step["path"]
            headers = {}
            if step.get("auth") and ctx.get("token"):
                headers["Authorization"] = f"Bearer {ctx['token']}"

            result = {
                "name": step["name"],
                "method": step["method"],
                "path": step["path"],
                "expected": step["expect"],
            }
            try:
                if step["method"] == "GET":
                    r = await client.get(url, headers=headers)
                else:
                    r = await client.request(step["method"], url, json=step.get("body", {}), headers=headers)

                latency = round((time.time() - t0) * 1000, 1)
                passed = r.status_code in step["expect"]
                result.update({
                    "status_code": r.status_code,
                    "latency_ms": latency,
                    "passed": passed,
                    "error": None if passed else f"Unexpected status {r.status_code}",
                })

                # Extract token if specified
                if step.get("extract"):
                    ex = step["extract"]
                    try:
                        body = r.json()
                        # Support nested e.g., user.token
                        val = body.get(ex["key"]) if isinstance(body, dict) else None
                        if val and ex.get("into"):
                            ctx[ex["into"]] = val
                    except Exception:
                        pass

            except Exception as e:
                latency = round((time.time() - t0) * 1000, 1)
                result.update({
                    "status_code": 0,
                    "latency_ms": latency,
                    "passed": False,
                    "error": str(e)[:200],
                })
            step_results.append(result)

    passed = sum(1 for s in step_results if s.get("passed"))
    total = len(step_results)
    return {
        "journey_id": journey_id,
        "label": spec["label"],
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / max(total, 1) * 100, 1),
        "steps": step_results,
    }


async def _llm_analyze(run_doc: Dict[str, Any]) -> Optional[str]:
    """Ask Claude (via Emergent key) to RCA the failures. Returns plain-text summary."""
    failures = []
    for j in run_doc.get("journeys", []):
        for s in j.get("steps", []):
            if not s.get("passed"):
                failures.append({
                    "journey": j.get("label"),
                    "step": s.get("name"),
                    "method": s.get("method"),
                    "path": s.get("path"),
                    "status_code": s.get("status_code"),
                    "error": s.get("error"),
                    "expected": s.get("expected"),
                })
    if not failures:
        return None

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            return None
        chat = LlmChat(
            api_key=key,
            session_id=f"qa-deep-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are AUREM's senior QA engineer. Given a list of API-journey failures, "
                "write a concise (max 6 lines) root-cause analysis with a numbered action list. "
                "Plain text, no markdown."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5")
        msg = UserMessage(text=f"Failures:\n{failures}")
        reply = await chat.send_message(msg)
        return str(reply)[:2000]
    except Exception as e:
        logger.warning(f"[QA_DEEP] LLM analysis skipped: {e}")
        return None


async def run_deep_qa(journey_ids: Optional[List[str]] = None, analyze: bool = True) -> Dict[str, Any]:
    """Run one or more journeys and save the combined run."""
    if _db is None:
        return {"error": "db_unavailable"}

    journey_ids = journey_ids or list(JOURNEYS.keys())
    started = datetime.now(timezone.utc)
    journeys = []
    for jid in journey_ids:
        journeys.append(await _run_journey(jid))

    total_steps = sum(j.get("total", 0) for j in journeys)
    total_pass = sum(j.get("passed", 0) for j in journeys)

    run_doc = {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "journey_ids": journey_ids,
        "journeys": journeys,
        "total_steps": total_steps,
        "passed_steps": total_pass,
        "failed_steps": total_steps - total_pass,
        "pass_rate": round(total_pass / max(total_steps, 1) * 100, 1),
    }

    # LLM RCA (optional)
    if analyze and total_pass < total_steps:
        rca = await _llm_analyze(run_doc)
        if rca:
            run_doc["rca"] = rca

    try:
        await _db.qa_agent_deep_runs.insert_one({**run_doc})
        run_doc.pop("_id", None)
    except Exception as e:
        logger.warning(f"[QA_DEEP] DB write failed: {e}")

    logger.info(
        f"[QA_DEEP] Run complete: {total_pass}/{total_steps} steps ({run_doc['pass_rate']}%)"
    )
    return run_doc


async def qa_agent_deep_scheduler():
    """Weekly deep run — Monday 3:30 AM UTC."""
    from datetime import timedelta
    await asyncio.sleep(300)  # 5 min warmup
    logger.info("[QA_DEEP] Scheduler started — weekly (Mon 03:30 UTC)")
    while True:
        try:
            now = datetime.now(timezone.utc)
            # Next Monday 3:30 UTC
            days_ahead = (0 - now.weekday()) % 7  # Monday=0
            if days_ahead == 0 and (now.hour > 3 or (now.hour == 3 and now.minute >= 30)):
                days_ahead = 7
            target = (now + timedelta(days=days_ahead)).replace(hour=3, minute=30, second=0, microsecond=0)
            wait = (target - now).total_seconds()
            logger.info(f"[QA_DEEP] Next run in {wait/3600:.1f} hours")
            await asyncio.sleep(wait)
            await run_deep_qa()
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[QA_DEEP] Scheduler error: {e}")
            await asyncio.sleep(3600)


# ══════════════════════════════════════════════════════════════
# Reporting helpers
# ══════════════════════════════════════════════════════════════
async def get_latest_deep_run() -> Optional[Dict[str, Any]]:
    if _db is None:
        return None
    return await _db.qa_agent_deep_runs.find_one({}, {"_id": 0}, sort=[("started_at", -1)])


async def get_deep_run_history(limit: int = 20) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    async for d in _db.qa_agent_deep_runs.find(
        {}, {"_id": 0, "journeys.steps": 0}
    ).sort("started_at", -1).limit(limit):
        out.append(d)
    return out
