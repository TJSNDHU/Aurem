"""
routers/admin_integrations_router.py — iter D-38

Read-only admin dashboard for every 3rd-party integration AUREM uses
in its CRM / outreach / chat / payments stack.

For each provider it surfaces:
  - whether the env var with the API key is configured (key present?)
  - the last 4 characters of the configured key (redacted tail) so the
    founder can confirm WHICH key is loaded without exposing the secret
  - the last 7-day failure count broken down by bucket
    (unauthorized / forbidden / rate_limit / other)
  - a "status" pill: green / yellow / red / unset based on the above
  - a "needs_recharge" boolean flag — true when bucket=unauthorized has
    been hit in the last 24 h or when the key is missing entirely

This is the data source for the new /admin/integrations admin page.

Auth: requires admin (super_admin or is_admin claim on the JWT).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── The integrations AUREM actually uses, in display order ──────────
# Each entry maps to:
#   env_var        : the os.environ key that holds the credential
#   group          : "llm" | "comms" | "payment" | "data" | "infra"
#                      → controls the colour grouping in the admin UI
#   role           : human-readable one-liner ("powers AUREM CTO chat")
#   recharge_url   : where the founder rotates / tops up the key
#   docs_url       : provider's API docs

INTEGRATIONS: list[dict[str, Any]] = [
    # ── LLM (chat / agents) ───────────────────────────────────────────
    {"provider": "anthropic",
     "env_var":  "ANTHROPIC_API_KEY",
     "group":    "llm",
     "role":     "AUREM CTO chat · ORA brain · council decisions",
     "recharge_url": "https://console.anthropic.com/settings/billing",
     "docs_url":     "https://docs.anthropic.com/"},
    {"provider": "openai",
     "env_var":  "OPENAI_API_KEY",
     "group":    "llm",
     "role":     "BYOK fallback · aurem_ai_service · image gen",
     "recharge_url": "https://platform.openai.com/settings/organization/billing",
     "docs_url":     "https://platform.openai.com/docs"},
    {"provider": "google_gemini",
     "env_var":  "GEMINI_API_KEY",
     "group":    "llm",
     "role":     "AUREM CTO BYOK · classifier fallback",
     "recharge_url": "https://aistudio.google.com/app/apikey",
     "docs_url":     "https://ai.google.dev/"},
    {"provider": "openrouter",
     "env_var":  "OPENROUTER_API_KEY",
     "group":    "llm",
     "role":     "multi-model router · race-pattern engine",
     "recharge_url": "https://openrouter.ai/credits",
     "docs_url":     "https://openrouter.ai/docs"},
    {"provider": "emergent_llm",
     "env_var":  "EMERGENT_LLM_KEY",
     "group":    "llm",
     "role":     "Emergent Universal Key (Claude/Gemini/OpenAI/Sora)",
     "recharge_url": "https://app.emergent.sh/profile/universal-key",
     "docs_url":     ""},
    # ── Comms (outreach + customer messaging) ────────────────────────
    {"provider": "twilio",
     "env_var":  "TWILIO_AUTH_TOKEN",
     "group":    "comms",
     "role":     "voice + SMS outreach · OTP delivery",
     "recharge_url": "https://console.twilio.com/billing",
     "docs_url":     "https://www.twilio.com/docs"},
    {"provider": "whatsapp_whapi",
     "env_var":  "WHAPI_API_KEY",
     "group":    "comms",
     "role":     "WhatsApp outreach blasts",
     "recharge_url": "https://panel.whapi.cloud/",
     "docs_url":     "https://whapi.cloud/docs"},
    {"provider": "resend",
     "env_var":  "RESEND_API_KEY",
     "group":    "comms",
     "role":     "transactional + outreach email",
     "recharge_url": "https://resend.com/billing",
     "docs_url":     "https://resend.com/docs"},
    {"provider": "sendgrid",
     "env_var":  "SENDGRID_API_KEY",
     "group":    "comms",
     "role":     "backup email provider",
     "recharge_url": "https://app.sendgrid.com/settings/billing",
     "docs_url":     "https://docs.sendgrid.com/"},
    {"provider": "linkedin",
     "env_var":  "LINKEDIN_API_KEY",
     "group":    "comms",
     "role":     "LinkedIn outreach + profile scrape",
     "recharge_url": "https://www.linkedin.com/developers/apps",
     "docs_url":     "https://learn.microsoft.com/en-us/linkedin/"},
    {"provider": "telegram",
     "env_var":  "TELEGRAM_BOT_TOKEN",
     "group":    "comms",
     "role":     "founder alerts · silent-failure notifications",
     "recharge_url": "https://t.me/BotFather",
     "docs_url":     "https://core.telegram.org/bots/api"},
    # ── Payments ──────────────────────────────────────────────────────
    {"provider": "stripe",
     "env_var":  "STRIPE_SECRET_KEY",
     "group":    "payment",
     "role":     "subscriptions · token-pack checkout · invoices",
     "recharge_url": "https://dashboard.stripe.com/test/apikeys",
     "docs_url":     "https://stripe.com/docs/api"},
    # ── Data / search ─────────────────────────────────────────────────
    {"provider": "tavily",
     "env_var":  "TAVILY_API_KEY",
     "group":    "data",
     "role":     "live web search inside chat",
     "recharge_url": "https://app.tavily.com/home",
     "docs_url":     "https://docs.tavily.com/"},
    {"provider": "scrapingbee",
     "env_var":  "SCRAPINGBEE_API_KEY",
     "group":    "data",
     "role":     "scout · competitor scrape · lead enrichment",
     "recharge_url": "https://app.scrapingbee.com/dashboard/billing",
     "docs_url":     "https://www.scrapingbee.com/documentation/"},
    # ── Infra ────────────────────────────────────────────────────────
    {"provider": "hetzner",
     "env_var":  "HETZNER_API_TOKEN",
     "group":    "infra",
     "role":     "real SSH deploy to customer servers",
     "recharge_url": "https://console.hetzner.cloud/projects",
     "docs_url":     "https://docs.hetzner.cloud/"},
    {"provider": "github_bot",
     "env_var":  "AUREM_CTO_BOT_GITHUB_PAT",
     "group":    "infra",
     "role":     "auto-create repos + branch protection",
     "recharge_url": "https://github.com/settings/tokens",
     "docs_url":     "https://docs.github.com/en/rest"},
    {"provider": "cloudflare",
     "env_var":  "CLOUDFLARE_API_TOKEN",
     "group":    "infra",
     "role":     "DNS + Caddy + customer-site routing",
     "recharge_url": "https://dash.cloudflare.com/profile/api-tokens",
     "docs_url":     "https://developers.cloudflare.com/"},
]


def _redacted_tail(value: str) -> str:
    """Returns the last 4 chars (or `····` when missing)."""
    if not value:
        return "····"
    s = str(value)
    return f"…{s[-4:]}" if len(s) >= 4 else "…" + s


def _pill_for(env_present: bool,
              unauthorized_24h: int,
              total_fail_7d: int) -> str:
    """Return one of: unset · red · yellow · green."""
    if not env_present:
        return "unset"
    if unauthorized_24h > 0:
        return "red"
    if total_fail_7d > 5:
        return "yellow"
    return "green"


async def _require_admin(authorization: str | None) -> dict[str, Any]:
    """Tiny inline admin guard. Mirrors the one used elsewhere — refuses
    anything without an admin or super_admin claim."""
    if not authorization:
        raise HTTPException(401, "missing_token")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "bad_scheme")
    token = authorization[7:]
    try:
        import jwt
        payload = jwt.decode(
            token,
            os.environ["JWT_SECRET"],
            algorithms=[os.environ.get("JWT_ALGORITHM", "HS256")],
        )
    except Exception as e:
        raise HTTPException(401, f"invalid_token: {type(e).__name__}")
    if not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(403, "admin_only")
    return payload


@router.get("/api/admin/integrations/health")
async def integrations_health(authorization: str | None = Header(None)) -> dict[str, Any]:
    """Returns the live status of every integration AUREM relies on.

    NEVER returns the actual key value — only the last 4 characters
    so the founder can confirm which key is loaded.
    """
    await _require_admin(authorization)

    out: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d  = now - timedelta(days=7)

    # Pre-pull all failures once so we don't hit the DB N times.
    by_provider_24h: dict[str, dict[str, int]] = {}
    by_provider_7d:  dict[str, dict[str, int]] = {}
    last_failure_by_provider: dict[str, datetime] = {}

    if _db is not None:
        try:
            cur = _db.api_key_health_log.find(
                {"ts": {"$gte": cutoff_7d}},
                {"_id": 0, "provider": 1, "bucket": 1, "ts": 1},
            ).limit(5000)
            async for r in cur:
                p = (r.get("provider") or "unknown").lower()
                b = (r.get("bucket")   or "other").lower()
                ts = r.get("ts")
                # Motor returns BSON datetimes as offset-naive; force to UTC
                # so comparisons against `cutoff_24h` (tz-aware) work.
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                by_provider_7d.setdefault(p, {}).setdefault(b, 0)
                by_provider_7d[p][b] += 1
                if ts and ts >= cutoff_24h:
                    by_provider_24h.setdefault(p, {}).setdefault(b, 0)
                    by_provider_24h[p][b] += 1
                if ts:
                    prev = last_failure_by_provider.get(p)
                    if not prev or ts > prev:
                        last_failure_by_provider[p] = ts
        except Exception as e:
            logger.warning(f"[admin-integrations] failure-log read failed: {e}")

    for it in INTEGRATIONS:
        key_val = os.environ.get(it["env_var"], "") or ""
        present = bool(key_val.strip())
        p = it["provider"]
        f24 = by_provider_24h.get(p, {})
        f7d = by_provider_7d.get(p,  {})
        total_24 = sum(f24.values())
        total_7d = sum(f7d.values())
        unauthorized_24h = f24.get("unauthorized", 0) + f24.get("forbidden", 0)
        pill = _pill_for(present, unauthorized_24h, total_7d)
        last_fail = last_failure_by_provider.get(p)

        out.append({
            "provider":         it["provider"],
            "group":            it["group"],
            "role":             it["role"],
            "env_var":          it["env_var"],
            "key_present":      present,
            "key_tail":         _redacted_tail(key_val),
            "status":           pill,
            "needs_recharge":   pill in ("red", "unset"),
            "failures_24h":     total_24,
            "failures_7d":      total_7d,
            "failures_24h_by_bucket": f24,
            "failures_7d_by_bucket":  f7d,
            "last_failure_at":  last_fail.isoformat() if last_fail else None,
            "recharge_url":     it["recharge_url"],
            "docs_url":         it["docs_url"],
        })

    return {
        "ok":           True,
        "as_of":        now.isoformat(),
        "window_days":  7,
        "summary":      {
            "total":          len(out),
            "green":          sum(1 for x in out if x["status"] == "green"),
            "yellow":         sum(1 for x in out if x["status"] == "yellow"),
            "red":            sum(1 for x in out if x["status"] == "red"),
            "unset":          sum(1 for x in out if x["status"] == "unset"),
            "needs_recharge": sum(1 for x in out if x["needs_recharge"]),
        },
        "integrations": out,
    }
