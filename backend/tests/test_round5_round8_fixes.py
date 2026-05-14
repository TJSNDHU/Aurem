"""
Regression tests — Round 5/6/7/8 security & logic bug fixes.
============================================================
Each test name maps 1:1 to the bug number from the audit reports.
Static-source verification (no live HTTP) keeps these fast and pod-
independent.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, "/app/backend")


def _read(path):
    return open(path, encoding="utf-8").read()


# ─── Bug 39 — admin role check on every formerly-broken router ───
ROUTERS_NEEDING_ADMIN_CHECK = [
    "/app/backend/routers/admin_customers_router.py",
    "/app/backend/routers/db_optimizer_router.py",
    "/app/backend/routers/news_monitor_router.py",
    "/app/backend/routers/shopify_pulse_router.py",
    "/app/backend/routers/churn_prediction_router.py",
    "/app/backend/routers/website_builder_router.py",
    "/app/backend/routers/fraud_prevention.py",
    "/app/backend/routers/agent_observatory_router.py",
    "/app/backend/routers/camofox_router.py",
    "/app/backend/routers/dark_scout_router.py",
    "/app/backend/pillars/sales/routes/_shared.py",
]


@pytest.mark.parametrize("path", ROUTERS_NEEDING_ADMIN_CHECK)
def test_bug39_router_has_admin_role_check(path):
    src = _read(path)
    assert "is_admin_email" in src or "is_admin" in src, (
        f"{path} still trusts a bare-decode JWT — Bug-fix #39 missing"
    )
    # The role-check phrase that the patch leaves behind.
    assert "Admin access required" in src or "admin only" in src.lower()


# ─── Bug 40 — deep-scan auth + SSRF blocklist ────────────────────
def test_bug40_deep_scan_auth_and_ssrf_guard():
    src = _read("/app/backend/routers/deep_scan_router.py")
    assert "_require_auth" in src
    assert "_is_private_or_loopback" in src
    # Decorator order requires the auth call inside the body.
    body = src.split("async def deep_scan")[1]
    assert "_require_auth(request)" in body


# ─── Bug 41 — Google OAuth redirect allowlist ───────────────────
def test_bug41_oauth_redirect_allowlist():
    src = _read("/app/backend/routers/google_oauth_router.py")
    assert "REDISCAR" not in src  # sanity
    assert "_safe_redirect" in src
    assert "REDIRECT_ALLOWLIST" in src


# ─── Bug 42 — shortlink create requires auth ─────────────────────
def test_bug42_shortlink_requires_auth():
    src = _read("/app/backend/routers/shortlink_router.py")
    assert "_require_auth(request)" in src
    block = src.split("async def shortlinks_create")[1]
    assert "_require_auth(request)" in block


# ─── Bug 43 — Twilio call moved off the event loop ───────────────
def test_bug43_twilio_uses_to_thread():
    src = _read("/app/backend/services/sms_engine.py")
    block = src.split("async def send_message")[1]
    # The new path must use asyncio.to_thread, not a bare sync call.
    assert "to_thread" in block
    # The bare call line is gone.
    assert "client.messages.create(\n" not in block


# ─── Bug 46 — settings can't change privileged fields ────────────
def test_bug46_profile_update_no_email_or_role():
    src = _read("/app/backend/routers/settings_router.py")
    # ProfileUpdate must not even declare `email`.
    profile_def = src.split("class ProfileUpdate(BaseModel):")[1].split("class ")[0]
    assert "email:" not in profile_def, "Bug-fix #46: email leaked back into ProfileUpdate"
    # Defence-in-depth — explicit pop list inside the handler.
    upd_fn = src.split("update_profile")[1]
    for k in ("email", "is_admin", "is_super_admin", "role", "tenant_id"):
        assert f"\"{k}\"" in upd_fn or f"'{k}'" in upd_fn


# ─── Bug 47 — admin seed refuses to run without env var ──────────
def test_bug47_admin_seed_requires_env_password():
    src = _read("/app/backend/bootstrap/background_init.py")
    assert "vyoOeNW" not in src, "the publicly-committed default must be deleted"
    assert "ADMIN_SEED_PASSWORD" in src
    assert "len(_seed_pw)" in src or "Admin seed skipped" in src


# ─── Bug 48 — /api/aurem/chat requires auth ──────────────────────
def test_bug48_aurem_chat_requires_auth():
    src = _read("/app/backend/routers/aurem_chat.py")
    body = src.split("async def aurem_chat")[1].split("async def ")[0]
    assert "Authorization required" in body
    assert "jwt.decode" in body or "_jwt.decode" in body


# ─── Bug 49 — vault refuses to encrypt with default key ──────────
def test_bug49_vault_requires_encryption_key():
    src = _read("/app/backend/routers/vault_router.py")
    # The hardcoded default must not be assigned anywhere.
    assert 'ENCRYPTION_KEY", "aurem32' not in src
    assert "AUREM_ENCRYPTION_KEY not configured" in src


# ─── Bug 50 — XSS escape in AdminConsole exportPdf ──────────────
def test_bug50_adminconsole_topic_escaped():
    src = _read("/app/frontend/src/platform/AdminConsole.jsx")
    # Look at the exportPdf body up to the closing `};`.
    assert "const exportPdf =" in src
    assert "safeTitle" in src
    # The interpolation in the <title> tag must use safeTitle, not raw.
    assert "<title>Intelligence Report — ${safeTitle}" in src
    # And the raw interpolation must not be in the actively-used <title>.
    assert "<title>Intelligence Report — ${m.inputs?.topic" not in src


# ─── Bug 55 — db_query verify_admin actually verifies ────────────
def test_bug55_db_query_verify_admin_is_real():
    src = _read("/app/backend/routes/db_query_routes.py")
    # The TODO comment is gone.
    assert "In production, verify JWT token here" not in src
    block = src.split("async def verify_admin")[1]
    assert "jwt" in block.lower()
    assert "Admin access required" in block


# ─── Bug 56 — admin action AI execute requires admin ─────────────
def test_bug56_admin_action_ai_execute_requires_admin():
    src = _read("/app/backend/routes/admin_action_ai_routes.py")
    body = src.split("async def execute_action")[1]
    assert "Authorization required" in body
    assert "Admin access required" in body


# ─── Bug 57 — setup-owner disabled without env key ───────────────
def test_bug57_setup_owner_no_default_key():
    src = _read("/app/backend/routes/rbac.py")
    # The committed default literal must not appear as an os.environ fallback.
    assert 'SETUP_KEY", "reroots-setup-2026"' not in src
    block = src.split("async def setup_owner_account")[1]
    assert "Owner setup is disabled" in block or "SETUP_KEY" in block


# ─── Bug 58 — Retell webhook rejects missing signature ───────────
def test_bug58_retell_rejects_missing_sig():
    src = _read("/app/backend/routers/voice_agent_router.py")
    assert "missing signature" in src


# ─── Bug 59 — approval router enforces admin/tenant ──────────────
def test_bug59_approval_admin_tenant_check():
    src = _read("/app/backend/routers/approval_router.py")
    assert "_ensure_can_decide" in src
    block = src.split("async def approve_action")[1].split("async def ")[0]
    assert "_ensure_can_decide" in block


# ─── Bug 60 — no "aurem_default_secret" fallback anywhere ────────
def test_bug60_no_aurem_default_secret_fallback():
    import subprocess
    out = subprocess.run(
        ["grep", "-rln", "aurem_default_secret", "/app/backend/routers/",
         "/app/backend/routes/"],
        capture_output=True, text=True,
    )
    # Only allowed in __pycache__ (stale bytecode).
    leaks = [
        ln for ln in (out.stdout or "").splitlines()
        if ln and "__pycache__" not in ln
    ]
    assert leaks == [], f"Bug 60: still found fallback in: {leaks}"


# ─── Bug 61 — no empty-string JWT_SECRET fallbacks ───────────────
def test_bug61_no_empty_string_jwt_fallback():
    import subprocess
    out = subprocess.run(
        ["grep", "-rln", 'JWT_SECRET", ""',
          "/app/backend/routers/", "/app/backend/routes/",
          "/app/backend/pillars/", "/app/backend/middleware/",
          "/app/backend/services/", "/app/backend/utils/"],
        capture_output=True, text=True,
    )
    leaks = [
        ln for ln in (out.stdout or "").splitlines()
        if ln and "__pycache__" not in ln and "_archive" not in ln
        and "/tests/" not in ln
    ]
    assert leaks == [], f"Bug 61: empty-string fallback still present in: {leaks}"


# ─── Bug 62 — agent harness execute requires admin ──────────────
def test_bug62_agent_harness_admin_required():
    src = _read("/app/backend/routers/agent_harness_router.py")
    block = src.split("async def execute_agent")[1]
    assert "_require_admin" in block


# ─── Bug 63 — RAG admin endpoints require admin ─────────────────
def test_bug63_rag_admin_refresh_requires_admin():
    src = _read("/app/backend/routers/rag_router.py")
    block = src.split("async def admin_refresh_knowledge_base")[1]
    assert "admin_only=True" in block


# ─── Bug 64 — seed endpoint requires admin ──────────────────────
def test_bug64_seed_requires_admin():
    src = _read("/app/backend/routes/seed.py")
    block = src.split("async def seed_database")[1]
    assert "_require_admin(request)" in block


# ─── Bug 65 — founders console removes `email` shortcut ─────────
def test_bug65_founders_console_no_email_shortcut():
    src = _read("/app/backend/routers/founders_console_router.py")
    # The dangerous shortcut was `if ... or payload.get("email"): return payload`.
    # Detect the *executable* pattern (not in a comment).
    code_lines = [
        ln for ln in src.splitlines()
        if 'or payload.get("email"):' in ln and not ln.lstrip().startswith("#")
    ]
    assert not code_lines, f"executable email-shortcut still present: {code_lines}"
    assert "is_admin_email" in src


# ─── Bug 66 — whatsapp_ai router has admin gate ─────────────────
def test_bug66_whatsapp_ai_admin_gated():
    src = _read("/app/backend/routes/whatsapp_ai_routes.py")
    assert "_require_admin" in src
    # Router declares the dependency at construction.
    assert "dependencies=[Depends(_require_admin)]" in src


# ─── Bug 67 — gmail channel router requires owner/admin ─────────
def test_bug67_gmail_owner_or_admin():
    src = _read("/app/backend/routers/gmail_channel_router.py")
    assert "_require_owner_or_admin" in src
    # Every endpoint that takes business_id calls the guard.
    for fn in ("list_messages", "get_message", "send_email", "get_labels",
                "trash_message", "get_profile", "get_thread", "health_check"):
        block = src.split(f"async def {fn}")[1].split("async def ")[0]
        assert "_require_owner_or_admin" in block, (
            f"{fn} doesn't call _require_owner_or_admin — Bug 67 not fully fixed"
        )


# ─── Bug 68 — automations router admin-gated at construction ────
def test_bug68_automations_admin_gated():
    src = _read("/app/backend/routes/automations.py")
    assert "dependencies=[Depends(_require_admin)]" in src


# ─── Bug 69 — phone provision/release/list admin-gated ──────────
def test_bug69_phone_endpoints_admin_gated():
    src = _read("/app/backend/routes/phone_routes.py")
    for line in src.splitlines():
        if line.startswith("@router.post(\"/provision\"") or \
           line.startswith("@router.get(\"/numbers\"") or \
           line.startswith("@router.delete(\"/release\""):
            assert "_require_admin" in line, f"missing admin gate: {line}"


# ─── Bug 70 — no default crypto password ────────────────────────
def test_bug70_no_default_crypto_password():
    src = _read("/app/backend/crypto_engine/router.py")
    # The os.environ fallback literal must be gone.
    assert 'CRYPTO_LOGIN_PASSWORD", "signal123"' not in src
    assert "Crypto auth not configured" in src


# ─── Bug 71 — face/verify enforces lockout + rejects zero descriptor ─
def test_bug71_face_verify_lockout_and_descriptor_guard():
    src = _read("/app/backend/routers/biometric_auth.py")
    block = src.split("async def face_verify")[1].split("async def ")[0]
    assert "Too many failed face verifications" in block
    assert "all(abs(float(v))" in block
    assert "biometric_auth_log.count_documents" in block


# ─── Bug 72 — legion queue has no empty-secret fallback ─────────
def test_bug72_legion_queue_no_empty_secret():
    src = _read("/app/backend/routers/legion_queue_router.py")
    assert "JWT_SECRET_KEY') or ''" not in src
    assert "Server config error" in src
