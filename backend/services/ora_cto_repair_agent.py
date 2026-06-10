"""
services/ora_cto_repair_agent.py — ORA CTO as a repair worker.

Iter 325f Phase 2 + iter 325g LLM rewiring.

Polls `db.pending_approvals` every 5 minutes for items of type:
   crash, endpoint_failure, security_fix, code_error

For each item, asks `services.llm_gateway_v2.route()` for a code-aware
analysis. The gateway is already wired to:
  - DeepSeek V3.1 via OpenRouter (primary, ~$0.0001 per task)
  - Claude Sonnet 4.5 via Anthropic/Emergent (fallback + sensitive tasks)

Sensitive flags
---------------
When the issue touches authentication / billing / JWT / Stripe / KYC,
we route via a task type listed in ``llm_gateway_v2.SENSITIVE_TASKS``
so the gateway's privacy guard strips DeepSeek/Kimi/Qwen from the
chain and forces Claude. Detection is keyword-based against the
approval title + detail.

The proposal — including the LLM response and tier classification — is
persisted to `db.ora_cto_proposals`. Tier-1 proposals (config/env
single-line edits) are auto-applied after the 5-minute cancel window
baked into the pending_approvals row. Tier-2 proposals (multi-file
code edits or anything HIGH-severity) escalate to the founder via
Telegram (services/telegram_bot_service).

The legacy localhost:8002 daemon path is no longer required. The
``ORA_CTO_URL`` env var is reserved for the future Legion integration
but is read only when ``ORA_CTO_USE_LEGION=true``; otherwise we always
go through the gateway.

Collections written
-------------------
  db.ora_cto_proposals  — every proposal (response, tier, status)
  db.pending_approvals  — status updated when a proposal lands

Schema (ora_cto_proposals):
  proposal_id, approval_id, type, signature, status (pending_apply |
  awaiting_founder | llm_unavailable | cancelled), tier, severity,
  summary, llm_response, llm_provider, llm_model, llm_tokens_in,
  llm_tokens_out, llm_latency_ms, sensitive (bool), created_at,
  applied_at, applied_by
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Reserved for Legion daemon (future). When ORA_CTO_USE_LEGION=true,
# the worker will round-trip a local CTO daemon at this URL instead of
# the LLM gateway. Default is the gateway path.
CTO_URL = os.environ.get("ORA_CTO_URL", "http://localhost:8002").rstrip("/")
USE_LEGION = (os.environ.get("ORA_CTO_USE_LEGION") or "").lower() in ("1", "true", "yes")
CTO_TIMEOUT_S = float(os.environ.get("ORA_CTO_TIMEOUT_S", "60"))
POLL_INTERVAL_S = int(os.environ.get("ORA_CTO_POLL_INTERVAL_S", "300"))  # 5 min
PROPOSAL_BATCH = int(os.environ.get("ORA_CTO_BATCH_SIZE", "5"))

REPAIRABLE_TYPES = ("crash", "endpoint_failure", "security_fix", "code_error")

# When the issue text smells like auth / billing / JWT / Stripe / KYC,
# we promote it to the sensitive lane so the gateway forces Claude
# (US-hosted) instead of DeepSeek. Conservative — false positives just
# cost ~10× more per task; false negatives are a privacy bug.
SENSITIVE_KEYWORDS = (
    "auth", "login", "logout", "session", "token", "jwt",
    "password", "credential", "2fa", "totp", "mfa",
    "stripe", "billing", "invoice", "subscription", "card",
    "kyc", "pii", "ssn", "tax_id",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


# ─── Tier classification ────────────────────────────────────────────────
# Conservative — anything we can't 100% identify as a config/env edit is
# escalated to tier 2.
TIER1_HINTS = (
    "env var", "environment variable", "single-line", "single line",
    "config value", ".env", "feature flag", "toggle",
    "restart worker", "restart pillar", "kick pillar",
)


def _classify_tier(cto_response_text: str, severity: str) -> int:
    """Return 1 (auto-apply) or 2 (founder approval)."""
    if (severity or "").lower() in ("critical", "high"):
        return 2  # security/HIGH severity always tier 2
    text = (cto_response_text or "").lower()
    if any(hint in text for hint in TIER1_HINTS):
        # Only tier 1 if the response talks about a SINGLE concrete change.
        if "multi-file" in text or "files changed" in text:
            return 2
        return 1
    return 2


# ─── Sensitivity gate ───────────────────────────────────────────────────
def _is_sensitive(approval: Dict[str, Any]) -> bool:
    """Return True iff this issue touches auth/billing/JWT/etc. Used to
    pick the SENSITIVE task type that bans DeepSeek and forces Claude."""
    haystack = " ".join((
        approval.get("title") or "",
        approval.get("detail") or "",
        approval.get("source") or "",
        str(approval.get("metadata") or ""),
    )).lower()
    return any(kw in haystack for kw in SENSITIVE_KEYWORDS)


# ─── CTO call ───────────────────────────────────────────────────────────
async def _ask_cto(approval: Dict[str, Any]) -> Dict[str, Any]:
    """Single round-trip to the LLM gateway (DeepSeek V3.1 primary,
    Claude fallback). Returns ``{ok, response, elapsed_ms, error,
    provider, model, tokens_in, tokens_out, sensitive}``.
    Never raises."""
    sensitive = _is_sensitive(approval)
    # Sensitive issues route via a task type listed in SENSITIVE_TASKS
    # so the gateway's _redact_sensitive_providers strips DeepSeek and
    # forces Claude Sonnet.
    task_type = "auth_token_decision" if sensitive else "repair_diagnose"

    system = (
        "You are the AUREM CTO. An autonomous scanner detected an issue. "
        "Investigate (you don't have tool access — reason from the context "
        "given) and reply with EXACTLY this structure:\n"
        "  ROOT CAUSE: one sentence.\n"
        "  PROPOSED FIX: a single concrete change. State if it is a "
        "single-line env-var/config edit OR a multi-file code change.\n"
        "  DIFF: unified-diff snippet if a code edit; otherwise the "
        "exact env value or command to run."
    )
    prompt = (
        f"type      : {approval.get('type')}\n"
        f"severity  : {approval.get('severity')}\n"
        f"source    : {approval.get('source')}\n"
        f"title     : {approval.get('title')}\n"
        f"detail    :\n{(approval.get('detail') or '')[:2000]}\n"
        f"metadata  : {approval.get('metadata') or {}}\n"
    )

    # Optional Legion daemon path (off by default).
    if USE_LEGION:
        return await _ask_cto_legion(approval, system, prompt)

    try:
        from services.llm_gateway_v2 import route
        res = await route(
            task_type=task_type,
            prompt=prompt,
            system=system,
            max_tokens=1500,
        )
    except Exception as e:
        return {"ok": False, "error": "gateway_unavailable",
                "detail": str(e)[:200], "sensitive": sensitive}

    if not res.get("ok") or not (res.get("text") or "").strip():
        return {
            "ok": False,
            "error": res.get("error") or "empty_response",
            "elapsed_ms": res.get("latency_ms"),
            "provider": res.get("provider"),
            "model": res.get("model"),
            "sensitive": sensitive,
        }

    return {
        "ok": True,
        "response": (res.get("text") or "")[:8000],
        "elapsed_ms": res.get("latency_ms"),
        "provider": res.get("provider"),
        "model": res.get("model"),
        "tokens_in": res.get("tokens_in"),
        "tokens_out": res.get("tokens_out"),
        "sensitive": sensitive,
    }


async def _ask_cto_legion(approval: Dict[str, Any], system: str, prompt: str) -> Dict[str, Any]:
    """Legacy/future path — round-trip a local ORA CTO daemon. Only
    used when ORA_CTO_USE_LEGION=true."""
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx_missing"}
    sensitive = _is_sensitive(approval)
    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=CTO_TIMEOUT_S) as c:
            r = await c.post(
                f"{CTO_URL}/api/chat",
                json={"message": f"{system}\n\n{prompt}",
                      "session_id": approval.get("approval_id")},
            )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        if r.status_code != 200:
            return {"ok": False, "error": f"legion_http_{r.status_code}",
                    "elapsed_ms": elapsed, "sensitive": sensitive}
        data = r.json()
        response_text = (data.get("response") or data.get("reply")
                         or data.get("text") or data.get("output")
                         or str(data))[:8000]
        return {"ok": True, "response": response_text,
                "elapsed_ms": elapsed,
                "provider": "legion", "model": "ora_cto_local",
                "sensitive": sensitive}
    except Exception as e:
        return {"ok": False, "error": "legion_unreachable",
                "detail": str(e)[:200], "sensitive": sensitive}


# ─── Proposal persistence + dispatch ────────────────────────────────────
async def _persist_proposal(
    db, approval: Dict[str, Any], cto: Dict[str, Any], tier: int
) -> Dict[str, Any]:
    if cto.get("ok"):
        status = "awaiting_founder" if tier == 2 else "pending_apply"
    else:
        status = "llm_unavailable"
    row = {
        "proposal_id": str(uuid.uuid4())[:12],
        "approval_id": approval.get("approval_id"),
        "type": approval.get("type"),
        "signature": approval.get("fingerprint") or approval.get("signature"),
        "severity": approval.get("severity"),
        "tier": tier,
        "status": status,
        "summary": (cto.get("response") or "")[:600],
        "llm_response": cto.get("response"),
        "llm_provider": cto.get("provider"),
        "llm_model": cto.get("model"),
        "llm_tokens_in": cto.get("tokens_in"),
        "llm_tokens_out": cto.get("tokens_out"),
        "llm_latency_ms": cto.get("elapsed_ms"),
        "llm_error": cto.get("error"),
        "sensitive": bool(cto.get("sensitive")),
        "created_at": _now_iso(),
    }
    await db.ora_cto_proposals.insert_one(row)
    await db.pending_approvals.update_one(
        {"approval_id": approval.get("approval_id")},
        {"$set": {
            "cto_proposal_id": row["proposal_id"],
            "cto_status": status,
            "cto_seen_at": _now_iso(),
        }},
    )
    row.pop("_id", None)
    return row


async def _notify_founder(approval: Dict[str, Any], proposal: Dict[str, Any]) -> None:
    """Tier-2 escalation to Telegram. Best-effort."""
    try:
        from services.telegram_bot_service import send_telegram_alert
        await send_telegram_alert(
            message=(
                f"Approval needed:\n\n"
                f"Type    : {approval.get('type')}\n"
                f"Severity: {approval.get('severity')}\n"
                f"Title   : {approval.get('title')}\n\n"
                f"CTO proposal (first 800 chars):\n"
                f"{(proposal.get('cto_response') or '')[:800]}\n\n"
                f"Approve: aurem.live/admin/approvals#{approval.get('approval_id')}"
            ),
            alert_type="ora_cto_proposal",
            fingerprint=approval.get("approval_id"),
        )
    except Exception as e:
        logger.warning(f"[ora_cto_repair_agent] telegram escalation failed: {e}")


# ─── Main loop ──────────────────────────────────────────────────────────
async def run_repair_tick(db=None) -> Dict[str, Any]:
    """Single pass — process up to PROPOSAL_BATCH new approvals.
    Returns a stats dict useful for cron logging + tests.

    iter D-73 also surfaces:
      * `legacy_count` — pre-iter-325f rows the agent can't process,
        so ops sees the backlog without grepping mongo.
      * `stale_awaiting_founder` — Shannon/proposal rows >14d in
        awaiting_founder state, waiting on the founder who'll never
        come back. Visible in stats so the admin endpoint
        /api/admin/autonomous-repair/expire-stale can clear them.
    """
    db = db if db is not None else _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    # iter D-73 — observability fields. Cheap counts, run once per tick.
    legacy_count = 0
    stale_awaiting = 0
    try:
        legacy_count = await db.pending_approvals.count_documents(
            {"type": {"$exists": False}}
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        stale_awaiting = await db.pending_approvals.count_documents({
            "status": "pending_approval",
            "cto_status": "awaiting_founder",
            "$or": [
                {"created_at": {"$lt": cutoff}},
                {"created_at": {"$lt": cutoff.isoformat()}},
            ],
        })
    except Exception:
        # Counts are observability, not correctness — never fail the tick.
        pass

    # Pick rows we haven't proposed against yet (cto_proposal_id missing).
    cursor = db.pending_approvals.find(
        {"type": {"$in": list(REPAIRABLE_TYPES)},
         "status": "pending_approval",
         "cto_proposal_id": {"$exists": False}},
        {"_id": 0},
    ).sort("created_at", 1).limit(PROPOSAL_BATCH)

    stats = {"considered": 0, "proposed": 0, "tier1": 0, "tier2": 0,
             "cto_unavailable": 0, "errors": 0, "sensitive_routed": 0,
             "llm_unavailable": 0,
             # iter D-73 observability
             "legacy_count": legacy_count,
             "stale_awaiting": stale_awaiting}
    async for approval in cursor:
        stats["considered"] += 1
        try:
            cto = await _ask_cto(approval)
            if cto.get("sensitive"):
                stats["sensitive_routed"] += 1
            tier = _classify_tier(cto.get("response", ""), approval.get("severity", "medium"))
            proposal = await _persist_proposal(db, approval, cto, tier)
            if cto.get("ok"):
                stats["proposed"] += 1
                if tier == 1:
                    stats["tier1"] += 1
                else:
                    stats["tier2"] += 1
                    await _notify_founder(approval, proposal)
            else:
                # Maintain back-compat key 'cto_unavailable' for older
                # log-scrapers + add 'llm_unavailable' as the proper name.
                stats["cto_unavailable"] += 1
                stats["llm_unavailable"] += 1
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"[ora_cto_repair_agent] tick error: {e}")
    stats["ok"] = True
    return stats


async def ora_cto_repair_agent_loop() -> None:
    """Background loop — used when wired via asyncio.create_task instead
    of APScheduler. Sleeps POLL_INTERVAL_S between ticks."""
    logger.info(f"[ora_cto_repair_agent] loop start, poll={POLL_INTERVAL_S}s")
    while True:
        try:
            stats = await run_repair_tick()
            if stats.get("considered"):
                logger.info(f"[ora_cto_repair_agent] tick {stats}")
        except Exception as e:
            logger.error(f"[ora_cto_repair_agent] unexpected: {e}")
        await asyncio.sleep(POLL_INTERVAL_S)
