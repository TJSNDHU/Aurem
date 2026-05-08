"""
Deep Scanner Router — exposes utils/deep_scanner.py via HTTP.
POST /api/scanner/deep-scan  {url}  → tech stack, third-party services, social, pages
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, HttpUrl
from typing import Optional

from utils.deep_scanner import deep_scan_website

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scanner", tags=["Deep Scanner"])


class DeepScanRequest(BaseModel):
    url: str
    save: bool = True  # save to deep_scans collection


_db = None


def set_db(db):
    global _db
    _db = db


@router.post("/deep-scan")
async def deep_scan(body: DeepScanRequest, request: Request):
    """Run the deep scanner on a URL; returns comprehensive tech stack + services discovery."""
    url = body.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        result = await deep_scan_website(url)
    except Exception as e:
        logger.error(f"[DEEP-SCAN] Failed for {url}: {e}")
        raise HTTPException(502, f"Deep scan failed: {e}")

    if body.save and _db is not None:
        from datetime import datetime, timezone
        try:
            await _db.deep_scans.insert_one({
                "url": url,
                "result": result,
                "scanned_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"[DEEP-SCAN] Save failed: {e}")

    return {"success": True, "url": url, "data": result}


@router.get("/deep-scan/latest")
async def deep_scan_latest(url: str):
    """Get the latest cached deep-scan for a URL."""
    if _db is None:
        raise HTTPException(503, "DB not available")
    doc = await _db.deep_scans.find_one({"url": url}, {"_id": 0}, sort=[("scanned_at", -1)])
    if not doc:
        raise HTTPException(404, "No deep scan found for this URL")
    return doc
