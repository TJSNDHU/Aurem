"""
Pillars Map Router — 3-Level Deep-Drill Diagnostic System (iter 269).
══════════════════════════════════════════════════════════════════════

Drives /admin/pillars-map. A recursive Pillar ➡ Collection ➡ Service health tree
designed to eliminate "silent failures" (worker reports green while DB writes
have stopped).

Level 1 — Pillar:
  Aggregate status rollup of all child collections & worker tasks.
Level 2 — Collection:
  Per-collection doc count + `last_write_at` freshness (silent-failure detect).
  If collection is expected to write and most-recent doc is > threshold old,
  mark it RED even if worker task is alive.
Level 3 — Service:
  Grep-based discovery of Python files that reference the collection.
  Lets operator jump straight to the suspect service file + recent errors.

Endpoints:
  GET  /api/admin/pillars-map/overview
  GET  /api/admin/pillars-map/collection/{name}/services
  GET  /api/admin/pillars-map/collection/{name}/errors
  GET  /api/admin/pillars-map/heartbeat            (cached snapshot, 200 fast)
  GET  /api/admin/pillars-map/health
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException

from utils.admin_guard import verify_admin as _unified_verify_admin

router = APIRouter(prefix="/api/admin/pillars-map", tags=["Pillars Map"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"

# Silent-failure thresholds — mark collection RED if no writes in this window
# (only applies to collections with `expects_writes=True`).
SILENT_FAILURE_MINUTES = 15

# iter 285.8 — per-collection threshold overrides.
# iter 322 — extended for known slow-cadence writers. Default is
# SILENT_FAILURE_MINUTES (15). Workers with slower cadences get longer
# windows so a single missed APScheduler tick doesn't paint the pillar red.
# Rule of thumb: threshold = expected_cadence_minutes × 2.5
SILENT_FAILURE_OVERRIDES = {
    # ClawChief heartbeat runs every 15 min + 3 min startup delay → buffer to 25 min
    "heartbeats":          25,
    # Site monitor runs every 5 min → 15 min default is fine but give generous buffer
    "site_monitor_logs":   20,
    # system_pulse is legacy (writer archived); give long buffer since we downgrade
    # to expects_writes=False below — this override is insurance only
    "system_pulse":        1440,
    # Hourly self-audit + nightly cycles need wider windows
    "self_audit_log":      90,
    "nightly_cycle_log":   1500,  # nightly = ~24h, allow 25h buffer
    "ora_brain_thoughts":  120,   # ORA learning is bursty
    "agent_actions":       45,    # agent ticks staggered
    "campaign_leads":      60,    # outreach ticks every 30-60 min
    "scout_runs":          90,    # scout ticks slow (Google Places quotas)
    "dr_backup_runs":      1500,  # daily DR mirror
    "council_decisions":   120,   # council convenes when needed
    "approvals":           240,   # approvals bursty
    "voice_call_logs":     1440,  # voice can have multi-hour idle stretches
    # Outreach channel writers — degrade to yellow not red when external
    # quota throttles them (handled below in breaker-aware logic).
    "email_log":           60,
    "sms_logs":            60,
}


def _threshold_minutes_for(coll_name: str) -> int:
    return SILENT_FAILURE_OVERRIDES.get(coll_name, SILENT_FAILURE_MINUTES)

# Codebase root for service discovery
_BACKEND_ROOT = "/app/backend"

# In-memory cache for service discovery (grep is ~500ms, cache avoids repeat)
_service_cache: dict[str, list[dict]] = {}

# Public base URL used to HEAD-check frontend routes and ping backend APIs.
# Falls back to same-origin if not set. Resolved at runtime.
_PUBLIC_BASE_URL_ENV = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
_LOCAL_BACKEND_URL = "http://localhost:8001"


def _resolve_public_base() -> str:
    """Best-effort resolution:
    1. PUBLIC_BASE_URL env var (explicit)
    2. REACT_APP_BACKEND_URL from /app/frontend/.env (fallback)
    3. empty string (disables FE HEAD checks)
    """
    if _PUBLIC_BASE_URL_ENV:
        return _PUBLIC_BASE_URL_ENV
    try:
        with open("/app/frontend/.env", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""


# Cache resolved URL at import time — but allow override via env later.
_PUBLIC_BASE_RESOLVED = _resolve_public_base()


def set_db(db):
    global _db
    _db = db


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> dict:
    return _unified_verify_admin(
        authorization,
        secret=_jwt_secret or (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
        algorithm=_jwt_alg,
    )


# ══════════════════════════════════════════════════════════════════════
# Pillar → Collection ownership map
# Each entry: (collection_name, label, empty_is_ok, expects_writes)
#   - empty_is_ok=True    → green even if 0 docs (pre-launch OK)
#   - empty_is_ok=False   → yellow if 0 docs (seed data expected)
#   - expects_writes=True → flag RED if last-write older than SILENT_FAILURE_MINUTES
#                           (detects silent failures — worker green but DB stopped)
# ══════════════════════════════════════════════════════════════════════

PILLAR_MAP = {
    "p1_sales": {
        "label": "Pillar 1 — Sales & Outreach",
        "prefix": "p1:",
        "color": "#3b82f6",
        "collections": [
            ("campaign_leads",      "Lead Pool",             False, False),
            ("campaigns",           "Campaign Configs",      False, False),
            ("do_not_contact",      "DNC List",              True,  False),
            ("unsubscribes",        "Unsubscribes",          True,  False),
            ("envoy_outreach",      "Envoy Outreach Queue",  True,  False),
            ("first_contact_emails","First Contact Emails",  True,  False),
            ("sms_logs",            "SMS Logs",              True,  False),
            ("email_logs",          "Email Logs",            True,  False),
            ("whatsapp_message_log","WhatsApp Log",          True,  False),
            ("sent_emails",         "Sent Emails",           True,  False),
            ("voice_call_logs",     "Voice Call Logs",       True,  False),
            ("drip_campaigns_log",  "Drip Campaigns",        True,  False),
        ],
    },
    "p2_billing": {
        "label": "Pillar 2 — Billing & Onboarding",
        "prefix": "p2:",
        "color": "#F59E0B",
        "collections": [
            ("subscription_plans",      "Subscription Plans",    False, False),
            ("customer_subscriptions",  "Active Subscriptions",  True,  False),
            ("payment_transactions",    "Payments",              True,  False),
            ("aurem_abandoned_carts",   "Abandoned Carts",       True,  False),
            ("aurem_onboarding",        "Onboarding State",      True,  False),
            ("tenant_customers",        "Tenant Customers",      True,  False),
            ("compliance_evidence",     "SOC 2 Evidence",        True,  False),
            ("compliance_reports",      "Compliance Reports",    True,  False),
            ("referrals",               "Referral Tracking",     True,  False),
            ("aurem_billing",           "Billing Config",        True,  False),
            ("customer_token_wallets",  "Token Wallets",         True,  False),
            ("payment_reminders",       "Payment Reminders",     True,  False),
        ],
    },
    "p3_monitor": {
        "label": "Pillar 3 — Site Monitor & Self-Heal",
        "prefix": "p3:",
        "color": "#22C55E",
        "collections": [
            ("repair_fixes",              "Auto-Fix Queue",         False, False),
            ("shannon_reports",           "Shannon Audits",         True,  False),
            ("sentinel_alerts",           "Sentinel Alerts",        True,  False),
            ("sentinel_diagnoses",        "Sentinel Diagnoses",     True,  False),
            # site_monitor_logs should write every 5 min → silent-failure flag ON
            ("site_monitor_logs",         "Site Monitor Logs",      True,  True),
            ("site_monitor_endpoints",    "Monitored Endpoints",    True,  False),
            ("client_scan_results",       "Client Scan Results",    True,  False),
            ("customer_website_fixes",    "Client Website Fixes",   True,  False),
            ("repair_deployments",        "Repair Deployments",     True,  False),
            ("live_patches",              "Live Patches",           True,  False),
            ("known_fixes",               "Known Fixes Library",    True,  False),
            ("unfixable_issues_queue",    "Unfixable Queue",        True,  False),
        ],
    },
    "p4_command_hub": {
        "label": "Pillar 4 — Command Hub & Observability",
        "prefix": "p4:",
        "color": "#A855F7",
        "collections": [
            ("auto_heal_log",        "Auto-Heal Log",          True, False),
            ("auto_heal_runs",       "Auto-Heal Runs",         True, False),
            ("auto_repair_log",      "Auto-Repair Log",        True, False),
            # system_pulse writer was moved to _archive (legacy collection —
            # pillar_heartbeats now carries the live signal). Keep listed as
            # passive cache (empty-OK, no writes expected) so operators still
            # see the historical doc count. iter 285.8
            ("system_pulse",         "System Pulse (legacy)",  True, False),
            ("heartbeats",           "Worker Heartbeats",      True, True),
            ("qa_bot_runs",          "QA Bot Runs",            True, False),
            ("qa_bot_alerts",        "QA Bot Alerts",          True, False),
            ("qa_agent_deep_runs",   "QA Deep Runs",           True, False),
            ("system_audit_reports", "System Audit Reports",   True, False),
            ("autonomy_audits",      "Autonomy Audits",        True, False),
            ("morning_briefs",       "Morning Briefs",         True, False),
            ("audit_chain",          "Audit Chain",            True, False),
            ("audit_backups",        "Audit Backups",          True, False),
            ("git_backup_log",       "Git Backup Log",         True, False),
            ("stem_fixes",           "Stem-Fix Queue",         True, False),
            ("stem_fix_backups",     "Stem-Fix Backups",       True, False),
            ("migrations",           "Migration Trail",        True, False),
            ("client_errors",        "Client Error Stream",    True, False),
            ("deployment_log",       "Deployment Log",         True, False),
        ],
    },
}

# Flattened index for quick lookups: collection_name → (pillar_key, label, empty_ok, expects_writes)
COLLECTION_INDEX: dict[str, tuple[str, str, bool, bool]] = {}
for _pk, _spec in PILLAR_MAP.items():
    for _c in _spec["collections"]:
        COLLECTION_INDEX[_c[0]] = (_pk, _c[1], _c[2], _c[3])


# ══════════════════════════════════════════════════════════════════════
# Collection → primary writer scheduler(s)
# Backend-side pulse (Triple-Pulse Layer 2) is GREEN iff at least ONE of
# these scheduler names is present in asyncio.all_tasks() and not done.
# If a collection has no entry here we fall back to "any worker of the
# owning pillar is alive" = backend green.
# Scheduler names match `t.get_name()` assigned in pillars/*/worker.py.
# ══════════════════════════════════════════════════════════════════════

COLLECTION_WRITERS: dict[str, list[str]] = {
    # ── Pillar 1 · Sales ──
    "campaign_leads":        ["p1:auto_blast_scheduler", "p1:news_monitor_scheduler", "p1:proactive_outreach"],
    "campaigns":             ["p1:auto_blast_scheduler"],
    "envoy_outreach":        ["p1:proactive_outreach"],
    "first_contact_emails":  ["p1:auto_blast_scheduler", "p1:proactive_outreach"],
    "sms_logs":              ["p1:auto_blast_scheduler"],
    "email_logs":            ["p1:auto_blast_scheduler"],
    "whatsapp_message_log":  ["p1:auto_blast_scheduler"],
    "sent_emails":           ["p1:auto_blast_scheduler"],
    "voice_call_logs":       ["p1:auto_blast_scheduler"],
    "drip_campaigns_log":    ["p1:auto_blast_scheduler"],

    # ── Pillar 2 · Billing ──
    # iter 322p — `aurem_abandoned_carts` and `payment_reminders` no longer
    # have dedicated writer schedulers (abandoned_cart_scheduler /
    # day21_review_scheduler / birthday_bonus_scheduler were deprecated to
    # no-op stubs in iter 322h). Removing their writer mappings makes the
    # backend pulse fall back to "any P2 worker alive" → green when the
    # pillar is healthy. Writes happen via Stripe webhooks + onboarding
    # endpoints, not background ticks, so the silent-failure threshold on
    # these collections is also turned off (expects_writes already False).
    "aurem_onboarding":      ["p2:aurem_morning_scheduler"],
    "compliance_evidence":   ["p2:compliance_scheduler"],
    "compliance_reports":    ["p2:compliance_scheduler"],

    # ── Pillar 3 · Site Monitor / Self-Heal ──
    "site_monitor_logs":     ["p3:site_monitor_scheduler"],
    "site_monitor_endpoints":["p3:site_monitor_scheduler"],
    "shannon_reports":       ["p3:shannon_runner"],
    "sentinel_alerts":       ["p3:self_repair_loop"],
    "sentinel_diagnoses":    ["p3:self_repair_loop"],
    "repair_fixes":          ["p3:self_repair_loop"],
    "repair_deployments":    ["p3:self_repair_loop"],
    "live_patches":          ["p3:self_repair_loop"],

    # ── Pillar 4 · Command Hub ──
    "auto_heal_log":         ["p4:auto_heal_scheduler"],
    "auto_heal_runs":        ["p4:auto_heal_scheduler"],
    "auto_repair_log":       ["p4:auto_repair_scheduler"],
    "system_pulse":          ["p4:auto_heal_scheduler", "p4:pillar_heartbeat"],
    "heartbeats":            ["p4:clawchief_heartbeat", "p4:pillar_heartbeat"],
    "pillar_heartbeats":     ["p4:pillar_heartbeat"],
    "qa_bot_runs":           ["p4:qa_bot_pulse_scheduler"],
    "qa_bot_alerts":         ["p4:qa_bot_pulse_scheduler"],
    "qa_agent_deep_runs":    ["p4:qa_agent_deep_scheduler"],
    "system_audit_reports":  ["p4:system_audit_scheduler"],
    "autonomy_audits":       ["p4:autonomy_cron_scheduler"],
    "morning_briefs":        ["p4:daily_digest_scheduler", "p4:orchestrator_digest_scheduler"],
    "audit_chain":           ["p4:autonomy_cron_scheduler"],
    "audit_backups":         ["p4:backup_loop"],
    "git_backup_log":        ["p4:backup_loop"],
    "stem_fixes":            [],  # admin-triggered, not scheduler-driven → skip writer check
    "stem_fix_backups":      [],
    "migrations":            [],  # one-shot CLI scripts
    "client_errors":         [],  # ingested via public endpoint, not scheduler
    "deployment_log":        [],
}


def _live_task_names() -> set[str]:
    """Snapshot current live asyncio task names."""
    return {t.get_name() for t in asyncio.all_tasks() if not t.done()}


# iter 325y — Orchestrator boot grace.
# `SCHED_BOOT_DELAY_S` (default 25s) is deliberate cold-boot breathing
# room for the pillar workers — see server.py `_deferred_orch_run`.
# During this window, no `p[1-4]:*` scheduler task is alive yet, so the
# old watchdog flashed RED for ~30 seconds on every restart and the
# admin saw scary "0/1 writers live" badges (e.g. user screenshot
# 2026-05-21). Fix: until the orchestrator has had a chance to attach
# (boot_delay + 60s settle window), report YELLOW with a clear reason
# instead of RED.
_PROCESS_STARTED_AT = datetime.now(timezone.utc)
_ORCH_GRACE_SECONDS = (
    float(os.environ.get("SCHED_BOOT_DELAY_S", "25")) + 60.0
)


def _in_boot_grace() -> bool:
    elapsed = (datetime.now(timezone.utc) - _PROCESS_STARTED_AT).total_seconds()
    return elapsed < _ORCH_GRACE_SECONDS


def _backend_pulse(coll_name: str, pillar_live_count: int, live_names: set[str]) -> tuple[str, str]:
    """Compute backend-side status for a collection.

    Returns (status, reason). `status` ∈ {green, yellow, red}.
    Rule:
      - If COLLECTION_WRITERS has entries:
          green = any mapped scheduler name in live_names
          yellow = none present BUT we're inside the orchestrator boot grace
          red   = none present AND grace has elapsed
      - Else (unmapped / admin-only collections):
          green if pillar_live_count > 0 else yellow
    """
    writers = COLLECTION_WRITERS.get(coll_name)
    if writers is None or writers == []:
        if pillar_live_count > 0:
            return "green", "pillar workers live"
        return "yellow", "no writer mapping"
    alive = [w for w in writers if w in live_names]
    if alive:
        return "green", f"{len(alive)}/{len(writers)} writer(s) live"
    # iter 325y — orchestrator boot grace: avoid red flash on restart.
    if _in_boot_grace():
        elapsed = int((datetime.now(timezone.utc) - _PROCESS_STARTED_AT).total_seconds())
        return "yellow", f"booting · orchestrator grace ({elapsed}s / {int(_ORCH_GRACE_SECONDS)}s)"
    # iter D-34 — LITE-mode demote. If EVERY writer is a `p4:*` scheduler
    # and the pod is in LITE mode, the writer is intentionally paused on
    # prod to save RAM (D-13 work). Surface as yellow `lite_mode` instead
    # of an outage-style red.
    if writers and all(w.startswith("p4:") for w in writers) and _is_lite_mode():
        return "yellow", "lite_mode — writer paused on prod (saves RAM)"
    return "red", f"0/{len(writers)} writers live"


async def _get_last_write(coll_name: str) -> Optional[datetime]:
    """Return the timestamp of the most recently inserted doc, using _id (ObjectId).

    ObjectId.generation_time is always populated for Mongo _id of type ObjectId.
    Fast because _id is always indexed. No doc scan needed.
    """
    try:
        # iter 282al-12 — bumped 0.6→2.0s. 0.6s was timing out on Atlas
        # cold sockets and producing false "no docs" reds even when the
        # collection had thousands of recent rows.
        doc = await asyncio.wait_for(
            _db[coll_name].find_one({}, sort=[("_id", -1)], projection={"_id": 1}),
            timeout=2.0,
        )
        if not doc:
            return None
        oid = doc.get("_id")
        if isinstance(oid, ObjectId):
            return oid.generation_time
        return None
    except Exception:
        return None


def _pick_worst(*statuses: str) -> str:
    """red > yellow > green."""
    if "red" in statuses:
        return "red"
    if "yellow" in statuses:
        return "yellow"
    return "green"


# iter D-34 — Module-level LITE-mode detector. Memoized after first call.
_LITE_MODE_CACHE: Optional[bool] = None


def _is_lite_mode() -> bool:
    """Returns True when AUREM_LITE_MODE=1 OR the pod hostname looks like
    Emergent production (so we never alarm the founder over schedulers
    that prod intentionally disables to save RAM)."""
    global _LITE_MODE_CACHE
    if _LITE_MODE_CACHE is not None:
        return _LITE_MODE_CACHE
    try:
        env_flag = os.environ.get("AUREM_LITE_MODE", "").strip()
        if env_flag in ("1", "true", "yes", "on"):
            _LITE_MODE_CACHE = True
            return True
        host = (os.environ.get("HOSTNAME") or "").lower()
        is_prod_pod = (
            ("live-support" in host or "emergent.host" in host)
            and not host.startswith("agent-env-")
        )
        _LITE_MODE_CACHE = bool(is_prod_pod)
    except Exception:
        _LITE_MODE_CACHE = False
    return _LITE_MODE_CACHE



# ══════════════════════════════════════════════════════════════════════
# Inter-Pillar Wiring — "Global Flow Map"
#
# Every wire is a declared data dependency between two pillars, modelled
# as a pair of source/target Mongo collections plus a max-lag threshold.
#
#   wire id:   "p1_to_p2_leads_to_customers"
#   rule:      if source has writes in last `activity_minutes` then target
#              must also have writes within `lag_seconds` of source's
#              last_write_at. Otherwise → yellow (slow) / red (broken).
#
# Status levels:
#   green  = both endpoints healthy & lag ≤ lag_seconds
#   yellow = source fresh but target lag > lag_seconds
#            or target reachable but no recent writes yet
#   red    = source has recent writes but target has no writes at all
#            (or collection unreachable, or lag > 3× threshold)
#
# If the source has been idle within `activity_minutes`, the wire is
# marked "idle" (grey) — no flow expected, no error.
# ══════════════════════════════════════════════════════════════════════

INTER_PILLAR_WIRES: list[dict] = [
    # P1 Sales → P2 Billing — a newly captured lead becomes a paying customer
    #
    # ⚠ ASPIRATIONAL / NON_BLOCKING:
    # This is a BUSINESS flow, not a system flow. The wire going red only
    # means "no lead converted into a paying customer within the lag window"
    # — which for a quiet/dev tenant is perfectly normal. Auto-heal cannot
    # repair "no human bought something". We still SHOW this wire red in UI
    # so the operator sees conversion drought, but we do NOT escalate
    # overall_status to red because of it (Truth-Sync: don't cry wolf on
    # system health when the system is healthy).
    {
        "id":                 "p1_to_p2_leads_to_customers",
        "source_pillar":      "p1_sales",
        "target_pillar":      "p2_billing",
        "source_collection":  "campaign_leads",
        "target_collection":  "tenant_customers",
        "activity_minutes":   60 * 24,   # source considered active if wrote in last 24h
        "lag_seconds":        60 * 60 * 24 * 30,  # iter 288.6 — relax to 30d (no paying customers yet is normal for early stage)
        "label":              "Lead → Customer",
        "description":        "Qualified lead from Sales becomes a paying customer row.",
        "non_blocking":       True,  # business flow — does not escalate overall_status
    },
    # P1 Sales → P4 Command Hub — every outreach event should land in observability
    {
        "id":                 "p1_to_p4_outreach_to_observability",
        "source_pillar":      "p1_sales",
        "target_pillar":      "p4_command_hub",
        "source_collection":  "email_logs",
        "target_collection":  "system_pulse",
        "activity_minutes":   60,
        "lag_seconds":        60 * 10,  # 10 min observability lag tolerated
        "label":              "Outreach → Pulse",
        "description":        "Email/SMS/WA outreach should register in the System Pulse stream.",
    },
    # P2 Billing → P4 Command Hub — payments must hit the audit chain
    {
        "id":                 "p2_to_p4_payments_to_audit",
        "source_pillar":      "p2_billing",
        "target_pillar":      "p4_command_hub",
        "source_collection":  "payment_transactions",
        "target_collection":  "audit_chain",
        "activity_minutes":   60 * 24,
        "lag_seconds":        60 * 15,  # payment → audit entry within 15 min
        "label":              "Payment → Audit",
        "description":        "Every Stripe payment must produce an immutable audit-chain row.",
    },
    # P3 Monitor → P4 Command Hub — downtime incidents must page the observer
    {
        "id":                 "p3_to_p4_monitor_to_alerts",
        "source_pillar":      "p3_monitor",
        "target_pillar":      "p4_command_hub",
        "source_collection":  "sentinel_alerts",
        "target_collection":  "auto_heal_log",
        "activity_minutes":   60,
        "lag_seconds":        60 * 5,
        "label":              "Alert → Auto-Heal",
        "description":        "Sentinel alerts should trigger an auto-heal entry within 5 min.",
    },
    # P4 Command Hub → P3 Monitor — approved stem-fixes must deploy
    {
        "id":                 "p4_to_p3_stemfix_to_deploy",
        "source_pillar":      "p4_command_hub",
        "target_pillar":      "p3_monitor",
        "source_collection":  "stem_fixes",
        "target_collection":  "repair_deployments",
        "activity_minutes":   60 * 24,
        "lag_seconds":        60 * 30,
        "label":              "Stem-Fix → Deploy",
        "description":        "Approved structural refactor must be deployed within 30 min.",
    },
    # P2 Billing → P1 Sales — new subscription should seed initial outreach
    #
    # ⚠ ASPIRATIONAL / NON_BLOCKING: same reasoning as p1_to_p2 — a
    # subscription row update ≠ a mandatory new drip. Show red, don't
    # escalate overall_status.
    {
        "id":                 "p2_to_p1_subscription_to_outreach",
        "source_pillar":      "p2_billing",
        "target_pillar":      "p1_sales",
        "source_collection":  "customer_subscriptions",
        "target_collection":  "drip_campaigns_log",
        "activity_minutes":   60 * 24,
        "lag_seconds":        60 * 60,
        "label":              "Subscription → Drip",
        "description":        "A new subscription should kick off a welcome/onboarding drip.",
        "non_blocking":       True,
    },
]


async def _check_wire(wire: dict) -> dict:
    """Return wire status dict: {id, source_*, target_*, status, reason,
    lag_seconds, src_last_write, tgt_last_write}."""
    src = wire["source_collection"]
    tgt = wire["target_collection"]
    now = datetime.now(timezone.utc)
    active_cutoff = now - timedelta(minutes=wire["activity_minutes"])

    try:
        src_lw, tgt_lw = await asyncio.gather(
            _get_last_write(src),
            _get_last_write(tgt),
            return_exceptions=True,
        )
    except Exception as e:
        return {
            **wire,
            "status":        "red",
            "reason":        f"query failed: {e}",
            "src_last_write": None,
            "tgt_last_write": None,
            "lag_seconds":   None,
        }

    if isinstance(src_lw, Exception):
        src_lw = None
    if isinstance(tgt_lw, Exception):
        tgt_lw = None

    # Idle source → no flow expected
    if src_lw is None or src_lw < active_cutoff:
        return {
            **wire,
            "status":         "idle",
            "reason":         "source idle, no flow expected",
            "src_last_write": src_lw.isoformat() if src_lw else None,
            "tgt_last_write": tgt_lw.isoformat() if tgt_lw else None,
            "lag_seconds":    None,
        }

    # Source fresh — target must also be fresh
    if tgt_lw is None:
        return {
            **wire,
            "status":         "red",
            "reason":         (
                "target has no writes — no business conversion yet (advisory only)"
                if wire.get("non_blocking") else "target has no writes — bridge broken"
            ),
            "src_last_write": src_lw.isoformat(),
            "tgt_last_write": None,
            "lag_seconds":    None,
        }

    lag = (src_lw - tgt_lw).total_seconds()
    # Positive lag = target older than source (behind). Negative lag = target wrote after source (healthy).
    if lag <= 0:
        return {
            **wire,
            "status":         "green",
            "reason":         f"target wrote {abs(int(lag))}s after source",
            "src_last_write": src_lw.isoformat(),
            "tgt_last_write": tgt_lw.isoformat(),
            "lag_seconds":    int(lag),
        }
    if lag <= wire["lag_seconds"]:
        return {
            **wire,
            "status":         "green",
            "reason":         f"lag {int(lag)}s within tolerance",
            "src_last_write": src_lw.isoformat(),
            "tgt_last_write": tgt_lw.isoformat(),
            "lag_seconds":    int(lag),
        }
    if lag <= wire["lag_seconds"] * 3:
        return {
            **wire,
            "status":         "yellow",
            "reason":         f"lag {int(lag)}s > {wire['lag_seconds']}s tolerance (slow)",
            "src_last_write": src_lw.isoformat(),
            "tgt_last_write": tgt_lw.isoformat(),
            "lag_seconds":    int(lag),
        }
    return {
        **wire,
        "status":         "red",
        "reason":         (
            f"lag {int(lag)}s > 3× tolerance ({wire['lag_seconds'] * 3}s) — "
            + ("no recent business conversion (advisory only)"
               if wire.get("non_blocking") else "bridge broken")
        ),
        "src_last_write": src_lw.isoformat(),
        "tgt_last_write": tgt_lw.isoformat(),
        "lag_seconds":    int(lag),
    }


async def _gather_wires() -> list[dict]:
    return list(await asyncio.gather(*[_check_wire(w) for w in INTER_PILLAR_WIRES]))


# ══════════════════════════════════════════════════════════════════════
# System Interface Flows — "Main-Screen X-Ray"
#
# Every critical page in the Admin Panel and Customer Portal is tracked
# as a 3-dimensional flow:
#
#   DB side       → required collections reachable (no query errors)
#   Backend side  → health-check API endpoint returns HTTP 200 and
#                   required schedulers are alive in asyncio.all_tasks()
#   Frontend side → HEAD on the public route returns 200/301/302 (meaning
#                   the React shell/bundle serves)
#
# Worst-of-three wins. Admin can see in one glance: "Is my Customer
# Portal /my/monitor page broken on any of the three axes?"
# ══════════════════════════════════════════════════════════════════════

SYSTEM_FLOWS: list[dict] = [
    # ══════════════════════════════════════════════════════════════
    # ADMIN PANEL — 6 critical flows
    # activity_collections → must have writes in last N min (functional health)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "admin_dash_overview",
        "surface": "admin",
        "label": "Dash-Overview",
        "fe_route": "/admin/root-command",
        "be_endpoint": "/api/admin/pillars-map/health",
        "required_collections": ["users", "pillar_heartbeats"],
        # iter 322bi — bumped 2 → 8 min. The pillar_heartbeat scheduler ticks
        # every 300s (5 min), so a 2-min freshness window was MATHEMATICALLY
        # IMPOSSIBLE to stay green for more than 24s out of every 300s window.
        # 8 min gives one full miss + safety buffer before flagging red.
        "activity_collections": [("pillar_heartbeats", 8)],
        "required_schedulers": ["p4:pillar_heartbeat"],
    },
    {
        "id": "admin_lead_manager",
        "surface": "admin",
        "label": "Lead Manager",
        "fe_route": "/dashboard",
        "be_endpoint": "/api/campaign/overview",
        "required_collections": ["campaign_leads", "campaigns"],
        "activity_collections": [],
        "required_schedulers": ["p1:auto_blast_scheduler"],
    },
    {
        "id": "admin_ora_logic",
        "surface": "admin",
        "label": "ORA Logic Settings",
        "fe_route": "/admin/agents",
        "be_endpoint": "/api/agents/status",
        "required_collections": ["agent_state", "agent_config"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    {
        "id": "admin_monitoring_hub",
        "surface": "admin",
        "label": "Monitoring Hub",
        "fe_route": "/admin/site-monitor",
        "be_endpoint": "/api/admin/site-monitor/overview",
        "required_collections": ["site_monitor_endpoints", "site_monitor_logs"],
        "activity_collections": [("site_monitor_logs", 15)],
        "required_schedulers": ["p3:site_monitor_scheduler"],
    },
    {
        "id": "admin_billing_invoicing",
        "surface": "admin",
        "label": "Billing / Invoicing",
        "fe_route": "/admin/plans",
        "be_endpoint": "/api/admin/catalog",
        "required_collections": ["service_catalog", "customer_subscriptions", "payment_transactions"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 280.14 — Payments / Stripe Webhook subsystem (4-axis health):
    #   DB        : payment_transactions, stripe_webhook_events reachable
    #   Backend   : /api/admin/payments/health rolls up:
    #               - Stripe key mode + sync
    #               - /api/stripe/webhook alias reachable (catches the
    #                 "404 webhook into the void" regression)
    #               - STRIPE_WEBHOOK_SECRET configured
    #               - recent payment_tx activity (no stale-out)
    #   Frontend  : /admin/plans serves
    {
        "id": "admin_payments_stripe",
        "surface": "admin",
        "label": "Payments + Stripe Webhook",
        "fe_route": "/admin/plans",
        "be_endpoint": "/api/admin/payments/health",
        "required_collections": ["payment_transactions", "stripe_webhook_events", "customer_subscriptions"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    {
        "id": "admin_stem_fix",
        "surface": "admin",
        "label": "Stem-Fix Queue",
        "fe_route": "/admin/stem-fix",
        "be_endpoint": "/api/admin/stem-fix/health",
        "required_collections": ["stem_fixes", "stem_fix_backups"],
        "activity_collections": [],
        "required_schedulers": [],
    },

    # ══════════════════════════════════════════════════════════════
    # CUSTOMER PORTAL — 6 critical flows
    # ══════════════════════════════════════════════════════════════
    {
        "id": "customer_landing",
        "surface": "customer",
        "label": "Landing Page",
        "fe_route": "/",
        "be_endpoint": "/api/health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    {
        "id": "customer_onboarding",
        "surface": "customer",
        "label": "Onboarding Wizard",
        "fe_route": "/welcome",
        "be_endpoint": "/api/onboarding/status",
        "required_collections": ["onboarding", "aurem_onboarding"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    {
        "id": "customer_site_status",
        "surface": "customer",
        "label": "Live Site Status",
        "fe_route": "/my/monitor",
        "be_endpoint": "/api/site-monitor/me/plan",
        "required_collections": ["site_monitor_endpoints", "site_monitor_free", "site_monitor_logs"],
        "activity_collections": [("site_monitor_logs", 15)],
        "required_schedulers": ["p3:site_monitor_scheduler"],
    },
    {
        "id": "customer_ora_chat",
        "surface": "customer",
        "label": "ORA AI Chat / Voice",
        "fe_route": "/my/dashboard",
        "be_endpoint": "/api/ora/health",
        "required_collections": ["voice_agent_configs", "voice_call_logs"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    {
        "id": "customer_payment_portal",
        "surface": "customer",
        "label": "Payment / Stripe Portal",
        "fe_route": "/pricing",
        "be_endpoint": "/api/catalog/services",
        "required_collections": ["service_catalog", "customer_subscriptions", "payment_transactions"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    {
        "id": "customer_user_settings",
        "surface": "customer",
        "label": "User Settings",
        "fe_route": "/my/dashboard",
        "be_endpoint": "/api/platform/auth/health",
        "required_collections": ["platform_users"],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282ad — Scout Web Scanner (webclaw) — Infrastructure pillar chip.
    # BE health pings webclaw with example.com; GREEN if scrape returns >50
    # chars, YELLOW if WEBCLAW_API_KEY unset (local-first skip), RED on error.
    {
        "id": "admin_web_scanner_webclaw",
        "surface": "admin",
        "label": "Web Scanner (webclaw)",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/webclaw/health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282ae — Website Builder brand injection chip (module-load check).
    {
        "id": "admin_website_builder_brand",
        "surface": "admin",
        "label": "Website Builder (Brand Injection)",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/webclaw/brand-injection",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282af — Site Diff Tracker chip (website_snapshots reachable).
    {
        "id": "admin_site_diff_tracker",
        "surface": "admin",
        "label": "Site Diff Tracker",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/webclaw/diff-health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282ag — Active Site Watcher chip (site_change_triggers reachable).
    {
        "id": "admin_active_site_watcher",
        "surface": "admin",
        "label": "Active Site Watcher",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/webclaw/watcher-health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282ai — ORA Composer (LLM) chip — Intelligence pillar.
    # iter 282al-12 — drop activity_collections=composer_fallbacks. It's
    # *intentionally* empty when the LLM cascade is healthy, so requiring
    # writes painted the chip red on a working system. BE health endpoint
    # already reflects cascade state.
    {
        "id": "admin_ora_composer_llm",
        "surface": "admin",
        "label": "ORA Composer (LLM)",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/composer/health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282aj — LinkedIn Publisher chip — Outreach pillar.
    # GREEN if connected + expires >7d; YELLOW <7d / not connected.
    # iter 282al-12 — drop activity_collections (zero posts is the cold-
    # start state; chip RED was misleading). BE status endpoint is the
    # source of truth.
    {
        "id": "admin_linkedin_publisher",
        "surface": "admin",
        "label": "LinkedIn Publisher",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/linkedin/status",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282ak — ORA Skills Router chip — Intelligence pillar.
    # iter 322bi — DROPPED activity_collections. Was requiring a
    # `skill_invocations` write every 24h, which only happens when a real
    # customer invokes a skill via chat. Cold periods (no chat in 24h) are a
    # legitimate state — same logic as ORA Learning Engine below. The chip
    # now reports purely on router availability (BE 200 + DB reachable).
    {
        "id": "admin_ora_skills_router",
        "surface": "admin",
        "label": "ORA Skills Router",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/skills/health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282ak — ORA Learning Engine chip — Intelligence pillar.
    # iter 282al-12 — drop activity_collections; empty `skill_learnings`
    # is the legitimate cold-start state. BE returns status:grey then,
    # which the evaluator now respects.
    {
        "id": "admin_ora_learning_engine",
        "surface": "admin",
        "label": "ORA Learning Engine",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/skills/learning-health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282al-4 — SEO Backlink Reclamation — Outreach pillar.
    # iter 282al-12 — drop activity_collections; service runs on a weekly
    # cron, 30m window is wrong shape.
    {
        "id": "admin_seo_unlinked_mentions",
        "surface": "admin",
        "label": "SEO Backlink Reclamation",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/seo/unlinked/health",
        "required_collections": [],
        "activity_collections": [],
        "required_schedulers": [],
    },
    # iter 282al-5 — Legion Sovereign Node (Ollama local LLM) — Infra pillar.
    # iter 332b D-30 — non_blocking: Ollama is an OPT-IN sovereign local LLM
    # node. Most tenants (including the founder's preview + production) do
    # not run Ollama, so `local_llm_usage` is naturally stale. This flow
    # still surfaces red in the UI for visibility but MUST NOT escalate
    # admin_worst → red and trigger the global "broken" badge. The previous
    # logic was painting the entire admin dashboard red purely because
    # nobody was using the optional Ollama feature.
    {
        "id": "admin_legion_sovereign_node",
        "surface": "admin",
        "label": "Legion Sovereign Node",
        "fe_route": "/admin/pillars-map",
        "be_endpoint": "/api/admin/sovereign/health",
        "required_collections": [],
        "activity_collections": ["local_llm_usage"],
        "required_schedulers": [],
        "non_blocking": True,
    },
]


async def _check_flow(flow: dict, live_names: set[str]) -> dict:
    """Compute DB / BE / FE status for one flow with STRICT functional health.

    DB:  required collections reachable AND (if specified) have writes within
         activity_minutes — catches "DB up but feature dead" silent failures.
    BE:  endpoint 2xx/3xx (4xx auth OK) AND required schedulers alive — catches
         "router loaded but worker crashed" silent failures.
    FE:  route HTTP 200 AND /manifest.json HTTP 200 — proves React bundle +
         CDN alive. Catches stale-build / broken-deploy where shell 200s but
         static assets 404.
    """
    now = datetime.now(timezone.utc)

    # ── DB side (reachable + activity) ────────────────────────────
    async def _check_coll_reachable(name: str) -> str:
        try:
            await asyncio.wait_for(_db[name].count_documents({}), timeout=0.6)
            return "green"
        except Exception:
            return "red"

    async def _check_coll_activity(name: str, mins: int) -> tuple[str, str]:
        lw = await _get_last_write(name)
        if lw is None:
            return "red", f"{name}: no docs"
        age_min = (now - lw).total_seconds() / 60.0
        if age_min <= mins:
            return "green", f"{name}: fresh {int(age_min)}m"
        return "red", f"{name}: stale {int(age_min)}m (>{mins}m)"

    coll_names = flow.get("required_collections", [])
    activity_specs = flow.get("activity_collections", [])
    db_statuses: list[str] = []
    db_reasons: list[str] = []

    if coll_names:
        reach_results = await asyncio.gather(*[_check_coll_reachable(c) for c in coll_names])
        if "red" in reach_results:
            bad = [c for c, s in zip(coll_names, reach_results) if s == "red"]
            db_statuses.append("red")
            db_reasons.append(f"unreachable: {','.join(bad)}")
        else:
            db_statuses.append("green")
            db_reasons.append(f"{len(coll_names)} reachable")

    if activity_specs:
        # iter 282al-9 hotfix — accept both ("name", minutes) tuples and
        # plain "name" strings (default window 30 min). Was crashing
        # heartbeat with "too many values to unpack" on str specs.
        norm_specs: list[tuple[str, int]] = []
        for spec in activity_specs:
            if isinstance(spec, str):
                norm_specs.append((spec, 30))
            elif isinstance(spec, (tuple, list)) and len(spec) >= 2:
                norm_specs.append((str(spec[0]), int(spec[1])))
            elif isinstance(spec, (tuple, list)) and len(spec) == 1:
                norm_specs.append((str(spec[0]), 30))
        act_results = await asyncio.gather(
            *[_check_coll_activity(c, m) for c, m in norm_specs]
        )
        for st, rs in act_results:
            db_statuses.append(st)
            db_reasons.append(rs)

    if not db_statuses:
        db_side = "green"
        db_reason = "no DB dependency"
    else:
        db_side = _pick_worst(*db_statuses)
        db_reason = " · ".join(db_reasons)

    # ── Backend side (endpoint + scheduler) ───────────────────────
    be_status_code: Optional[int] = None
    be_error: Optional[str] = None
    be_url = _LOCAL_BACKEND_URL + flow["be_endpoint"]
    # iter 280.14: capture body-level status field for endpoints that
    # roll up multi-axis health (e.g. /api/admin/payments/health).
    # When present, this overrides the HTTP-status-code-only inference
    # below — letting "all 200, but stripe in test mode" render yellow
    # rather than green.
    be_body_status: Optional[str] = None
    be_body_reason: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            r = await client.get(be_url)
            be_status_code = r.status_code
            try:
                payload = r.json()
                if isinstance(payload, dict):
                    s = payload.get("status")
                    if isinstance(s, str) and s.lower() in ("green", "yellow", "red", "grey", "gray"):
                        be_body_status = "yellow" if s.lower() in ("grey", "gray") else s.lower()
                        be_body_reason = payload.get("reason")
            except Exception:
                pass
    except Exception as e:
        be_error = str(e)[:80]

    sched_required = flow.get("required_schedulers", [])
    sched_alive = [s for s in sched_required if s in live_names]
    sched_missing = [s for s in sched_required if s not in live_names]

    # iter D-34 — LITE-mode awareness at the FLOW level.
    # Production runs with AUREM_LITE_MODE=1 to suppress 34 heavy P4
    # schedulers (saves ~700Mi RAM per pod). When the schedulers are
    # disabled ON PURPOSE, every flow that lists `p4:*` in its
    # required_schedulers would otherwise paint RED on the production
    # dashboard. Downgrade these to a "lite_mode" green-with-info state
    # so the founder sees calm "lite mode" instead of an outage.
    if sched_missing and _is_lite_mode():
        lite_disabled = [s for s in sched_missing if s.startswith("p4:")]
        still_required = [s for s in sched_missing if not s.startswith("p4:")]
        if lite_disabled and not still_required:
            sched_missing = []          # don't paint red
            # capture for downstream display:
            flow["_lite_disabled_schedulers"] = lite_disabled

    if be_error:
        be_side = "red"
        be_reason = f"endpoint error: {be_error}"
    elif be_status_code is None:
        be_side = "red"
        be_reason = "endpoint unreachable"
    elif be_status_code >= 500:
        be_side = "red"
        be_reason = f"HTTP {be_status_code}"
    elif be_status_code in (401, 403):
        # iter 325v — ROUTE-LEVEL ROOT-CAUSE FIX.
        # An auth-gated endpoint that responds 401/403 to an *un-authed*
        # localhost probe is PROOF the server + router are alive (the
        # request reached FastAPI and the auth middleware rejected it).
        # The old code left be_reason="HTTP 401" which is technically
        # correct but visually scary — admins on /admin/pillars-map saw
        # "BE 401" badges everywhere and assumed everything was broken.
        #
        # New behavior: explicit green with a human reason. Scheduler
        # checks below still run; if the scheduler is dead the flow
        # still goes red — auth status alone never masks a real outage.
        be_side = "green"
        be_reason = f"auth-gated endpoint reachable (HTTP {be_status_code})"
        if sched_missing:
            be_side = "red"
            be_reason = (
                f"scheduler(s) dead: {','.join(sched_missing)} "
                f"(endpoint itself is auth-gated reachable)"
            )
    elif be_status_code >= 400:
        be_side = "yellow"
        be_reason = f"HTTP {be_status_code}"
    elif sched_missing:
        be_side = "red"
        be_reason = f"scheduler(s) dead: {','.join(sched_missing)}"
    elif be_body_status:
        # iter 280.14 — endpoint reported its own roll-up status
        be_side = be_body_status
        be_reason = be_body_reason or f"HTTP {be_status_code} · body={be_body_status}"
    else:
        be_side = "green"
        be_reason = (
            f"HTTP {be_status_code}"
            + (f" · {len(sched_alive)} scheduler(s) live" if sched_alive else "")
        )

    # ── Frontend side (route + asset bundle) ──────────────────────
    fe_side = "green"
    fe_reason = "skipped"
    fe_route_status: Optional[int] = None
    fe_asset_status: Optional[int] = None

    if _PUBLIC_BASE_RESOLVED:
        route_url = _PUBLIC_BASE_RESOLVED + flow["fe_route"]
        asset_url = _PUBLIC_BASE_RESOLVED + "/manifest.json"
        try:
            async with httpx.AsyncClient(timeout=2.5, follow_redirects=False) as client:
                route_res, asset_res = await asyncio.gather(
                    client.get(route_url),
                    client.get(asset_url),
                    return_exceptions=True,
                )
            if isinstance(route_res, Exception):
                fe_side = "red"
                fe_reason = f"route failed: {str(route_res)[:40]}"
            else:
                fe_route_status = route_res.status_code
                if not isinstance(asset_res, Exception):
                    fe_asset_status = asset_res.status_code

                if not (200 <= fe_route_status < 400):
                    fe_side = "red"
                    fe_reason = f"route HTTP {fe_route_status}"
                elif fe_asset_status is not None and not (200 <= fe_asset_status < 400):
                    fe_side = "red"
                    fe_reason = f"assets HTTP {fe_asset_status} (CDN/build broken)"
                else:
                    fe_side = "green"
                    fe_reason = f"route {fe_route_status} · assets {fe_asset_status or 'n/a'}"
        except Exception as e:
            fe_side = "yellow"
            fe_reason = f"probe failed: {str(e)[:60]}"
    else:
        fe_side = "green"
        fe_reason = "PUBLIC_BASE_URL unresolved (skipped)"

    overall = _pick_worst(db_side, be_side, fe_side)

    return {
        "id":       flow["id"],
        "surface":  flow["surface"],
        "label":    flow["label"],
        "fe_route": flow["fe_route"],
        "be_endpoint": flow["be_endpoint"],
        "status":   overall,
        "non_blocking": bool(flow.get("non_blocking", False)),
        "triple_pulse": {
            "db":       {"status": db_side, "reason": db_reason,
                         "collections": coll_names,
                         "activity_windows": [
                             {"collection": (s if isinstance(s, str) else s[0]),
                              "minutes": (30 if isinstance(s, str)
                                          else (s[1] if len(s) >= 2 else 30))}
                             for s in activity_specs
                         ]},
            "backend":  {"status": be_side, "reason": be_reason,
                         "http_status": be_status_code,
                         "schedulers_required": sched_required,
                         "schedulers_alive": sched_alive,
                         "schedulers_missing": sched_missing},
            "frontend": {"status": fe_side, "reason": fe_reason,
                         "route_status": fe_route_status,
                         "asset_status": fe_asset_status},
        },
    }


async def _gather_flows() -> list[dict]:
    live_names = _live_task_names()
    # Limit concurrency so we don't stampede uvicorn during the sweep
    sem = asyncio.Semaphore(6)

    async def _one(f):
        async with sem:
            return await _check_flow(f, live_names)

    return list(await asyncio.gather(*[_one(f) for f in SYSTEM_FLOWS]))


async def _gather_pillar(key: str, spec: dict) -> dict:
    prefix = spec["prefix"]
    tasks = asyncio.all_tasks()
    workers_live = [t for t in tasks if t.get_name().startswith(prefix) and not t.done()]
    workers_done = [t for t in tasks if t.get_name().startswith(prefix) and t.done()]
    live_names = {t.get_name() for t in workers_live}

    # Frontend side is a single global check — if this code is running, the
    # API route itself is serving HTTP 200, so the frontend pulse is GREEN
    # for the whole snapshot. (Any outage would return 500/502 upstream.)
    frontend_side = "green"

    coll_rows: list[dict] = []
    reachable = 0
    unreachable = 0
    empty_but_required = 0
    silent_failures = 0
    backend_red = 0
    now = datetime.now(timezone.utc)
    # iter 285.8 — threshold is now per-collection (see SILENT_FAILURE_OVERRIDES)

    async def _gather_one(coll_name: str, label: str, empty_ok: bool, expects_writes: bool):
        # Per-collection silent-failure threshold
        coll_threshold_min = _threshold_minutes_for(coll_name)
        threshold = now - timedelta(minutes=coll_threshold_min)
        # ── DB SIDE ────────────────────────────────────────────────
        try:
            n_task = asyncio.wait_for(_db[coll_name].count_documents({}), timeout=0.6)
            lw_task = _get_last_write(coll_name)  # always check — cheap, uses _id index
            n, last_write = await asyncio.gather(n_task, lw_task)
        except Exception as e:
            # DB unreachable — everything red
            back, back_reason = _backend_pulse(coll_name, len(workers_live), live_names)
            return {
                "collection": coll_name, "label": label, "count": None,
                "status": "red", "last_write_at": None, "silent_failure": False,
                "expects_writes": expects_writes, "error": str(e)[:80],
                "triple_pulse": {
                    "db":       {"status": "red",    "reason": "query failed"},
                    "backend":  {"status": back,     "reason": back_reason},
                    "frontend": {"status": frontend_side, "reason": "api reachable"},
                },
            }

        silent = False
        if expects_writes and n and n > 0 and (last_write is None or last_write < threshold):
            # iter D-34 — LITE-mode demote. If the writer for this
            # collection is a `p4:*` scheduler and we're running LITE
            # (prod), the staleness is BY DESIGN — surface it as
            # `lite_mode` (yellow-info) rather than red silent-failure.
            writers = COLLECTION_WRITERS.get(coll_name, []) or []
            all_p4 = writers and all(w.startswith("p4:") for w in writers)
            if all_p4 and _is_lite_mode():
                db_side = "yellow"
                db_reason = (
                    f"lite_mode — writer paused on prod to save RAM "
                    f"(last write {coll_threshold_min}min+ ago)"
                )
                silent = False
            else:
                db_side = "red"
                db_reason = f"no writes within {coll_threshold_min} min (silent failure)"
                silent = True
        elif n == 0 and not empty_ok:
            db_side = "yellow"
            db_reason = "collection empty (seed expected)"
        elif n is None:
            db_side = "red"
            db_reason = "count failed"
        else:
            db_side = "green"
            db_reason = f"{n} docs"

        # ── BACKEND SIDE ──────────────────────────────────────────
        backend_side, backend_reason = _backend_pulse(coll_name, len(workers_live), live_names)

        # ── FRONTEND SIDE ─────────────────────────────────────────
        # (global single check — already computed in outer scope)

        overall_status = _pick_worst(db_side, backend_side, frontend_side)

        return {
            "collection": coll_name,
            "label": label,
            "count": n,
            "status": overall_status,
            "last_write_at": last_write.isoformat() if last_write else None,
            "silent_failure": silent,
            "expects_writes": expects_writes,
            "triple_pulse": {
                "db":       {"status": db_side,       "reason": db_reason},
                "backend":  {"status": backend_side,  "reason": backend_reason,
                             "writers": COLLECTION_WRITERS.get(coll_name, [])},
                "frontend": {"status": frontend_side, "reason": "api reachable"},
            },
        }

    results = await asyncio.gather(
        *[_gather_one(c[0], c[1], c[2], c[3]) for c in spec["collections"]]
    )

    for row in results:
        coll_rows.append(row)
        tp = row.get("triple_pulse", {})
        if tp.get("backend", {}).get("status") == "red":
            backend_red += 1
        if row["status"] == "red" and row.get("error"):
            unreachable += 1
        elif row.get("silent_failure"):
            silent_failures += 1
            reachable += 1
        elif row["status"] == "yellow":
            empty_but_required += 1
            reachable += 1
        else:
            reachable += 1

    # Overall pillar status — worst of (collections + worker health)
    if unreachable or silent_failures or backend_red:
        overall = "red"
    elif workers_done and not workers_live:
        overall = "red"
    elif not workers_live:
        overall = "yellow"
    elif empty_but_required:
        overall = "yellow"
    else:
        overall = "green"

    # iter 332b D-28 — LITE-mode awareness for Pillar 4.
    # Production auto-engages LITE mode (D-24) which intentionally
    # disables all 34 P4 schedulers. Without this check the dashboard
    # showed "Broken" with red status, alarming the founder unnecessarily.
    # Now we detect "no workers expected" and label it `lite_mode` =
    # green with reason, so the founder sees calm "LITE MODE BY DESIGN"
    # instead of red "0 LIVE WORKERS / BROKEN".
    lite_mode_active = False
    if key == "p4_command_hub" and len(workers_live) == 0 and len(workers_done) == 0:
        try:
            _host = (os.environ.get("HOSTNAME") or "").lower()
            _is_prod_pod = (
                ("live-support" in _host or "emergent.host" in _host)
                and not _host.startswith("agent-env-")
            )
            _lite_env = os.environ.get("AUREM_LITE_MODE", "").strip() in ("1", "true", "yes")
            if _is_prod_pod or _lite_env:
                lite_mode_active = True
                # Downgrade reds caused by missing-worker → not a real failure
                # in LITE mode. The collections themselves are fine; their
                # writers are just paused on purpose.
                if not unreachable and not silent_failures:
                    overall = "green"
        except Exception:
            pass

    # iter 322 — breaker-aware downgrade: when the cause of red is an OPEN
    # external breaker (Twilio / Resend / OpenRouter / Groq quota or rate
    # limit), the system itself is healthy — only the upstream is throttled.
    # Surface this as YELLOW with a `throttled_by` label so the frontend can
    # show "Outreach throttled — Twilio cooling down" instead of "OFFLINE".
    throttled_by: list[str] = []
    if overall == "red":
        try:
            from services.breakers import breaker_status
            statuses = breaker_status()
            # Map a breaker to the pillar(s) it influences.
            pillar_breaker_map = {
                "p3_outreach":  ("twilio", "resend"),
                "p2_cognition": ("openrouter", "groq", "anthropic", "openai"),
                "p4_revenue":   ("stripe",),
            }
            relevant = pillar_breaker_map.get(key, ())
            for b_name, b_state in statuses.items():
                if not isinstance(b_state, dict):
                    continue
                if b_state.get("state") == "open" and any(
                    r in b_name.lower() for r in relevant
                ):
                    throttled_by.append(b_name)
            # Only downgrade if EVERY red signal is attributable to a breaker
            # AND there is no silent_failure or unreachable (genuine app bugs).
            if throttled_by and not unreachable and not silent_failures:
                overall = "yellow"
        except Exception:
            pass

    return {
        "key": key,
        "label": spec["label"],
        "color": spec["color"],
        "status": overall,
        "throttled_by": throttled_by or None,
        "lite_mode": lite_mode_active,
        "workers": {
            "live": len(workers_live),
            "done": len(workers_done),
            "names": sorted(list(live_names))[:30],
        },
        "collections": {
            "total": len(coll_rows),
            "reachable": reachable,
            "unreachable": unreachable,
            "empty_required": empty_but_required,
            "silent_failures": silent_failures,
            "backend_red": backend_red,
            "rows": coll_rows,
        },
    }


# ══════════════════════════════════════════════════════════════════════
# Level 3 — Service Discovery (grep-based)
# Scans /app/backend/** for Python files referencing a given collection.
# Cached in-memory after first call per collection.
# ══════════════════════════════════════════════════════════════════════

_COLL_NAME_RE = re.compile(r"^[a-z0-9_]+$")


def _discover_services(coll_name: str) -> list[dict]:
    """Return list of {file, line, snippet} for every Python file that references
    the collection via db.<name>, db["<name>"], db.get_collection("<name>"),
    or tenant_db[...] equivalents.
    """
    if not _COLL_NAME_RE.match(coll_name):
        return []  # reject anything that isn't a safe collection name

    if coll_name in _service_cache:
        return _service_cache[coll_name]

    patterns = [
        rf"\bdb\.{coll_name}\b",
        rf'\bdb\["{coll_name}"\]',
        rf"\bdb\['{coll_name}'\]",
        rf'get_collection\(\s*["\']{coll_name}["\']',
    ]
    combined = "|".join(patterns)

    try:
        # grep -R -n -E (extended regex), include only .py, exclude __pycache__
        proc = subprocess.run(
            [
                "grep", "-R", "-n", "-E", "--include=*.py",
                "--exclude-dir=__pycache__", "--exclude-dir=.git",
                "--exclude-dir=node_modules", "--exclude-dir=tests",
                combined, _BACKEND_ROOT,
            ],
            capture_output=True, text=True, timeout=4.0, check=False,
        )
        hits: list[dict] = []
        for line in proc.stdout.splitlines():
            # Format:  path:lineno:snippet
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path, lineno, snippet = parts
            rel = path.replace(_BACKEND_ROOT + "/", "")
            hits.append({
                "file": rel,
                "line": int(lineno) if lineno.isdigit() else 0,
                "snippet": snippet.strip()[:180],
            })
        # Sort: routers first, then services, then pillars, then the rest
        def _rank(h: dict) -> tuple:
            f = h["file"]
            if f.startswith("routers/"): return (0, f)
            if f.startswith("services/"): return (1, f)
            if f.startswith("pillars/"): return (2, f)
            return (3, f)
        hits.sort(key=_rank)
        _service_cache[coll_name] = hits[:50]  # cap
        return _service_cache[coll_name]
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════
# Heartbeat cache (fast path for UI polling)
# Updated by services.pillar_heartbeat_service every 20s.
# ══════════════════════════════════════════════════════════════════════

_cached_snapshot: Optional[dict] = None
_cached_at_mono: float = 0.0  # iter 280.3 — monotonic clock for stale detection


def set_cached_snapshot(snapshot: dict) -> None:
    global _cached_snapshot, _cached_at_mono
    import time as _time
    _cached_snapshot = snapshot
    _cached_at_mono = _time.monotonic()


def get_cached_snapshot() -> Optional[dict]:
    return _cached_snapshot


def get_cached_age_seconds() -> float:
    """Returns seconds since last cache write; 0 if no cache yet."""
    import time as _time
    if _cached_at_mono <= 0:
        return 0.0
    return max(0.0, _time.monotonic() - _cached_at_mono)


# ══════════════════════════════════════════════════════════════════════
# SENTINEL OVERLAY — iter 280.3
# Previously /overview only checked collection write-freshness which is
# backwards: a RED-hot tenant with a surge of client_errors would actually
# show GREEN because writes were fresh. This overlay pulls real error
# counts from db.client_errors and db.sentinel_alerts and escalates the
# Pillar 3 (Monitor) verdict so Dev Console and Pillars Map agree.
#
# Thresholds (evidence-backed — matches Sentinel alert tiers):
#   errors_1h >= SENTINEL_HOT_1H                     → pillar RED
#   errors_1h >= SENTINEL_WARM_1H or alerts active   → pillar YELLOW (at least)
#   critical sentinel_alert in last 30 min           → pillar RED
# ══════════════════════════════════════════════════════════════════════

SENTINEL_HOT_1H = 20       # 20+ errors in 1h = red
SENTINEL_WARM_1H = 5       # 5+ errors in 1h = yellow


async def _fetch_sentinel_overlay() -> dict:
    """Read error counts + critical alerts. Zero-crash on empty collections."""
    if _db is None:
        return {"errors_1h": 0, "errors_24h": 0, "critical_alerts": 0, "verdict": "green"}
    now = datetime.now(timezone.utc)
    cut_1h = now - timedelta(hours=1)
    cut_24h = now - timedelta(hours=24)
    cut_30m = now - timedelta(minutes=30)
    try:
        errors_1h = await _db.client_errors.count_documents({"ts": {"$gte": cut_1h}})
    except Exception:
        errors_1h = 0
    try:
        errors_24h = await _db.client_errors.count_documents({"ts": {"$gte": cut_24h}})
    except Exception:
        errors_24h = 0
    try:
        critical = await _db.sentinel_alerts.count_documents({
            "created_at": {"$gte": cut_30m},
            "max_score": {"$gte": 8},
        })
    except Exception:
        critical = 0

    verdict = "green"
    reason = ""
    if critical > 0:
        verdict, reason = "red", f"critical_sentinel_alert (score≥8) active in last 30 min ({critical})"
    elif errors_1h >= SENTINEL_HOT_1H:
        verdict, reason = "red", f"errors_1h={errors_1h} ≥ hot threshold {SENTINEL_HOT_1H}"
    elif errors_1h >= SENTINEL_WARM_1H:
        verdict, reason = "yellow", f"errors_1h={errors_1h} ≥ warm threshold {SENTINEL_WARM_1H}"

    return {
        "errors_1h": errors_1h,
        "errors_24h": errors_24h,
        "critical_alerts": critical,
        "verdict": verdict,
        "reason": reason,
        "hot_threshold_1h": SENTINEL_HOT_1H,
        "warm_threshold_1h": SENTINEL_WARM_1H,
    }


def _merge_sentinel_into_pillar(pillars: list, overlay: dict) -> None:
    """In-place escalate p3_monitor pillar status based on sentinel overlay."""
    if not overlay or not pillars:
        return
    sev = overlay.get("verdict", "green")
    if sev == "green":
        # still attach overlay for transparency
        for p in pillars:
            if p.get("key") == "p3_monitor":
                p["sentinel_overlay"] = overlay
                break
        return
    for p in pillars:
        if p.get("key") != "p3_monitor":
            continue
        prev = p.get("status", "green")
        # worst-of rule: never downgrade
        order = {"green": 0, "yellow": 1, "red": 2}
        if order.get(sev, 0) > order.get(prev, 0):
            p["status"] = sev
        p["sentinel_overlay"] = overlay
        break


# ══════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.get("/overview")
async def overview(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    pillars = await asyncio.gather(
        *[_gather_pillar(k, s) for k, s in PILLAR_MAP.items()]
    )

    wires, flows = await asyncio.gather(_gather_wires(), _gather_flows())

    # iter 280.3 — Sentinel overlay: escalate p3_monitor if client_errors surge
    sentinel_overlay = await _fetch_sentinel_overlay()
    _merge_sentinel_into_pillar(pillars, sentinel_overlay)

    # Interface desync — only BLOCKING flows escalate admin/customer worst.
    # iter 332b D-30 — advisory flows (e.g. opt-in Ollama node) stay visible
    # in the UI but no longer flip the global verdict.
    admin_flows = [f for f in flows if f["surface"] == "admin"]
    customer_flows = [f for f in flows if f["surface"] == "customer"]
    admin_blocking = [f for f in admin_flows if not f.get("non_blocking")]
    customer_blocking = [f for f in customer_flows if not f.get("non_blocking")]
    admin_worst = _pick_worst(*[f["status"] for f in admin_blocking]) if admin_blocking else "green"
    customer_worst = _pick_worst(*[f["status"] for f in customer_blocking]) if customer_blocking else "green"
    interface_desync = (
        admin_worst == "green" and customer_worst in ("red", "yellow")
    ) or (
        customer_worst == "green" and admin_worst in ("red", "yellow")
    )

    worst = "green"
    for p in pillars:
        if p["status"] == "red":
            worst = "red"; break
        if p["status"] == "yellow":
            worst = "yellow"

    total_collections = sum(p["collections"]["total"] for p in pillars)
    total_silent = sum(p["collections"].get("silent_failures", 0) for p in pillars)
    total_unreachable = sum(p["collections"]["unreachable"] for p in pillars)
    total_backend_red = sum(p["collections"].get("backend_red", 0) for p in pillars)
    # Split wires into blocking vs advisory (non_blocking business flows).
    # advisory wires are displayed red in UI but do NOT flip overall_status
    # — Truth-Sync: zero paying customers ≠ system broken.
    wires_red_blocking = sum(1 for w in wires if w["status"] == "red" and not w.get("non_blocking"))
    wires_red_advisory = sum(1 for w in wires if w["status"] == "red" and w.get("non_blocking"))
    wires_red = wires_red_blocking + wires_red_advisory
    wires_yellow = sum(1 for w in wires if w["status"] == "yellow" and not w.get("non_blocking"))
    wires_idle = sum(1 for w in wires if w["status"] == "idle")
    flows_red_blocking = sum(1 for f in flows if f["status"] == "red" and not f.get("non_blocking"))
    flows_red_advisory = sum(1 for f in flows if f["status"] == "red" and f.get("non_blocking"))
    flows_red = flows_red_blocking + flows_red_advisory
    flows_yellow_blocking = sum(1 for f in flows if f["status"] == "yellow" and not f.get("non_blocking"))
    flows_yellow = sum(1 for f in flows if f["status"] == "yellow")

    # Wiring failure escalates pillar verdict — but ONLY blocking wires/flows
    if wires_red_blocking > 0 or flows_red_blocking > 0:
        worst = "red"
    elif (wires_yellow > 0 or flows_yellow_blocking > 0) and worst == "green":
        worst = "yellow"

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": worst,
        "pillars": pillars,
        "wires": wires,
        "flows": flows,
        "interface_desync": interface_desync,
        "admin_worst": admin_worst,
        "customer_worst": customer_worst,
        "totals": {
            "collections": total_collections,
            "silent_failures": total_silent,
            "unreachable": total_unreachable,
            "backend_red": total_backend_red,
            "wires_total": len(wires),
            "wires_red": wires_red,
            "wires_red_blocking": wires_red_blocking,
            "wires_red_advisory": wires_red_advisory,
            "wires_yellow": wires_yellow,
            "wires_idle": wires_idle,
            "flows_total": len(flows),
            "flows_red": flows_red,
            "flows_red_blocking": flows_red_blocking,
            "flows_red_advisory": flows_red_advisory,
            "flows_yellow": flows_yellow,
        },
        "silent_failure_threshold_minutes": SILENT_FAILURE_MINUTES,
        "sentinel_overlay": sentinel_overlay,
    }
    # Update cache so /heartbeat returns fresh data
    set_cached_snapshot(snapshot)
    return snapshot


@router.get("/heartbeat")
async def heartbeat(authorization: Optional[str] = Header(None)):
    """Fast cached snapshot for UI polling. Falls back to live overview if cache cold."""
    _verify_admin(authorization)
    cached = get_cached_snapshot()
    if cached:
        age = get_cached_age_seconds()
        return {
            **cached,
            "cached": True,
            "served_from": "cache",
            "cached_age_sec": round(age, 1),
            "stale": age > 60,  # iter 280.3 — flag if cache older than 60s
        }
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    # cold start — build fresh
    payload = await overview(authorization)
    return {**payload, "served_from": "live", "cached_age_sec": 0.0, "stale": False}


@router.get("/wires")
async def wires(authorization: Optional[str] = Header(None)):
    """Inter-Pillar Wiring — global flow map of data dependencies."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    wire_rows = await _gather_wires()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(wire_rows),
        "wires": wire_rows,
        "summary": {
            "red":    sum(1 for w in wire_rows if w["status"] == "red"),
            "yellow": sum(1 for w in wire_rows if w["status"] == "yellow"),
            "green":  sum(1 for w in wire_rows if w["status"] == "green"),
            "idle":   sum(1 for w in wire_rows if w["status"] == "idle"),
        },
    }


@router.get("/flows")
async def flows(authorization: Optional[str] = Header(None)):
    """System Interface Flows — Admin + Customer pages with DB/BE/FE triple-pulse."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    flow_rows = await _gather_flows()
    admin_rows = [f for f in flow_rows if f["surface"] == "admin"]
    customer_rows = [f for f in flow_rows if f["surface"] == "customer"]

    # Interface Desync — only blocking flows escalate the verdict.
    # iter 332b D-30 — see overview() for rationale.
    admin_blocking = [f for f in admin_rows if not f.get("non_blocking")]
    customer_blocking = [f for f in customer_rows if not f.get("non_blocking")]
    admin_worst = _pick_worst(*[f["status"] for f in admin_blocking]) if admin_blocking else "green"
    customer_worst = _pick_worst(*[f["status"] for f in customer_blocking]) if customer_blocking else "green"
    interface_desync = (
        admin_worst == "green" and customer_worst in ("red", "yellow")
    ) or (
        customer_worst == "green" and admin_worst in ("red", "yellow")
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(flow_rows),
        "flows": flow_rows,
        "summary": {
            "red":    sum(1 for f in flow_rows if f["status"] == "red"),
            "yellow": sum(1 for f in flow_rows if f["status"] == "yellow"),
            "green":  sum(1 for f in flow_rows if f["status"] == "green"),
        },
        "admin_count":    len(admin_rows),
        "customer_count": len(customer_rows),
        "admin_worst":    admin_worst,
        "customer_worst": customer_worst,
        "interface_desync": interface_desync,
        "desync_reason":   (
            f"Admin is {admin_worst} but Customer is {customer_worst} — interface mismatch"
            if interface_desync else None
        ),
    }


@router.get("/wire/{wire_id}/trace")
async def wire_trace(wire_id: str, authorization: Optional[str] = Header(None)):
    """Wiring Trace — deep diagnostic for a single broken/slow wire.

    Returns the wire status plus a few recent docs from source and target
    collections so the operator can see exactly WHICH rows didn't propagate.
    """
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    wire_def = next((w for w in INTER_PILLAR_WIRES if w["id"] == wire_id), None)
    if wire_def is None:
        raise HTTPException(status_code=404, detail=f"Unknown wire: {wire_id}")

    status_row = await _check_wire(wire_def)

    # Pull last 5 docs from each side for visual "where did it stop?" inspection
    async def _recent(coll_name: str) -> list[dict]:
        try:
            cursor = _db[coll_name].find({}, projection={"_id": 1}).sort("_id", -1).limit(5)
            out: list[dict] = []
            async for doc in cursor:
                oid = doc.get("_id")
                ts = None
                if isinstance(oid, ObjectId):
                    ts = oid.generation_time.isoformat()
                out.append({"_id": str(oid), "ts": ts})
            return out
        except Exception as e:
            return [{"error": str(e)[:100]}]

    src_recent, tgt_recent = await asyncio.gather(
        _recent(wire_def["source_collection"]),
        _recent(wire_def["target_collection"]),
    )

    trace_text = ""
    if status_row["status"] == "red":
        trace_text = (
            f"Pillar {wire_def['source_pillar']} ({wire_def['source_collection']}) "
            f"wrote at {status_row.get('src_last_write')}, but Pillar {wire_def['target_pillar']} "
            f"({wire_def['target_collection']}) "
            + ("has NO writes — the bridge is broken." if status_row.get("tgt_last_write") is None
               else f"last wrote at {status_row.get('tgt_last_write')} "
                    f"({status_row.get('lag_seconds')}s behind — exceeds {wire_def['lag_seconds']}s threshold).")
        )
    elif status_row["status"] == "yellow":
        trace_text = (
            f"Wire is SLOW: source wrote at {status_row.get('src_last_write')} but target "
            f"lagged by {status_row.get('lag_seconds')}s (tolerance {wire_def['lag_seconds']}s)."
        )
    elif status_row["status"] == "idle":
        trace_text = "Source collection has been idle, so no flow was expected. No error."
    else:
        trace_text = f"Wire healthy — target wrote {abs(status_row.get('lag_seconds') or 0)}s of source."

    return {
        "wire": status_row,
        "trace": trace_text,
        "source_recent_docs": src_recent,
        "target_recent_docs": tgt_recent,
    }


@router.get("/collection/{name}/services")
async def collection_services(name: str, authorization: Optional[str] = Header(None)):
    """Level 3 drill — return Python files referencing this collection."""
    _verify_admin(authorization)
    if name not in COLLECTION_INDEX:
        raise HTTPException(status_code=404, detail=f"Unknown collection: {name}")
    pk, label, _empty_ok, expects_writes = COLLECTION_INDEX[name]
    hits = _discover_services(name)
    return {
        "collection": name,
        "label": label,
        "pillar": pk,
        "expects_writes": expects_writes,
        "service_refs": hits,
        "count": len(hits),
    }


@router.get("/collection/{name}/errors")
async def collection_errors(name: str, authorization: Optional[str] = Header(None)):
    """Level 3 drill — return recent errors (client_errors + stem_fixes) tied to this collection."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    if name not in COLLECTION_INDEX:
        raise HTTPException(status_code=404, detail=f"Unknown collection: {name}")

    # Pull client_errors that mention the collection name in message / stack / url
    client_errors: list[dict] = []
    try:
        cursor = _db.client_errors.find(
            {
                "$or": [
                    {"message": {"$regex": name, "$options": "i"}},
                    {"stack":   {"$regex": name, "$options": "i"}},
                    {"url":     {"$regex": name, "$options": "i"}},
                ],
            },
            projection={"_id": 0, "message": 1, "classification": 1, "url": 1,
                        "status_code": 1, "created_at": 1, "signature": 1},
        ).sort("created_at", -1).limit(15)
        async for doc in cursor:
            if doc.get("created_at") and isinstance(doc["created_at"], datetime):
                doc["created_at"] = doc["created_at"].isoformat()
            client_errors.append(doc)
    except Exception:
        pass

    # Pull stem_fixes that target this collection's suspected service files
    stem_fix_hits: list[dict] = []
    try:
        cursor = _db.stem_fixes.find(
            {"$or": [
                {"target_file": {"$regex": name, "$options": "i"}},
                {"target_function": {"$regex": name, "$options": "i"}},
            ]},
            projection={"_id": 0, "target_file": 1, "target_function": 1,
                        "status": 1, "created_at": 1, "sandbox_attempts": 1},
        ).sort("created_at", -1).limit(10)
        async for doc in cursor:
            if doc.get("created_at") and isinstance(doc["created_at"], datetime):
                doc["created_at"] = doc["created_at"].isoformat()
            stem_fix_hits.append(doc)
    except Exception:
        pass

    return {
        "collection": name,
        "client_errors": client_errors,
        "stem_fixes": stem_fix_hits,
        "counts": {
            "client_errors": len(client_errors),
            "stem_fixes": len(stem_fix_hits),
        },
    }


# ══════════════════════════════════════════════════════════════════════
# Sidebar Blocks — "Data > Lights" Command Interface
#
# Reads directly from the cached pillar snapshot (no fresh Mongo queries)
# so the sidebar UI is a PURE PROJECTION of pillar health. Strict rule:
# "If the pillar is red, the block is red — no independent logic."
#
# Block definition:
#   pillar_keys:        which pillars roll up into this block
#   collections:        which mapped collections provide the live numbers
#   badge_builders:     list of (label, collection, aggregation) tuples
# ══════════════════════════════════════════════════════════════════════

SIDEBAR_BLOCKS: list[dict] = [
    {
        "id":          "morning_brief",
        "glyph":       "◆",
        "label":       "Morning Brief",
        "pillar_keys": ["p4_command_hub"],
        "primary_sidebar_section": "☀️ Morning Brief",
        "badges": [
            # (label, collection, aggregation_type)
            ("Briefs",        "morning_briefs",     "count"),
            ("Auto-Heals",    "auto_heal_log",      "count"),
            ("Audits",        "system_audit_reports", "count"),
        ],
    },
    {
        "id":          "pipeline",
        "glyph":       "◈",
        "label":       "Pipeline",
        "pillar_keys": ["p1_sales"],
        "primary_sidebar_section": "🔍 Scout & Hunt + 📣 Campaign HQ",
        "badges": [
            ("Leads",         "campaign_leads",   "count"),
            ("Emails Sent",   "sent_emails",      "count"),
            ("SMS",           "sms_logs",         "count"),
            ("WA",            "whatsapp_message_log", "count"),
        ],
    },
    {
        "id":          "cash_flow",
        "glyph":       "◉",
        "label":       "Cash Flow",
        "pillar_keys": ["p2_billing"],
        "primary_sidebar_section": "💰 Revenue & 🛒 Shopify",
        "badges": [
            ("Payments",      "payment_transactions",  "count"),
            ("Subscriptions", "customer_subscriptions", "count"),
            ("Carts",         "aurem_abandoned_carts",  "count"),
        ],
    },
    {
        "id":          "websites",
        "glyph":       "◇",
        "label":       "Websites",
        "pillar_keys": ["p3_monitor"],
        "primary_sidebar_section": "🌐 Websites",
        "badges": [
            ("Endpoints",    "site_monitor_endpoints", "count"),
            ("Scans",        "site_monitor_logs",      "count"),
            ("Fixes",        "repair_fixes",           "count"),
        ],
    },
    {
        "id":          "machine",
        "glyph":       "⚙",
        "label":       "Machine",
        "pillar_keys": ["p3_monitor", "p4_command_hub"],
        "primary_sidebar_section": "⚡ Automation & 🧠 Intelligence",
        "badges": [
            ("Auto-Fixes",   "auto_heal_log",    "count"),
            ("Alerts",       "sentinel_alerts",  "count"),
            ("Stem-Fixes",   "stem_fixes",       "count"),
        ],
    },
    {
        # iter 277 — Vanguard surfaced as its own command block.
        # Evidence: 8 endpoints · 7,884 hits/30d on production (hotter than P2 Monetization).
        "id":          "vanguard",
        "glyph":       "◆",
        "label":       "Vanguard",
        "pillar_keys": ["p1_sales"],
        "primary_sidebar_section": "🛡️ Vanguard Swarm (Elite First-Contact)",
        "badges": [
            ("Missions",     "aurem_missions",   "count"),
            ("Leads",        "campaign_leads",   "count"),
            ("API Keys",     "aurem_api_keys",   "count"),
        ],
    },
]


def _find_collection_row(pillars: list[dict], coll_name: str) -> Optional[dict]:
    for p in pillars:
        for row in p.get("collections", {}).get("rows", []):
            if row.get("collection") == coll_name:
                return row
    return None


def _build_sidebar_block(block: dict, pillars: list[dict]) -> dict:
    """Projection of pillars cache into sidebar block payload. No new queries."""
    # 1. Aggregate pillar status → block status (worst-of)
    child_pillars = [p for p in pillars if p["key"] in block["pillar_keys"]]
    statuses = [p["status"] for p in child_pillars] or ["green"]
    block_status = _pick_worst(*statuses)

    # 2. Build per-badge data from cached collection rows
    badges: list[dict] = []
    any_stale = False
    for label, coll_name, _agg in block["badges"]:
        row = _find_collection_row(pillars, coll_name)
        if row is None:
            badges.append({
                "label":       label,
                "collection":  coll_name,
                "count":       None,
                "status":      "yellow",
                "stale":       True,
                "reason":      "collection not tracked",
                "last_write":  None,
            })
            any_stale = True
            continue

        tp = row.get("triple_pulse", {}) or {}
        db_status = (tp.get("db") or {}).get("status", "green")
        stale = (db_status == "red")  # DB-side red → cached count is stale
        if stale:
            any_stale = True

        badges.append({
            "label":       label,
            "collection":  coll_name,
            "count":       row.get("count"),
            "status":      row.get("status", "green"),
            "stale":       stale,
            "reason":      (tp.get("db") or {}).get("reason", ""),
            "last_write":  row.get("last_write_at"),
        })

    return {
        "id":          block["id"],
        "glyph":       block["glyph"],
        "label":       block["label"],
        "primary_sidebar_section": block["primary_sidebar_section"],
        "pillar_keys": block["pillar_keys"],
        "status":      block_status,
        "any_stale":   any_stale,
        "badges":      badges,
        "pillar_snapshots": [
            {"key": p["key"], "label": p["label"], "status": p["status"]}
            for p in child_pillars
        ],
    }


@router.get("/sidebar-blocks")
async def sidebar_blocks(authorization: Optional[str] = Header(None)):
    """Read-only projection of cached pillar snapshot into 5 merged sidebar blocks.

    Rule: block status == worst of child pillar statuses. Badge count comes
    from cached collection row. If DB-side is red, `stale=true` so the UI
    can show ⚠️ next to the last-known count.
    """
    _verify_admin(authorization)
    snapshot = get_cached_snapshot()
    if snapshot is None:
        # Cold start — ask for the live overview; scheduler will warm cache in 20s
        if _db is None:
            raise HTTPException(status_code=503, detail="Database not initialized")
        snapshot = await overview(authorization)
    pillars = snapshot.get("pillars", [])
    blocks = [_build_sidebar_block(b, pillars) for b in SIDEBAR_BLOCKS]
    return {
        "generated_at":   snapshot.get("generated_at"),
        "overall_status": snapshot.get("overall_status", "green"),
        "cached":         snapshot.get("cached", False),
        "blocks":         blocks,
    }


@router.get("/live-events")
async def live_events(
    since: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Lightweight polling endpoint for live toasts (Stripe payments etc.).

    Returns docs from `payment_transactions` inserted after the given ISO
    timestamp (UTC). Frontend polls every ~8s with the last-seen timestamp.
    """
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    # Parse `since` (ISO 8601); default = last 60 s
    cutoff: datetime
    if since:
        try:
            cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
        except Exception:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)

    # ObjectId generated from `cutoff` lets us use the _id index directly
    oid_cutoff = ObjectId.from_datetime(cutoff)
    events: list[dict] = []

    try:
        cursor = _db.payment_transactions.find(
            {"_id": {"$gt": oid_cutoff}},
            projection={"_id": 1, "amount": 1, "amount_total": 1,
                        "currency": 1, "customer_email": 1,
                        "customer_id": 1, "status": 1, "created_at": 1},
        ).sort("_id", 1).limit(25)
        async for doc in cursor:
            oid = doc.get("_id")
            ts = oid.generation_time.isoformat() if isinstance(oid, ObjectId) else None
            events.append({
                "kind": "payment",
                "id": str(oid),
                "ts": ts,
                "amount": doc.get("amount_total") or doc.get("amount"),
                "currency": (doc.get("currency") or "USD").upper(),
                "status": doc.get("status", "ok"),
                "customer": doc.get("customer_email") or str(doc.get("customer_id", "unknown"))[:30],
            })
    except Exception as e:
        events = [{"kind": "error", "error": str(e)[:80]}]

    return {
        "now":         datetime.now(timezone.utc).isoformat(),
        "since":       cutoff.isoformat(),
        "count":       len(events),
        "events":      events,
    }


@router.post("/sync")
async def sync_now(authorization: Optional[str] = Header(None)):
    """Force refresh the cached pillar snapshot.

    Used by the Mission Control Ribbon's 'Sync Now' button for instant
    debugging feedback instead of waiting the 20 s scheduler cadence.
    """
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    # Rebuild just like /overview does, and update the cache atomically.
    pillars = await asyncio.gather(
        *[_gather_pillar(k, s) for k, s in PILLAR_MAP.items()]
    )
    wires, flows = await asyncio.gather(_gather_wires(), _gather_flows())

    # iter 280.3 — Sentinel overlay on sync path too
    sentinel_overlay = await _fetch_sentinel_overlay()
    _merge_sentinel_into_pillar(pillars, sentinel_overlay)

    worst = "green"
    for p in pillars:
        if p["status"] == "red":
            worst = "red"; break
        if p["status"] == "yellow":
            worst = "yellow"

    wires_red_blocking = sum(1 for w in wires if w["status"] == "red" and not w.get("non_blocking"))
    wires_red_advisory = sum(1 for w in wires if w["status"] == "red" and w.get("non_blocking"))
    wires_red = wires_red_blocking + wires_red_advisory
    wires_yellow = sum(1 for w in wires if w["status"] == "yellow" and not w.get("non_blocking"))
    wires_idle = sum(1 for w in wires if w["status"] == "idle")
    flows_red = sum(1 for f in flows if f["status"] == "red")
    flows_yellow = sum(1 for f in flows if f["status"] == "yellow")
    if wires_red_blocking > 0 or flows_red > 0:
        worst = "red"
    elif (wires_yellow > 0 or flows_yellow > 0) and worst == "green":
        worst = "yellow"

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": worst,
        "pillars": pillars,
        "wires": wires,
        "flows": flows,
        "totals": {
            "collections":     sum(p["collections"]["total"] for p in pillars),
            "silent_failures": sum(p["collections"].get("silent_failures", 0) for p in pillars),
            "unreachable":     sum(p["collections"]["unreachable"] for p in pillars),
            "backend_red":     sum(p["collections"].get("backend_red", 0) for p in pillars),
            "wires_total":     len(wires),
            "wires_red":       wires_red,
            "wires_red_blocking": wires_red_blocking,
            "wires_red_advisory": wires_red_advisory,
            "wires_yellow":    wires_yellow,
            "wires_idle":      wires_idle,
            "flows_total":     len(flows),
            "flows_red":       flows_red,
            "flows_yellow":    flows_yellow,
        },
        "silent_failure_threshold_minutes": SILENT_FAILURE_MINUTES,
        "sentinel_overlay": sentinel_overlay,
    }
    set_cached_snapshot(snapshot)
    return {
        "ok": True,
        "forced": True,
        "generated_at": snapshot["generated_at"],
        "overall_status": worst,
        "totals": snapshot["totals"],
        "sentinel_overlay": sentinel_overlay,
    }


@router.get("/health")
async def health():
    return {"status": "ok", "component": "pillars-map", "db_ready": _db is not None}
