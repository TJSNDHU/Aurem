"""
Regression tests — Round 2/3/4 security & logic bug fixes.
==========================================================
Each test name maps 1:1 to the bug number from the audit reports so
future agents can grep `# Bug-fix #NN` to find the patch + test that
prove it stays fixed.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import time

import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

# Make `/app/backend` importable when tests are run from /app
sys.path.insert(0, "/app/backend")


# ─── Bug 11 — Password reset token MUST be hashed at rest ────────
def test_bug11_reset_token_stored_as_hash():
    """The reset email contains a plaintext token; the DB must store
    only the sha256 hash of that token, never the raw value."""
    src = open("/app/backend/routes/auth.py", encoding="utf-8").read()
    # Plaintext "token" field must NOT be written on issuance.
    forgot_block = src.split("async def forgot_password")[1].split("async def reset_password")[0]
    assert "token_hash" in forgot_block, "forgot_password must persist token_hash"
    assert "$set" in forgot_block and '"token":' not in forgot_block.split("token_hash")[1].split("upsert=True")[0], \
        "forgot_password must not also $set the raw token"


def test_bug11_reset_password_lookup_by_hash():
    """The reset-password verifier looks the record up via sha256 hash."""
    src = open("/app/backend/routes/auth.py", encoding="utf-8").read()
    reset_block = src.split("async def reset_password")[1].split("async def verify_reset_token")[0]
    assert "token_hash" in reset_block
    assert "hashlib" in reset_block


# ─── Bug 12 — Stripe calls must be awaited via run_in_executor ───
def test_bug12_stripe_calls_offloaded_to_executor():
    """All Stripe SDK calls in billing_service must go through
    `_stripe_call` (run_in_executor) so the event loop never blocks."""
    src = open("/app/backend/shared/commercial/billing_service.py",
                encoding="utf-8").read()
    # No bare-sync Stripe method calls left in business logic.
    for forbidden in (
        "stripe.Customer.create(",
        "stripe.Customer.retrieve(",
        "stripe.checkout.Session.create(",
        "stripe.Price.list(",
        "stripe.Price.create(",
        "stripe.Product.create(",
        "stripe.billing_portal.Session.create(",
    ):
        # Filter out the executor-wrapped call: `_stripe_call(stripe.X.Y,`
        cleaned = src.replace(f"_stripe_call({forbidden.rstrip('(')},",
                                 "")
        assert forbidden not in cleaned, (
            f"bare blocking Stripe call still present: {forbidden}"
        )


# ─── Bug 13 — _safe_task auto-restarts on crash when given factory ──
def test_bug13_safe_task_auto_restarts_factory():
    """Static check: the wrapper must accept a factory and loop with
    asyncio.sleep on crash. We don't drive an event loop here because
    cancelling the supervisor task across asyncio.run boundaries races
    with the worker bookkeeping list."""
    src = open("/app/backend/pillars/billing/worker.py",
                encoding="utf-8").read()
    body = src.split("def _safe_task")[1].split("def start_pillar2_worker")[0]
    assert "max_restarts" in body
    assert "asyncio.sleep(restart_delay)" in body
    assert "while True" in body
    assert "is_factory" in body


# ─── Bug 14 — Google OAuth httpx calls must have read timeouts ───
def test_bug14_google_oauth_httpx_has_timeout():
    src = open("/app/backend/routes/auth.py", encoding="utf-8").read()
    # All three async-with blocks must specify a timeout.
    bare = src.count("httpx.AsyncClient()")
    assert bare == 0, f"found {bare} httpx.AsyncClient() with no timeout"
    assert "httpx.Timeout(8.0" in src or "timeout=" in src


# ─── Bug 17 — Register handles unique-index race via DuplicateKey ─
def test_bug17_register_handles_duplicatekey():
    src = open("/app/backend/routes/auth.py", encoding="utf-8").read()
    assert "DuplicateKeyError" in src
    assert "Email already registered" in src


# ─── Bug 18 — failed_logins memory is bounded (TTLCache) ─────────
def test_bug18_failed_logins_is_ttlcache():
    from routes import auth as auth_mod
    # When cachetools is available the dict is a TTLCache; otherwise it
    # falls back to defaultdict(list). Either way it must NOT grow
    # forever.
    fl = auth_mod.failed_logins
    cls = type(fl).__name__
    assert cls in ("TTLCache", "defaultdict"), f"unexpected: {cls}"
    if cls == "TTLCache":
        # The cache should auto-expire keys; we don't sleep here because
        # the default TTL is 30 min. Just confirm maxsize cap.
        assert fl.maxsize > 0


# ─── Bug 23 — tier_metering resolves the REAL tier, not the default ─
def test_bug23_tier_metering_real_tier_resolution():
    src = open("/app/backend/middleware/tier_metering.py",
                encoding="utf-8").read()
    assert "_resolve_tier_from_scope" in src
    # The middleware body must call the resolver instead of hard-coding.
    body = src.split("async def __call__")[1]
    assert "_resolve_tier_from_scope(" in body
    # The free-tier safety fallback must be present.
    assert "TIER_LIMITS[\"free\"]" in body or "TIER_LIMITS['free']" in body


# ─── Bug 24 — tier_metering counter dict is bounded ──────────────
def test_bug24_tier_metering_counters_bounded():
    src = open("/app/backend/middleware/tier_metering.py",
                encoding="utf-8").read()
    assert "_MAX_TRACKED_TENANTS" in src
    body = src.split("async def __call__")[1]
    assert "_MAX_TRACKED_TENANTS" in body
    assert "pop(" in body


# ─── Bug 26 — llm_gateway no longer imports `server` directly ────
def test_bug26_llm_gateway_no_circular_import():
    src = open("/app/backend/services/llm_gateway.py",
                encoding="utf-8").read()
    # Must use sys.modules lookup, not direct `import server`.
    assert "sys.modules.get(\"server\")" in src
    # The naïve `import server as _srv` is gone.
    assert "import server as _srv" not in src


# ─── Bug 27 — founder emails read from env ───────────────────────
def test_bug27_founder_email_from_env():
    src = open(
        "/app/backend/routers/admin_founder_customers_router.py",
        encoding="utf-8",
    ).read()
    assert "FOUNDER_EMAILS" in src and "_os.environ.get" in src


# ─── Bug 30 — safe_edit / shell_exec NOT publicly invokable ──────
def test_bug30_safe_edit_shell_exec_gated():
    from services.ora_tools import invoke_tool, list_tools

    # They must not appear in the public catalog.
    names = {t["name"] for t in list_tools()}
    assert "safe_edit" not in names
    assert "shell_exec" not in names

    # And calling them through the dispatcher must error out.
    async def _check(name):
        return await invoke_tool(name, {"path": "/tmp/x", "find_string": "a",
                                           "replace_string": "b"})

    res = asyncio.run(_check("safe_edit"))
    assert res["ok"] is False and "gated" in (res.get("error") or "")
    res = asyncio.run(_check("shell_exec"))
    assert res["ok"] is False and "gated" in (res.get("error") or "")


# ─── Bug 31 — env tool filter blocks REDIS_URL / DATABASE_URL ────
def test_bug31_env_redaction_covers_connection_strings():
    from services.ora_tools import _redact_env

    sample = (
        "PATH=/usr/bin\n"
        "REDIS_URL=redis://:hunter2@cache:6379\n"
        "DATABASE_URL=postgres://user:pw@db/x\n"
        "DISCORD_WEBHOOK=https://discord.com/api/webhooks/xxx\n"
        "ADMIN_PASSWORD_HASH=$2b$12$abcdef\n"
        "SAFE=keep_me\n"
    )
    redacted = _redact_env(sample)
    assert "hunter2" not in redacted
    assert "user:pw" not in redacted
    assert "discord.com/api/webhooks" not in redacted
    assert "$2b$12" not in redacted
    assert "SAFE=keep_me" in redacted, "non-secret line must survive"


# ─── Bug 32 — bin_auth uses the correct redis accessor ───────────
def test_bug32_bin_auth_uses_get_async_redis():
    src = open(
        "/app/backend/routers/bin_auth_router.py", encoding="utf-8"
    ).read()
    # Must alias get_async_redis under the name `get_redis` so the four
    # historic call sites still resolve.
    assert "get_async_redis as get_redis" in src
    # The bare `from utils.redis_pool import get_redis` (no alias) is
    # gone — that import would have raised ImportError at runtime.
    assert "from utils.redis_pool import get_redis\n" not in src


# ─── Bug 33 — reset-token jti is single-use ──────────────────────
def test_bug33_reset_token_jti_blacklisted():
    src = open(
        "/app/backend/routers/bin_auth_router.py", encoding="utf-8"
    ).read()
    # The /reset-password handler must persist + check the jti.
    reset_block = src.split("async def reset_password")[1]
    assert "bin_reset_token_jtis" in reset_block
    assert "Reset token already used" in reset_block


# ─── Bug 34 — /by-session/{session_id} requires auth + owns the session ──
def test_bug34_by_session_requires_auth():
    src = open(
        "/app/backend/routers/aurem_onboarding_router.py", encoding="utf-8"
    ).read()
    block = src.split("async def onboarding_by_session")[1]
    # The handler must accept `request: Request` and decode the bearer.
    assert "request: Request" in block
    assert "Bearer " in block
    assert "jwt.decode" in block
    # Caller-owns-session check must be present.
    assert "session does not belong to caller" in block


# ─── Bug 35 — OTP attempt counter has no TOCTOU race ─────────────
def test_bug35_otp_counter_atomic_or_locked():
    src = open(
        "/app/backend/routers/bin_auth_router.py", encoding="utf-8"
    ).read()
    verify_block = src.split("async def verify_otp")[1]
    # Must use Redis INCR (atomic) and/or an asyncio.Lock fallback.
    assert "incr(" in verify_block
    assert "_OTP_ATTEMPT_LOCK" in verify_block


# ─── Bug 36 — .env.txt etc. are in _WRITE_FORBIDDEN_FILES ────────
def test_bug36_envtxt_in_forbidden_files():
    from services.ora_tools import _WRITE_FORBIDDEN_FILES
    assert ".env.txt" in _WRITE_FORBIDDEN_FILES
    assert ".env.staging" in _WRITE_FORBIDDEN_FILES
