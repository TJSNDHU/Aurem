"""
services/campaign_autofix.py — iter D-59

Autonomous repair loop for campaign components flagged 🔴 / 🟡 by
`campaign_health.full_report()`.

Each autofix returns:
  {
    "ok":              bool,
    "component":       str,
    "action_taken":    str,
    "result":          str,
    "fixed":           bool,
    "residual_issue":  str | None,
    "requires_human":  bool,
    "human_hint":      str | None,
    "ts":              iso,
  }

Hard rules:
  • Idempotent — running the same fix twice is safe.
  • Never silent — every attempt + outcome lands in `campaign_autofix_log`.
  • Bounded — no fix loops longer than 30 s. Hard timeout on each.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_db = None
_TIMEOUT_S = 30


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log(component: str, action: str, result: dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        await _db.campaign_autofix_log.insert_one({
            "component":   component,
            "action":      action,
            "result":      result,
            "ts":          _now(),
        })
    except Exception as e:
        logger.warning(f"[autofix] log insert failed: {e}")


async def _wrap(component: str, action: str, fn) -> dict[str, Any]:
    """Run an autofix with timeout + logging."""
    try:
        out = await asyncio.wait_for(fn(), timeout=_TIMEOUT_S)
    except asyncio.TimeoutError:
        out = {
            "ok":             False,
            "fixed":          False,
            "result":         f"timeout after {_TIMEOUT_S}s",
            "residual_issue": "timeout",
            "requires_human": False,
        }
    except Exception as e:
        out = {
            "ok":             False,
            "fixed":          False,
            "result":         f"exception: {type(e).__name__}: {e}",
            "residual_issue": str(e),
            "requires_human": False,
        }
    out["component"]    = component
    out["action_taken"] = action
    out["ts"]           = _now()
    await _log(component, action, out)
    return out


# ── Per-component fixers ─────────────────────────────────────────────

async def _fix_trigger_scout_run() -> dict[str, Any]:
    """Kick a single Ghost Scout cycle. Cap to one query so we don't
    burn the proxy quota."""
    try:
        from services.ghost_scout_iproyal import harvest_leads
        res = await harvest_leads(
            "beauty clinic", "Toronto", country="ca", limit=5,
        )
        inserted = res.get("inserted", 0)
        return {
            "ok":             res.get("ok", False),
            "fixed":          bool(res.get("ok") and inserted >= 0),
            "result":         f"scout fetched={res.get('fetched',0)} "
                              f"inserted={inserted}",
            "residual_issue": None if res.get("ok")
                              else res.get("error", "scout_failed"),
            "requires_human": not res.get("ok"),
            "human_hint":     ("Check IPROYAL_PROXY_URL or quota in "
                                "iproyal dashboard")
                              if not res.get("ok") else None,
        }
    except Exception as e:
        return {"ok": False, "fixed": False,
                 "result": f"scout import failed: {e}",
                 "residual_issue": "scout_module_unavailable",
                 "requires_human": True,
                 "human_hint": "Check IPROYAL env vars + ghost_scout_iproyal.py"}


async def _fix_trigger_blast_cycle() -> dict[str, Any]:
    """Force one auto-blast cycle."""
    try:
        from services.auto_blast_engine import run_auto_blast_cycle
        res = await run_auto_blast_cycle(force=True)
        ok   = bool(res.get("ok"))
        sent = res.get("total_sent", 0)
        note = ""
        summaries = res.get("summaries", []) or []
        if summaries:
            note = summaries[0].get("note", "") or ""
        if sent > 0:
            return {"ok": True, "fixed": True,
                     "result": f"sent={sent}",
                     "residual_issue": None,
                     "requires_human": False}
        if note == "no-eligible-leads":
            return {"ok": True, "fixed": False,
                     "result": "engine ran clean but no eligible leads",
                     "residual_issue": "pool_empty",
                     "requires_human": False,
                     "human_hint": ("Trigger 'topup_via_scout' next, "
                                     "or upload CSV")}
        return {"ok": ok, "fixed": False,
                 "result": f"cycle ran but sent=0 (note={note!r})",
                 "residual_issue": note or "unknown",
                 "requires_human": False}
    except Exception as e:
        return {"ok": False, "fixed": False,
                 "result": f"blast import failed: {e}",
                 "residual_issue": "blast_engine_unavailable",
                 "requires_human": True,
                 "human_hint": "Check auto_blast_engine.py + Mongo connection"}


async def _fix_topup_via_scout() -> dict[str, Any]:
    """Pool empty → run a 3-query scout burst (Toronto + Mississauga
    salons / spas)."""
    try:
        from services.ghost_scout_iproyal import harvest_leads
        queries = [
            ("beauty clinic", "Toronto", "ca"),
            ("med spa",       "Mississauga", "ca"),
            ("nail salon",    "Toronto", "ca"),
        ]
        total = 0
        for q, loc, ctry in queries:
            try:
                r = await asyncio.wait_for(
                    harvest_leads(q, loc, country=ctry, limit=8),
                    timeout=10,
                )
                total += r.get("inserted", 0)
            except Exception:
                continue
        if total > 0:
            return {"ok": True, "fixed": True,
                     "result": f"+{total} fresh leads inserted",
                     "residual_issue": None,
                     "requires_human": False}
        return {"ok": True, "fixed": False,
                 "result": "scout completed but 0 inserted "
                          "(all duplicates or proxy slow)",
                 "residual_issue": "all_duplicates_or_slow",
                 "requires_human": True,
                 "human_hint": ("Try a new query niche or upload a CSV. "
                                 "Or check iProyal quota.")}
    except Exception as e:
        return {"ok": False, "fixed": False,
                 "result": f"topup failed: {e}",
                 "residual_issue": str(e),
                 "requires_human": True,
                 "human_hint": "Manual lead upload via /api/admin/leads/upload-csv"}


async def _fix_send_morning_brief() -> dict[str, Any]:
    try:
        from services.daily_brief import send_morning_brief
        res = await send_morning_brief()
        return {"ok": True, "fixed": True,
                 "result": f"brief sent, id={res.get('brief_id','')[:8]}",
                 "residual_issue": None, "requires_human": False}
    except Exception as e:
        return {"ok": False, "fixed": False,
                 "result": f"brief send failed: {e}",
                 "residual_issue": str(e), "requires_human": True,
                 "human_hint": "Check ADMIN_DAILY_BRIEF_EMAIL env var"}


# Map: autofix tag → (fixer, action label)
_FIXERS = {
    "trigger_scout_run":     (_fix_trigger_scout_run,
                                "ran one Ghost Scout cycle"),
    "trigger_blast_cycle":   (_fix_trigger_blast_cycle,
                                "forced one auto-blast cycle"),
    "topup_via_scout":       (_fix_topup_via_scout,
                                "ran 3-query Ghost Scout burst"),
    "send_morning_brief":    (_fix_send_morning_brief,
                                "sent morning brief"),
}


async def apply(autofix_tag: str) -> dict[str, Any]:
    if autofix_tag not in _FIXERS:
        out = {
            "ok":             False,
            "fixed":          False,
            "component":      autofix_tag,
            "action_taken":   "no-op",
            "result":         f"unknown autofix tag {autofix_tag!r}",
            "residual_issue": "unknown_tag",
            "requires_human": True,
            "human_hint":     "Use one of: " + ", ".join(_FIXERS.keys()),
            "ts":             _now(),
        }
        await _log(autofix_tag, "no-op", out)
        return out
    fn, action = _FIXERS[autofix_tag]
    return await _wrap(autofix_tag, action, fn)


async def apply_all_from_report(rows: list[dict[str, Any]]
                                  ) -> dict[str, Any]:
    """Walk the campaign_health rows and run every available autofix.
    Returns aggregated result."""
    results: list[dict[str, Any]] = []
    for row in rows:
        tag = row.get("autofix")
        if not tag:
            continue
        if tag not in _FIXERS:
            continue
        results.append(await apply(tag))
    fixed_n = sum(1 for r in results if r.get("fixed"))
    return {
        "ok":         True,
        "attempted":  len(results),
        "fixed":      fixed_n,
        "results":    results,
        "ts":         _now(),
    }
