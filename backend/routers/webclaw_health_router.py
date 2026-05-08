"""
Webclaw health router — iter 282ad/282ae/282af.

Exposes:
  GET /api/admin/webclaw/health              — live webclaw probe (chip 1)
  GET /api/admin/webclaw/brand-injection     — brand_injection module probe (chip 2)
  GET /api/admin/webclaw/diff-health         — website_snapshots reachable (chip 3)
"""
from fastapi import APIRouter

from services.webclaw_client import brand_injection_health, health_check

router = APIRouter(prefix="/api/admin/webclaw", tags=["webclaw"])


@router.get("/health")
async def webclaw_health() -> dict:
    """Returns {ok, status, detail} — green/red/skipped."""
    return await health_check()


@router.get("/brand-injection")
async def webclaw_brand_injection_health() -> dict:
    """Second pillars-map chip: verifies the Website Builder brand-injection
    helper module loads cleanly. GREEN on import success, RED on import fail."""
    return await brand_injection_health()


@router.get("/diff-health")
async def webclaw_diff_health() -> dict:
    """Third pillars-map chip: website_snapshots collection reachable?

    GREEN iff we can run a count on db.website_snapshots (collection exists
    or creates cleanly on first write). RED on any DB error.
    """
    try:
        import server as _srv  # type: ignore
        db = getattr(_srv, "db", None)
        if db is None:
            return {"ok": False, "status": "red", "detail": "db handle unavailable"}
        cnt = await db.website_snapshots.count_documents({}, limit=1)
        return {"ok": True, "status": "green",
                "detail": f"website_snapshots reachable (any_docs={bool(cnt)})"}
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"website_snapshots unreachable: {type(e).__name__}: {str(e)[:120]}"}


@router.get("/watcher-health")
async def webclaw_watcher_health() -> dict:
    """Fourth pillars-map chip: Active Site Watcher reachable + last run ts.

    GREEN iff site_change_triggers collection reachable. Surfaces last-run
    timestamp in detail when available.
    """
    try:
        import server as _srv  # type: ignore
        db = getattr(_srv, "db", None)
        from services.site_change_watcher import watcher_health as _wh
        return await _wh(db)
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"watcher_health failed: {type(e).__name__}: {str(e)[:120]}"}
