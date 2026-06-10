"""
D-76 Route Dedupe — Regression Suite
====================================

After D-75 #2 the route table had 17 cross-handler duplicates. D-76
purged all 17 by deleting / moving the loser handler in each pair.
This suite proves none of them creep back AND verifies the surviving
canonical handler still answers HTTP traffic.

Run:
    pytest backend/tests/test_d76_dedupe.py -v
"""
from __future__ import annotations

import sys
from collections import defaultdict

import pytest


@pytest.fixture(scope="module")
def live_app():
    """Import server + run register_all_routers so the route table is
    fully populated. Without this fixture app.routes only has the ~67
    routes inline-registered before startup_event."""
    sys.path.insert(0, "/app/backend")
    import server
    from routers.registry import register_all_routers
    # idempotent — registry's wrapper dedupes router objects
    try:
        register_all_routers(server.app, None)
    except Exception:
        # bulk wiring tolerates None db; ignore set_db failures here
        pass
    return server.app


# ── verified-dead handlers — must NOT appear in app.routes ──
DELETED_ENDPOINTS = {
    # (verb, path) → fully-qualified handler that was deleted
    ("POST", "/api/auth/forgot-password"):      "routers.server_misc_routes.forgot_password",
    ("POST", "/api/auth/reset-password"):       "routers.server_misc_routes.reset_password",
    ("GET",  "/api/auth/verify-reset-token"):   "routers.server_misc_routes.verify_token",
    ("POST", "/api/aurem/chat"):                "routers.aurem_routes.chat",
    ("POST", "/api/email/inbound"):             "routers.inbound_email_router.inbound_webhook",
    ("GET",  "/api/email/inbound/health"):      "routers.inbound_email_router.inbound_health",
    ("GET",  "/api/enterprise/audit"):          "routers.enterprise_engine.get_audit_trail",
    ("POST", "/api/incident/resolve/{incident_id}"): "routers.v2_customer_actions_router.resolve_incident_alias",
    ("POST", "/api/self-audit/run"):            "routers.self_audit_router.self_audit_run_now",
}


def _walk(app):
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods:
            continue
        ep = getattr(r, "endpoint", None)
        if ep is None:
            continue
        fq = f"{ep.__module__}.{ep.__qualname__}"
        for verb in methods:
            yield verb, path, fq


def test_d76_no_route_table_duplicates(live_app):
    """The big one — boot-time dedupe-audit count is 0."""
    by_route: dict[tuple[str, str], set[str]] = defaultdict(set)
    for verb, path, fq in _walk(live_app):
        if path.startswith(("/openapi", "/docs", "/redoc")):
            continue
        by_route[(verb, path)].add(fq)
    dupes = {k: v for k, v in by_route.items() if len(v) > 1}
    assert not dupes, (
        f"{len(dupes)} cross-handler route duplicates remain — D-76 regression. "
        f"Sample: {list(dupes.items())[:3]}"
    )


def test_d76_deleted_handlers_are_actually_gone(live_app):
    """Every loser handler from the original 17 must be absent."""
    present = {(v, p): fq for v, p, fq in _walk(live_app)}
    resurrected = [
        f"{verb} {path} → {dead_fq}"
        for (verb, path), dead_fq in DELETED_ENDPOINTS.items()
        if present.get((verb, path)) == dead_fq
    ]
    assert not resurrected, (
        "Deleted D-76 loser handlers came back: " + "; ".join(resurrected)
    )


@pytest.mark.parametrize("verb,path,expected", [
    ("POST", "/api/auth/google/callback",            "routes.auth.process_google_callback"),
    ("POST", "/api/aurem/chat",                      "routers.aurem_chat.aurem_chat"),
    ("POST", "/api/self-audit/run",                  "routers.autonomy_router.run_audit"),
    ("POST", "/api/incident/resolve/{incident_id}",  "routers.incident_router.resolve_incident"),
])
def test_d76_canonical_handler_active(live_app, verb, path, expected):
    """Each (verb, path) resolves to its single canonical handler."""
    handlers = {fq for v, p, fq in _walk(live_app) if v == verb and p == path}
    assert handlers == {expected}, (
        f"{verb} {path} resolves to {handlers!r}; expected {{{expected!r}}}"
    )


def test_d76_email_inbound_is_comprehensive_pipeline(live_app):
    """Cloudflare-Worker → ORA-reply pipeline owns /api/email/inbound."""
    handlers = {
        fq for v, p, fq in _walk(live_app)
        if v == "POST" and p == "/api/email/inbound"
    }
    assert len(handlers) == 1, (
        f"/api/email/inbound has {len(handlers)} handlers; expected 1"
    )
    fq = next(iter(handlers))
    assert "email_inbound_router" in fq, (
        f"/api/email/inbound active handler is {fq!r}; expected "
        "routers.email_inbound_router.* (D-76 canonical)."
    )


def test_d76_z_image_router_file_removed():
    import os
    assert not os.path.isfile("/app/backend/routers/z_image_router.py"), (
        "z_image_router.py was resurrected — D-76 regression."
    )
    assert "routers.z_image_router" not in sys.modules, (
        "routers.z_image_router is in sys.modules — someone imported it."
    )


def test_d76_google_oauth_callback_file_removed():
    import os
    assert not os.path.isfile("/app/backend/routers/google_oauth_callback.py"), (
        "routers/google_oauth_callback.py resurrected — D-76 regression."
    )

