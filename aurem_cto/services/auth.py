"""
aurem_cto.services.auth — single auth seam to the host application.

This is one of the **3 whitelisted host imports** declared in
DEPENDENCIES.md. The function is wrapped so the rest of the module
imports it from `aurem_cto.services.auth` (zero direct touch of the
host module from feature code), keeping the extraction patch tiny.
"""
from __future__ import annotations
from typing import Optional


async def current_dev(authorization: Optional[str]) -> dict:
    """Resolve the caller from a Bearer JWT.

    Falls through to admin auto-bootstrap (founder uses platform JWT)
    via the host's developer-portal logic. Returns the developer-account
    dict so downstream code can read `user_id`, `email`, etc.
    """
    from routers.developer_portal_router import _current_dev  # whitelisted
    return await _current_dev(authorization)
