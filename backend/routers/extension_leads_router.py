"""
Extension Leads Router
API endpoints for Chrome Extension lead scraping sync + extension download

Endpoints:
- POST /api/extension/leads/bulk  — Receive bulk leads from Chrome extension
- GET  /api/extension/leads       — List all scraped leads
- GET  /api/extension/leads/stats — Stats overview
- GET  /api/extension/leads/export — Export as CSV
- DELETE /api/extension/leads/{id} — Delete a lead
- GET  /api/extension/download     — Download extension as ZIP
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging
import io
import csv
import zipfile
import os
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extension", tags=["Extension Leads"])

db = None

def set_db(database):
    global db
    db = database


class LeadItem(BaseModel):
    name: str
    title: Optional[str] = ""
    company: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    location: Optional[str] = ""
    about: Optional[str] = ""
    source: Optional[str] = "website"
    source_url: Optional[str] = ""


class BulkLeadsRequest(BaseModel):
    leads: List[LeadItem]


@router.post("/leads/bulk")
async def bulk_import_leads(request: BulkLeadsRequest, http_request: Request):
    """Receive bulk leads from Chrome extension.

    Bug-fix #177 (R21): admin auth required. Also enforce a hard cap
    of 500 leads/call to bound storage usage on import.
    """
    from utils.admin_guard import verify_admin
    verify_admin(http_request.headers.get("Authorization", ""))
    if len(request.leads) > 500:
        raise HTTPException(413, "max 500 leads per bulk import")

    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        imported = 0
        duplicates = 0

        for lead in request.leads:
            # Dedupe by name + email
            existing = None
            if lead.email:
                existing = await db.extension_leads.find_one(
                    {"email": lead.email},
                    {"_id": 1}
                )
            if not existing and lead.name:
                existing = await db.extension_leads.find_one(
                    {"name": lead.name, "source_url": lead.source_url},
                    {"_id": 1}
                )

            if existing:
                duplicates += 1
                continue

            doc = {
                "lead_id": str(uuid.uuid4())[:12],
                "name": lead.name,
                "title": lead.title or "",
                "company": lead.company or "",
                "email": lead.email or "",
                "phone": lead.phone or "",
                "location": lead.location or "",
                "about": lead.about or "",
                "source": lead.source or "website",
                "source_url": lead.source_url or "",
                "status": "new",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.extension_leads.insert_one(doc)
            imported += 1

        logger.info(f"[ExtensionLeads] Imported {imported}, duplicates skipped: {duplicates}")
        return {"success": True, "imported": imported, "duplicates": duplicates}

    except Exception as e:
        logger.error(f"[ExtensionLeads] Bulk import error: {e}")
        raise HTTPException(500, str(e))


@router.get("/leads")
async def list_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    """List all scraped leads"""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        query = {}
        if status:
            query["status"] = status
        if source:
            query["source"] = source
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"company": {"$regex": search, "$options": "i"}}
            ]

        cursor = db.extension_leads.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        leads = await cursor.to_list(length=limit)
        total = await db.extension_leads.count_documents(query)

        return {"success": True, "leads": leads, "total": total, "count": len(leads)}

    except Exception as e:
        logger.error(f"[ExtensionLeads] List error: {e}")
        raise HTTPException(500, str(e))


@router.get("/leads/stats")
async def leads_stats():
    """Get stats overview for extension leads"""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        total = await db.extension_leads.count_documents({})
        new_count = await db.extension_leads.count_documents({"status": "new"})
        contacted = await db.extension_leads.count_documents({"status": "contacted"})
        converted = await db.extension_leads.count_documents({"status": "converted"})

        # Source breakdown
        pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        source_cursor = db.extension_leads.aggregate(pipeline)
        sources = {}
        async for doc in source_cursor:
            sources[doc["_id"] or "unknown"] = doc["count"]

        # With email vs without
        with_email = await db.extension_leads.count_documents({"email": {"$ne": ""}})
        with_phone = await db.extension_leads.count_documents({"phone": {"$ne": ""}})

        return {
            "success": True,
            "stats": {
                "total": total,
                "new": new_count,
                "contacted": contacted,
                "converted": converted,
                "with_email": with_email,
                "with_phone": with_phone,
                "sources": sources
            }
        }

    except Exception as e:
        logger.error(f"[ExtensionLeads] Stats error: {e}")
        raise HTTPException(500, str(e))


@router.get("/leads/export")
async def export_leads_csv():
    """Export all leads as CSV"""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        cursor = db.extension_leads.find({}, {"_id": 0}).sort("created_at", -1)
        leads = await cursor.to_list(length=5000)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Title", "Company", "Email", "Phone", "Location", "Source", "URL", "Status", "Scraped At"])

        for l in leads:
            writer.writerow([
                l.get("name", ""), l.get("title", ""), l.get("company", ""),
                l.get("email", ""), l.get("phone", ""), l.get("location", ""),
                l.get("source", ""), l.get("source_url", ""), l.get("status", ""),
                l.get("scraped_at", "")
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=aurem-leads-{datetime.now().strftime('%Y%m%d')}.csv"}
        )

    except Exception as e:
        logger.error(f"[ExtensionLeads] Export error: {e}")
        raise HTTPException(500, str(e))


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, http_request: Request):
    """Delete a single lead.

    Bug-fix #177 (R21): admin auth required.
    """
    from utils.admin_guard import verify_admin
    verify_admin(http_request.headers.get("Authorization", ""))

    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        result = await db.extension_leads.delete_one({"lead_id": lead_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Lead not found")
        return {"success": True, "deleted": lead_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExtensionLeads] Delete error: {e}")
        raise HTTPException(500, str(e))


@router.put("/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, request: Request):
    """Update lead status (new, contacted, converted, lost)"""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        body = await request.json()
        new_status = body.get("status")
        if new_status not in ["new", "contacted", "converted", "lost"]:
            raise HTTPException(400, "Invalid status")

        result = await db.extension_leads.update_one(
            {"lead_id": lead_id},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Lead not found")

        return {"success": True, "lead_id": lead_id, "status": new_status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExtensionLeads] Status update error: {e}")
        raise HTTPException(500, str(e))


@router.get("/download")
async def download_extension():
    """Download Chrome extension as ZIP file"""
    ext_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "public", "chrome-extension")

    if not os.path.exists(ext_dir):
        raise HTTPException(404, "Extension files not found")

    try:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(ext_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    arcname = os.path.relpath(filepath, ext_dir)
                    zf.write(filepath, f"aurem-lead-scraper/{arcname}")

        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=aurem-lead-scraper.zip"}
        )

    except Exception as e:
        logger.error(f"[ExtensionLeads] Download error: {e}")
        raise HTTPException(500, str(e))
