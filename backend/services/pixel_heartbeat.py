"""
Pixel Heartbeat Scan
====================

Runs every 6 hours. For every unique customer URL present in `db.repair_fixes`,
live-fetches the page and checks whether the AUREM pixel snippet is still present.

Self-healing outcomes:
  • If pixel DETECTED and there are pending/approved fixes → auto-mark deployed
    (green badge, health score jumps).
  • If pixel MISSING and there are fixes in `status=deployed` via pixel_verified_live
    or pixel_manual → flip them back to `approved` (red badge, admin notified
    via SSE feed).

This is the self-healing half of "Detect & Deploy Pixel" — admins never need to
manually re-check whether a customer's pixel is still live.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

PIXEL_SIGNATURES = [
    "aurem-pixel.js",
    "data-aurem-key",
    "/api/pixel/aurem-pixel",
    "window.aurem",
    "AUREM_PIXEL",
]

_CONCURRENCY = 4  # cap parallel fetches so we don't storm customer sites


async def _check_one(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    """Fetch URL, return detection result (no DB writes)."""
    try:
        r = await client.get(url)
        html = (r.text or "").lower()
        matched = [s for s in PIXEL_SIGNATURES if s.lower() in html]
        return {
            "url": url,
            "ok": r.status_code < 400,
            "status_code": r.status_code,
            "detected": bool(matched),
            "matched": matched,
            "bytes": len(html),
        }
    except Exception as e:
        return {"url": url, "ok": False, "detected": False, "matched": [], "error": str(e)[:200]}


async def run_pixel_heartbeat(db) -> Dict[str, Any]:
    """Main entry — scan all tracked URLs. Returns summary."""
    started = datetime.now(timezone.utc)
    urls: List[str] = await db.repair_fixes.distinct("scan_url")
    urls = [u for u in urls if u and isinstance(u, str)]
    if not urls:
        return {"scanned": 0, "auto_marked": 0, "auto_reverted": 0, "started_at": started.isoformat()}

    results: List[Dict[str, Any]] = []
    sem = asyncio.Semaphore(_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AUREM-Heartbeat/1.0)"},
    ) as client:
        async def _guarded(u):
            async with sem:
                return await _check_one(client, u)
        results = await asyncio.gather(*[_guarded(u) for u in urls])

    now_iso = datetime.now(timezone.utc).isoformat()
    auto_marked = 0
    auto_reverted = 0

    for res in results:
        url = res["url"]
        try:
            if res.get("detected"):
                # Flip any pending/approved fixes to deployed
                r1 = await db.repair_fixes.update_many(
                    {"scan_url": url, "status": {"$in": ["pending_approval", "approved"]}},
                    {"$set": {
                        "status": "deployed",
                        "deployed_at": now_iso,
                        "deploy_method": "pixel_verified_heartbeat",
                        "pixel_verified_signatures": res["matched"],
                    }},
                )
                auto_marked += int(r1.modified_count)
            elif res.get("ok") is False and res.get("status_code") is None:
                # Skip reverts when we literally couldn't reach the site (DNS/TLS/timeout).
                # Treat as inconclusive, not a removal.
                pass
            else:
                # Pixel not present on a reachable page → revert any manual/heartbeat deploys.
                r2 = await db.repair_fixes.update_many(
                    {
                        "scan_url": url,
                        "status": "deployed",
                        "deploy_method": {"$in": ["pixel_manual", "pixel_verified_live", "pixel_verified_heartbeat"]},
                    },
                    {"$set": {"status": "approved"}, "$unset": {"deployed_at": "", "deploy_method": "", "pixel_verified_signatures": ""}},
                )
                auto_reverted += int(r2.modified_count)
        except Exception as e:
            logger.warning(f"[PixelHeartbeat] apply failed for {url}: {e}")

        # Audit every site checked.
        try:
            await db.pixel_verification_log.insert_one({
                "url": url,
                "verified_at": now_iso,
                "source": "heartbeat",
                "detected": res.get("detected", False),
                "matched_signatures": res.get("matched", []),
                "fetched": res.get("ok", False),
                "fetch_error": res.get("error"),
                "status_code": res.get("status_code"),
            })
        except Exception:
            pass

    # Single summary SSE event so admins see the scan in the feed.
    try:
        from routers.agents_router import _broadcast_feed
        await _broadcast_feed(
            "pixel_heartbeat",
            f"🫀 Heartbeat scan: {len(urls)} site(s) checked · "
            f"{auto_marked} auto-marked · {auto_reverted} reverted",
            "warning" if auto_reverted else "info",
        )
    except Exception:
        pass

    summary = {
        "run_at": started.isoformat(),           # canonical field used by dashboard queries
        "sites_scanned": len(urls),              # canonical field used by dashboard queries
        "pixels_found": sum(1 for r in results if r.get("detected")),
        "failures": sum(1 for r in results if r.get("ok") is False),
        "scanned": len(urls),                    # legacy alias
        "auto_marked": auto_marked,
        "auto_reverted": auto_reverted,
        "started_at": started.isoformat(),
        "finished_at": now_iso,
        "duration_sec": (datetime.now(timezone.utc) - started).total_seconds(),
    }
    try:
        await db.pixel_heartbeat_runs.insert_one({**summary, "per_site": results})
    except Exception:
        pass

    logger.info(f"[PixelHeartbeat] {summary}")
    return summary
