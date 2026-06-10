"""
test_ai_platform_router_patches.py — locks the 7 real bugs fixed in the
audit of ai_platform_router.py (iter 322fi).

Real bugs covered:
  #3  get_api_key raised KeyError for admin users (no `api_key` field)
  #4  Tool credentials stored unencrypted (mitigation: explicit flag + TODO)
  #5  JWT_SECRET fell back to a hardcoded default — token forgery risk
  #6  In-memory rate-limit single-pod only (mitigation: documented assumption)
  #8  api-key /execute path could pass None crew_config to background task
  #9  Webhook delivery was a `pass` no-op — customers got silent failures
  #10 Concurrent quota bypass on /execute and /api/execute endpoints

Run: PYTHONPATH=/app/backend python3 tests/test_ai_platform_router_patches.py
"""
from __future__ import annotations

import inspect
import os
import sys

sys.path.insert(0, "/app/backend")


def _load_router_module():
    # JWT_SECRET must be set in env BEFORE importing the router because the
    # module raises at import time if it's missing (FIX #5).
    os.environ.setdefault("JWT_SECRET", "test-secret-for-import-only")
    from routers import ai_platform_router  # noqa: WPS433
    return ai_platform_router


# ── FIX #5: JWT_SECRET hardcoded-default eliminated (iter 322fi) ────
#
# iter D-74 re-evaluation: when this test was originally written, the
# ask was "fail loudly if JWT_SECRET is missing". Since then,
# iter 272 + 324d introduced a 3-tier resolver in `config.py`
# (env → /app/.jwt_secret file → ephemeral generation) so that uvicorn
# never crashes at module import time — that was causing K8s liveness
# probes to ECONNREFUSED and the pod to restart-loop.
#
# The original SECURITY concern (hardcoded fallback secret) is still
# covered by `test_jwt_secret_has_no_default_string_in_source` below.
# This test now guards the CURRENT contract:
#   • Module imports successfully whether JWT_SECRET is set or not
#     (no K8s death-spiral).
#   • `JWT_SECRET` is always a non-empty string at module level
#     (so encode/decode can't crash on None).
#   • config.py has the 3-tier audit comment so the design intent
#     survives future PRs.
def test_jwt_secret_resolves_via_three_tier_fallback():
    """Confirms the iter 272+324d K8s-safe 3-tier resolver is in place
    and `JWT_SECRET` is always populated. Hardcoded-default elimination
    is asserted separately by `_has_no_default_string_in_source`."""
    import importlib
    orig = os.environ.get("JWT_SECRET")
    os.environ.pop("JWT_SECRET", None)
    # Drop cached imports so config.py + router re-evaluate
    for mod in list(sys.modules.keys()):
        if mod in ("config", "routers.ai_platform_router"):
            del sys.modules[mod]
    try:
        # Module MUST import without JWT_SECRET set — the resolver
        # falls back to file / ephemeral and the pod stays up.
        cfg = importlib.import_module("config")
        assert cfg.JWT_SECRET, (
            "config.JWT_SECRET resolved to falsy value — K8s pod would "
            "be functional but every JWT call would crash"
        )
        assert isinstance(cfg.JWT_SECRET, str)
        assert len(cfg.JWT_SECRET) >= 16, (
            f"resolved JWT_SECRET suspiciously short ({len(cfg.JWT_SECRET)} chars)"
        )
        # Confirms which tier it came from is logged
        assert hasattr(cfg, "_JWT_SECRET_SOURCE")
        assert cfg._JWT_SECRET_SOURCE in ("env", "file", "file-new", "ephemeral"), (
            f"unexpected JWT secret source: {cfg._JWT_SECRET_SOURCE!r}"
        )
        # Router must also import cleanly (it does `from config import JWT_SECRET`)
        importlib.import_module("routers.ai_platform_router")
    finally:
        if orig is not None:
            os.environ["JWT_SECRET"] = orig
        for mod in list(sys.modules.keys()):
            if mod in ("config", "routers.ai_platform_router"):
                del sys.modules[mod]


def test_jwt_secret_has_no_default_string_in_source():
    """The infamous hardcoded fallback string must be gone."""
    apr = _load_router_module()
    src = inspect.getsource(apr)
    assert "aurem-secure-jwt-secret-key-2026-production" not in src, (
        "Hardcoded JWT_SECRET default still present (Bug #5)"
    )


# ── FIX #3: get_api_key returns safely for admins ────────────────────
def test_get_api_key_handles_missing_field_gracefully():
    """Source must use .get('api_key') with a fallback path for admins."""
    apr = _load_router_module()
    src = inspect.getsource(apr.get_api_key)
    # The bug pattern (in CODE, not comments): user["api_key"]
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert 'user["api_key"]' not in code_only, (
        "Direct dict access still present in code (Bug #3)"
    )
    # The fix: user.get("api_key") + admin role branch
    assert "user.get(\"api_key\")" in src
    assert "admin" in src.lower(), "no admin fallback path"


# ── FIX #8: api-key /execute requires crew_config ────────────────────
def test_api_execute_validates_crew_config():
    """The api-key endpoint must validate template_id OR custom_crew explicitly."""
    apr = _load_router_module()
    src = inspect.getsource(apr)
    # Strip comments — historical mention of the old pattern is allowed
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    # The bug pattern: crew_config = CREW_TEMPLATES.get(data.template_id, data.custom_crew)
    assert "CREW_TEMPLATES.get(data.template_id, data.custom_crew)" not in code_only, (
        "Old None-fallback pattern still present in code (Bug #8)"
    )
    # The fix introduces a Provide-or-raise guard (twice — one per endpoint)
    assert src.count("Provide template_id or custom_crew") >= 2


# ── FIX #9: webhook actually fires HTTP POST ─────────────────────────
def test_webhook_actually_dispatches():
    """run_platform_crew must POST to webhook URLs, not just `pass`."""
    apr = _load_router_module()
    src = inspect.getsource(apr.run_platform_crew)
    # The bug pattern: bare `pass` after the comment about webhooks
    # The fix: httpx.AsyncClient POST + webhook_delivery_log
    assert "AsyncClient" in src, "no async http client used to fire webhooks"
    assert "webhook_delivery_log" in src, "no delivery logging for webhooks"
    assert "X-Aurem-Event" in src, "webhook headers missing event marker"


# ── FIX #10: atomic check-and-increment on /execute paths ────────────
def test_execute_crew_uses_atomic_increment():
    """The standard /execute endpoint must use a conditional update that
    increments only if quota is still available — not read-then-write."""
    apr = _load_router_module()
    src = inspect.getsource(apr)
    # Both endpoints must contain the atomic pattern (conditional $lt + $inc)
    # The old bug pattern: `if usage.get(...) >= limit: raise` followed by a
    # separate $inc.
    # We check the new pattern is present at least twice (both endpoints).
    pattern_pieces = [
        '"usage.crew_executions": {"$lt":',
        'inc_result = await db.platform_users.update_one',
        'inc_result.modified_count == 0',
    ]
    for piece in pattern_pieces:
        count = src.count(piece)
        assert count >= 2, (
            f"atomic increment pattern '{piece}' present only {count}× "
            "(should be ≥2: /execute and api /execute) — Bug #10"
        )


# ── FIX #4 (re-evaluated D-74): credentials now encrypted via Fernet ─
def test_tool_connect_uses_fernet_encryption_envelope():
    """iter D-74 re-evaluation: the original test asserted
    `_encrypted: False` because credentials WERE stored in plaintext
    with that hardcoded marker. iter 326ww replaced that with real
    Fernet AES encryption via `services/credential_crypto.py`, and the
    `_encrypted` field is now `bool(envelope.get("_encrypted"))` —
    i.e. it reflects ACTUAL encryption state, not a hardcoded flag.

    This test now locks the CURRENT correct contract:
      • `connect_tool` calls `encrypt_credentials` from
        `credential_crypto` (real encryption, no mock).
      • The persisted row stores the encrypted envelope, NOT the
        plaintext `data.credentials`.
      • If encryption is unavailable AND the tool is in the sensitive
        list (whatsapp/email/twilio/stripe/openai/gemini/claude/smtp),
        the endpoint REFUSES with HTTP 503 instead of silently writing
        plaintext.
    """
    apr = _load_router_module()
    src = inspect.getsource(apr.connect_tool)

    # The encryption layer is wired in
    assert "encrypt_credentials" in src, (
        "connect_tool no longer calls encrypt_credentials — "
        "iter 326ww Fernet encryption regressed"
    )
    assert "credential_crypto" in src, (
        "connect_tool source no longer imports credential_crypto"
    )

    # The persisted row stores the envelope, not the plaintext
    assert "config_envelope" in src, (
        "connect_tool no longer persists `config_envelope` field — "
        "the encrypted shape changed without updating this guard"
    )
    # `_encrypted` is reflective, not hardcoded
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert '"_encrypted":      bool(envelope.get("_encrypted"))' in src or \
           '"_encrypted": bool(envelope.get("_encrypted"))' in src, (
        "_encrypted field is not derived from the actual envelope state"
    )
    # Hardcoded plaintext marker must be gone
    assert '"_encrypted": False' not in code_only, (
        "connect_tool still uses the hardcoded `_encrypted: False` "
        "plaintext marker — iter 326ww refactor incomplete"
    )

    # The 503 refusal-to-store-plaintext branch must exist
    assert "503" in src and "Encryption key not configured" in src, (
        "connect_tool no longer refuses with 503 when encryption is "
        "unavailable for sensitive tools — silent plaintext write risk"
    )
    assert "is_encryption_available" in src, (
        "encryption availability check missing"
    )


# ── FIX #6: single-pod assumption documented ─────────────────────────
def test_rate_limit_assumption_documented():
    """iter D-72 — Auth dedupe: the `_login_attempts` rate-limiter (along
    with the /auth/login + /auth/register handlers it guarded) has been
    DELETED from this file. The route now lives exclusively in
    `routers.platform_auth_router`, which itself uses MongoDB-based brute
    force tracking (login_attempts collection) — superior to the old
    in-memory single-pod approach this test originally validated.

    This test is now a regression guard: assert the duplicate is gone
    so future PRs can't silently re-introduce it. The audit comment
    block stays as the historical breadcrumb."""
    apr = _load_router_module()
    src = inspect.getsource(apr)

    # Strip Python comments — historical mention in the audit block is OK
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )

    # The duplicate auth handlers must NOT come back in code
    assert "@router.post(\"/auth/login\")" not in code_only, (
        "Duplicate /auth/login handler re-introduced in ai_platform_router "
        "— it must live ONLY in platform_auth_router (iter D-72)"
    )
    assert "@router.post(\"/auth/register\")" not in code_only, (
        "Duplicate /auth/register handler re-introduced in ai_platform_router "
        "— it must live ONLY in platform_auth_router (iter D-72)"
    )
    # Orphan rate-limiter dict must stay deleted
    assert "_login_attempts = {}" not in code_only, (
        "_login_attempts in-memory dict re-introduced; brute-force tracking "
        "now lives in platform_auth_router's login_attempts collection"
    )
    # Audit-comment breadcrumb must remain so future maintainers find this
    assert "iter D-72" in src and "Auth dedupe" in src, (
        "iter D-72 auth-dedupe audit-comment block missing — required so "
        "future readers know why these handlers are absent"
    )


# ── iter D-72: confirm platform_auth_router is the only owner ────────
def test_only_platform_auth_router_serves_login():
    """The /auth/login + /auth/register routes must be exposed by
    platform_auth_router and NOT by ai_platform_router. Last-loaded-wins
    means a duplicate handler in either file would silently shadow the
    other. This test pins ownership."""
    import sys
    # Reset module cache so both routers re-evaluate against current env
    for mod_name in ("routers.platform_auth_router", "routers.ai_platform_router"):
        sys.modules.pop(mod_name, None)
    os.environ.setdefault("JWT_SECRET", "test-secret-for-import-only")

    from routers import platform_auth_router as par  # noqa: WPS433
    from routers import ai_platform_router as apr  # noqa: WPS433

    par_routes = {(r.path, tuple(sorted(r.methods))) for r in par.router.routes}
    apr_routes = {(r.path, tuple(sorted(r.methods))) for r in apr.router.routes}

    # platform_auth_router MUST own /api/platform/auth/login + /register
    assert ("/api/platform/auth/login", ("POST",)) in par_routes, (
        "platform_auth_router lost ownership of /api/platform/auth/login"
    )
    assert ("/api/platform/auth/register", ("POST",)) in par_routes, (
        "platform_auth_router lost ownership of /api/platform/auth/register"
    )

    # ai_platform_router MUST NOT have those routes anymore
    apr_paths = {p for p, _ in apr_routes}
    assert "/api/platform/auth/login" not in apr_paths, (
        "ai_platform_router re-introduced /auth/login — duplicate auth "
        "handler returned (iter D-72 regression)"
    )
    assert "/api/platform/auth/register" not in apr_paths, (
        "ai_platform_router re-introduced /auth/register — duplicate auth "
        "handler returned (iter D-72 regression)"
    )


if __name__ == "__main__":
    tests = [
        test_jwt_secret_resolves_via_three_tier_fallback,
        test_jwt_secret_has_no_default_string_in_source,
        test_get_api_key_handles_missing_field_gracefully,
        test_api_execute_validates_crew_config,
        test_webhook_actually_dispatches,
        test_execute_crew_uses_atomic_increment,
        test_tool_connect_uses_fernet_encryption_envelope,
        test_rate_limit_assumption_documented,
        test_only_platform_auth_router_serves_login,
    ]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print()
    print("ALL ai_platform_router patch tests passed ✓")
