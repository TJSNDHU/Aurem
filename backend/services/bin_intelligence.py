"""
BIN Intelligence Service — unified contact intelligence per BIN.

Single source of truth for hashed contact records aggregated across:
  • Pixel form fills (db.pixel_events)
  • Gmail metadata (db.bin_intelligence.email_data)        — DEFERRED
  • Mobile contacts/call-log scores (mobile_data)         — STUB ingestion
  • Invoice imports (invoice_data)                        — LIVE

Storage:
  db.bin_intelligence keyed by (bin_id, contact_hash).
  RAW contact info is NEVER stored — only sha256 hashes + numeric scores.

Merge logic (run every 15 min via background task):
  For each BIN:
    For each contact_hash that appears in 2+ sources:
      → write to db.bin_unified_profiles with intent_level + action.

PRIVACY RULES (NON-NEGOTIABLE):
  ❌ No raw emails, phones, names anywhere.
  ❌ No email or SMS content.
  ✅ Only hashes, scores, patterns, counts.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Hashing — SHA256, normalised so the same email/phone collides reliably.
# ═══════════════════════════════════════════════════════════════════════
def _digits_only(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def normalise_email(email: str) -> str:
    """Lowercase + strip + drop dots in gmail local part.

    NOT stored — used only as input to sha256.
    """
    e = (email or "").strip().lower()
    if "@" not in e:
        return e
    local, dom = e.split("@", 1)
    if dom in ("gmail.com", "googlemail.com"):
        local = local.split("+")[0].replace(".", "")
        dom = "gmail.com"
    return f"{local}@{dom}"


def normalise_phone(phone: str) -> str:
    """Keep digits only, pad to E.164-like.

    NOT stored — used only as input to sha256.
    """
    d = _digits_only(phone)
    # If it looks like a NANP number without country code, prefix 1.
    if len(d) == 10:
        d = "1" + d
    return d


def hash_email(email: str) -> str:
    if not email:
        return ""
    return hashlib.sha256(normalise_email(email).encode("utf-8")).hexdigest()


def hash_phone(phone: str) -> str:
    if not phone:
        return ""
    n = normalise_phone(phone)
    return hashlib.sha256(n.encode("utf-8")).hexdigest() if n else ""


def hash_contact(email: str = "", phone: str = "") -> str:
    """Primary contact hash — prefers email (more stable) over phone.

    Falls back to phone if no email. Empty string if both absent.
    """
    if email:
        return hash_email(email)
    if phone:
        return hash_phone(phone)
    return ""


# ═══════════════════════════════════════════════════════════════════════
# CASL / PIPEDA — log a consent record per import batch.
# ═══════════════════════════════════════════════════════════════════════
async def log_casl_consent(
    db,
    *,
    business_id: str,
    basis: str,
    source: str,
    record_count: int,
    ip: Optional[str] = None,
    user_email: Optional[str] = None,
) -> str:
    """Insert a CASL/PIPEDA consent record. Returns the consent_id."""
    consent_id = hashlib.sha256(
        f"{business_id}:{source}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:24]
    try:
        await db.casl_consent_log.insert_one({
            "consent_id": consent_id,
            "business_id": business_id,
            "basis": basis,
            "source": source,
            "record_count": int(record_count),
            "user_email_hash": hash_email(user_email) if user_email else None,
            "ip": (ip or "")[:64],
            "ts": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning(f"[CASL] log failed: {e}")
    return consent_id


# ═══════════════════════════════════════════════════════════════════════
# upsert_contact — single entry-point. Idempotent per (bin, hash, source).
# ═══════════════════════════════════════════════════════════════════════
async def upsert_contact(
    db,
    *,
    business_id: str,
    contact_hash: str,
    source: str,                                # "pixel" | "email" | "phone" | "invoice" | "mobile"
    business_score: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Upsert a per-source row in db.bin_intelligence.

    Schema:
      {
        bin_id, contact_hash, source,
        business_score, last_seen, first_seen,
        metadata: { ...source-specific... }
      }
    """
    if not (business_id and contact_hash and source):
        return
    now = datetime.now(timezone.utc)
    metadata = metadata or {}
    # Strip any PII keys that might have leaked in metadata.
    for k in list(metadata.keys()):
        if k.lower() in ("email", "phone", "name", "first_name", "last_name", "address"):
            metadata.pop(k, None)

    try:
        await db.bin_intelligence.update_one(
            {"bin_id": business_id, "contact_hash": contact_hash, "source": source},
            {
                "$set": {
                    "bin_id": business_id,
                    "contact_hash": contact_hash,
                    "source": source,
                    "business_score": int(max(0, min(100, business_score))),
                    "metadata": metadata,
                    "last_seen": now,
                },
                "$setOnInsert": {"first_seen": now},
                "$inc": {"frequency": 1},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[bin_intelligence] upsert failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Bucketing — Verified / Likely / Unclear.
# ═══════════════════════════════════════════════════════════════════════
def bucket_for(score: int, source: str) -> str:
    """Auto-bucket: 'verified' | 'likely' | 'unclear'."""
    if source == "invoice" or score >= 70:
        return "verified"
    if score >= 40:
        return "likely"
    return "unclear"


# ═══════════════════════════════════════════════════════════════════════
# Merge — combine multi-source rows into unified profiles.
# ═══════════════════════════════════════════════════════════════════════
SOURCE_WEIGHT = {"invoice": 1.5, "email": 1.0, "phone": 1.0, "pixel": 0.8, "mobile": 1.0}
INTENT_FOR = {4: "VERY_HIGH", 3: "HIGH", 2: "MEDIUM", 1: "LOW"}
ACTION_FOR = {
    "VERY_HIGH": "Call today",
    "HIGH": "Send offer now",
    "MEDIUM": "Add to campaign",
    "LOW": "Monitor",
}


async def merge_bin(db, business_id: str) -> Dict[str, int]:
    """Build/refresh `db.bin_unified_profiles` for one BIN.

    For every contact_hash that appears in 2+ sources, write a unified
    row with averaged-weighted business_score, sources[], intent_level,
    recommended_action.
    """
    if not business_id:
        return {"profiles_written": 0}
    pipeline = [
        {"$match": {"bin_id": business_id}},
        {"$group": {
            "_id": "$contact_hash",
            "sources": {"$addToSet": "$source"},
            "scores": {"$push": "$business_score"},
            "last_seen": {"$max": "$last_seen"},
        }},
    ]
    written = 0
    skipped_single_source = 0
    now = datetime.now(timezone.utc)
    try:
        async for row in db.bin_intelligence.aggregate(pipeline):
            ch = row.get("_id") or ""
            sources = [s for s in (row.get("sources") or []) if s]
            if not ch:
                continue
            if len(sources) < 2:
                skipped_single_source += 1
                continue
            scores = [int(s or 0) for s in (row.get("scores") or [])]
            if scores:
                w_sum = 0.0
                w_total = 0.0
                for src, sc in zip(sources, scores[:len(sources)]):
                    w = SOURCE_WEIGHT.get(src, 1.0)
                    w_sum += sc * w
                    w_total += w
                avg = int(round(w_sum / w_total)) if w_total else 0
            else:
                avg = 0
            n = len(sources)
            intent = INTENT_FOR.get(min(4, n), "LOW")
            await db.bin_unified_profiles.update_one(
                {"bin_id": business_id, "contact_hash": ch},
                {"$set": {
                    "bin_id": business_id,
                    "contact_hash": ch,
                    "sources": sorted(sources),
                    "business_score": avg,
                    "intent_level": intent,
                    "recommended_action": ACTION_FOR[intent],
                    "last_seen": row.get("last_seen") or now,
                    "updated_at": now,
                }},
                upsert=True,
            )
            written += 1
    except Exception as e:
        logger.warning(f"[bin_intelligence] merge failed for {business_id}: {e}")

    return {"profiles_written": written, "single_source_skipped": skipped_single_source}


async def merge_all(db) -> Dict[str, Any]:
    """Iterate every BIN that has intelligence rows and merge it."""
    if db is None:
        return {"ok": False, "reason": "no db"}
    bins = await db.bin_intelligence.distinct("bin_id")
    out: Dict[str, Any] = {}
    for b in bins:
        out[b] = await merge_bin(db, b)
    return {"ok": True, "bins": len(bins), "results": out}


# ═══════════════════════════════════════════════════════════════════════
# 15-min cron loop. Started by server.py.
# ═══════════════════════════════════════════════════════════════════════
INTERVAL_S = 900  # 15 minutes


async def merge_loop(db) -> None:
    """Background task — runs merge_all every INTERVAL_S seconds."""
    logger.info(f"[bin_intelligence] merge_loop started (every {INTERVAL_S}s)")
    await asyncio.sleep(60)  # initial settle
    while True:
        try:
            res = await merge_all(db)
            logger.debug(f"[bin_intelligence] merge cycle: {res}")
        except Exception as e:
            logger.warning(f"[bin_intelligence] merge cycle error: {e}")
        await asyncio.sleep(INTERVAL_S)


# ═══════════════════════════════════════════════════════════════════════
# CSV invoice import — Part 4.
# ═══════════════════════════════════════════════════════════════════════
COLUMN_MAP = {
    "name": ("name", "customer", "client", "contact"),
    "phone": ("phone", "mobile", "cell", "tel"),
    "email": ("email", "e-mail"),
    "amount": ("amount", "total", "price", "invoice total", "subtotal", "$"),
    "date": ("date", "invoice date", "billed", "billed on"),
    "service": ("service", "description", "item", "product"),
}


def detect_column(header: str) -> Optional[str]:
    """Map a CSV header cell to a canonical field, or None."""
    h = (header or "").strip().lower()
    for canon, aliases in COLUMN_MAP.items():
        for a in aliases:
            if a == h or a in h.split():
                return canon
    return None


async def import_invoice_rows(
    db,
    *,
    business_id: str,
    rows: Iterable[Dict[str, Any]],
    consent_id: str,
) -> Dict[str, Any]:
    """Process pre-parsed invoice rows: hash + write to bin_intelligence.

    Each row should look like:
      {name?, phone?, email?, amount?, date?, service?}
    """
    accepted = 0
    skipped_no_contact = 0
    for r in rows:
        email = (r.get("email") or "").strip()
        phone = (r.get("phone") or "").strip()
        if not email and not phone:
            skipped_no_contact += 1
            continue
        ch = hash_contact(email=email, phone=phone)
        service_history = {
            "service": (r.get("service") or "")[:60],
            "amount": _safe_float(r.get("amount")),
            "date": (r.get("date") or "")[:32],
        }
        await upsert_contact(
            db,
            business_id=business_id,
            contact_hash=ch,
            source="invoice",
            business_score=100,
            metadata={
                "has_email": bool(email),
                "has_phone": bool(phone),
                "service_history": [service_history] if service_history["service"] else [],
                "casl_basis": "existing_relationship",
                "consent_id": consent_id,
            },
        )
        accepted += 1
    return {
        "accepted": accepted,
        "skipped_no_contact": skipped_no_contact,
        "bucket": "verified",
    }


def _safe_float(v: Any) -> float:
    try:
        if v in (None, ""):
            return 0.0
        s = str(v).replace("$", "").replace(",", "").strip()
        return float(s)
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════════
# Pixel event — Part 1.
# ═══════════════════════════════════════════════════════════════════════
async def record_pixel_event(
    db,
    *,
    business_id: str,
    visitor_hash: str,
    page: str = "",
    time_spent: int = 0,
    referrer: str = "",
    device: str = "desktop",
    form_filled: bool = False,
    form_email: str = "",
    form_phone: str = "",
) -> Dict[str, Any]:
    """Write to db.pixel_events; if form_filled, also upsert into
    db.bin_intelligence under source='pixel'.

    Raw email/phone are immediately hashed — only hashes hit the DB.
    """
    now = datetime.now(timezone.utc)
    form_data_hash = ""
    contact_hash = ""
    if form_filled and (form_email or form_phone):
        contact_hash = hash_contact(email=form_email, phone=form_phone)
        form_data_hash = contact_hash  # alias

    event = {
        "bin_id": business_id,
        "visitor_hash": (visitor_hash or "")[:64],
        "page": (page or "")[:300],
        "time_spent": int(max(0, time_spent)),
        "source": (referrer or "")[:200],
        "device": "mobile" if device == "mobile" else "desktop",
        "form_filled": bool(form_filled),
        "form_data_hash": form_data_hash,
        "timestamp": now,
    }
    try:
        await db.pixel_events.insert_one(event)
    except Exception as e:
        logger.warning(f"[pixel] event insert failed: {e}")

    # Score for the pixel source — page-time gives signal.
    pixel_score = 30
    if form_filled:
        pixel_score = 70
    if time_spent and time_spent >= 90:
        pixel_score = min(100, pixel_score + 10)

    if contact_hash:
        await upsert_contact(
            db,
            business_id=business_id,
            contact_hash=contact_hash,
            source="pixel",
            business_score=pixel_score,
            metadata={"form_filled": form_filled, "device": event["device"]},
        )
    return {
        "ok": True,
        "form_data_hash": form_data_hash,
        "matched": bool(contact_hash),
    }


# ═══════════════════════════════════════════════════════════════════════
# Mobile contact-score ingest — Part 3 (stub).
# ═══════════════════════════════════════════════════════════════════════
async def ingest_mobile_score(
    db,
    *,
    business_id: str,
    contact_hash: str,
    business_score: int,
    pattern: str = "",
    frequency_bucket: str = "med",
) -> None:
    """Single contact score from the device. NO names, NO phone numbers."""
    if not (business_id and contact_hash):
        return
    await upsert_contact(
        db,
        business_id=business_id,
        contact_hash=contact_hash,
        source="mobile",
        business_score=int(max(0, min(100, business_score))),
        metadata={
            "pattern": (pattern or "")[:32],
            "frequency_bucket": (frequency_bucket or "")[:8],
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# Intelligence summary — used by Morning Brief (Part 6).
# ═══════════════════════════════════════════════════════════════════════
async def intelligence_summary(db, business_id: str) -> Dict[str, Any]:
    """Snapshot rollup for a BIN — counts only, no names."""
    if not (db is not None and business_id):
        return {"pixel": {}, "email": {}, "phone": {}, "invoice": {}, "top_actions": []}

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    pixel_visitors = await db.pixel_events.count_documents(
        {"bin_id": business_id, "timestamp": {"$gte": today_start}}
    )
    pixel_forms = await db.pixel_events.count_documents(
        {"bin_id": business_id, "timestamp": {"$gte": today_start}, "form_filled": True}
    )
    pixel_matched = await db.bin_unified_profiles.count_documents(
        {"bin_id": business_id, "sources": "pixel"}
    )
    email_contacts = await db.bin_intelligence.count_documents(
        {"bin_id": business_id, "source": "email"}
    )
    phone_contacts = await db.bin_intelligence.count_documents(
        {"bin_id": business_id, "source": "mobile"}
    )
    invoice_contacts = await db.bin_intelligence.count_documents(
        {"bin_id": business_id, "source": "invoice"}
    )

    # Top 3 actions — highest intent unified profiles.
    top_cursor = db.bin_unified_profiles.find(
        {"bin_id": business_id},
        {"_id": 0, "contact_hash": 1, "intent_level": 1, "sources": 1,
         "recommended_action": 1, "business_score": 1},
    ).sort([("business_score", -1)]).limit(3)
    top_actions = []
    async for p in top_cursor:
        top_actions.append({
            "contact_hash": (p.get("contact_hash") or "")[:16],
            "intent_level": p.get("intent_level"),
            "sources_count": len(p.get("sources") or []),
            "recommended_action": p.get("recommended_action"),
            "score": p.get("business_score"),
        })

    return {
        "pixel": {
            "visitors_today": pixel_visitors,
            "forms_today": pixel_forms,
            "matched_contacts": pixel_matched,
        },
        "email": {"identified": email_contacts},
        "phone": {"verified": phone_contacts},
        "invoice": {"past_clients": invoice_contacts},
        "top_actions": top_actions,
    }


# ═══════════════════════════════════════════════════════════════════════
# Indexes — called from server.py startup.
# ═══════════════════════════════════════════════════════════════════════
async def ensure_indexes(db) -> None:
    if db is None:
        return
    try:
        await db.bin_intelligence.create_index(
            [("bin_id", 1), ("contact_hash", 1), ("source", 1)],
            unique=True, background=True,
        )
        await db.bin_intelligence.create_index(
            [("bin_id", 1), ("source", 1)], background=True
        )
        await db.bin_unified_profiles.create_index(
            [("bin_id", 1), ("contact_hash", 1)],
            unique=True, background=True,
        )
        await db.bin_unified_profiles.create_index(
            [("bin_id", 1), ("business_score", -1)], background=True
        )
        await db.pixel_events.create_index(
            [("bin_id", 1), ("timestamp", -1)], background=True
        )
        await db.casl_consent_log.create_index(
            [("business_id", 1), ("ts", -1)], background=True
        )
        logger.info("[bin_intelligence] indexes ensured")
    except Exception as e:
        logger.warning(f"[bin_intelligence] index ensure failed: {e}")
