"""
Tenant helpers — canonical way to read the current tenant_id in a router.

Usage inside a router:
    from utils.tenant import current_tenant

    @router.get("")
    async def get_leads(tenant_id: str = Depends(current_tenant)):
        ...

Or imperatively inside the function body:
    from utils.tenant import current_tenant
    tenant_id = current_tenant()

Falls back to `"aurem_platform"` when TenantGuard has not been populated
(exempt routes, local dev). That preserves existing admin-platform behaviour
while closing the "user can spoof ?tenant_id=" hole on authenticated routes.
"""
from __future__ import annotations

try:
    from middleware.tenant_guard import TenantGuard
except Exception:  # defensive — keep this importable even if middleware fails
    TenantGuard = None  # type: ignore

PLATFORM_DEFAULT = "aurem_platform"


def current_tenant() -> str:
    """Read tenant_id from request context (JWT → middleware); fallback to platform."""
    if TenantGuard is None:
        return PLATFORM_DEFAULT
    try:
        return TenantGuard.get() or PLATFORM_DEFAULT
    except Exception:
        return PLATFORM_DEFAULT
