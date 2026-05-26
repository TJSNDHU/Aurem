"""
AUREM CTO — Isolated, portable developer ops module.

Mount under FastAPI like so:

    from aurem_cto import build_router, set_db
    app.include_router(build_router())
    set_db(mongo_db)

Everything else (collections, routes, env vars) is namespaced under
`aurem_cto_` / `/aurem-cto/` / `AUREM_CTO_*`. See DEPENDENCIES.md for
the full extraction recipe and the 3 whitelisted host imports.
"""
from __future__ import annotations

from fastapi import APIRouter

from .routers.deploy import router as _deploy_router
from .routers.domain import router as _domain_router
from .routers.github_bot import router as _github_router
from .routers.harden import router as _harden_router
from .routers.chat_commits import router as _chat_commits_router
from .routers.unlock import router as _unlock_router
from .routers.vault import router as _vault_router
from .routers.stacks import router as _stacks_router
from .routers.trust import router as _trust_router
from .routers.engagement import router as _engagement_router
from .services import db as _db_service
from .services.codebase_indexer import router as _codebase_router

__all__ = ["build_router", "set_db", "VERSION"]

VERSION = "0.1.0-D31"


def build_router() -> APIRouter:
    """Returns the single root router that the host app mounts."""
    root = APIRouter(prefix="/aurem-cto", tags=["AUREM CTO"])
    root.include_router(_deploy_router)
    root.include_router(_domain_router)
    root.include_router(_github_router)
    root.include_router(_harden_router)
    root.include_router(_chat_commits_router)
    root.include_router(_unlock_router)
    root.include_router(_vault_router)
    root.include_router(_codebase_router)
    root.include_router(_stacks_router)
    root.include_router(_trust_router)
    root.include_router(_engagement_router)
    return root


def set_db(db) -> None:
    """Forward the Mongo client to every service that needs it."""
    _db_service.set_db(db)
