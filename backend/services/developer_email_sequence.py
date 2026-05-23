"""
services/developer_email_sequence.py — iter 331e Part 4

Onboarding email sequence for the Developer Portal:

  Day  0   — Welcome (already sent on OTP verify; not handled here)
  Day  3   — "Connect GitHub to get started"  (only if NOT connected)
  Day  7   — "You're halfway through your tokens" (if tokens < 500 but used)
  Day  7   — "Your tokens are waiting" (if tokens_total_used == 0)
  Day 25   — "Your free tokens expire in 5 days"

Mechanism:
  - APScheduler daily 05:00 UTC cron walks `developer_accounts`,
    classifies each account into 0..N email buckets, sends the email
    via `services.email_service_resend.send_email`, then stamps
    `email_sequence_sent[<bucket_id>]` on the account so we never
    re-fire the same email.

  - Idempotent: re-running the cron the same day is safe.
  - Per-bucket fingerprint persisted in `developer_email_sequence_log`
    collection for auditing.
  - Zero external dependencies beyond Resend wrapper + Mongo.
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


def _site_url() -> str:
    return (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("SITE_URL")
        or "https://aurem.live"
    ).rstrip("/")


def _hours_since(iso: str | datetime | None) -> float:
    if not iso:
        return 0.0
    if isinstance(iso, datetime):
        when = iso
    else:
        try:
            when = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except Exception:
            return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - when
    return delta.total_seconds() / 3600.0


# ── Templates ───────────────────────────────────────────────────────

def _shell(title: str, body_html: str) -> str:
    return f"""<!doctype html><html><body
        style="font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
               background:#0b1020;color:#e7ecff;margin:0;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#10172a;
              border:1px solid #1e2a4a;border-radius:14px;padding:32px;">
    <h1 style="font-size:20px;margin:0 0 12px;letter-spacing:-0.01em;">
      {title}
    </h1>
    {body_html}
    <p style="color:#6a7aab;font-size:12px;margin-top:28px;text-align:center;">
      Reply to this email and a human will read it. We promise.
    </p>
  </div></body></html>"""


def render_day3_github_nudge(name: str) -> tuple[str, str, str]:
    first = (name or "there").split()[0]
    site = _site_url()
    subject = "Connect GitHub to get started"
    html = _shell(
        "Connect GitHub — 5-minute setup",
        f"""<p style="color:#9aa6c7;line-height:1.55;">Hi {first}, your AUREM CTO
        account is ready but GitHub isn't connected yet. AUREM CTO needs read access
        to your repos so it can understand your codebase before making any
        changes.</p>
        <ol style="color:#9aa6c7;line-height:1.7;padding-left:18px;">
          <li>Open <a href="{site}/developers/connect"
              style="color:#7ad9b6;text-decoration:none;">
              {site}/developers/connect</a></li>
          <li>Click "Connect GitHub" — uses GitHub OAuth, read-only by default</li>
          <li>Pick the repo you want AUREM CTO to work on</li>
        </ol>
        <p style="color:#9aa6c7;line-height:1.55;">Once connected, just chat
        with AUREM CTO. "Add a stripe checkout button" or "fix the 500 on /api/orders"
        — that's the whole API.</p>""")
    text = (
        f"Hi {first}, your AUREM CTO account is ready but GitHub isn't connected yet.\n\n"
        f"Connect in 5 minutes: {site}/developers/connect\n\n"
        f"ORA needs read access so it can understand your code before any change.\n"
    )
    return subject, html, text


def render_day7_halfway(name: str, tokens_remaining: int) -> tuple[str, str, str]:
    first = (name or "there").split()[0]
    site = _site_url()
    subject = "You're halfway through your tokens"
    html = _shell(
        "Halfway through — keep building",
        f"""<p style="color:#9aa6c7;line-height:1.55;">Hi {first}, you have
        <strong style="color:#f6c177;">{tokens_remaining} tokens</strong> left.
        That's still enough to ship a feature or two, but worth knowing.</p>
        <p style="color:#cfd8f5;font-weight:600;margin:18px 0 6px;">Three tips
        that stretch your tokens:</p>
        <ul style="color:#9aa6c7;line-height:1.7;padding-left:18px;">
          <li>Ask AUREM CTO to <em>plan</em> first ("show me the plan") — costs 1
              token vs. 10 for a wrong edit-then-rebuild.</li>
          <li>Connect <strong>BYOK</strong> at <a href="{site}/developers/settings"
              style="color:#7ad9b6;text-decoration:none;">/developers/settings</a>
              — using your own LLM keys stops token deduction entirely.</li>
          <li>Run <code style="color:#7ad9b6;">run_pytest</code> with a
              specific path, not a directory scan.</li>
        </ul>
        <p style="margin-top:18px;">
          <a href="{site}/developers/tokens" style="display:inline-block;
             background:#7ad9b6;color:#0b1020;padding:10px 18px;border-radius:8px;
             text-decoration:none;font-weight:600;">Buy more tokens</a>
        </p>""")
    text = (
        f"Hi {first}, you have {tokens_remaining} tokens left.\n\n"
        f"Tips to stretch them:\n"
        f"  • Ask AUREM CTO to plan first (1 token vs. 10 for a wrong edit)\n"
        f"  • Connect BYOK at {site}/developers/settings\n"
        f"  • Use specific paths with run_pytest\n\n"
        f"Buy more: {site}/developers/tokens\n"
    )
    return subject, html, text


def render_day7_unused(name: str) -> tuple[str, str, str]:
    first = (name or "there").split()[0]
    site = _site_url()
    subject = "Your tokens are waiting"
    html = _shell(
        "Your 1,000 tokens are still waiting",
        f"""<p style="color:#9aa6c7;line-height:1.55;">Hi {first}, your tokens
        haven't been used yet. AUREM CTO can build your first feature in about 10
        minutes once you've connected a repo.</p>
        <p style="color:#cfd8f5;font-weight:600;margin:18px 0 6px;">Here's the
        fastest path:</p>
        <ol style="color:#9aa6c7;line-height:1.7;padding-left:18px;">
          <li>Open <a href="{site}/developers/dashboard"
              style="color:#7ad9b6;text-decoration:none;">
              {site}/developers/dashboard</a></li>
          <li>Type one line: "Add a contact form that posts to /api/contact"</li>
          <li>Hit enter. Watch AUREM CTO plan it, write it, test it, and ship a PR.</li>
        </ol>
        <p style="color:#9aa6c7;line-height:1.55;">Stuck? Reply to this email
        with what you're trying to build — we'll point you at the right
        starting prompt.</p>""")
    text = (
        f"Hi {first}, your 1,000 tokens haven't been used yet.\n\n"
        f"Fastest path to first feature:\n"
        f"  1. Open {site}/developers/dashboard\n"
        f"  2. Type: 'Add a contact form that posts to /api/contact'\n"
        f"  3. Hit enter\n\n"
        f"Reply to this email if you're stuck.\n"
    )
    return subject, html, text


def render_day25_expiry(name: str, tokens_remaining: int) -> tuple[str, str, str]:
    first = (name or "there").split()[0]
    site = _site_url()
    subject = "Your free tokens expire in 5 days"
    html = _shell(
        "Use them or buy more",
        f"""<p style="color:#9aa6c7;line-height:1.55;">Hi {first}, you have
        <strong style="color:#f6c177;">{tokens_remaining} tokens</strong>
        remaining and they expire in 5 days. After that the balance resets.</p>
        <p style="color:#cfd8f5;font-weight:600;margin:18px 0 6px;">Two options:</p>
        <ul style="color:#9aa6c7;line-height:1.7;padding-left:18px;">
          <li><strong>Use them</strong> — open <a href="{site}/developers/dashboard"
              style="color:#7ad9b6;text-decoration:none;">your dashboard</a>
              and ship one feature. The Starter pack is 10× the tokens for $9.</li>
          <li><strong>Top up</strong> — <a href="{site}/developers/tokens"
              style="color:#7ad9b6;text-decoration:none;">/developers/tokens</a>.
              Starter $9 / Builder $39 / Pro $99/month.</li>
        </ul>
        <p style="margin-top:18px;">
          <a href="{site}/developers/tokens" style="display:inline-block;
             background:#7ad9b6;color:#0b1020;padding:10px 18px;border-radius:8px;
             text-decoration:none;font-weight:600;">Top up</a>
        </p>""")
    text = (
        f"Hi {first}, you have {tokens_remaining} tokens left and they expire "
        f"in 5 days.\n\n"
        f"Two options:\n"
        f"  • Use them at {site}/developers/dashboard\n"
        f"  • Top up at {site}/developers/tokens\n"
    )
    return subject, html, text


# ── Bucket classifier ───────────────────────────────────────────────

def classify_account(acc: dict) -> list[str]:
    """Return the set of bucket ids this account currently belongs to.
    The cron filters out any bucket already in `email_sequence_sent`.
    """
    if not acc or not acc.get("email_verified"):
        return []
    sent = set(acc.get("email_sequence_sent") or [])
    hours = _hours_since(acc.get("created_at"))
    days = hours / 24.0
    buckets: list[str] = []

    # Day 3 — GitHub not connected
    if 3.0 <= days < 7.0:
        if "day3_github_nudge" not in sent and not acc.get("github_connected"):
            buckets.append("day3_github_nudge")

    # Day 7 — usage-conditional
    if 7.0 <= days < 25.0:
        used = int(acc.get("tokens_total_used") or 0)
        remaining = int(acc.get("tokens_remaining") or 0)
        if used == 0 and "day7_unused" not in sent:
            buckets.append("day7_unused")
        elif used > 0 and remaining < 500 and "day7_halfway" not in sent:
            buckets.append("day7_halfway")

    # Day 25 — expiry warning
    if 25.0 <= days < 32.0:
        if "day25_expiry" not in sent:
            buckets.append("day25_expiry")

    return buckets


# ── Sender ──────────────────────────────────────────────────────────

async def _send(bucket_id: str, acc: dict) -> dict:
    """Render + send one email. Returns `{ok, bucket_id, message_id?}`."""
    name = acc.get("name") or ""
    tokens_remaining = int(acc.get("tokens_remaining") or 0)
    if bucket_id == "day3_github_nudge":
        subject, html, text = render_day3_github_nudge(name)
    elif bucket_id == "day7_halfway":
        subject, html, text = render_day7_halfway(name, tokens_remaining)
    elif bucket_id == "day7_unused":
        subject, html, text = render_day7_unused(name)
    elif bucket_id == "day25_expiry":
        subject, html, text = render_day25_expiry(name, tokens_remaining)
    else:
        return {"ok": False, "reason": "unknown_bucket"}

    try:
        from services.email_service_resend import send_email
        ok, msg = await send_email(
            to=acc["email"], subject=subject, html=html, text=text,
        )
        return {"ok": ok, "bucket_id": bucket_id, "message_id": msg if ok else None,
                "error": None if ok else msg}
    except Exception as e:
        logger.exception("[dev-email-seq] send failed")
        return {"ok": False, "bucket_id": bucket_id, "error": str(e)[:120]}


async def run_sequence_tick(*, limit: int = 500) -> dict:
    """Walk verified developer accounts, classify, send each pending
    bucket. Idempotent — re-running the same day is safe.

    Returns a structured run summary used by the admin endpoint.
    """
    if _db is None:
        return {"ok": False, "reason": "db not ready"}
    cursor = _db.developer_accounts.find(
        {"email_verified": True},
        {"_id": 0},
        limit=limit,
    )
    accounts = await cursor.to_list(length=limit)
    sent_log: list[dict] = []
    skipped = 0
    failed = 0

    for acc in accounts:
        buckets = classify_account(acc)
        if not buckets:
            skipped += 1
            continue
        for bucket_id in buckets:
            r = await _send(bucket_id, acc)
            if r.get("ok"):
                # Stamp the account so we never re-fire
                await _db.developer_accounts.update_one(
                    {"user_id": acc["user_id"]},
                    {"$addToSet": {"email_sequence_sent": bucket_id}},
                )
                sent_log.append({
                    "user_id":    acc["user_id"],
                    "email":      acc["email"],
                    "bucket_id":  bucket_id,
                    "message_id": r.get("message_id"),
                    "ts":         datetime.now(timezone.utc).isoformat(),
                })
                # Audit row (best-effort)
                try:
                    await _db.developer_email_sequence_log.insert_one({
                        "user_id":    acc["user_id"],
                        "email":      acc["email"],
                        "bucket_id":  bucket_id,
                        "message_id": r.get("message_id"),
                        "ts":         datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    pass
            else:
                failed += 1
                logger.warning(
                    f"[dev-email-seq] send failed for "
                    f"{acc.get('email')}: {r.get('error')}"
                )
    return {
        "ok":           True,
        "scanned":      len(accounts),
        "sent":         len(sent_log),
        "skipped":      skipped,
        "failed":       failed,
        "sent_buckets": sent_log[:50],   # truncated for logging
    }


__all__ = [
    "set_db", "classify_account", "run_sequence_tick",
    "render_day3_github_nudge", "render_day7_halfway",
    "render_day7_unused", "render_day25_expiry",
]
