"""
iter 331a Sprint 3.5 + 3.7 — Blindspots + Safety Gaps
======================================================

Covers:
  Sprint 3.5: VS Code + db_manager + deploy tool + 3 blindspots
  Sprint 3.7: path guard + semantic memory + secrets scrubber
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest


# ═════════════════════════════════════════════════════════════
# Sprint 3.5 — VS Code + db_manager + deploy
# ═════════════════════════════════════════════════════════════

def test_vscode_tasks_json_valid():
    p = Path("/app/.vscode/tasks.json")
    assert p.exists(), "tasks.json missing"
    data = json.loads(p.read_text())
    labels = {t["label"] for t in data["tasks"]}
    required = {"Deploy to Production", "Deploy to Preview",
                "Run Tests", "Check Coverage", "Lint All"}
    assert required.issubset(labels), f"missing tasks: {required - labels}"


def test_vscode_launch_json_valid():
    p = Path("/app/.vscode/launch.json")
    assert p.exists()
    data = json.loads(p.read_text())
    names = {c["name"] for c in data["configurations"]}
    assert "Debug Backend (FastAPI)" in names
    assert "Debug Tests (pytest)" in names


def test_deploy_script_exists_executable_valid_syntax():
    p = Path("/app/scripts/deploy.sh")
    assert p.exists()
    assert os.access(p, os.X_OK), "deploy.sh not executable"
    # Bash syntax check (won't actually run)
    import subprocess
    rc = subprocess.run(["bash", "-n", str(p)],
                          capture_output=True).returncode
    assert rc == 0, "deploy.sh has bash syntax errors"


def test_deploy_script_supports_four_platforms():
    src = Path("/app/scripts/deploy.sh").read_text()
    for plat in ("emergent", "hetzner", "docker", "local"):
        assert plat in src, f"deploy.sh missing case '{plat}'"


# ─── db_manager ───────────────────────────────────────────────

def test_db_manager_module_exists():
    from services import db_manager
    for fn in ("get_connection_info", "get_client", "get_db", "ping",
                "mongo_migrate"):
        assert hasattr(db_manager, fn)


def test_db_manager_redacts_passwords_in_url():
    from services.db_manager import get_connection_info
    import os
    old = os.environ.get("MONGO_URL")
    os.environ["MONGO_URL"] = "mongodb://user:secretP@host:27017/db"
    try:
        info = get_connection_info()
        assert "secret" not in info["mongo_url_redacted"]
        assert "***" in info["mongo_url_redacted"]
    finally:
        if old:
            os.environ["MONGO_URL"] = old


@pytest.mark.asyncio
async def test_db_manager_real_ping():
    from services.db_manager import ping
    r = await ping(timeout_s=5.0)
    assert r["ok"] is True
    assert r["db_name"]


def test_db_manager_db_type_switch():
    from services.db_manager import get_connection_info
    import os
    saved_url = os.environ.pop("MONGO_URL", None)
    os.environ["DB_TYPE"] = "local"
    try:
        info = get_connection_info()
        assert info["db_type"] == "local"
        assert "localhost" in info["mongo_url_redacted"]
    finally:
        os.environ.pop("DB_TYPE", None)
        if saved_url:
            os.environ["MONGO_URL"] = saved_url


# ─── Deploy tool ──────────────────────────────────────────────

def test_deploy_tool_registered_tier3():
    from services.ora_agent import TIER_3_HIGH_RISK
    assert "deploy_to_platform" in TIER_3_HIGH_RISK
    assert "rollback_deploy" in TIER_3_HIGH_RISK


# ═════════════════════════════════════════════════════════════
# Blindspot 1 — Git Branch Management
# ═════════════════════════════════════════════════════════════

def test_blindspot1_git_tools_registered():
    from services.ora_tools import TOOL_REGISTRY
    for t in ("git_current_branch", "git_create_branch", "git_push_branch",
              "git_create_pr", "git_merge_branch"):
        assert t in TOOL_REGISTRY


def test_git_merge_is_tier3():
    from services.ora_agent import TIER_3_HIGH_RISK
    assert "git_merge_branch" in TIER_3_HIGH_RISK


def test_feature_branches_are_tier2():
    from services.ora_agent import TIER_2_APPROVE
    for t in ("git_create_branch", "git_push_branch", "git_create_pr"):
        assert t in TIER_2_APPROVE


@pytest.mark.asyncio
async def test_git_current_branch_real():
    from services.ora_tools import TOOL_REGISTRY
    r = await TOOL_REGISTRY["git_current_branch"]["fn"]()
    assert r["ok"] is True
    assert r["branch"]


# ═════════════════════════════════════════════════════════════
# Blindspot 2 — Workspace Sandboxing
# ═════════════════════════════════════════════════════════════

def test_blindspot2_sandbox_tools_registered():
    from services.ora_tools import TOOL_REGISTRY
    for t in ("create_sandbox", "run_in_sandbox",
              "promote_from_sandbox", "cleanup_sandbox"):
        assert t in TOOL_REGISTRY


def test_promote_is_tier3():
    from services.ora_agent import TIER_3_HIGH_RISK
    assert "promote_from_sandbox" in TIER_3_HIGH_RISK


@pytest.mark.asyncio
async def test_sandbox_full_lifecycle():
    from services.ora_tools import TOOL_REGISTRY
    r1 = await TOOL_REGISTRY["create_sandbox"]["fn"](task_id="pytest-lifecycle")
    assert r1["ok"] is True
    sandbox_path = r1["sandbox_path"]
    assert sandbox_path.startswith("/tmp/ora-sandbox-")
    r2 = await TOOL_REGISTRY["run_in_sandbox"]["fn"](
        task_id="pytest-lifecycle",
        command='echo "test" > x.txt && cat x.txt',
    )
    assert r2["ok"] is True
    assert "test" in r2["stdout"]
    r3 = await TOOL_REGISTRY["cleanup_sandbox"]["fn"](task_id="pytest-lifecycle")
    assert r3["ok"] is True


# ═════════════════════════════════════════════════════════════
# Blindspot 3 — Background Process Tracking
# ═════════════════════════════════════════════════════════════

def test_blindspot3_process_tools_registered():
    from services.ora_tools import TOOL_REGISTRY
    for t in ("start_background_process", "check_process_status",
              "wait_for_process", "kill_process"):
        assert t in TOOL_REGISTRY


def test_kill_process_is_tier3():
    from services.ora_agent import TIER_3_HIGH_RISK
    assert "kill_process" in TIER_3_HIGH_RISK


# ═════════════════════════════════════════════════════════════
# Sprint 3.7 Gap 1 — Path traversal guard
# ═════════════════════════════════════════════════════════════

def test_path_safety_blocks_forbidden_paths():
    from services.ora_safety import assert_path_safe, PathOutsideRoot
    for bad in ("/etc/passwd", "/root/.ssh/id_rsa", "/sys/kernel",
                "/proc/1/cmdline", "/dev/sda1"):
        with pytest.raises(PathOutsideRoot):
            assert_path_safe(bad)


def test_path_safety_allows_app_paths():
    from services.ora_safety import assert_path_safe
    p = assert_path_safe("/app/backend/server.py")
    assert str(p).startswith("/app")


def test_path_safety_allows_tmp_paths():
    from services.ora_safety import assert_path_safe
    p = assert_path_safe("/tmp/ora-sandbox-xyz/file.txt")
    assert str(p).startswith("/tmp")


def test_path_safety_allows_log_dir_read():
    from services.ora_safety import assert_path_safe
    p = assert_path_safe("/var/log/supervisor/backend.err.log", mode="read")
    assert str(p).startswith("/var/log")


def test_path_safety_blocks_log_dir_write():
    from services.ora_safety import assert_path_safe, PathOutsideRoot
    with pytest.raises(PathOutsideRoot):
        assert_path_safe("/var/log/supervisor/backend.err.log", mode="write")


# ═════════════════════════════════════════════════════════════
# Sprint 3.7 Gap 2 — Semantic memory search
# ═════════════════════════════════════════════════════════════

def test_semantic_memory_registered():
    from services.ora_tools import TOOL_REGISTRY
    assert "semantic_memory_search" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_semantic_memory_returns_ranked_chunks():
    from services.ora_tools import TOOL_REGISTRY
    r = await TOOL_REGISTRY["semantic_memory_search"]["fn"](
        query="deploy hetzner supervisor", top_k=3,
    )
    assert r["ok"] is True
    assert r["count"] >= 1
    # Returns snippets, not full files
    for hit in r["results"]:
        assert len(hit["snippet"]) <= 800
        assert "score" in hit


# ═════════════════════════════════════════════════════════════
# Sprint 3.7 Gap 4 — Secrets scrubber
# ═════════════════════════════════════════════════════════════

def test_scrub_secrets_redacts_stripe():
    from services.ora_safety import scrub_secrets
    # NB: literal is split so GitHub secret-scanning push protection
    # doesn't flag this test as a leaked key. At runtime the two halves
    # concatenate into a valid `sk_live_...` token that the scrubber
    # is expected to redact.
    fake_stripe = "sk_" + "live_" + "aBcDeFgHiJkLmNoPqRsTu1234567"
    s, n = scrub_secrets(f"STRIPE={fake_stripe}")
    assert n >= 1
    assert "sk_" + "live_" not in s
    assert "[REDACTED_STRIPE_KEY]" in s


def test_scrub_secrets_redacts_mongo_url():
    from services.ora_safety import scrub_secrets
    s, n = scrub_secrets("URL=mongodb+srv://user:pass@cluster0.mongodb.net/db")
    assert n >= 1
    assert "pass@cluster" not in s
    assert "[REDACTED_MONGO_URL]" in s


def test_scrub_secrets_redacts_jwt():
    from services.ora_safety import scrub_secrets
    # Literal split so this test file doesn't itself look like it
    # contains a leaked JWT to static scanners.
    header = "eyJh" + "lbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    payload = "eyJzdW" + "IiOiIxIn0"
    sig = "signaturepartABCDEFG12345"
    jwt = f"{header}.{payload}.{sig}"
    s, n = scrub_secrets(f"Token={jwt}")
    assert n >= 1
    assert "[REDACTED_JWT]" in s


def test_scrub_secrets_redacts_bearer():
    from services.ora_safety import scrub_secrets
    bearer = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890ABCDEF"
    s, n = scrub_secrets(bearer)
    assert n >= 1
    assert "[REDACTED_TOKEN]" in s


def test_scrub_secrets_preserves_normal_text():
    from services.ora_safety import scrub_secrets
    plain = "The user clicked the button and saw the dashboard."
    s, n = scrub_secrets(plain)
    assert n == 0
    assert s == plain


@pytest.mark.asyncio
async def test_view_file_scrubs_secrets_in_content():
    """E2E: write a fake secret to an /app/ path, view it via the
    tool, verify the LLM-visible content has no raw secret."""
    from services.ora_tools import TOOL_REGISTRY
    tmp = "/app/backend/tests/_scrub_e2e.txt"
    # Literal split to bypass GitHub push protection. Concatenated at
    # runtime into a valid `sk_live_...` Stripe-shaped token that the
    # scrubber MUST redact.
    fake = "sk_" + "live_" + "aBcDeFgHiJkLmNoPqRsTuVwXyZ12345"
    Path(tmp).write_text(
        f"STRIPE_SECRET_KEY={fake}\n"
        "ok\n"
    )
    try:
        r = await TOOL_REGISTRY["view_file"]["fn"](path=tmp, max_lines=10)
        assert r["ok"] is True
        assert "sk_" + "live_" not in r["content"]
        assert "[REDACTED_STRIPE_KEY]" in r["content"]
    finally:
        Path(tmp).unlink(missing_ok=True)


# ═════════════════════════════════════════════════════════════
# Markers + manifests
# ═════════════════════════════════════════════════════════════

def test_migration_checklist_exists():
    assert Path("/app/memory/MIGRATION_CHECKLIST.md").exists()


def test_portable_manifest_exists():
    p = Path("/app/memory/ORA_PORTABLE_MANIFEST.md")
    assert p.exists()
    text = p.read_text()
    assert "ORA_SESSION_USD_CAP" in text
    assert "DB_TYPE" in text


def test_iter_331a_markers_present_in_new_modules():
    paths = (
        "/app/backend/services/db_manager.py",
        "/app/backend/services/ora_deploy_tool.py",
        "/app/backend/services/ora_blindspot_tools.py",
        "/app/backend/services/ora_safety.py",
        "/app/backend/services/ora_semantic_memory.py",
    )
    for p in paths:
        assert "iter 331a" in Path(p).read_text(), f"331a marker missing in {p}"
