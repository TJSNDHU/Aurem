"""
AUREM Lead Sort & Validation — Section 4 of growth-engine upgrade
==================================================================
Runs AFTER scout_enrichment (Section 3) and BEFORE Blast (Section 7).

Per spec:
  EMAIL    → syntax + MX record check; fail = email_invalid flag
  PHONE    → normalize E.164 → Twilio Lookup; landline = email only
  WEBSITE  → HTTP 200 + >500 chars content; fail = no_website queue
  FACEBOOK → no website but FB URL found → `scout_queue_facebook`
             (hold, no blast yet)

Queues:
  has_website / no_website / facebook / rejected

Sort:
  by `score` DESC within each queue.

Output is a dict { has_website: [...], no_website: [...], facebook: [...],
                   rejected: [{lead, reasons:[...]}] }

Side-effects (when db is provided):
  • Each lead's queue is persisted on the lead doc as `sort_queue`
    + `sort_validation` (full audit trail) + `sort_at` timestamp.
  • `scout_queue_facebook` collection receives Facebook-only leads.

The validators are SAFE on missing data — every check fails-closed
to "rejected" only when a contact channel is required but absent.
"""
from __future__ import annotations

import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
FB_HOSTS = {"facebook.com", "www.facebook.com", "fb.com", "m.facebook.com"}

# Tunables — env-overridable for staging
WEBSITE_TIMEOUT_S = float(__import__("os").environ.get("SORT_WEBSITE_TIMEOUT_S", "6"))
WEBSITE_MIN_CHARS = int(__import__("os").environ.get("SORT_WEBSITE_MIN_CHARS", "500"))
TWILIO_LOOKUP_ENABLED = __import__("os").environ.get(
    "SORT_TWILIO_LOOKUP", "true"
).lower() == "true"
MX_LOOKUP_ENABLED = __import__("os").environ.get(
    "SORT_MX_LOOKUP", "true"
).lower() == "true"

# Cap concurrent network checks per sort batch to keep the event loop
# responsive (each sort op uses 3 net calls × 50 leads = 150 sockets).
SORT_CONCURRENCY = int(__import__("os").environ.get("SORT_CONCURRENCY", "12"))


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def sort_leads(
    leads: List[Dict[str, Any]],
    db=None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Validate + queue every lead. Returns 4 queues sorted by score DESC.

    Mutates each lead in place with:
        sort_queue       ∈ {"has_website","no_website","facebook","rejected"}
        sort_validation  = {email, phone, website}  (full audit dict)
        sort_at          = ISO timestamp
    """
    if not leads:
        return {"has_website": [], "no_website": [], "facebook": [], "rejected": []}

    sem = asyncio.Semaphore(SORT_CONCURRENCY)

    async def _validate_one(lead):
        async with sem:
            return await _validate_lead(lead)

    results = await asyncio.gather(*[_validate_one(L) for L in leads])

    queues: Dict[str, List[Dict[str, Any]]] = {
        "has_website": [],
        "no_website": [],
        "facebook": [],
        "rejected": [],
    }
    now_iso = datetime.now(timezone.utc).isoformat()
    for lead, validation in zip(leads, results):
        queue, reasons = _classify_queue(lead, validation)
        lead["sort_queue"] = queue
        lead["sort_validation"] = validation
        lead["sort_at"] = now_iso
        if queue == "rejected":
            lead.setdefault("sort_reject_reasons", []).extend(reasons)
        queues[queue].append(lead)

    # Sort by score DESC within each queue (industry priority is upstream).
    for q in queues:
        queues[q].sort(key=lambda x: -(x.get("score") or 0))

    if db is not None:
        await _persist_sort(db, leads, queues)

    logger.info(
        "[sort] queued: has_website=%d no_website=%d facebook=%d rejected=%d",
        len(queues["has_website"]), len(queues["no_website"]),
        len(queues["facebook"]), len(queues["rejected"]),
    )
    return queues


# ─────────────────────────────────────────────────────────────────────
# Per-lead validation
# ─────────────────────────────────────────────────────────────────────

async def _validate_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Run all 3 validators in parallel and return a structured audit."""
    email_task = _validate_email(lead.get("email"))
    phone_task = _validate_phone(lead.get("phone"))
    website_task = _validate_website(lead)
    email, phone, website = await asyncio.gather(
        email_task, phone_task, website_task, return_exceptions=False
    )
    return {"email": email, "phone": phone, "website": website}


async def _validate_email(raw: Optional[str]) -> Dict[str, Any]:
    out = {"present": False, "syntax_ok": False, "mx_ok": False,
           "value": "", "reason": ""}
    if not raw:
        out["reason"] = "missing"
        return out
    val = str(raw).strip().lower()
    out["present"] = True
    out["value"] = val
    if not EMAIL_RE.match(val):
        out["reason"] = "syntax_invalid"
        return out
    out["syntax_ok"] = True
    # Read env at call-time so tests can flip it without re-import.
    mx_enabled = __import__("os").environ.get("SORT_MX_LOOKUP", "true").lower() == "true"
    if not mx_enabled:
        out["mx_ok"] = True  # trust syntax only
        return out
    domain = val.split("@", 1)[1]
    try:
        out["mx_ok"] = await _has_mx_record(domain)
        if not out["mx_ok"]:
            out["reason"] = "mx_missing"
    except Exception as e:
        # Network errors → optimistic pass (don't punish DNS hiccups)
        out["mx_ok"] = True
        out["reason"] = f"mx_check_skipped: {e}"
    return out


async def _has_mx_record(domain: str) -> bool:
    """DNS MX lookup with hard timeout — uses dnspython if available."""
    try:
        import dns.resolver  # type: ignore
        loop = asyncio.get_running_loop()
        def _q():
            try:
                resp = dns.resolver.resolve(domain, "MX", lifetime=2.5)
                return len(list(resp)) > 0
            except Exception:
                return False
        return await asyncio.wait_for(loop.run_in_executor(None, _q), timeout=3.0)
    except ImportError:
        # Fallback: socket gethostbyname proxy — not as accurate, but better than nothing
        try:
            import socket
            loop = asyncio.get_running_loop()
            def _g():
                try:
                    socket.gethostbyname(domain)
                    return True
                except Exception:
                    return False
            return await asyncio.wait_for(loop.run_in_executor(None, _g), timeout=2.0)
        except Exception:
            return False
    except Exception:
        return False


async def _validate_phone(raw: Optional[str]) -> Dict[str, Any]:
    out = {"present": False, "e164": "", "valid": False, "type": None,
           "is_landline": False, "reason": ""}
    if not raw:
        out["reason"] = "missing"
        return out
    out["present"] = True
    e164 = _to_e164(raw)
    out["e164"] = e164
    if not e164:
        out["reason"] = "format_invalid"
        return out
    # Read env at call-time so tests can flip it without re-import.
    twilio_enabled = __import__("os").environ.get("SORT_TWILIO_LOOKUP", "true").lower() == "true"
    if not twilio_enabled:
        out["valid"] = True
        return out
    try:
        from shared.providers.twilio import validate_phone_number
        # Twilio Lookup uses sync SDK — push to executor with hard timeout.
        loop = asyncio.get_running_loop()
        def _do_lookup():
            try:
                return loop.run_until_complete(validate_phone_number(e164))  # noqa
            except Exception:
                pass
        # `validate_phone_number` itself is async — call via wait_for.
        result = await asyncio.wait_for(validate_phone_number(e164), timeout=4.0)
        if not result:
            out["reason"] = "lookup_empty"
            return out
        out["valid"] = bool(result.get("valid"))
        ptype = (result.get("phone_type") or "").lower()
        out["type"] = ptype or None
        out["is_landline"] = ptype in ("landline", "voip")
        if not out["valid"]:
            out["reason"] = result.get("reason") or "lookup_invalid"
    except asyncio.TimeoutError:
        # Lookup down/slow → trust E.164 syntax, allow blast
        out["valid"] = True
        out["reason"] = "lookup_timeout"
    except Exception as e:
        out["valid"] = True
        out["reason"] = f"lookup_skipped: {e}"
    return out


def _to_e164(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if str(raw).strip().startswith("+"):
        return f"+{digits}"
    return ""


async def _validate_website(lead: Dict[str, Any]) -> Dict[str, Any]:
    out = {"present": False, "url": "", "is_facebook": False,
           "status": None, "content_len": 0, "ok": False, "reason": ""}
    url = (lead.get("website") or lead.get("website_url") or "").strip()
    if not url:
        out["reason"] = "missing"
        return out
    out["present"] = True
    out["url"] = url
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or "").lower()
    if any(host.endswith(h) or host == h for h in FB_HOSTS):
        out["is_facebook"] = True
        out["reason"] = "facebook_only"
        return out
    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=WEBSITE_TIMEOUT_S, follow_redirects=True,
            headers={"User-Agent": "AUREM-LeadSort/1.0"},
        ) as client:
            r = await client.get(parsed.geturl())
            out["status"] = r.status_code
            if r.status_code == 200:
                out["content_len"] = len(r.text or "")
                out["ok"] = out["content_len"] >= WEBSITE_MIN_CHARS
                if not out["ok"]:
                    out["reason"] = f"thin_content_{out['content_len']}b"
            else:
                out["reason"] = f"http_{r.status_code}"
    except Exception as e:
        out["reason"] = f"fetch_failed: {type(e).__name__}"
    return out


# ─────────────────────────────────────────────────────────────────────
# Queue classification
# ─────────────────────────────────────────────────────────────────────

def _classify_queue(
    lead: Dict[str, Any], v: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """Apply the spec's queue rules. Returns (queue, reject_reasons)."""
    reasons: List[str] = []
    email_v = v.get("email", {})
    phone_v = v.get("phone", {})
    web_v = v.get("website", {})

    has_email = email_v.get("syntax_ok") and email_v.get("mx_ok")
    has_phone = phone_v.get("valid") and phone_v.get("e164")
    is_landline = phone_v.get("is_landline", False)
    web_ok = web_v.get("ok", False)
    web_is_fb = web_v.get("is_facebook", False)
    web_present = web_v.get("present", False)

    # iter 322p — flag for downstream Blast: landline = email-only channel
    lead["sort_email_only"] = bool(is_landline and not phone_v.get("type") in (None, "mobile"))

    # 1. Facebook-only (no real website) → hold queue
    if not web_ok and web_is_fb:
        if not (has_email or has_phone):
            return "rejected", ["fb_only_no_other_contact"]
        return "facebook", []

    # 2. Has working website → has_website queue
    if web_ok:
        if not (has_email or has_phone):
            return "rejected", ["no_contact_channel"]
        return "has_website", []

    # 3. No usable website & no FB → no_website queue
    if not web_present or web_v.get("reason", "").startswith(("http_", "thin_content_", "fetch_failed")):
        if has_phone or has_email:
            return "no_website", []
        return "rejected", ["no_contact_channel"]

    # 4. Catch-all rejected
    if not has_phone and not has_email:
        reasons.append("no_contact_channel")
    if email_v.get("present") and not has_email:
        reasons.append("email_invalid")
    if phone_v.get("present") and not has_phone:
        reasons.append("phone_invalid")
    return "rejected", reasons or ["unknown"]


# ─────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────

async def _persist_sort(db, leads: List[Dict[str, Any]],
                        queues: Dict[str, List[Dict[str, Any]]]) -> None:
    """Write each lead's queue assignment back to campaign_leads.

    Identifies leads by `lead_id` if present, else by `phone_e164`,
    else by `dedup_name_postal`. Skips silently when no key is set
    (Scout output may be pre-persistence).
    """
    now = datetime.now(timezone.utc)
    for L in leads:
        key: Dict[str, Any] = {}
        if L.get("lead_id"):
            key = {"lead_id": L["lead_id"]}
        elif L.get("phone_e164"):
            key = {"phone_e164": L["phone_e164"]}
        elif L.get("dedup_name_postal"):
            key = {"dedup_name_postal": L["dedup_name_postal"]}
        if not key:
            continue
        update = {
            "sort_queue": L.get("sort_queue"),
            "sort_validation": L.get("sort_validation"),
            "sort_at": now,
            "score": L.get("score"),
            "industry": L.get("industry"),
            "industry_priority": L.get("industry_priority"),
        }
        try:
            await db.campaign_leads.update_one(
                {**key, "business_id": FOUNDER_BIN},
                {"$set": update}, upsert=False)
        except Exception as e:
            logger.debug(f"[sort] persist skipped for {key}: {e}")

    # Mirror Facebook holds into a dedicated "wait queue" collection
    if queues.get("facebook"):
        try:
            ops = []
            for L in queues["facebook"]:
                doc = {
                    "lead_id": L.get("lead_id") or L.get("phone_e164") or L.get("dedup_name_postal"),
                    "name": L.get("name") or L.get("business_name"),
                    "phone": L.get("phone"),
                    "fb_url": (L.get("website") or L.get("website_url") or ""),
                    "score": L.get("score"),
                    "industry": L.get("industry"),
                    "queued_at": now,
                    "released": False,
                }
                if doc["lead_id"]:
                    ops.append((doc["lead_id"], doc))
            for lead_id, doc in ops:
                await db.scout_queue_facebook.update_one(
                    {"lead_id": lead_id}, {"$setOnInsert": doc}, upsert=True,
                )
        except Exception as e:
            logger.debug(f"[sort] facebook persist skipped: {e}")


async def ensure_indexes(db) -> None:
    if db is None:
        return
    try:
        await db.campaign_leads.create_index("sort_queue")
        await db.scout_queue_facebook.create_index("lead_id", unique=True, sparse=True)
        await db.scout_queue_facebook.create_index("released")
    except Exception as e:
        logger.debug(f"[sort] index ensure skipped: {e}")
