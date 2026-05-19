"""
Admin-only diagnostic: expose the env-var report produced by
bootstrap.startup_validation. One-liner endpoint, no DB calls — safe to
hit even when Mongo is down.
"""
from fastapi import APIRouter, HTTPException, Request

from bootstrap.startup_validation import get_last_report, validate_environment
from config import JWT_SECRET

router = APIRouter(prefix="/api/admin", tags=["Admin Diagnostics"])


def _verify_admin(request: Request):
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    from utils.admin_guard import is_admin_email
    if not (payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin")
            or is_admin_email(payload.get("email"))):
        raise HTTPException(403, "Admin access required")
    return payload


@router.get("/startup-report")
async def startup_report(request: Request, refresh: bool = False):
    """Return the last env-var validation report. Pass ?refresh=true to
    recompute live (cheap — just reads os.environ)."""
    _verify_admin(request)
    if refresh:
        return validate_environment()
    return get_last_report()
