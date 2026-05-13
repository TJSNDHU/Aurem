"""
csv_leads_upload_router.py — manual CSV/JSON bulk upload for real prospects.
═══════════════════════════════════════════════════════════════════════════
Founder pain: "campaign properly chalti rahe, paisa aata rahe" — but the
pool is starved (Ghost Scout offline, Google Places noise-filtered).

Quick fix: paste a CSV of real B2B prospects → goes straight into
`campaign_leads` with status='new' and `verification.channel_gating`
pre-seeded based on email/phone presence so auto_blast picks them up
on its NEXT 2-min cycle.

Usage (founder-only — admin token required):

    POST /api/admin/leads/upload-csv
    headers: Authorization: Bearer <admin_jwt>
    body (raw CSV):
        business_name,email,phone,city,country,website
        Acme Roofing,owner@acme.com,+14165550199,Toronto,ca,acme.com
        ...

Accepted formats:
  • multipart/form-data with `file` field (CSV)
  • application/json with `{"leads": [...]}`  (list of dicts)
  • text/csv raw body

Returns:
  {"inserted": N, "skipped_dup": M, "skipped_invalid": K, "lead_ids": [...]}
"""
from __future__ import annotations

import csv
import io
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("csv_leads_upload")

router = APIRouter(prefix="/api/admin/leads", tags=["admin", "leads"])

_db: AsyncIOMotorDatabase | None = None
_jwt_verify = None  # lazy-bound to whatever the rest of the app uses


def set_db(database: AsyncIOMotorDatabase) -> None:
    global _db
    _db = database


def set_jwt_verify(fn) -> None:
    global _jwt_verify
    _jwt_verify = fn


# ── helpers ──────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm_email(s: str) -> str:
    return (s or "").strip().lower()


def _norm_phone(s: str) -> str:
    s = (s or "").strip()
    # Keep + and digits only
    out = re.sub(r"[^\d+]", "", s)
    return out


def _valid_lead(row: dict) -> tuple[bool, str]:
    name = (row.get("business_name") or row.get("name") or "").strip()
    if not name:
        return False, "missing business_name"
    email = _norm_email(row.get("email") or "")
    phone = _norm_phone(row.get("phone") or "")
    if not (email or phone):
        return False, "no email/phone"
    if email and not _EMAIL_RE.match(email):
        return False, "invalid email"
    return True, ""


def _build_lead_doc(row: dict) -> dict:
    """Normalise a raw row → campaign_leads document ready for insert."""
    email = _norm_email(row.get("email") or "")
    phone = _norm_phone(row.get("phone") or "")
    name = (row.get("business_name") or row.get("name") or "").strip()
    city = (row.get("city") or "").strip()
    country = (row.get("country") or "us").strip().lower()
    website = (row.get("website") or row.get("website_url") or "").strip()
    address = (row.get("address") or "").strip()

    lead_id = f"manual-{secrets.token_hex(6)}"
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "lead_id": lead_id,
        "business_name": name,
        "email": email,
        "phone": phone,
        "city": city,
        "country": country,
        "address": address,
        "website_url": website,
        "source": "manual_csv_upload",
        "status": "new",
        "created_at": now_iso,
        "verification": {
            "channel_gating": {
                "email":    bool(email),
                "call":     bool(phone),
                "sms":      bool(phone),
                "whatsapp": bool(phone),
            },
            "source": "manual_csv_upload",
            "verified_at": now_iso,
        },
    }


# ── auth gate (lightweight — assumes admin JWT) ──────────────────────
async def _require_admin(request: Request) -> str:
    """Verify admin JWT. Returns founder_email on success."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[7:]
    # Try project's own JWT verifier first, fall back to local decode
    if _jwt_verify is not None:
        try:
            claims = _jwt_verify(token)
            email = claims.get("email") or claims.get("sub") or ""
            if email:
                return email
        except Exception as e:
            logger.warning(f"[csv-upload] jwt verify err: {e}")
    # Fallback: pyjwt decode using JWT_SECRET
    try:
        import jwt as _jwt
        import os as _os
        secret = _os.environ.get("JWT_SECRET", "")
        if not secret:
            raise HTTPException(500, "JWT_SECRET unset")
        claims = _jwt.decode(token, secret, algorithms=["HS256"])
        email = claims.get("email") or claims.get("sub") or ""
        if not email:
            raise HTTPException(401, "no email in token")
        return email
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(401, f"jwt invalid: {e}")


# ── core ingestion ───────────────────────────────────────────────────
async def _ingest_rows(rows: list[dict]) -> dict:
    if _db is None:
        raise HTTPException(503, "db not ready")
    inserted = 0
    skipped_dup = 0
    skipped_invalid = 0
    lead_ids: list[str] = []
    errors: list[str] = []

    # Pre-load existing emails+phones in chunks for fast dup check.
    new_emails = {_norm_email(r.get("email") or "") for r in rows if r.get("email")}
    new_phones = {_norm_phone(r.get("phone") or "") for r in rows if r.get("phone")}
    new_emails.discard("")
    new_phones.discard("")

    existing_emails: set[str] = set()
    existing_phones: set[str] = set()
    if new_emails:
        async for d in _db.campaign_leads.find(
            {"email": {"$in": list(new_emails)}},
            {"_id": 0, "email": 1},
        ):
            existing_emails.add(_norm_email(d.get("email") or ""))
    if new_phones:
        async for d in _db.campaign_leads.find(
            {"phone": {"$in": list(new_phones)}},
            {"_id": 0, "phone": 1},
        ):
            existing_phones.add(_norm_phone(d.get("phone") or ""))

    # DNC check (cheap)
    dnc_emails: set[str] = set()
    dnc_phones: set[str] = set()
    async for d in _db.do_not_contact.find({}, {"_id": 0, "email": 1, "phone": 1}):
        if d.get("email"):
            dnc_emails.add(_norm_email(d["email"]))
        if d.get("phone"):
            dnc_phones.add(_norm_phone(d["phone"]))

    for idx, row in enumerate(rows):
        ok, reason = _valid_lead(row)
        if not ok:
            skipped_invalid += 1
            if len(errors) < 20:
                errors.append(f"row {idx+1}: {reason}")
            continue
        email = _norm_email(row.get("email") or "")
        phone = _norm_phone(row.get("phone") or "")
        if (email and email in existing_emails) or (phone and phone in existing_phones):
            skipped_dup += 1
            continue
        if (email and email in dnc_emails) or (phone and phone in dnc_phones):
            skipped_dup += 1
            errors.append(f"row {idx+1}: in DNC list") if len(errors) < 20 else None
            continue

        doc = _build_lead_doc(row)
        try:
            await _db.campaign_leads.insert_one(doc)
            inserted += 1
            lead_ids.append(doc["lead_id"])
            # Track in our seen-set so duplicate rows within same upload are caught.
            if email:
                existing_emails.add(email)
            if phone:
                existing_phones.add(phone)
        except Exception as e:
            skipped_invalid += 1
            logger.warning(f"[csv-upload] insert failed row {idx+1}: {e}")

    return {
        "ok": True,
        "inserted": inserted,
        "skipped_dup": skipped_dup,
        "skipped_invalid": skipped_invalid,
        "lead_ids": lead_ids[:200],  # cap response size
        "errors": errors,
    }


# ── endpoints ────────────────────────────────────────────────────────
def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict] = []
    for row in reader:
        # Lower-case + strip keys
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        out.append(clean)
    return out


@router.post("/upload-csv")
async def upload_csv(
    request: Request,
    file: UploadFile | None = File(None),
    _email: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Upload prospects via CSV file, raw CSV body, or JSON {"leads": [...]}."""
    rows: list[dict] = []

    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="ignore")
        rows = _parse_csv(raw)
    else:
        ctype = (request.headers.get("content-type") or "").lower()
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="ignore")
        if "application/json" in ctype:
            import json as _json
            try:
                payload = _json.loads(body_text or "{}")
            except Exception:
                raise HTTPException(400, "invalid JSON body")
            rows = payload.get("leads") or []
            if not isinstance(rows, list):
                raise HTTPException(400, "leads must be a list")
        elif body_text.strip():
            rows = _parse_csv(body_text)
        else:
            raise HTTPException(400, "no body — send CSV/JSON or `file` upload")

    if not rows:
        raise HTTPException(400, "no rows parsed")
    if len(rows) > 5000:
        raise HTTPException(413, f"max 5000 rows per upload (got {len(rows)})")

    res = await _ingest_rows(rows)
    res["uploaded_by"] = _email
    logger.warning(
        f"[csv-upload] by {_email}: inserted={res['inserted']} "
        f"dup={res['skipped_dup']} invalid={res['skipped_invalid']}"
    )
    return res


@router.get("/upload-template")
async def csv_template() -> dict[str, Any]:
    """Return a sample CSV header + 1 row so founder knows the format."""
    sample = (
        "business_name,email,phone,city,country,website,address\n"
        "Acme Roofing,owner@acme.com,+14165550199,Toronto,ca,acme.com,123 Main St\n"
        "Beta Plumbing,info@betaplumb.com,+12125550100,New York,us,betaplumb.com,\n"
    )
    return {
        "headers": ["business_name", "email", "phone", "city",
                    "country", "website", "address"],
        "required": ["business_name", "email or phone"],
        "example_csv": sample,
        "max_rows": 5000,
        "note": "Country: 'us' or 'ca'. Phone: E.164 preferred (+1...). "
                "Status auto-set to 'new'. Channel gating pre-seeded. "
                "Auto-blast picks up on next 2-min cycle.",
    }
