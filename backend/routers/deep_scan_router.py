"""
Deep Scanner Router — exposes utils/deep_scanner.py via HTTP.
POST /api/scanner/deep-scan  {url}  → tech stack, third-party services, social, pages
"""
import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

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


def _is_private_or_loopback(host: str) -> bool:
    """Bug-fix #40 — refuse to scan internal/private/loopback IPs.

    Resolves the host (DNS rebinding-safe: we check the resolved IP, not
    just the textual hostname) and rejects:
      - Loopback (127.0.0.0/8, ::1)
      - Private RFC-1918 (10/8, 172.16/12, 192.168/16)
      - Link-local (169.254/16) — blocks AWS metadata
      - Multicast / reserved / unspecified
    """
    try:
        # First check if `host` is already an IP literal.
        try:
            ip = ipaddress.ip_address(host)
            ips = [ip]
        except ValueError:
            infos = socket.getaddrinfo(host, None)
            ips = [ipaddress.ip_address(info[4][0]) for info in infos]
        for ip in ips:
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
                return True
    except Exception as e:
        logger.warning(f"[DEEP-SCAN] DNS resolve failed for {host!r}: {e}")
        # Fail closed on unresolvable hosts.
        return True
    return False


def _require_auth(request: Request) -> dict:
    """Bug-fix #40 — endpoint was unauthenticated → trivial SSRF.
    Now every caller must present a valid JWT."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    import jwt as _jwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        return _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


@router.post("/deep-scan")
async def deep_scan(body: DeepScanRequest, request: Request):
    """Run the deep scanner on a URL; returns comprehensive tech stack + services discovery."""
    _require_auth(request)  # Bug-fix #40
    url = body.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    # Bug-fix #40 — SSRF guard: reject internal-network targets.
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if not host or _is_private_or_loopback(host):
        raise HTTPException(400, "URL host is not scannable (private/loopback/invalid)")

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
