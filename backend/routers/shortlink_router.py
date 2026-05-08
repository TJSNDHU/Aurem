"""
Shortlink + Founder Brief router — iter 282al.

Endpoints:
  POST /api/shortlinks/create              — mint slug for a target URL
  GET  /r/{slug}                            — 302 redirect
  GET  /api/shortlinks/{lead_id}/stats     — click stats
  GET  /api/admin/brief/health             — Morning Brief cron health chip
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from services.shortlink_service import (
    SHORTLINK_BASE,
    create_shortlink,
    resolve_shortlink,
    shortlink_stats,
)

router = APIRouter(tags=["shortlinks"])


def _db():
    try:
        import server  # type: ignore
        return getattr(server, "db", None)
    except Exception:
        return None


class _ShortlinkCreateBody(BaseModel):
    lead_id: str
    target_url: str
    expires_days: int = 30


@router.post("/api/shortlinks/create")
async def shortlinks_create(body: _ShortlinkCreateBody):
    db = _db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    if not body.target_url.startswith(("http://", "https://")):
        raise HTTPException(400, "target_url must be absolute")
    r = await create_shortlink(db, body.lead_id, body.target_url,
                                 expires_days=body.expires_days)
    return r


@router.get("/r/{slug}")
async def shortlinks_resolve(slug: str):
    db = _db()
    target = await resolve_shortlink(db, slug)
    return RedirectResponse(target or SHORTLINK_BASE, status_code=302)


# iter 282al — preview/testing alias. Production DNS (aurem.live) forwards
# /r/* straight to the backend, but the Emergent preview ingress only
# routes /api/*. Mount the same resolver under /api/r/{slug} so E2E tests
# through the preview URL can hit the redirect path.
@router.get("/api/r/{slug}")
async def shortlinks_resolve_api_alias(slug: str):
    db = _db()
    target = await resolve_shortlink(db, slug)
    return RedirectResponse(target or SHORTLINK_BASE, status_code=302)


@router.get("/api/shortlinks/{lead_id}/stats")
async def shortlinks_stats(lead_id: str):
    db = _db()
    return await shortlink_stats(db, lead_id)


@router.get("/api/admin/sovereign/health")
async def sovereign_health_endpoint():
    """GREEN when Sovereign Node (Legion Ollama) is reachable."""
    from services.llm_gateway import sovereign_health
    return await sovereign_health()


@router.get("/api/admin/brief/health")
async def brief_health():
    """GREEN if last brief fired <25h ago, YELLOW 25-48h, RED >48h or never.

    Reads from `founder_brief_sends` / `morning_briefs` / `morning_brief_runs`,
    whichever is most recent. Accepts both datetime and ISO-string timestamps
    (the canonical `morning_briefs.generated_at` is an ISO string).
    """
    db = _db()
    if db is None:
        return {"ok": False, "status": "red", "detail": "db unavailable"}
    last_ts = None

    def _coerce(v):
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    for coll in ("founder_brief_sends", "morning_briefs", "morning_brief_runs"):
        try:
            doc = await db[coll].find_one(
                {},
                sort=[("generated_at", -1), ("ts", -1), ("sent_at", -1)],
                projection={"_id": 0, "ts": 1, "sent_at": 1,
                              "created_at": 1, "generated_at": 1},
            )
            if not doc:
                continue
            for key in ("generated_at", "ts", "sent_at", "created_at"):
                cand = _coerce(doc.get(key))
                if cand is not None:
                    if last_ts is None or cand > last_ts:
                        last_ts = cand
                    break
        except Exception:
            continue

    now = datetime.now(timezone.utc)
    if last_ts is None:
        return {"ok": False, "status": "red",
                "detail": "no brief fired yet",
                "last_fired": None}
    age = now - last_ts
    last_iso = last_ts.isoformat()
    if age <= timedelta(hours=25):
        status = "green"
    elif age <= timedelta(hours=48):
        status = "yellow"
    else:
        status = "red"
    return {
        "ok":         status == "green",
        "status":     status,
        "last_fired": last_iso,
        "detail":     f"last fired {last_iso} (age {int(age.total_seconds()/3600)}h)",
    }
