"""
services/campaign_health.py — iter D-59

Live status report for every component the marketing campaign depends
on. Each row returns a standard shape that the admin page renders as
🟢 / 🔴 with daily-progress detail or root-cause.

Hard rules:
  • Pure inspection — never mutates state.
  • Low-cost: every check is a single Mongo query or an env lookup.
  • Deterministic: the same call gives the same answer (timestamp
    differs).

Shape of each row:
  {
    "component":  "ghost_scout",
    "status":     "green" | "red" | "yellow",
    "headline":   "20 runs last 24h",
    "detail":     "last @ 18:17 UTC, query='roofing contractor'",
    "issue":      None | "WHAPI_BLAST_DISABLED=true",
    "autofix":    None | "trigger_scout_run" | "manual_topup" | ...
    "checked_at": iso,
  }
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_minus(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


# ── Individual checks ────────────────────────────────────────────────

async def _check_ghost_scout() -> dict[str, Any]:
    cnt = await _db.ghost_scout_log.count_documents({"ts": {"$gte": _iso_minus(24)}}) if _db is not None else 0
    last = await _db.ghost_scout_log.find_one({}, {"_id": 0}, sort=[("ts", -1)]) if _db is not None else None
    if cnt == 0:
        return {
            "component": "ghost_scout",
            "status":   "red",
            "headline": "no runs in last 24h",
            "detail":   "scheduler may be stopped or proxy expired",
            "issue":    "scout_dormant",
            "autofix":  "trigger_scout_run",
        }
    return {
        "component": "ghost_scout",
        "status":   "green",
        "headline": f"{cnt} runs last 24h",
        "detail":   f"last @ {(last or {}).get('ts','?')[:19]} q={(last or {}).get('query','?')}",
        "issue":    None,
        "autofix":  None,
    }


async def _check_auto_blast() -> dict[str, Any]:
    abc = await _db.auto_blast_config.find_one(
        {"tenant_id": "global"}, {"_id": 0},
    ) if _db is not None else None
    abc = abc or {}
    last_at  = abc.get("last_run_at", "")
    sent     = int(abc.get("last_run_sent", 0))
    note     = abc.get("last_run_note", "")
    if not last_at:
        return {
            "component": "auto_blast",
            "status":   "red",
            "headline": "never run",
            "detail":   "scheduler not firing",
            "issue":    "blast_scheduler_dormant",
            "autofix":  "trigger_blast_cycle",
        }
    # Run within last 30 min = healthy
    cutoff_30m = (datetime.now(timezone.utc)
                   - timedelta(minutes=30)).isoformat()
    fresh = last_at >= cutoff_30m
    if not fresh:
        return {
            "component": "auto_blast",
            "status":   "red",
            "headline": "stale (>30 min)",
            "detail":   f"last @ {last_at[:19]}, sent={sent}, note={note}",
            "issue":    "blast_stale",
            "autofix":  "trigger_blast_cycle",
        }
    if sent == 0 and note == "no-eligible-leads":
        return {
            "component": "auto_blast",
            "status":   "yellow",
            "headline": "running but pool empty",
            "detail":   f"last @ {last_at[:19]}, no eligible leads",
            "issue":    "no_eligible_leads",
            "autofix":  "topup_via_scout",
        }
    return {
        "component": "auto_blast",
        "status":   "green",
        "headline": f"sent={sent} last cycle",
        "detail":   f"last @ {last_at[:19]}, note={note}",
        "issue":    None,
        "autofix":  None,
    }


async def _check_resend() -> dict[str, Any]:
    if not os.environ.get("RESEND_API_KEY"):
        return {
            "component": "resend",
            "status":   "red",
            "headline": "RESEND_API_KEY missing",
            "detail":   "set the env var on the host",
            "issue":    "resend_key_missing",
            "autofix":  None,    # founder must paste the key
        }
    sent_24h = 0
    if _db is not None:
        pipe = [
            {"$match": {"ts": {"$gte": _iso_minus(24)}}},
            {"$unwind": "$result.sent"},
            {"$match": {"result.sent.channel": "email",
                          "result.sent.id":      {"$exists": True}}},
            {"$count": "n"},
        ]
        async for d in _db.outreach_history.aggregate(pipe):
            sent_24h = d["n"]
    if sent_24h == 0:
        return {
            "component": "resend",
            "status":   "yellow",
            "headline": "key OK, 0 deliveries last 24h",
            "detail":   "check Resend dashboard for bounce / domain block",
            "issue":    "no_recent_deliveries",
            "autofix":  None,
        }
    return {
        "component": "resend",
        "status":   "green",
        "headline": f"{sent_24h} deliveries last 24h",
        "detail":   "Resend webhook tracking opens / clicks",
        "issue":    None,
        "autofix":  None,
    }


async def _check_twilio() -> dict[str, Any]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
    wa  = os.environ.get("TWILIO_WA_FROM_NUMBER", "")
    if not (sid and tok):
        return {
            "component": "twilio",
            "status":   "red",
            "headline": "TWILIO creds missing",
            "detail":   "SMS + WhatsApp fallback both blocked",
            "issue":    "twilio_creds_missing",
            "autofix":  None,
        }
    if not wa:
        return {
            "component": "twilio",
            "status":   "yellow",
            "headline": "SMS OK, WhatsApp number missing",
            "detail":   "set TWILIO_WA_FROM_NUMBER for WABA channel",
            "issue":    "twilio_wa_number_missing",
            "autofix":  None,
        }
    return {
        "component": "twilio",
        "status":   "green",
        "headline": "creds + WABA number set",
        "detail":   "SMS + WhatsApp fallback ready",
        "issue":    None,
        "autofix":  None,
    }


async def _check_whapi() -> dict[str, Any]:
    tok = os.environ.get("WHAPI_API_TOKEN", "")
    dis = (os.environ.get("WHAPI_BLAST_DISABLED", "false").lower()
            in ("1", "true", "yes"))
    if not tok:
        return {
            "component": "whapi",
            "status":   "yellow",
            "headline": "WHAPI not configured",
            "detail":   "Twilio WABA will handle WhatsApp",
            "issue":    None,
            "autofix":  None,
        }
    if dis:
        return {
            "component": "whapi",
            "status":   "yellow",
            "headline": "WHAPI disabled by env flag",
            "detail":   "Twilio WABA fallback wired (D-57)",
            "issue":    "whapi_blast_disabled",
            "autofix":  None,
        }
    return {
        "component": "whapi",
        "status":   "green",
        "headline": "WHAPI active",
        "detail":   "primary WA channel",
        "issue":    None,
        "autofix":  None,
    }


async def _check_proactive_ora() -> dict[str, Any]:
    if _db is None:
        return {"component": "proactive_ora", "status": "red",
                 "headline": "db unreachable", "detail": "", "issue": "db",
                 "autofix": None}
    cfg = await _db.proactive_ora_config.find_one(
        {"tenant_id": "global"}, {"_id": 0},
    ) or {}
    enabled = [k for k, v in (cfg.get("enabled_rules") or {}).items() if v]
    fired_24h = await _db.outreach_history.count_documents({
        "type":   {"$regex": "^proactive_ora_"},
        "ts":     {"$gte": _iso_minus(24)},
    })
    if not enabled:
        return {
            "component": "proactive_ora",
            "status":   "yellow",
            "headline": "all rules OFF",
            "detail":   "founder has not enabled any rules",
            "issue":    "rules_off",
            "autofix":  None,    # founder choice
        }
    return {
        "component": "proactive_ora",
        "status":   "green",
        "headline": f"{len(enabled)} rule(s) on",
        "detail":   f"rules={','.join(enabled)} · {fired_24h} actions/24h",
        "issue":    None,
        "autofix":  None,
    }


async def _check_template_perf() -> dict[str, Any]:
    if _db is None:
        return {"component": "template_perf", "status": "red",
                 "headline": "db unreachable", "detail": "",
                 "issue": "db", "autofix": None}
    events_30d = await _db.blast_performance.count_documents({
        "ts": {"$gte": _iso_minus(24 * 30)},
    })
    state = await _db.blast_template_state.find_one(
        {"_id": "global"}, {"_id": 0},
    ) or {}
    if events_30d == 0:
        return {
            "component": "template_perf",
            "status":   "yellow",
            "headline": "no events tracked yet",
            "detail":   "tag outgoing emails with template_id",
            "issue":    "no_perf_events",
            "autofix":  None,
        }
    return {
        "component": "template_perf",
        "status":   "green",
        "headline": f"{events_30d} events last 30d",
        "detail":   f"default={state.get('default_template','?')}",
        "issue":    None,
        "autofix":  None,
    }


async def _check_daily_brief() -> dict[str, Any]:
    if _db is None:
        return {"component": "daily_brief", "status": "red",
                 "headline": "db unreachable", "detail": "",
                 "issue": "db", "autofix": None}
    last = await _db.daily_briefs.find_one(
        {}, {"_id": 0, "kind": 1, "generated_at": 1},
        sort=[("generated_at", -1)],
    )
    if not last:
        return {
            "component": "daily_brief",
            "status":   "yellow",
            "headline": "never run",
            "detail":   "first cron fires at 09:00 America/Toronto",
            "issue":    "brief_never_run",
            "autofix":  "send_morning_brief",
        }
    return {
        "component": "daily_brief",
        "status":   "green",
        "headline": f"last {last['kind']} brief sent",
        "detail":   f"at {last['generated_at'][:19]}",
        "issue":    None,
        "autofix":  None,
    }


async def _check_lead_pool() -> dict[str, Any]:
    if _db is None:
        return {"component": "lead_pool", "status": "red",
                 "headline": "db unreachable", "detail": "",
                 "issue": "db", "autofix": None}
    elig = await _db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "noise_flag":    {"$ne": True},
        "$or": [
            {"email": {"$nin": ["", None]}},
            {"phone": {"$nin": ["", None]}},
        ],
        "status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]},
    })
    if elig == 0:
        # Distinguish "campaign caught up" (good problem) from "pool empty".
        already_blasted = await _db.campaign_leads.count_documents({
            "last_blast_at": {"$exists": True},
        })
        total = await _db.campaign_leads.count_documents({})
        if total > 100 and already_blasted >= int(total * 0.80):
            return {
                "component": "lead_pool",
                "status":   "yellow",
                "headline": f"campaign caught up · {already_blasted} blasted / {total} total",
                "detail":   "all current leads already contacted — top up to keep firing",
                "issue":    "all_contacted",
                "autofix":  "topup_via_scout",
            }
        return {
            "component": "lead_pool",
            "status":   "red",
            "headline": "0 eligible leads",
            "detail":   "scout exhausted or all already contacted",
            "issue":    "pool_empty",
            "autofix":  "topup_via_scout",
        }
    if elig < 25:
        return {
            "component": "lead_pool",
            "status":   "yellow",
            "headline": f"{elig} eligible leads (low)",
            "detail":   "run scout to top up",
            "issue":    "pool_low",
            "autofix":  "topup_via_scout",
        }
    return {
        "component": "lead_pool",
        "status":   "green",
        "headline": f"{elig} eligible leads",
        "detail":   "blast queue healthy",
        "issue":    None,
        "autofix":  None,
    }


async def _check_emergent_llm() -> dict[str, Any]:
    if not os.environ.get("EMERGENT_LLM_KEY"):
        return {
            "component": "emergent_llm",
            "status":   "yellow",
            "headline": "EMERGENT_LLM_KEY missing",
            "detail":   "free-tier LLM ladder will be used",
            "issue":    "emergent_key_missing",
            "autofix":  None,
        }
    return {
        "component": "emergent_llm",
        "status":   "green",
        "headline": "EMERGENT_LLM_KEY set",
        "detail":   "premium LLM access available",
        "issue":    None,
        "autofix":  None,
    }


async def _check_resend_webhook() -> dict[str, Any]:
    """Resend webhook receiving events? (uses lead_lifecycle outreach
    history written by lifecycle handler)."""
    if _db is None:
        return {"component": "resend_webhook", "status": "yellow",
                 "headline": "db unreachable", "detail": "",
                 "issue": "db", "autofix": None}
    # Webhook handler updates campaign_leads.hot_lead_flag — easiest signal
    recent_hot = await _db.campaign_leads.count_documents({
        "hot_lead_signal_at": {"$gte": _iso_minus(24)},
    })
    if recent_hot == 0:
        return {
            "component": "resend_webhook",
            "status":   "yellow",
            "headline": "no webhook events last 24h",
            "detail":   "configure URL in Resend dashboard or no emails opened",
            "issue":    "no_webhook_events",
            "autofix":  None,
        }
    return {
        "component": "resend_webhook",
        "status":   "green",
        "headline": f"{recent_hot} opens/clicks last 24h",
        "detail":   "webhook is firing",
        "issue":    None,
        "autofix":  None,
    }


# ── Master report ────────────────────────────────────────────────────

async def full_report() -> dict[str, Any]:
    rows = await __import__("asyncio").gather(
        _check_ghost_scout(),
        _check_auto_blast(),
        _check_resend(),
        _check_twilio(),
        _check_whapi(),
        _check_proactive_ora(),
        _check_template_perf(),
        _check_daily_brief(),
        _check_lead_pool(),
        _check_emergent_llm(),
        _check_resend_webhook(),
    )
    by_status = {"green": 0, "yellow": 0, "red": 0}
    for r in rows:
        by_status[r.get("status", "red")] = by_status.get(r.get("status", "red"), 0) + 1
        r["checked_at"] = _now()
    return {
        "ok":         True,
        "summary":    by_status,
        "rows":       rows,
        "generated_at": _now(),
    }
