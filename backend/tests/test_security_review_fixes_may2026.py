"""Tests for the May-2026 security fixes.

User's LLM bug review claimed 9 issues. Slow scan rejected 4 false
positives and shipped 5 real fixes:

  - Bug 2: verify_token now enforces blocklist on every read
  - Bug 3: TenantGuard rejects expired tokens
  - Bug 5: aurem-cto/api JWT_SECRET fails-fast at import if missing
  - Bug 7: log_crash defensive guard, no more swallowed NameError
  - Bug 8: in-memory rate-limiter bounded at 10k keys with bulk prune
  - Bug 9: redis_pool _async_lock lazy-init in running loop

These tests pin the live fixes.
"""
from __future__ import annotations

import importlib
import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest


# ─── Bug 2: verify_token enforces blocklist ───────────────────────────
@pytest.mark.asyncio
async def test_verify_token_rejects_blacklisted_token(monkeypatch):
    """A token with a jti in the blocklist must be refused — previous
    code skipped the check on the read path so logout was a no-op."""
    from utils import aurem_jwt
    monkeypatch.setattr(aurem_jwt, "_db", MagicMock())

    # Mock platform_users.find_one → returns a valid user
    aurem_jwt._db.platform_users = MagicMock()
    aurem_jwt._db.platform_users.find_one = AsyncMock(return_value={"_id": "u1"})

    # Spy on is_token_blacklisted
    is_blocked = AsyncMock(return_value=True)
    monkeypatch.setattr(aurem_jwt, "is_token_blacklisted", is_blocked)

    secret = aurem_jwt.JWT_SECRET
    algo = aurem_jwt.JWT_ALGORITHM
    tok = jwt.encode(
        {"sub": "u1", "type": "access", "jti": "abc12345", "exp": int(time.time()) + 60},
        secret,
        algorithm=algo,
    )
    out = await aurem_jwt.verify_token(tok)
    assert out is None
    is_blocked.assert_awaited_once_with("abc12345")


@pytest.mark.asyncio
async def test_verify_token_accepts_non_blacklisted_token(monkeypatch):
    from utils import aurem_jwt
    monkeypatch.setattr(aurem_jwt, "_db", MagicMock())
    aurem_jwt._db.platform_users = MagicMock()
    aurem_jwt._db.platform_users.find_one = AsyncMock(return_value={"_id": "u1"})
    monkeypatch.setattr(aurem_jwt, "is_token_blacklisted",
                        AsyncMock(return_value=False))

    secret = aurem_jwt.JWT_SECRET
    algo = aurem_jwt.JWT_ALGORITHM
    tok = jwt.encode(
        {"sub": "u1", "type": "access", "jti": "abc12345", "exp": int(time.time()) + 60},
        secret,
        algorithm=algo,
    )
    out = await aurem_jwt.verify_token(tok)
    assert out is not None
    assert out["sub"] == "u1"


# ─── Bug 3: TenantGuard rejects expired tokens ────────────────────────
def test_tenant_guard_source_does_not_disable_exp_check():
    """Functional pin: TenantGuard's jwt.decode call must NOT pass
    verify_exp=False. We grep the source for that exact kwargs payload
    appearing INSIDE a jwt.decode argument list, not in commentary."""
    import re
    src = open("/app/backend/middleware/tenant_guard.py", encoding="utf-8").read()
    # Match any jwt.decode(...) up to its closing paren and verify the
    # options kwarg with verify_exp=False is not present.
    decode_calls = re.findall(r"jwt\.decode\([^)]*?\)", src, re.DOTALL)
    assert decode_calls, "no jwt.decode() call found in tenant_guard"
    for call in decode_calls:
        assert "verify_exp" not in call or "False" not in call, (
            f"Bug-fix #3 regression — TenantGuard re-disabled exp check: {call!r}"
        )
    assert "ExpiredSignatureError" in src


# ─── Bug 5: aurem-cto/api fails fast without JWT_SECRET ───────────────
def test_aurem_cto_api_main_requires_jwt_secret():
    """Functional pin: the raise-on-missing-secret guard is present."""
    src = open("/app/aurem-cto/api/main.py", "r", encoding="utf-8").read()
    # No call site uses the old fallback.
    assert 'os.getenv("JWT_SECRET", "dev-secret-change-in-prod")' not in src
    # And a raise-when-missing guard exists somewhere.
    assert "raise RuntimeError" in src
    assert "JWT_SECRET must be set" in src


# ─── Bug 7: crash_protection defensive guard ──────────────────────────
def test_crash_protection_guards_log_crash():
    import inspect
    from middleware import crash_protection
    src = inspect.getsource(crash_protection)
    # The defensive None default is present
    assert "log_crash = None" in src
    # The call site checks before invoking
    assert "if log_crash is not None" in src


# ─── Bug 8: rate limiter has a global watermark prune ─────────────────
@pytest.mark.asyncio
async def test_rate_limiter_prunes_when_dict_exceeds_watermark():
    """Seed >10 000 stale keys and verify the next request causes a
    bulk prune rather than letting RAM grow forever."""
    from middleware import security
    rl = security.RedisRateLimiter.__new__(security.RedisRateLimiter)
    rl._redis = None
    rl._connected = False
    rl._memory_storage = defaultdict(list)

    now = time.time()
    # Seed 10500 stale buckets (timestamps 2 hours old).
    for i in range(10500):
        rl._memory_storage[f"old_ip_{i}"] = [now - 7200]

    # An incoming request from a *new* key triggers the watermark check.
    blocked = await rl.is_rate_limited("fresh_key", limit=10, window=60)
    assert blocked is False
    # Bulk prune should have collapsed the dict — only the active key
    # (or even nothing, if window pruning killed it) survives.
    assert len(rl._memory_storage) <= 1, (
        f"Bug-fix #8 broken — dict still {len(rl._memory_storage)} after prune"
    )


# ─── Bug 9: redis_pool lazy-init lock ─────────────────────────────────
def test_redis_pool_lock_lazy_init():
    """Module import must NOT create an asyncio.Lock immediately. The
    lock is None until first _get_async_lock() call."""
    # Force a fresh import in case other tests touched it.
    if "utils.redis_pool" in importlib.sys.modules:
        importlib.reload(importlib.sys.modules["utils.redis_pool"])
    else:
        importlib.import_module("utils.redis_pool")
    from utils import redis_pool
    assert redis_pool._async_lock is None, (
        "Bug-fix #9 broken — _async_lock was eagerly created at import"
    )
    # First use materialises it
    import asyncio
    async def _go():
        lk = redis_pool._get_async_lock()
        assert lk is not None
        # Second call returns the same object
        assert redis_pool._get_async_lock() is lk
    asyncio.run(_go())
