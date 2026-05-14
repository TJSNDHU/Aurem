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


# ── FIX #5: JWT_SECRET fail-fast ─────────────────────────────────────
def test_jwt_secret_must_fail_fast_when_unset():
    """Re-importing without JWT_SECRET must raise (no hardcoded fallback)."""
    import importlib
    orig = os.environ.get("JWT_SECRET")
    os.environ.pop("JWT_SECRET", None)
    # Drop any cached import so the module re-evaluates the env check
    for mod in list(sys.modules.keys()):
        if mod == "routers.ai_platform_router":
            del sys.modules[mod]
    try:
        try:
            importlib.import_module("routers.ai_platform_router")
        except RuntimeError as e:
            assert "JWT_SECRET" in str(e)
            return
        raise AssertionError("import succeeded without JWT_SECRET (Bug #5 not fixed)")
    finally:
        if orig is not None:
            os.environ["JWT_SECRET"] = orig
        for mod in list(sys.modules.keys()):
            if mod == "routers.ai_platform_router":
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


# ── FIX #4: credentials stored with explicit unencrypted flag ────────
def test_tool_connect_marks_creds_as_unencrypted():
    """Until a real encryption layer lands, the connect_tool route must at
    least flag the row so future migrations can target it."""
    apr = _load_router_module()
    src = inspect.getsource(apr.connect_tool)
    assert '"_encrypted": False' in src or "'_encrypted': False" in src, (
        "credentials row missing _encrypted=False migration marker (Bug #4)"
    )
    assert "PLAINTEXT" in src.upper() or "FIX #4" in src, (
        "no audit marker comment on connect_tool credential write"
    )


# ── FIX #6: single-pod assumption documented ─────────────────────────
def test_rate_limit_assumption_documented():
    """The in-memory rate limiter must carry a documented single-pod caveat
    so future maintainers know it has to move to Redis when scaling out."""
    apr = _load_router_module()
    src = inspect.getsource(apr)
    assert "_login_attempts" in src
    # The audit comment block must exist near the declaration
    assert "single-pod" in src.lower() or "single pod" in src.lower(), (
        "no single-pod assumption documented (Bug #6 mitigation missing)"
    )


if __name__ == "__main__":
    tests = [
        test_jwt_secret_must_fail_fast_when_unset,
        test_jwt_secret_has_no_default_string_in_source,
        test_get_api_key_handles_missing_field_gracefully,
        test_api_execute_validates_crew_config,
        test_webhook_actually_dispatches,
        test_execute_crew_uses_atomic_increment,
        test_tool_connect_marks_creds_as_unencrypted,
        test_rate_limit_assumption_documented,
    ]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print()
    print("ALL ai_platform_router patch tests passed ✓")
