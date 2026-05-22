"""
Lead Email Mining Router — iter 282g / Task 3
==============================================
Admin-gated endpoints to run `tomba_local.mine_emails_from_url` against a
specific lead's website and persist results to `campaign_leads.discovered_emails`.

Endpoints:
    POST /api/admin/leads/{lead_id}/mine-emails
          Kick off a background mine. Returns immediately with a job_id;
          the actual scan runs in a task. Subsequent calls to `/status`
          return progress + final emails.

    GET  /api/admin/leads/{lead_id}/mine-emails/status
          Returns the latest mine state for this lead.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from routers.ora_dev_actions_router import verify_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/leads", tags=["Admin Leads Mining"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server as _srv
        if hasattr(_srv, "db") and _srv.db is not None:
            _db = _srv.db
    except Exception:
        pass
    return _db


class MineRequest(BaseModel):
    website: Optional[str] = None  # override; else uses lead's stored website
    verify_mx: bool = True
    max_pages: int = 5


async def _run_mine(lead_id: str, url: str, *, verify_mx: bool, max_pages: int):
    """Background task — do the work + persist to campaign_leads."""
    db = _get_db()
    if db is None:
        logger.warning(f"[leads_mining] no DB, skipping {lead_id}")
        return
    try:
        from services.tomba_local import mine_emails_from_url
        res = await mine_emails_from_url(
            url, max_pages=max_pages, verify_mx=verify_mx, persist=True,
        )
        update = {
            "discovered_emails": res.get("emails", []),
            "discovered_emails_count": len(res.get("emails", [])),
            "discovered_emails_at": datetime.now(timezone.utc).isoformat(),
            "email_mining_status": "complete",
            "email_mining_error": None,
        }
        await db.campaign_leads.update_one(
            {"lead_id": lead_id}, {"$set": update},
        )
        logger.info(
            f"[leads_mining] {lead_id} → {len(res.get('emails', []))} emails "
            f"in {res.get('duration_ms', 0)}ms"
        )
    except Exception as e:
        logger.warning(f"[leads_mining] {lead_id} failed: {e}")
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "email_mining_status": "failed",
                    "email_mining_error": str(e)[:200],
                    "email_mining_failed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        except Exception:
            pass


@router.post("/{lead_id}/mine-emails")
async def mine_lead_emails(
    lead_id: str,
    body: Optional[MineRequest] = None,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")
    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id},
        {"_id": 0, "lead_id": 1, "business_name": 1, "website": 1,
         "website_url": 1},
    )
    if not lead:
        raise HTTPException(404, "Lead not found")
    url = (body.website if (body and body.website)
            else lead.get("website") or lead.get("website_url") or "").strip()
    if not url:
        raise HTTPException(400, "No website on lead (pass `website` in body)")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Mark lead as running immediately so UI can show spinner
    job_id = f"mine_{secrets.token_hex(5)}"
    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "email_mining_status": "running",
            "email_mining_job_id": job_id,
            "email_mining_started_at": datetime.now(timezone.utc).isoformat(),
            "email_mining_started_by": payload.get("email"),
            "email_mining_error": None,
        }},
    )
    # Kick off background task
    verify = True if body is None else body.verify_mx
    max_pages = 5 if body is None else max(1, min(10, body.max_pages))
    asyncio.create_task(_run_mine(lead_id, url, verify_mx=verify,
                                    max_pages=max_pages))

    return {
        "ok": True,
        "lead_id": lead_id,
        "job_id": job_id,
        "status": "running",
        "url": url,
        "message": "Mining started. Poll /status for completion.",
    }


@router.get("/{lead_id}/mine-emails/status")
async def lead_mine_status(
    lead_id: str,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")
    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id},
        {"_id": 0, "lead_id": 1, "email_mining_status": 1,
         "email_mining_job_id": 1, "email_mining_started_at": 1,
         "email_mining_error": 1, "discovered_emails": 1,
         "discovered_emails_at": 1, "discovered_emails_count": 1},
    )
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {"ok": True, **lead}


# ─── Bulk Auto-Enrich All (iter 282i Task 3) ───────────────────────────────
# Concurrency=5, rate-limit=1 req/sec via semaphore + interval delay.
# Job state persisted to `lead_mining_jobs` so UI can poll across restarts.

class BulkMineRequest(BaseModel):
    lead_ids: Optional[list] = None     # explicit subset; else mines unmined
    only_unmined: bool = True           # skip leads w/ discovered_emails > 0
    max_leads: int = 100                # safety cap


async def _run_bulk_mine(job_id: str, lead_ids: list, *,
                         concurrency: int = 5, rate_per_sec: float = 1.0):
    """Background worker for bulk mining. Updates job doc as it progresses."""
    db = _get_db()
    if db is None:
        return
    sem = asyncio.Semaphore(int(max(1, concurrency)))
    interval = 1.0 / max(0.1, rate_per_sec)
    completed = 0
    succeeded = 0
    failed = 0
    last_kick = [0.0]
    lock = asyncio.Lock()

    async def _one(lid: str):
        nonlocal completed, succeeded, failed
        # Rate-limit: ensure ≥interval seconds between starts.
        async with lock:
            now = asyncio.get_event_loop().time()
            wait = max(0.0, last_kick[0] + interval - now)
            if wait > 0:
                await asyncio.sleep(wait)
            last_kick[0] = asyncio.get_event_loop().time()
        async with sem:
            try:
                lead = await db.campaign_leads.find_one(
                    {"lead_id": lid},
                    {"_id": 0, "website": 1, "website_url": 1},
                )
                url = (lead or {}).get("website") or (lead or {}).get("website_url") or ""
                url = (url or "").strip()
                if not url:
                    failed += 1
                    completed += 1
                    return
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                await db.campaign_leads.update_one(
                    {"lead_id": lid},
                    {"$set": {
                        "email_mining_status": "running",
                        "email_mining_job_id": job_id,
                        "email_mining_started_at": datetime.now(timezone.utc).isoformat(),
                        "email_mining_error": None,
                    }},
                )
                await _run_mine(lid, url, verify_mx=True, max_pages=5)
                # _run_mine writes complete or failed status into the doc
                doc = await db.campaign_leads.find_one(
                    {"lead_id": lid}, {"_id": 0, "email_mining_status": 1},
                )
                if (doc or {}).get("email_mining_status") == "complete":
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"[bulk_mine] {lid} failed: {e}")
                failed += 1
            finally:
                completed += 1
                # Update job progress
                await db.lead_mining_jobs.update_one(
                    {"job_id": job_id},
                    {"$set": {
                        "completed": completed,
                        "succeeded": succeeded,
                        "failed": failed,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )

    # Schedule all leads concurrently — semaphore + rate-limit gate them.
    await asyncio.gather(*[_one(lid) for lid in lead_ids],
                         return_exceptions=True)
    # Mark job complete
    await db.lead_mining_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "complete",
            "completed": completed,
            "succeeded": succeeded,
            "failed": failed,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    # Task 2 (iter 282j) — Founder completion email with stats + top 5 contacts
    try:
        await _send_bulk_completion_email(db, job_id, lead_ids,
                                            succeeded, failed, completed)
    except Exception as e:
        logger.warning(f"[bulk_mine] completion email failed: {e}")


async def _send_bulk_completion_email(db, job_id: str, lead_ids: list,
                                        succeeded: int, failed: int,
                                        completed: int) -> None:
    """Email teji.ss1986@gmail.com a summary when bulk enrichment finishes.

    Contents: job stats + top 5 best contacts table (highest-scored email
    from each enriched lead, sorted by score desc).
    """
    import os
    try:
        from services.email_engine import resend  # iter 326x defensive
    except ImportError:
        logger.warning("[bulk_mine] resend SDK not installed")
        return
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("[bulk_mine] RESEND_API_KEY not set — skipping email")
        return
    to_email = os.environ.get("FOUNDER_EMAIL", "teji.ss1986@gmail.com")

    # Pull discovered emails for these leads, sort by score
    enriched = await db.campaign_leads.find(
        {"lead_id": {"$in": lead_ids},
         "discovered_emails": {"$exists": True, "$ne": []}},
        {"_id": 0, "lead_id": 1, "business_name": 1,
         "website": 1, "discovered_emails": 1},
    ).to_list(length=len(lead_ids))

    rows = []
    for lead in enriched:
        emails = lead.get("discovered_emails") or []
        if not emails:
            continue
        top = emails[0]  # already sorted by score in tomba_local
        rows.append({
            "biz": lead.get("business_name") or lead.get("lead_id"),
            "site": lead.get("website") or "",
            "email": top.get("email", ""),
            "score": top.get("score", 0),
            "role": top.get("role", False),
        })
    rows.sort(key=lambda r: -float(r.get("score") or 0))
    top5 = rows[:5]

    rows_html = "".join(
        f'<tr style="border-bottom:1px solid rgba(249,115,22,0.12);">'
        f'<td style="padding:10px 12px;color:#E8E0D0;font-size:13px;">{r["biz"]}</td>'
        f'<td style="padding:10px 12px;font-family:monospace;font-size:12px;">'
        f'<a href="mailto:{r["email"]}" style="color:#86EFAC;text-decoration:none;">{r["email"]}</a></td>'
        f'<td style="padding:10px 12px;color:#FDBA74;font-size:12px;">'
        f'{float(r["score"]):.2f}{" · role" if r["role"] else " · personal"}</td>'
        f'</tr>'
        for r in top5
    ) or '<tr><td colspan="3" style="padding:18px;color:#8A8070;text-align:center;font-style:italic;">No emails discovered.</td></tr>'

    base = (os.environ.get("AUREM_PUBLIC_URL")
            or os.environ.get("PUBLIC_APP_URL") or "https://aurem.live").rstrip("/")
    html = f"""\
<!doctype html>
<html><body style="margin:0;padding:0;background:#080808;font-family:'Helvetica Neue',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#080808;padding:32px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#0D0D0D;border:1px solid rgba(249,115,22,0.2);border-radius:14px;overflow:hidden;">

<tr><td style="padding:32px 32px 12px;">
  <div style="font-family:'Cinzel',serif;font-size:11px;letter-spacing:.22em;color:#F97316;text-transform:uppercase;margin-bottom:8px;">AUREM · Bulk Enrich Done</div>
  <div style="font-family:'Cinzel',serif;font-size:24px;color:#FFF;letter-spacing:.02em;">
    {succeeded} leads enriched · {sum(1 for r in rows if r['email'])} emails ready
  </div>
</td></tr>

<tr><td style="padding:8px 32px 24px;">
  <div style="display:inline-block;margin-right:18px;color:#86EFAC;font-size:14px;">✓ {succeeded} succeeded</div>
  <div style="display:inline-block;margin-right:18px;color:#FCA5A5;font-size:14px;">✕ {failed} failed</div>
  <div style="display:inline-block;color:#8A8070;font-size:14px;">{completed} of {len(lead_ids)} processed</div>
</td></tr>

<tr><td style="padding:0 32px 12px;">
  <div style="font-size:10px;letter-spacing:.18em;color:#F97316;text-transform:uppercase;margin-bottom:10px;">Top 5 Best Contacts</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#060606;border:1px solid rgba(249,115,22,0.18);border-radius:10px;border-collapse:collapse;">
    <thead>
      <tr style="background:rgba(249,115,22,0.06);">
        <th style="padding:10px 12px;text-align:left;font-size:10px;letter-spacing:.16em;color:#8A8070;text-transform:uppercase;">Business</th>
        <th style="padding:10px 12px;text-align:left;font-size:10px;letter-spacing:.16em;color:#8A8070;text-transform:uppercase;">Email</th>
        <th style="padding:10px 12px;text-align:left;font-size:10px;letter-spacing:.16em;color:#8A8070;text-transform:uppercase;">Score</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</td></tr>

<tr><td style="padding:24px 32px 32px;text-align:center;">
  <a href="{base}/admin/leads-mining" style="display:inline-block;padding:14px 28px;background:#F97316;color:#0A0A00;text-decoration:none;border-radius:8px;font-weight:700;font-size:12px;letter-spacing:.08em;">OPEN LEADS MINING →</a>
</td></tr>

<tr><td style="padding:18px 32px;background:#030303;border-top:1px solid rgba(249,115,22,0.12);text-align:center;color:#5A5248;font-size:11px;letter-spacing:.06em;">
  Job <code style="color:#8A8070;">{job_id}</code> · AUREM Sovereign OS
</td></tr>

</table>
</td></tr>
</table>
</body></html>
"""

    resend.api_key = api_key
    from_email = os.environ.get("RESEND_FROM_EMAIL", "tj@aurem.live")
    try:
        resp = resend.Emails.send({
            "from": from_email,
            "to": to_email,
            "subject": f"[AUREM] Bulk Enrich Done — {succeeded} leads, {len(rows)} emails",
            "html": html,
        })
        logger.info(f"[bulk_mine] completion email sent id={resp.get('id')}")
    except Exception as e:
        logger.warning(f"[bulk_mine] resend send failed: {e}")


@router.post("/mine-emails/bulk")
async def bulk_mine(
    body: Optional[BulkMineRequest] = None,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Auto-Enrich All leads. Concurrency=5, rate=1/sec.

    If `lead_ids` is provided, mines exactly those.
    Else mines up to `max_leads` campaign_leads that have a website
    and (if only_unmined) no discovered_emails yet.
    """
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")

    body = body or BulkMineRequest()

    # Build the lead list
    if body.lead_ids:
        target_ids = list({str(x) for x in body.lead_ids})[: body.max_leads]
    else:
        q: Dict[str, Any] = {
            "$or": [
                {"website": {"$nin": [None, ""]}},
                {"website_url": {"$nin": [None, ""]}},
            ],
        }
        if body.only_unmined:
            q["$and"] = [{"$or": [
                {"discovered_emails_count": {"$in": [None, 0]}},
                {"discovered_emails": {"$in": [None, []]}},
            ]}]
        cur = db.campaign_leads.find(q, {"_id": 0, "lead_id": 1}) \
            .limit(int(max(1, min(500, body.max_leads))))
        target_ids = [d["lead_id"] async for d in cur if d.get("lead_id")]

    if not target_ids:
        return {"ok": True, "job_id": None, "total": 0,
                "message": "No leads to enrich (already mined or no website)"}

    job_id = f"bulkmine_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()
    await db.lead_mining_jobs.insert_one({
        "job_id": job_id,
        "type": "bulk_mine",
        "started_at": now,
        "started_by": payload.get("email"),
        "status": "running",
        "total": len(target_ids),
        "completed": 0,
        "succeeded": 0,
        "failed": 0,
        "lead_ids": target_ids,
        "concurrency": 5,
        "rate_per_sec": 1.0,
        "updated_at": now,
    })
    asyncio.create_task(_run_bulk_mine(job_id, target_ids,
                                        concurrency=5, rate_per_sec=1.0))
    return {
        "ok": True,
        "job_id": job_id,
        "total": len(target_ids),
        "status": "running",
        "message": f"Bulk mining started for {len(target_ids)} leads.",
    }


@router.get("/mine-emails/bulk/{job_id}")
async def bulk_mine_status(
    job_id: str,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")
    job = await db.lead_mining_jobs.find_one(
        {"job_id": job_id},
        {"_id": 0, "lead_ids": 0},  # exclude lead_ids array (large)
    )
    if not job:
        raise HTTPException(404, "Job not found")
    return {"ok": True, **job}


# ─── Lead list (for the mining UI) ──────────────────────────────────────────
_list_router = APIRouter(prefix="/api/admin/platform", tags=["Admin Leads Mining"])


@_list_router.get("/campaign-leads")
async def list_campaign_leads(
    q: Optional[str] = None,
    limit: int = 25,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Paged list of campaign_leads for the mining UI. Filters by
    business_name (partial, case-insensitive) or exact lead_id."""
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")
    query: Dict[str, Any] = {}
    if q:
        q = q.strip()
        query = {
            "$or": [
                {"lead_id": q},
                {"business_name": {"$regex": q, "$options": "i"}},
            ]
        }
    cur = db.campaign_leads.find(
        query,
        {
            "_id": 0, "lead_id": 1, "business_name": 1,
            "website": 1, "website_url": 1,
            "discovered_emails": 1, "discovered_emails_count": 1,
            "email_mining_status": 1, "email_mining_error": 1,
            "email_mining_started_at": 1, "discovered_emails_at": 1,
            "logo_url": 1, "logo_uploaded_at": 1,
        },
    ).sort("_id", -1).limit(int(max(1, min(100, limit))))
    rows = [d async for d in cur]
    return {"ok": True, "leads": rows, "count": len(rows)}
