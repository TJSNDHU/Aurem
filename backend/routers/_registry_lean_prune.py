"""
AUREM router registry — LEAN-mode post-registration route prune.

Extracted from `registry.py` (iter 322m+). Runs once after every router
has been registered: walks the FastAPI route table and deletes any
route whose path matches one of the prune-prefixes or one of the exact
prune-paths. This is how the LEAN profile drops ~2000 routes down to
~400 without touching the original router source.

Behaviour-preserving — paths and counts mirror the original inline
block exactly. The lists are kept here (rather than in
``_registry_config.py``) because they are about *URL paths*, not module
imports, so they belong to the prune step, not the skip step.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# Path prefixes pruned post-registration.
_PRUNE_PREFIXES: tuple[str, ...] = (
    "/api/cart/",              # ecommerce cart (not used)
    "/api/admin/orders",       # admin order mgmt (0 frontend refs)
    "/api/admin/automations",  # admin automation mgmt (0 frontend refs)
    "/api/admin/combo-offers", # combo offers CRUD (0 frontend refs)
    "/api/admin/rls",          # row-level security (0 frontend refs)
    "/api/admin/brands",       # brand mgmt (0 frontend refs)
    "/api/admin/products",     # product admin (0 frontend refs)
    "/api/admin/whatsapp",     # whatsapp admin (0 frontend refs)
    "/api/admin/security",     # security admin (0 frontend refs)
    "/api/pipeline/rollout",   # pipeline rollout (0 frontend refs)
    "/api/pipeline/shadow",    # shadow pipeline (0 frontend refs)
    "/api/subscription/admin", # subscription admin (0 frontend refs)
    "/api/webhook/",           # generic webhooks
    "/api/aurem-voice/webhook",# voice webhooks (server callbacks)
    "/api/aurem-voice/parse-date", # parse date utility (0 refs)
    "/api/openrouter/test",    # openrouter test endpoints
    "/api/booking/",           # booking (0 frontend refs)
    "/api/chat/history",       # standalone chat (not AUREM chat)
    "/api/chat/message",       # standalone chat (not AUREM chat)
    "/api/openrouter/",        # openrouter test/status (0 frontend refs)
    "/api/aurem-voice/health", # health check
    "/api/aurem-voice/tools",  # internal tool listing
    "/api/aurem-voice/personas", # internal persona listing
    "/api/aurem-redis/health", # health check
    "/api/aurem-keys/health",  # health check
)


# Exact paths pruned (no prefix match).
# NOTE: ``/``, ``/health``, ``/ready`` must NEVER be pruned — they are
# Kubernetes liveness/readiness probe targets. Removing them causes
# 404 on probes → pod marked not-ready → CrashLoopBackOff on deploy.
_PRUNE_EXACT: frozenset[str] = frozenset({
    "/.well-known/assetlinks.json",
    "/.well-known/ucp",
})


def apply_lean_prune(app, lean_mode: bool) -> int:
    """Remove unused routes from the FastAPI app's route table.

    Returns the number of routes pruned (0 when LEAN_MODE is off).
    Safe to call exactly once at the end of `register_all_routers`.
    """
    if not lean_mode:
        return 0

    from starlette.routing import Route

    before_count = len(app.router.routes)
    to_remove: list[int] = []
    for i, r in enumerate(app.router.routes):
        if isinstance(r, Route):
            if (
                any(r.path.startswith(p) for p in _PRUNE_PREFIXES)
                or r.path in _PRUNE_EXACT
            ):
                to_remove.append(i)

    for i in reversed(to_remove):
        del app.router.routes[i]

    pruned = before_count - len(app.router.routes)
    if pruned > 0:
        logger.info(f"[REGISTRY] LEAN prune: removed {pruned} unused routes")
    return pruned
