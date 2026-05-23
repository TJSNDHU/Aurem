"""
Autopilot Brief Notifier — iter 285.9
═══════════════════════════════════════════════════════════════════════

Post-run summary dispatcher. Hooked after `_execute_morning_run` finishes.

Channels (tried in order, each is fire-and-forget):
  1. Telegram (if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID set)
  2. WHAPI    (if WHAPI_TOKEN + WHAPI_CHANNEL_ID + NOTIFY_PHONE set)
  3. Resend   (if RESEND_API_KEY + NOTIFY_EMAIL set)

If NO channel is configured → records to truth_ledger as `notifications_skipped`
with honest reason (Truth-Sync: never lie that a send happened).

Zero-mock policy: every send either actually hits the provider or gets
logged as `notification_skipped` in `db.autopilot_notifications` with
the reason (missing creds / http error / provider down).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("autopilot_brief")

NOTIFY_COLLECTION = "autopilot_notifications"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_brief(run: dict) -> str:
    """Hinglish, operator-friendly one-liner + phase breakdown."""
    phases = run.get("phases") or []
    ok_count = sum(1 for p in phases if p.get("ok"))

    # Pull real numbers from phase results
    leads = 0
    sent = 0
    processed = 0
    brief_id = None
    for p in phases:
        name = p.get("phase")
        result = p.get("result") or {}
        if name == "scout":
            leads = int(result.get("leads", 0) or 0) or (1 if result.get("hunt_id") else 0)
        if name == "blast":
            processed = int(result.get("processed", 0) or 0)
            sent = int(result.get("sent", 0) or 0)
        if name == "report":
            brief_id = result.get("brief_id")

    head_emoji = "🚀" if run.get("success") else "⚠️"
    headline = (
        f"{head_emoji} AUREM Morning Run — {ok_count}/{len(phases)} phases OK "
        f"in {run.get('duration_seconds', 0)}s"
    )

    # iter 331c Sprint 6.3 — Vanguard Security line.
    # Best-effort; never breaks the brief.
    security_line = ""
    try:
        # Synchronous shim — we can't await inside _format_brief, but the
        # caller (dispatch_brief) is async, so we expose a sync helper
        # that reads the stashed line from run["security_line"] if set.
        security_line = run.get("security_line") or ""
    except Exception:
        security_line = ""

    lines = [
        headline,
        "",
        f"  Scout: {leads} lead{'s' if leads != 1 else ''} processed",
        f"  Blast: {sent}/{processed} sent" if processed else "  Blast: 0 eligible",
        f"  Brief: {brief_id or 'not_generated'}",
    ]
    if security_line:
        lines.append(f"  {security_line}")
    lines += [
        "",
        f"  Run ID: {run.get('run_id', '?')}",
        f"  Time:   {run.get('started_at', '?')}",
        f"  HUD:    /admin/pillars-map",
    ]
    return "\n".join(lines)


async def _send_telegram(text: str) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"ok": False, "channel": "telegram", "reason": "creds_missing",
                "missing": [k for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
                            if not os.environ.get(k)]}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                # No parse_mode — brief text contains underscores (run_ids, etc)
                # which Markdown/MarkdownV2 would reject as unclosed italics.
                # Plain text is honest + always delivers.
                json={"chat_id": chat_id, "text": text,
                      "disable_web_page_preview": True},
            )
        if r.status_code == 200:
            return {"ok": True, "channel": "telegram", "reason": "sent"}
        return {"ok": False, "channel": "telegram",
                "reason": f"http_{r.status_code}",
                "detail": r.text[:200]}
    except Exception as e:
        return {"ok": False, "channel": "telegram", "reason": "error",
                "detail": str(e)[:200]}


async def _send_whapi(text: str) -> dict:
    # iter 287.4 — honor the WHAPI_BLAST_DISABLED kill-switch.
    # Brief notifier respects it too: if WHAPI is off globally (account
    # restricted), don't even attempt — Telegram + Email carry the brief.
    if (os.environ.get("WHAPI_BLAST_DISABLED", "false").lower()
            in ("1", "true", "yes", "on")):
        return {"ok": False, "channel": "whapi", "reason": "disabled_by_admin",
                "detail": "WHAPI_BLAST_DISABLED=true (account restricted)"}
    # Accept both WHAPI_API_TOKEN (production .env) and WHAPI_TOKEN (legacy)
    token = (os.environ.get("WHAPI_API_TOKEN") or os.environ.get("WHAPI_TOKEN") or "").strip()
    # NOTIFY_PHONE preferred; fall back to ADMIN_ALERT_PHONE so operator always gets brief
    phone = (os.environ.get("NOTIFY_PHONE") or os.environ.get("ADMIN_ALERT_PHONE") or "").strip()
    base = (os.environ.get("WHAPI_API_URL") or "https://gate.whapi.cloud").rstrip("/")
    if not token or not phone:
        missing = []
        if not token:
            missing.append("WHAPI_API_TOKEN")
        if not phone:
            missing.append("NOTIFY_PHONE_or_ADMIN_ALERT_PHONE")
        return {"ok": False, "channel": "whapi", "reason": "creds_missing", "missing": missing}
    # WHAPI accepts "to" as digits-only; strip + and any separators
    phone_digits = "".join(ch for ch in phone if ch.isdigit())
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"{base}/messages/text",
                headers={"Authorization": f"Bearer {token}"},
                json={"to": phone_digits, "body": text},
            )
        if r.status_code in (200, 201):
            return {"ok": True, "channel": "whapi", "reason": "sent"}
        return {"ok": False, "channel": "whapi",
                "reason": f"http_{r.status_code}",
                "detail": r.text[:200]}
    except Exception as e:
        return {"ok": False, "channel": "whapi", "reason": "error",
                "detail": str(e)[:200]}


async def _send_email(subject: str, body_text: str) -> dict:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    # NOTIFY_EMAIL preferred; fall back to AUREM_SALES_BCC_EMAIL (admin inbox) so email fires too
    to_addr = (os.environ.get("NOTIFY_EMAIL") or os.environ.get("AUREM_SALES_BCC_EMAIL") or "").strip()
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "AUREM <alerts@aurem.live>").strip()
    if not api_key or not to_addr:
        missing = []
        if not api_key:
            missing.append("RESEND_API_KEY")
        if not to_addr:
            missing.append("NOTIFY_EMAIL_or_AUREM_SALES_BCC_EMAIL")
        return {"ok": False, "channel": "email", "reason": "creds_missing", "missing": missing}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"from": from_addr, "to": [to_addr],
                      "subject": subject, "text": body_text},
            )
        if r.status_code in (200, 201, 202):
            return {"ok": True, "channel": "email", "reason": "sent"}
        return {"ok": False, "channel": "email",
                "reason": f"http_{r.status_code}",
                "detail": r.text[:200]}
    except Exception as e:
        return {"ok": False, "channel": "email", "reason": "error",
                "detail": str(e)[:200]}


async def dispatch_brief(db: Any, run: dict) -> dict:
    """Send post-run brief to all configured channels. Returns rollup.

    Records every attempt to db.autopilot_notifications for auditability.
    Never raises — autopilot run is not allowed to fail because of a
    notification hiccup.

    Also drains db.alerts_digest_queue and appends the consolidated
    overnight QA digest to the brief (iter 286.0 alert suppression).
    """
    # ── iter 331c Sprint 6.3 — Vanguard Security one-liner ──
    try:
        from services.vanguard_alerts import (
            morning_brief_security_line, set_db as _set_va_db,
        )
        _set_va_db(db)
        run["security_line"] = await morning_brief_security_line()
    except Exception:
        run["security_line"] = ""

    # ── Drain pending alerts digest queue (mute-mode consolidated list) ──
    digest_summary: dict = {"pending": 0, "by_source": {}, "sample_ids": []}
    try:
        cursor = db.alerts_digest_queue.find(
            {"delivered": False}, {"_id": 0}
        ).limit(500)
        pending = [d async for d in cursor]
        if pending:
            by_src: dict[str, int] = {}
            for a in pending:
                by_src[a.get("source", "unknown")] = by_src.get(a.get("source", "unknown"), 0) + 1
            digest_summary = {
                "pending": len(pending),
                "by_source": by_src,
                "sample_ids": [p.get("endpoint_id") for p in pending[:5] if p.get("endpoint_id")],
            }
    except Exception:
        pass

    text = _format_brief(run)
    if digest_summary["pending"]:
        by_src = digest_summary["by_source"]
        src_str = ", ".join(f"{k}={v}" for k, v in sorted(by_src.items()))
        text += f"\n\n  Overnight alerts digest: {digest_summary['pending']} queued ({src_str})"
        if digest_summary["sample_ids"]:
            text += f"\n  Sample: {', '.join(str(s) for s in digest_summary['sample_ids'])}"

    subject = f"AUREM Morning Run — {run.get('run_id', 'unknown')}"

    attempts = []
    try:
        attempts.append(await _send_telegram(text))
    except Exception as e:
        attempts.append({"ok": False, "channel": "telegram", "reason": "wrapper_error", "detail": str(e)[:200]})
    try:
        attempts.append(await _send_whapi(text))
    except Exception as e:
        attempts.append({"ok": False, "channel": "whapi", "reason": "wrapper_error", "detail": str(e)[:200]})
    try:
        attempts.append(await _send_email(subject, text))
    except Exception as e:
        attempts.append({"ok": False, "channel": "email", "reason": "wrapper_error", "detail": str(e)[:200]})

    delivered = [a for a in attempts if a.get("ok")]
    skipped = [a for a in attempts if not a.get("ok")]

    # Mark digest queue entries as delivered IF at least one channel succeeded
    if delivered and digest_summary["pending"]:
        try:
            await db.alerts_digest_queue.update_many(
                {"delivered": False},
                {"$set": {"delivered": True,
                          "delivered_at": _now_iso(),
                          "delivered_via": [a["channel"] for a in delivered],
                          "run_id": run.get("run_id")}},
            )
        except Exception:
            pass

    doc = {
        "run_id": run.get("run_id"),
        "ts_iso": _now_iso(),
        "delivered_to": [a["channel"] for a in delivered],
        "skipped": skipped,
        "text_preview": text[:400],
        "digest_summary": digest_summary,
    }
    try:
        await db[NOTIFY_COLLECTION].insert_one(dict(doc))
    except Exception:
        pass

    # Truth Ledger — honest signal whether we actually reached a human
    try:
        from services import truth_ledger
        if delivered:
            await truth_ledger.record_success(
                actor="autopilot_brief",
                description=f"Post-run brief delivered to {len(delivered)} channel(s)",
                evidence={"run_id": run.get("run_id"),
                          "channels": [a["channel"] for a in delivered]},
            )
        else:
            # This is NOT a failure — it's honestly "no notification channel cfg".
            # Truth-Sync: tell the operator creds are missing, don't pretend we sent.
            await truth_ledger.record_failure(
                actor="autopilot_brief",
                description="No post-run notification channel configured — brief recorded only",
                evidence={"run_id": run.get("run_id"), "skipped": skipped},
                outcome="notification_skipped_no_creds",
            )
    except Exception:
        pass

    return {
        "ok": bool(delivered),
        "delivered": [a["channel"] for a in delivered],
        "skipped": [{"channel": s["channel"], "reason": s["reason"]} for s in skipped],
    }
