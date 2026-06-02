"""
services/bug_catch.py — iter D-60 (BugCatch)

Internal QA bug-report capture. Founder/admin clicks the floating
BugCatch button in `/admin/*` → modal grabs DOM screenshot,
annotation overlay, console logs, network calls, URL + viewport →
POST to `/api/admin/bug-reports`.

This service handles:
  • create_report(payload)        — store in Mongo + email founder + AI tag
  • list_reports(status, limit)
  • get_report(report_id)
  • set_status(report_id, status)
  • _ai_root_cause(report)        — DeepSeek free-tier guess

Mongo collection: `bug_reports`
  {
    report_id:      "br_<8hex>",
    ts:             iso,
    submitted_by:   email,
    description:    "...",
    severity:       "low|med|high",
    screenshot_b64: "data:image/png;base64,...",   (≤ 1.5 MB after compression)
    url:            "/admin/api-keys",
    viewport:       {w, h},
    user_agent:     "...",
    console_logs:   [{level, msg, ts}, ...]        (last ≤ 200)
    network_calls:  [{method, url, status, ts}, ...] (last ≤ 50)
    annotations:    [{kind, points/text/color}, ...] (optional — drawn on canvas)
    status:         "open|investigating|resolved|won't-fix",
    ai_root_cause:  "..."   (1–2 sentence guess, ≤ 240 chars),
    ai_model:       "deepseek-v3" | "skipped",
    ai_generated_at: iso,
  }
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_db = None
_MAX_SCREENSHOT_BYTES = 2_000_000     # 2 MB hard cap (base64-padded)
_AI_TIMEOUT_S = 20
_VALID_STATUS = {"open", "investigating", "resolved", "wont_fix"}
_VALID_SEVERITY = {"low", "med", "high"}


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "br_" + secrets.token_hex(4)


def _clip_screenshot(b64: str) -> tuple[str, str]:
    """Returns (clipped_b64, note). If oversized, return empty string +
    note so it isn't silently saved at half-size."""
    if not b64:
        return "", "no_screenshot"
    if len(b64) > _MAX_SCREENSHOT_BYTES:
        return "", f"screenshot_dropped_oversized_{len(b64)}b"
    return b64, ""


async def _ai_root_cause(report: dict[str, Any]) -> tuple[str, str]:
    """Use existing free-tier LLM ladder (no extra cost) to guess root
    cause. Returns (text, model). Never raises."""
    try:
        from services.dev_cto_chat import _free_tier_key, _dispatch_free_tier
        api_key = _free_tier_key() or ""
        if not api_key:
            return "", "skipped_no_llm_key"
        # Trim console logs to last 30 entries with errors prioritised.
        logs = report.get("console_logs") or []
        err_logs = [l for l in logs if l.get("level") in ("error", "warn")]
        sample = (err_logs + logs)[:30]
        net = report.get("network_calls") or []
        failed_net = [n for n in net
                       if int(n.get("status", 0)) >= 400][:8]
        prompt_user = (
            f"URL: {report.get('url','?')}\n"
            f"User said: {report.get('description','(no description)')}\n"
            f"Viewport: {report.get('viewport',{})}\n"
            f"Last console entries (errors first):\n"
            + "\n".join([f"[{l.get('level','?')}] {l.get('msg','')[:200]}"
                          for l in sample])
            + "\nFailed network calls:\n"
            + "\n".join([f"{n.get('method','?')} {n.get('url','')} → "
                          f"{n.get('status','?')}"
                          for n in failed_net])
        )
        messages = [
            {"role": "system",
              "content": ("You are AUREM's QA triage assistant. "
                          "Given a bug report (user description + "
                          "console logs + failed network calls), reply "
                          "with ONE plain-English sentence (≤ 240 "
                          "chars) guessing the most likely root cause. "
                          "Be specific. No code, no JSON.")},
            {"role": "user", "content": prompt_user},
        ]
        text, label = await _dispatch_free_tier(api_key, messages,
                                                  temperature=0.0)
        text = (text or "").strip().replace("\n", " ")[:240]
        return text, label
    except Exception as e:
        logger.warning(f"[bugcatch] ai root cause failed: {e}")
        return "", f"skipped_{type(e).__name__}"


async def _email_founder(report: dict[str, Any]) -> None:
    """Best-effort founder email. Never raises — bug capture must not
    fail because of a downstream mailer."""
    to = os.environ.get("ADMIN_DAILY_BRIEF_EMAIL", "").strip()
    if not to:
        return
    try:
        from services.email_service_resend import send_email
        rid = report.get("report_id", "?")
        desc = (report.get("description", "") or "(no description)")[:400]
        sev = report.get("severity", "med")
        url = report.get("url", "?")
        ai = report.get("ai_root_cause", "")
        html = f"""
<h2 style="font-family:'Cinzel',serif;color:#E8C86A">
  🐛 BugCatch · new report {rid}
</h2>
<p><strong>Severity:</strong> {sev}<br>
<strong>URL:</strong> {url}<br>
<strong>Submitted by:</strong> {report.get('submitted_by','admin')}</p>
<p><em>Description:</em><br>{desc}</p>
{f"<p><strong>AI root cause:</strong> {ai}</p>" if ai else ""}
<p><a href="https://aurem.live/admin/bug-reports">
   Open BugCatch dashboard →</a></p>
"""
        await send_email(
            to=to, subject=f"🐛 BugCatch · {sev.upper()} · {rid}",
            html=html,
        )
    except Exception as e:
        logger.warning(f"[bugcatch] email_founder failed: {e}")


# ── Public API ───────────────────────────────────────────────────────

async def create_report(payload: dict[str, Any],
                         submitted_by: str) -> dict[str, Any]:
    if _db is None:
        raise RuntimeError("db_not_ready")
    description = (payload.get("description") or "").strip()[:4000]
    severity = (payload.get("severity") or "med").lower()
    if severity not in _VALID_SEVERITY:
        severity = "med"
    rid = _new_id()
    shot, shot_note = _clip_screenshot(payload.get("screenshot_b64") or "")
    row: dict[str, Any] = {
        "report_id":      rid,
        "ts":             _now(),
        "submitted_by":   submitted_by or "admin",
        "description":    description,
        "severity":       severity,
        "screenshot_b64": shot,
        "screenshot_note": shot_note,
        "url":            (payload.get("url") or "")[:400],
        "viewport":       {
            "w": int((payload.get("viewport") or {}).get("w", 0) or 0),
            "h": int((payload.get("viewport") or {}).get("h", 0) or 0),
        },
        "user_agent":     (payload.get("user_agent") or "")[:400],
        "console_logs":   (payload.get("console_logs") or [])[-200:],
        "network_calls":  (payload.get("network_calls") or [])[-50:],
        "annotations":    payload.get("annotations") or [],
        "status":         "open",
        "ai_root_cause":  "",
        "ai_model":       "",
        "ai_generated_at": "",
    }
    # AI root cause — best-effort, never blocks
    ai_text, ai_model = await _ai_root_cause(row)
    if ai_text:
        row["ai_root_cause"]   = ai_text
        row["ai_model"]        = ai_model
        row["ai_generated_at"] = _now()
    else:
        row["ai_model"] = ai_model    # carries the skip-reason
    await _db.bug_reports.insert_one(row)
    # Email founder asynchronously of the body of work; clip screenshot
    # out of the email-side dict so we don't blow up Resend.
    email_row = {k: v for k, v in row.items()
                  if k not in ("screenshot_b64", "_id")}
    await _email_founder(email_row)
    # Return without _id
    return {k: v for k, v in row.items() if k != "_id"}


async def list_reports(status: str = "",
                        limit: int = 50) -> list[dict[str, Any]]:
    if _db is None:
        return []
    q: dict[str, Any] = {}
    if status and status in _VALID_STATUS:
        q["status"] = status
    rows: list[dict[str, Any]] = []
    async for d in _db.bug_reports.find(
        q,
        {"_id": 0, "screenshot_b64": 0, "console_logs": 0,
          "network_calls": 0, "annotations": 0},
    ).sort("ts", -1).limit(limit):
        rows.append(d)
    return rows


async def get_report(report_id: str) -> dict[str, Any] | None:
    if _db is None:
        return None
    return await _db.bug_reports.find_one(
        {"report_id": report_id}, {"_id": 0},
    )


async def set_status(report_id: str, status: str) -> dict[str, Any]:
    if _db is None:
        raise RuntimeError("db_not_ready")
    if status not in _VALID_STATUS:
        return {"ok": False, "error": f"invalid_status:{status}"}
    res = await _db.bug_reports.update_one(
        {"report_id": report_id}, {"$set": {"status": status}},
    )
    return {"ok": True, "modified": res.modified_count == 1}


async def stats() -> dict[str, int]:
    if _db is None:
        return {"open": 0, "investigating": 0, "resolved": 0, "wont_fix": 0}
    out: dict[str, int] = {s: 0 for s in _VALID_STATUS}
    for s in _VALID_STATUS:
        out[s] = await _db.bug_reports.count_documents({"status": s})
    return out
