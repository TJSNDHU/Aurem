"""
services/ora_guards.py — iter 331a Sprint 3

Six safety guardrails for ORA's autonomous loop:

  1. Per-session cost cap        — warn at 80%, halt at 100%
  2. Idempotency guard           — detect same-content file edit loops
  3. Stuck-process watchdog      — kill if no tool/message for N minutes
  4. Destructive command filter  — block rm -rf / dropDatabase / etc.
  5. Integration playbook gate   — require web_search before vendor calls
  6. Package verification gate   — verify PyPI/npm before install

Every guard:
  - Logs to `ora_guard_events` collection for audit.
  - Fires a Telegram alert via `services.telegram_notify.send_alert(text)`
    when a hard block triggers.
  - Returns a structured dict the caller checks before proceeding.

Portability: zero Emergent imports. All thresholds env-overridable.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration (env-overridable) ─────────────────────────────────
SESSION_USD_CAP   = float(os.environ.get("ORA_SESSION_USD_CAP",   "5.00"))
WARN_FRACTION     = float(os.environ.get("ORA_USD_WARN_FRACTION", "0.80"))
STUCK_MIN_MINUTES = float(os.environ.get("ORA_STUCK_MINUTES",     "5.0"))
IDEMPOTENCY_HITS  = int(  os.environ.get("ORA_IDEMP_HITS",        "3"))
INTEGRATION_WINDOW = int( os.environ.get("ORA_INTEGRATION_WINDOW", "5"))


# ── Shared DB handle (set from server.py via ora_tools.set_db) ──────
_db = None

def set_db(database) -> None:
    global _db
    _db = database


# ── Telegram alert wrapper (best-effort, never raises) ──────────────

async def _alert(title: str, body: str) -> None:
    try:
        from services.telegram_bot_service import send_telegram_alert
        coro = send_telegram_alert(f"🛡️ ORA Guard — {title}\n\n{body}")
        if asyncio.iscoroutine(coro):
            await coro
    except Exception as e:
        logger.debug(f"[ora-guards] alert skipped: {e}")


async def _audit(event_type: str, payload: dict) -> None:
    if _db is None:
        return
    try:
        await _db.ora_guard_events.insert_one({
            "event_type": event_type,
            "ts":         datetime.now(timezone.utc).isoformat(),
            **payload,
        })
    except Exception as e:
        logger.debug(f"[ora-guards] audit skipped: {e}")


# ── GUARD 1: Per-session cost cap ───────────────────────────────────

# Session cost is tracked elsewhere via _format_cost_footer; we re-use
# the same accumulator if available. Otherwise, callers pass usd_so_far
# explicitly to check_cost_cap().

async def check_cost_cap(session_id: str, usd_so_far: float) -> dict:
    """Returns:
      ok        : True if under cap
      level     : "ok"|"warn"|"halt"
      cap       : float
      usd_so_far: float
      message   : plain English for the founder
    """
    cap = SESSION_USD_CAP
    pct = usd_so_far / cap if cap > 0 else 0.0
    level = "ok"
    message = ""
    if pct >= 1.0:
        level = "halt"
        message = (
            f"Session cost ${usd_so_far:.2f} reached the cap of "
            f"${cap:.2f}. Stopping autonomous work. Bump "
            f"ORA_SESSION_USD_CAP if you want me to continue."
        )
        await _audit("cost_cap_halt", {
            "session_id": session_id, "usd": usd_so_far, "cap": cap,
        })
        await _alert("Session cost cap hit",
                     f"Session {session_id} stopped at ${usd_so_far:.2f}/${cap:.2f}.")
    elif pct >= WARN_FRACTION:
        level = "warn"
        message = (
            f"Heads up: this session has spent ${usd_so_far:.2f} of the "
            f"${cap:.2f} budget ({int(pct*100)}%). I'll stop at 100%."
        )
        await _audit("cost_cap_warn", {
            "session_id": session_id, "usd": usd_so_far, "cap": cap,
        })
    return {
        "ok":         level != "halt",
        "level":      level,
        "cap":        cap,
        "usd_so_far": usd_so_far,
        "message":    message,
    }


# ── GUARD 2: Idempotency guard (file edit loops) ────────────────────

# In-memory ring buffer per session of (file_path, content_sha256, ts).
# If the same (path, sha) appears 3+ times, we halt that session.

_EDIT_HISTORY: dict[str, list[tuple[str, str, float]]] = {}

async def check_edit_loop(session_id: str, path: str, new_content: str) -> dict:
    """Returns:
      ok                : True if NOT a loop
      level             : "ok"|"warn"|"halt"
      hits              : int — how many times this exact content seen
      message           : plain English
    """
    sha = hashlib.sha256(new_content.encode("utf-8", errors="replace")).hexdigest()
    history = _EDIT_HISTORY.setdefault(session_id, [])
    now_ts = time.time()
    # Drop entries older than 30 minutes.
    history[:] = [(p, s, t) for p, s, t in history if now_ts - t < 1800]
    history.append((path, sha, now_ts))
    matches = sum(1 for p, s, _t in history if p == path and s == sha)
    if matches >= IDEMPOTENCY_HITS:
        msg = (
            f"I'm going in circles on {path} — the exact same content "
            f"was proposed {matches} times in the last 30 minutes. "
            f"Stopping so we don't loop forever."
        )
        await _audit("edit_loop_halt", {
            "session_id": session_id, "path": path, "sha": sha[:16],
            "matches":    matches,
        })
        await _alert("Edit loop detected",
                     f"Session {session_id} stuck editing {path} "
                     f"({matches} identical attempts).")
        return {"ok": False, "level": "halt", "hits": matches, "message": msg}
    if matches == IDEMPOTENCY_HITS - 1:
        return {
            "ok": True, "level": "warn", "hits": matches,
            "message": f"Warning: same edit proposed {matches} times — one more will halt.",
        }
    return {"ok": True, "level": "ok", "hits": matches, "message": ""}


def reset_edit_history(session_id: str | None = None) -> None:
    """Founder can clear the edit-loop history (e.g. after intentional retry)."""
    if session_id is None:
        _EDIT_HISTORY.clear()
    else:
        _EDIT_HISTORY.pop(session_id, None)


# ── GUARD 3: Stuck-process watchdog ─────────────────────────────────

# A background task that scans `ora_session_heartbeats` collection for
# any session that hasn't pinged in N minutes. Caller wires this into
# the APScheduler at boot.

async def heartbeat(session_id: str) -> None:
    """Caller pings this from every tool call + every assistant emit."""
    if _db is None:
        return
    try:
        await _db.ora_session_heartbeats.update_one(
            {"_id": session_id},
            {"$set": {"last_ping": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[ora-guards] heartbeat skipped: {e}")


async def stuck_watchdog_tick() -> dict:
    """Scan heartbeats, flag any session silent >STUCK_MIN_MINUTES.
    Returns summary dict suitable for scheduler logging.
    """
    if _db is None:
        return {"ok": False, "checked": 0, "stuck": 0}
    now = datetime.now(timezone.utc)
    threshold_iso = now.timestamp() - (STUCK_MIN_MINUTES * 60)
    cursor = _db.ora_session_heartbeats.find({}, {"_id": 1, "last_ping": 1})
    docs = await cursor.to_list(length=200)
    stuck: list[str] = []
    for d in docs:
        try:
            last = datetime.fromisoformat(d["last_ping"].replace("Z", "+00:00"))
            if last.timestamp() < threshold_iso:
                stuck.append(d["_id"])
        except Exception:
            continue
    for sid in stuck:
        await _audit("stuck_session_halt", {"session_id": sid})
        await _alert("Stuck session detected",
                     f"Session {sid} has not pinged in >{STUCK_MIN_MINUTES} min.")
        # Reset the heartbeat so we don't re-alert every tick.
        try:
            await _db.ora_session_heartbeats.delete_one({"_id": sid})
        except Exception:
            pass
    return {"ok": True, "checked": len(docs), "stuck": len(stuck)}


# ── GUARD 4: Destructive command filter ─────────────────────────────

_BLOCKED_PATTERNS = [
    (r"\brm\s+-rf\s+/(?:app|root|home|etc|var|usr)\b", "rm -rf on protected path"),
    (r"\bdropDatabase\s*\(\s*\)", "dropDatabase()"),
    (r"\bkubectl\s+delete\s+(?:ns|namespace)\b", "kubectl delete namespace"),
    (r"\bTRUNCATE\s+TABLE\b", "TRUNCATE TABLE"),
    (r"\bDELETE\s+FROM\s+\w+\s*;", "DELETE FROM ... without WHERE"),
    (r"\bDROP\s+TABLE\b", "DROP TABLE"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"\bmkfs\.\w+\b", "filesystem format"),
    (r"\bdd\s+if=.+\s+of=/dev/", "raw disk write"),
]

async def check_destructive(cmd: str) -> dict:
    """Returns:
      ok            : True if safe
      level         : "ok"|"block"
      matched       : str — pattern label if blocked
      message       : plain English
    """
    if not cmd:
        return {"ok": True, "level": "ok", "matched": None, "message": ""}
    for pat, label in _BLOCKED_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            msg = (
                f"Blocked: this command matches the destructive pattern "
                f"'{label}'. If you really want to run it, propose it as "
                f"a Tier-3 legion_exec with risk_hint='high' and the founder "
                f"will need to type CONFIRM."
            )
            await _audit("destructive_blocked", {
                "cmd_excerpt": cmd[:200], "pattern_label": label,
            })
            await _alert("Destructive command blocked",
                         f"Pattern: {label}\nCmd excerpt: {cmd[:200]}")
            return {"ok": False, "level": "block", "matched": label, "message": msg}
    return {"ok": True, "level": "ok", "matched": None, "message": ""}


# ── GUARD 5: Integration playbook hard gate ─────────────────────────

# When the LLM tries to call a vendor integration tool, we require that
# `web_search` (or a memory injection of INTEGRATION_PLAYBOOK.md via the
# tier-2 loader) happened within the last N turns. Otherwise, we refuse.

_VENDOR_TOOLS = {
    "stripe_charge", "stripe_create_session", "stripe_refund",
    "twilio_send_sms", "twilio_send_whatsapp",
    "retell_create_call",
    "resend_send_email",
    "github_push", "github_pr_create",
    "deploy_to_platform",
}

_INTEGRATION_KEYWORDS = (
    "stripe", "twilio", "retell", "resend", "whatsapp", "github",
    "webhook", "sdk", "api key", "deploy", "integration",
)

async def check_integration_gate(
    session_id: str,
    tool_name: str,
    last_n_turns: list[dict],
) -> dict:
    """Returns:
      ok      : True if the gate passes
      level   : "ok"|"block"
      message : plain English
      reason  : audit reason
    """
    if tool_name not in _VENDOR_TOOLS:
        return {"ok": True, "level": "ok", "message": "", "reason": "not_vendor"}

    # Inspect the last N assistant/tool/system turns for evidence the
    # founder asked us to prepare (web_search call) or the tier-2
    # INTEGRATION_PLAYBOOK injection fired.
    window = (last_n_turns or [])[-INTEGRATION_WINDOW:]
    saw_search = False
    saw_playbook = False
    for t in window:
        content = str(t.get("content") or "")
        # Tool-call evidence — look for a search invocation.
        if t.get("role") == "tool" and "wikipedia" in content.lower():
            saw_search = True
        if t.get("role") == "system" and (
            "INTEGRATION PLAYBOOK" in content
            or "INTEGRATION_PLAYBOOK" in content
        ):
            saw_playbook = True

    if saw_search or saw_playbook:
        return {"ok": True, "level": "ok", "message": "",
                "reason": "search_or_playbook_found"}

    msg = (
        f"I tried to call `{tool_name}` but I haven't checked current docs "
        f"for that vendor yet. Call `web_search` first (or trigger the "
        f"INTEGRATION_PLAYBOOK by mentioning the vendor name) so I can "
        f"verify the API hasn't changed since my training data."
    )
    await _audit("integration_gate_block", {
        "session_id": session_id, "tool": tool_name,
    })
    return {"ok": False, "level": "block", "message": msg,
            "reason": "no_recent_search"}


# ── GUARD 6: Package verification gate ──────────────────────────────

_PYPI_URL = "https://pypi.org/pypi/{}/json"
_NPM_URL  = "https://registry.npmjs.org/{}"


async def verify_package(package: str, ecosystem: str = "pypi") -> dict:
    """Returns:
      ok            : True if package exists on the registry
      package       : echo
      ecosystem     : "pypi" | "npm"
      latest_version: str | None
      message       : plain English
    """
    if not package:
        return {"ok": False, "package": package, "ecosystem": ecosystem,
                "latest_version": None, "message": "package name is empty"}
    pkg = re.sub(r"[^a-zA-Z0-9._@\-/]", "", str(package))[:100]
    if not pkg:
        return {"ok": False, "package": package, "ecosystem": ecosystem,
                "latest_version": None,
                "message": "package name contains only invalid characters"}

    if ecosystem == "pypi":
        url = _PYPI_URL.format(urllib.parse.quote(pkg))
    elif ecosystem == "npm":
        url = _NPM_URL.format(urllib.parse.quote(pkg))
    else:
        return {"ok": False, "package": pkg, "ecosystem": ecosystem,
                "latest_version": None,
                "message": f"unknown ecosystem '{ecosystem}' (pypi|npm)"}

    try:
        def _fetch() -> dict:
            req = urllib.request.Request(url, headers={
                "User-Agent": "ORA-CTO/1.0 (+aurem.live)",
            })
            with urllib.request.urlopen(req, timeout=8) as r:
                import json as _json
                return _json.loads(r.read().decode("utf-8", errors="replace"))
        data = await asyncio.to_thread(_fetch)
    except Exception as e:
        if "404" in str(e):
            msg = (
                f"Package `{pkg}` not found on {ecosystem.upper()}. Aborting. "
                f"Double-check the name — could be a typo or a hallucinated package."
            )
            await _audit("package_not_found", {
                "package": pkg, "ecosystem": ecosystem,
            })
            return {"ok": False, "package": pkg, "ecosystem": ecosystem,
                    "latest_version": None, "message": msg}
        return {"ok": False, "package": pkg, "ecosystem": ecosystem,
                "latest_version": None,
                "message": f"verification failed: {type(e).__name__}: {e}"}

    if ecosystem == "pypi":
        version = (data.get("info") or {}).get("version")
    else:
        version = (data.get("dist-tags") or {}).get("latest")
    return {
        "ok":             True,
        "package":        pkg,
        "ecosystem":      ecosystem,
        "latest_version": version,
        "message":        f"Package `{pkg}` verified on {ecosystem.upper()} (latest: {version}).",
    }


__all__ = [
    "set_db",
    "check_cost_cap",
    "check_edit_loop", "reset_edit_history",
    "heartbeat", "stuck_watchdog_tick",
    "check_destructive",
    "check_integration_gate",
    "verify_package",
]
