"""
Customer DIY Edit Portal — service (iter 311)
==============================================
Magic-link login → edit token (4 h) → save changes to auto_built_sites
→ trigger AWB re-render → push to R2.

Public:
  await request_access(db, business_email, site_slug) -> dict
  await verify_token(db, token) -> dict | None
  await save_changes(db, token, changes) -> dict
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# 24 h request token, 4 h session token (after verify)
REQUEST_TOKEN_TTL_H = 24
SESSION_TTL_H = 4

ALLOWED_FIELDS = {
    "business_name", "tagline", "about", "services", "phone", "email",
    "address", "hours", "colors", "images", "social", "google_maps_address",
}
ALLOWED_COLOR_KEYS = {"primary", "background"}
ALLOWED_IMAGE_KEYS = {"hero_url", "logo_url"}
ALLOWED_SOCIAL_KEYS = {"instagram", "facebook", "tiktok", "youtube",
                        "linkedin", "twitter", "x"}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_changes(changes: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (changes or {}).items():
        if k not in ALLOWED_FIELDS:
            continue
        if k == "services" and isinstance(v, list):
            out[k] = [str(x)[:200] for x in v[:30]]
        elif k == "colors" and isinstance(v, dict):
            out[k] = {ck: str(cv)[:32] for ck, cv in v.items()
                       if ck in ALLOWED_COLOR_KEYS}
        elif k == "images" and isinstance(v, dict):
            out[k] = {ik: str(iv)[:1024] for ik, iv in v.items()
                       if ik in ALLOWED_IMAGE_KEYS}
        elif k == "social" and isinstance(v, dict):
            out[k] = {sk: str(sv)[:300] for sk, sv in v.items()
                       if sk in ALLOWED_SOCIAL_KEYS}
        elif isinstance(v, str):
            cap = 4000 if k == "about" else 400
            out[k] = v.strip()[:cap]
    return out


async def _find_site(db, slug_or_id: str) -> Optional[Dict[str, Any]]:
    """Match by site_id, slug, or live_url."""
    for q in (
        {"site_id": slug_or_id},
        {"slug": slug_or_id},
        {"live_url": {"$regex": re.escape(slug_or_id)}},
    ):
        row = await db.auto_built_sites.find_one(q, {"_id": 0})
        if row:
            return row
    return None


def _site_email(site: Dict[str, Any]) -> str:
    return ((site.get("custom_content") or {}).get("email")
            or site.get("contact_email")
            or site.get("business_email")
            or "")


async def request_access(db, business_email: str,
                           site_slug: str) -> Dict[str, Any]:
    site = await _find_site(db, site_slug)
    if not site:
        return {"ok": False, "error": "site_not_found"}
    on_file = (_site_email(site) or "").lower().strip()
    given = (business_email or "").lower().strip()
    # Soft match: customer can also request via lead's email
    if on_file and on_file != given:
        # Don't leak — pretend we sent
        logger.warning(f"[edit] email mismatch on {site.get('site_id')}")
        return {"ok": True, "sent": True, "masked": True}

    raw = secrets.token_urlsafe(28)
    rec = {
        "request_id": uuid.uuid4().hex[:12],
        "site_id": site["site_id"],
        "slug": site.get("slug"),
        "email_to": given or on_file,
        "token_hash": _hash(raw),
        "kind": "request",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc)
                        + timedelta(hours=REQUEST_TOKEN_TTL_H)).isoformat(),
        "consumed": False,
    }
    try:
        await db.edit_sessions.insert_one(dict(rec))
    except Exception as e:
        logger.warning(f"[edit] insert request failed: {e}")
        return {"ok": False, "error": "persist_failed"}

    # Send magic link via Resend
    base = os.environ.get("AUREM_PUBLIC_URL", "https://aurem.live").rstrip("/")
    link = f"{base}/edit?token={raw}&site={site.get('slug') or site['site_id']}"
    sent = await _send_magic_link(rec["email_to"],
                                    site.get("business_name") or "your site",
                                    link)
    return {"ok": True, "sent": bool(sent),
            "request_id": rec["request_id"]}


async def _send_magic_link(to: str, biz: str, link: str) -> bool:
    if not to:
        return False
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "ORA <ora@aurem.live>")
    if not api_key:
        logger.warning("[edit] RESEND_API_KEY not set — skipping email")
        return False
    html = (
        f"<div style='font-family:Georgia,serif;max-width:520px'>"
        f"<h2 style='color:#8a6d1c'>Edit your AUREM site</h2>"
        f"<p>Click below to start editing <strong>{biz}</strong>. "
        f"This link is valid for {REQUEST_TOKEN_TTL_H} hours.</p>"
        f"<p style='margin:24px 0'>"
        f"<a href='{link}' style='background:#C9A227;color:#0A0A0A;"
        f"padding:12px 22px;border-radius:6px;font-weight:700;"
        f"text-decoration:none'>Open Edit Portal</a></p>"
        f"<p style='font-size:11px;color:#888'>Didn't request this? "
        f"Ignore this email.</p>"
        f"</div>"
    )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"authorization": f"Bearer {api_key}",
                          "content-type": "application/json"},
                json={"from": from_addr, "to": [to],
                       "subject": f"Edit your {biz} site",
                       "html": html},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[edit] email send failed: {e}")
        return False


async def verify_token(db, token: str) -> Optional[Dict[str, Any]]:
    """Consume a request token → return short-lived session.

    Idempotent: if the same request token is verified again within the
    session lifetime, return the previously-minted session token (handles
    React StrictMode double-mounts and refresh on /edit?token=...).
    """
    if not token:
        return None
    h = _hash(token)
    rec = await db.edit_sessions.find_one(
        {"token_hash": h, "kind": "request"}, {"_id": 0},
    )

    # Already-consumed request → return the session it minted, if still valid
    if rec and rec.get("consumed") and rec.get("minted_session_token"):
        sess_token = rec["minted_session_token"]
        sess = await db.edit_sessions.find_one(
            {"token_hash": _hash(sess_token), "kind": "session"}, {"_id": 0},
        )
        if sess and sess.get("expires_at", "") > datetime.now(timezone.utc).isoformat():
            # Stamp opened_at on the request row if missing (first-time open
            # via cached session — important for follow-up tracker).
            if not rec.get("opened_at"):
                try:
                    await db.edit_sessions.update_one(
                        {"request_id": rec["request_id"]},
                        {"$set": {"opened_at": datetime.now(timezone.utc).isoformat()}},
                    )
                except Exception:
                    pass
            site = await _find_site(db, sess["site_id"])
            return {"ok": True, "session_token": sess_token,
                    "site_id": sess["site_id"],
                    "expires_at": sess.get("expires_at"),
                    "site": _public_site(site)}
        return None

    # Plain session-token replay
    if not rec:
        sess = await db.edit_sessions.find_one(
            {"token_hash": h, "kind": "session"}, {"_id": 0},
        )
        if sess and sess.get("expires_at", "") > datetime.now(timezone.utc).isoformat():
            site = await _find_site(db, sess["site_id"])
            return {"ok": True, "session_token": token,
                    "site_id": sess["site_id"],
                    "expires_at": sess.get("expires_at"),
                    "site": _public_site(site)}
        return None

    if rec.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
        return None

    # First-time consume — mint a session and remember it on the request row
    new_token = secrets.token_urlsafe(28)
    sess_doc = {
        "session_id": uuid.uuid4().hex[:12],
        "site_id": rec["site_id"], "slug": rec.get("slug"),
        "token_hash": _hash(new_token),
        "kind": "session",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc)
                        + timedelta(hours=SESSION_TTL_H)).isoformat(),
    }
    try:
        await db.edit_sessions.insert_one(dict(sess_doc))
        await db.edit_sessions.update_one(
            {"request_id": rec["request_id"]},
            {"$set": {"consumed": True,
                       "consumed_at": datetime.now(timezone.utc).isoformat(),
                       "opened_at": datetime.now(timezone.utc).isoformat(),
                       "minted_session_token": new_token}},
        )
    except Exception as e:
        logger.warning(f"[edit] session mint failed: {e}")
        return None

    site = await _find_site(db, rec["site_id"])
    return {"ok": True, "session_token": new_token,
            "site_id": rec["site_id"],
            "expires_at": sess_doc["expires_at"],
            "site": _public_site(site)}


def _public_site(site: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not site:
        return {}
    return {
        "site_id": site.get("site_id"),
        "slug": site.get("slug"),
        "business_name": site.get("business_name"),
        "preview_url": site.get("preview_url"),
        "live_url": site.get("live_url"),
        "custom_content": site.get("custom_content") or {},
        "edit_count": site.get("edit_count", 0),
        "last_edited": site.get("last_edited"),
    }


async def _resolve_session(db, token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    rec = await db.edit_sessions.find_one(
        {"token_hash": _hash(token), "kind": "session"}, {"_id": 0},
    )
    if not rec:
        return None
    if rec.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
        return None
    return rec


async def save_changes(db, token: str,
                        changes: Dict[str, Any]) -> Dict[str, Any]:
    sess = await _resolve_session(db, token)
    if not sess:
        return {"ok": False, "error": "invalid_or_expired_session"}
    clean = _validate_changes(changes or {})
    if not clean:
        return {"ok": False, "error": "no_valid_fields"}

    now_iso = datetime.now(timezone.utc).isoformat()
    set_doc = {f"custom_content.{k}": v for k, v in clean.items()}
    set_doc.update({
        "last_edited": now_iso,
        "last_edited_token_hint": (token[:6] + "…"),
    })
    try:
        await db.auto_built_sites.update_one(
            {"site_id": sess["site_id"]},
            {"$set": set_doc, "$inc": {"edit_count": 1}},
        )
    except Exception as e:
        logger.warning(f"[edit] save failed: {e}")
        return {"ok": False, "error": "save_failed"}

    # Iter 315 — first edit counts as a "responded" campaign outcome
    try:
        site = await db.auto_built_sites.find_one(
            {"site_id": sess["site_id"]},
            {"_id": 0, "lead_id": 1, "edit_count": 1},
        )
        if site and site.get("lead_id") and (site.get("edit_count") or 0) <= 2:
            from services.attribution import attribute_lead_outcome
            await attribute_lead_outcome(
                db, site["lead_id"], "responded",
                source_hint="customer_edit",
            )
    except Exception as e:
        logger.debug(f"[edit] attribution failed: {e}")

    # Trigger re-render in background (R2 push)
    rerender = await _trigger_rerender(db, sess["site_id"])

    return {"ok": True, "site_id": sess["site_id"],
            "fields_updated": list(clean.keys()),
            "rerender": rerender, "ts": now_iso}


async def _trigger_rerender(db, site_id: str) -> Dict[str, Any]:
    """Re-render HTML with custom_content overlay + republish if R2 set up."""
    try:
        from services.auto_website_builder import _render_html  # type: ignore
    except Exception as e:
        return {"ok": False, "skipped": f"renderer_unavailable:{e}"}

    site = await db.auto_built_sites.find_one({"site_id": site_id}, {"_id": 0})
    if not site:
        return {"ok": False, "skipped": "site_missing"}

    # Merge: custom_content over claude_refined over gemini_draft
    base_copy = (site.get("claude_refined") or site.get("gemini_draft") or {})
    if isinstance(base_copy, str):
        base_copy = {}
    custom = site.get("custom_content") or {}
    merged = dict(base_copy)
    # Map custom_content fields onto copy-style keys
    if custom.get("tagline"):
        merged["sub_headline"] = custom["tagline"]
    if custom.get("about"):
        merged["about"] = custom["about"]
    if custom.get("services"):
        merged["services"] = [{"name": s} if isinstance(s, str) else s
                                for s in custom["services"]]

    lead = await db.campaign_leads.find_one(
        {"id": site.get("lead_id"), "business_id": FOUNDER_BIN}, {"_id": 0},
    ) or {}
    if custom.get("business_name"):
        lead["business_name"] = custom["business_name"]
    if custom.get("phone"):
        lead["phone"] = custom["phone"]
    if custom.get("email"):
        lead["email"] = custom["email"]

    style = site.get("style") or {}
    if (custom.get("colors") or {}).get("primary"):
        style["accent"] = custom["colors"]["primary"]
    if (custom.get("colors") or {}).get("background"):
        style["primary_bg"] = custom["colors"]["background"]

    try:
        html = _render_html(merged, lead, style=style)
        await db.auto_built_sites.update_one(
            {"site_id": site_id},
            {"$set": {"rendered_html": html,
                       "rerendered_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        return {"ok": False, "error": f"render_failed:{e}"}

    # Optional: push to R2 if helper exists
    pushed = False
    try:
        from services.auto_website_builder import publish_to_r2  # type: ignore
        out = await publish_to_r2(site_id=site_id, html=html,
                                    slug=site.get("slug"))
        pushed = bool(out and out.get("ok"))
    except Exception:
        pass
    return {"ok": True, "rerendered": True, "r2_pushed": pushed}
