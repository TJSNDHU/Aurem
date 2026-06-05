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
        # iter D-66 — WhatsApp via Twilio isn't the only path. If WHAPI
        # is wired (TOKEN set and not disabled), or SMS is the only need
        # right now, the system is functionally healthy. Mark green and
        # describe which channel is active.
        whapi_tok      = os.environ.get("WHAPI_API_TOKEN", "")
        whapi_disabled = (os.environ.get("WHAPI_BLAST_DISABLED", "false").lower()
                           in ("1", "true", "yes"))
        wa_active = bool(whapi_tok and not whapi_disabled)
        return {
            "component": "twilio",
            "status":   "green",
            "headline": "SMS OK · WA via WHAPI" if wa_active else "SMS OK (WhatsApp not wired)",
            "detail":   ("WhatsApp routes through WHAPI primary channel"
                          if wa_active else
                          "set TWILIO_WA_FROM_NUMBER or enable WHAPI for WhatsApp"),
            "issue":    None if wa_active else "wa_channel_optional",
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
    twilio_wa = os.environ.get("TWILIO_WA_FROM_NUMBER", "")
    if not tok:
        # No WHAPI token. Honest state depends on whether Twilio WA is
        # wired as the fallback. iter D-66 — make this green when an
        # alternate channel exists; we're a campaign tool, not a single-
        # vendor monitor.
        if twilio_wa:
            return {
                "component": "whapi",
                "status":   "green",
                "headline": "WHAPI not used · Twilio WABA active",
                "detail":   "WhatsApp routes through Twilio's WABA channel",
                "issue":    None,
                "autofix":  None,
            }
        return {
            "component": "whapi",
            "status":   "yellow",
            "headline": "no WhatsApp channel wired",
            "detail":   "neither WHAPI_API_TOKEN nor TWILIO_WA_FROM_NUMBER set",
            "issue":    "no_wa_channel",
            "autofix":  None,
        }
    if dis:
        # iter D-66 — explicit env disable IS the intended state when
        # using Twilio WABA. Green if Twilio path exists; yellow only
        # when no WA channel at all.
        if twilio_wa:
            return {
                "component": "whapi",
                "status":   "green",
                "headline": "WHAPI disabled · Twilio WABA primary",
                "detail":   "intentional fallback to Twilio (iter D-57)",
                "issue":    None,
                "autofix":  None,
            }
        return {
            "component": "whapi",
            "status":   "yellow",
            "headline": "WHAPI disabled and Twilio WA missing",
            "detail":   "set TWILIO_WA_FROM_NUMBER or re-enable WHAPI",
            "issue":    "wa_fully_offline",
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
        # iter D-66 — autofix can flip on safe defaults (R1+R2). These
        # are non-spammy rules (R1=3-day no-reply follow-up email,
        # R2=opened-no-reply WhatsApp ping). R3+R4 stay off (need
        # extra plumbing).
        return {
            "component": "proactive_ora",
            "status":   "yellow",
            "headline": "all rules OFF",
            "detail":   "enable R1+R2 safe defaults via autofix",
            "issue":    "rules_off",
            "autofix":  "enable_proactive_defaults",
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
    # iter D-66 — the original check looked at `blast_performance` only,
    # which is populated by the Resend webhook. That collection stays
    # empty until the webhook URL is set in the Resend dashboard. Real
    # fix: also count outbound sends that were tagged with a template_id
    # — those events are written by `send_email(...)` every time,
    # webhook or not. So we surface template usage even before opens
    # / clicks start flowing.
    events_30d = await _db.blast_performance.count_documents({
        "ts": {"$gte": _iso_minus(24 * 30)},
    })
    # Fallback signal: emails sent with a template_id tag (outreach_history).
    tagged_sends_30d = await _db.outreach_history.count_documents({
        "ts":          {"$gte": _iso_minus(24 * 30)},
        "template_id": {"$exists": True, "$nin": ["", None]},
    })
    state = await _db.blast_template_state.find_one(
        {"_id": "global"}, {"_id": 0},
    ) or {}
    if events_30d == 0 and tagged_sends_30d == 0:
        return {
            "component": "template_perf",
            "status":   "yellow",
            "headline": "no template_id tags on sends yet",
            "detail":   "tag every send with template_id in send_email()",
            "issue":    "no_perf_events",
            "autofix":  None,
        }
    if events_30d == 0 and tagged_sends_30d > 0:
        return {
            "component": "template_perf",
            "status":   "green",
            "headline": f"{tagged_sends_30d} tagged sends · waiting on webhook for opens/clicks",
            "detail":   f"sends tracked OK · configure Resend webhook for engagement metrics",
            "issue":    None,
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
    """Resend webhook receiving events? iter D-66 — broaden the signal:
    any of the following counts as 'webhook is firing':
      • a campaign_lead with `hot_lead_signal_at` in last 24h (opens/clicks)
      • a touchpoint with sub_type starting `resend_` (delivered, opened…)
      • a blast_performance row written from the webhook handler
    Founders typically configure the URL late — without this broader read,
    the page sits yellow even while emails are flowing.
    """
    if _db is None:
        return {"component": "resend_webhook", "status": "yellow",
                 "headline": "db unreachable", "detail": "",
                 "issue": "db", "autofix": None}
    cutoff_24h = _iso_minus(24)
    # Signal 1 — hot-lead (open/click) flag
    recent_hot = await _db.campaign_leads.count_documents({
        "hot_lead_signal_at": {"$gte": cutoff_24h},
    })
    # Signal 2 — any touchpoint sub_type recorded by the webhook handler
    recent_touch = await _db.outreach_history.count_documents({
        "ts":       {"$gte": cutoff_24h},
        "sub_type": {"$regex": "^resend_"},
    })
    # Signal 3 — template_perf events from webhook
    recent_perf = await _db.blast_performance.count_documents({
        "ts":     {"$gte": cutoff_24h},
        "source": "resend_webhook",
    }) if await _db.list_collection_names() else 0  # tolerate missing coll
    # Signal 4 — any document in webhook audit log (if main code persists one)
    try:
        recent_audit = await _db.resend_webhook_log.count_documents({
            "ts": {"$gte": cutoff_24h},
        })
    except Exception:
        recent_audit = 0
    total_signals = recent_hot + recent_touch + recent_perf + recent_audit
    if total_signals == 0:
        return {
            "component": "resend_webhook",
            "status":   "yellow",
            "headline": "no webhook events last 24h",
            "detail":   ("configure URL in Resend dashboard: "
                          "<host>/api/lifecycle/resend-webhook"),
            "issue":    "no_webhook_events",
            "autofix":  None,
        }
    return {
        "component": "resend_webhook",
        "status":   "green",
        "headline": f"{total_signals} events last 24h",
        "detail":   (f"touchpoints={recent_touch} opens/clicks={recent_hot} "
                      f"tpl_perf={recent_perf} audit={recent_audit}"),
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
