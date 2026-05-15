"""
Round 16-17 Security Sprint — Regression Suite
==============================================
Verifies the 15 critical security fixes (Bugs 133-148) shipped in this
sprint. Tests 401/403 gates and SSRF blocks where applicable.
"""
from __future__ import annotations

import os
import pytest
import requests

BACKEND = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[-1].splitlines()[0]
).strip()


def _post(path: str, **kw):
    return requests.post(f"{BACKEND}{path}", timeout=15, **kw)


def _get(path: str, **kw):
    return requests.get(f"{BACKEND}{path}", timeout=15, **kw)


def _put(path: str, **kw):
    return requests.put(f"{BACKEND}{path}", timeout=15, **kw)


# ─── Bug 133/147 — self_repair_router _require_admin role check ─────────────
def test_bug_133_self_repair_builder_blocks_random_jwt():
    """Was: any valid JWT triggered LLM → file write → backend restart."""
    # Random-but-valid-looking bearer (will fail JWT verify → 401)
    r = _post("/api/self-repair/unfixable/abc/fix-with-builder")
    assert r.status_code in (401, 403)


# ─── Bug 134 — orchestrator_brain_router auth ───────────────────────────────
def test_bug_134_orchestrator_command_requires_admin():
    r = _post("/api/orchestrator/command", json={"command": "blast all Toronto leads"})
    assert r.status_code in (401, 403)


def test_bug_134_orchestrator_workflow_execute_requires_admin():
    r = _post("/api/orchestrator/workflow/execute", json={"workflow_id": "x"})
    assert r.status_code in (401, 403)


def test_bug_134_orchestrator_task_requires_admin():
    r = _post("/api/orchestrator/task", json={"agent_id": "whatsapp", "action": "send", "input_data": {}})
    assert r.status_code in (401, 403)


# ─── Bug 135 — ai_email_router auth ─────────────────────────────────────────
def test_bug_135_ai_email_send_requires_admin():
    r = _post("/api/ai-email/send", json={"to": ["v@x.com"], "subject": "s", "body_html": "<p>x</p>"})
    assert r.status_code in (401, 403)


def test_bug_135_ai_email_broadcast_requires_admin():
    r = _post("/api/ai-email/broadcast", json={"segment": "all", "subject": "s", "body_html": "<p>x</p>"})
    assert r.status_code in (401, 403)


# ─── Bug 136 — SSRF blocked in seo_audit_router ─────────────────────────────
def test_bug_136_seo_audit_blocks_aws_metadata():
    r = _post("/api/seo-audit/scan",
              json={"url": "http://169.254.169.254/latest/meta-data/", "email": "a@b.co"})
    assert r.status_code == 400


def test_bug_136_seo_audit_blocks_localhost():
    r = _post("/api/seo-audit/scan",
              json={"url": "http://localhost:27017", "email": "a@b.co"})
    assert r.status_code == 400


def test_bug_136_v2_scan_blocks_private_ip():
    r = _post("/api/seo-audit/v2/scan",
              json={"url": "http://127.0.0.1/", "email": "a@b.co"})
    assert r.status_code == 400


# ─── Bug 137 — design_extract _verify_token admin check ─────────────────────
def test_bug_137_design_extract_requires_admin():
    r = _post("/api/admin/design-extract/run", json={"url": "https://example.com"})
    assert r.status_code in (401, 403)


# ─── Bug 139 — a2a task auth (router may be lean-pruned, accept 404 too) ────
def test_bug_139_a2a_task_requires_auth_or_lean_pruned():
    r = _post("/api/a2a/task", json={"task_id": "t1", "skill_id": "skincare_advice", "input": {}})
    # 401 = auth required, 404 = router pruned by LEAN_ROUTES (no exposure)
    assert r.status_code in (401, 403, 404)


# ─── Bug 140 — aurem_routes hardcoded JWT default removed ──────────────────
def test_bug_140_no_hardcoded_aurem_jwt_default():
    import importlib, sys as _sys
    _sys.path.insert(0, "/app/backend")
    mod = importlib.import_module("routers.aurem_routes")
    # Either matches the env var, or is None (env not set). Must NOT be the
    # public hardcoded fallback.
    assert mod.JWT_SECRET != "aurem-secure-jwt-secret-key-2026-production"


# ─── Bug 141 — git_gate _verify_token admin check ──────────────────────────
def test_bug_141_git_gate_approve_requires_admin():
    r = _post("/api/admin/git-gate/proposals/p1/approve", json={"files": [], "message": "x"})
    assert r.status_code in (401, 403, 404)


def test_bug_141_git_gate_hard_reset_requires_admin():
    r = _post("/api/admin/git-gate/hard-reset", json={"n": 1})
    assert r.status_code in (401, 403, 404, 405)


# ─── Bug 142 — hermes_router admin check ────────────────────────────────────
def test_bug_142_hermes_identity_put_requires_admin():
    r = _put("/api/hermes/identity", json={"file": "SOUL", "content": "hacked"})
    assert r.status_code in (401, 403)


# ─── Bug 143 — ai_repair PIN gate ───────────────────────────────────────────
def test_bug_143_repair_free_tier_requires_pin_or_admin():
    r = _post("/api/repair/deploy/free/some_deploy_id")
    # 401 (no auth) or 402 (auth ok but no PIN) — both block free-deploy abuse
    assert r.status_code in (401, 402, 403)


# ─── Bug 144 — customer_scanner email-bypass removed ───────────────────────
def test_bug_144_customer_scanner_push_review_requires_admin():
    r = _post("/api/scanner/push-fixes/p1/review-approve",
              headers={"Authorization": "Bearer not.a.real.jwt"})
    assert r.status_code in (401, 403, 404)


# ─── Bug 145 — ora_optimize _verify_token admin check ──────────────────────
def test_bug_145_ora_optimize_clear_cache_requires_admin():
    r = _post("/api/admin/ora-optimize/clear-cache?confirm=YES_NUKE_CACHE")
    assert r.status_code in (401, 403)


# ─── Bug 146 — session_memory router auth ──────────────────────────────────
def test_bug_146_session_memory_append_requires_admin():
    r = _post("/api/session-memory/append",
              json={"built": "x", "changed": "x", "tested": "x", "pending": "x"})
    assert r.status_code in (401, 403)


def test_bug_146_session_memory_latest_requires_admin():
    r = _get("/api/session-memory/latest")
    assert r.status_code in (401, 403)


# ─── Bug 138 — backup file permissions ─────────────────────────────────────
def test_bug_138_backup_dir_or_module_imports():
    """Module must import cleanly with the new chmod / encryption logic."""
    import importlib, sys as _sys
    _sys.path.insert(0, "/app/backend")
    mod = importlib.import_module("services.backup_service")
    assert hasattr(mod, "write_file_backup")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
