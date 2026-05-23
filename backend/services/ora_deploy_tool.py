"""
services/ora_deploy_tool.py — iter 331a Sprint 3.5

Two ORA tools wrapped around `scripts/deploy.sh`:

  - deploy_to_platform(platform, environment, run_tests_first=True)
      Tier-3 (always explicit founder approval — destructive at scale).
      8-step deploy: pytest → coverage → lint → checkpoint → push →
      health-check → smoke-tests → report.

  - rollback_deploy(steps_back=1)
      Tier-3 (always explicit).
      git revert last N commits, redeploy, verify.

Portability: zero Emergent imports. Reads DEPLOY_PLATFORM env var to
decide where to deploy. Works locally, on Hetzner, in Docker, etc.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
from pathlib import Path

logger = logging.getLogger(__name__)

_DEPLOY_SCRIPT = Path(os.environ.get("ORA_DEPLOY_SCRIPT", "/app/scripts/deploy.sh"))
_APP_ROOT = Path(os.environ.get("ORA_TOOLS_ROOT", "/app"))


async def deploy_to_platform(
    platform: str = "",
    environment: str = "preview",
    run_tests_first: bool = True,
) -> dict:
    """Run the 8-step safe deploy.

    Args:
      platform:     emergent | hetzner | docker | local (defaults to
                    DEPLOY_PLATFORM env var, else 'emergent')
      environment:  preview | production
      run_tests_first: if False, skip the pytest gate (NOT recommended)

    Returns the deploy script's stdout/stderr + exit code.
    """
    if platform:
        os.environ["DEPLOY_PLATFORM"] = platform
    if not _DEPLOY_SCRIPT.exists():
        return {
            "ok":    False,
            "error": f"deploy script missing at {_DEPLOY_SCRIPT}. "
                     f"Set ORA_DEPLOY_SCRIPT or create /app/scripts/deploy.sh.",
        }

    env = os.environ.copy()
    env["DEPLOY_ENV"] = environment
    env["DEPLOY_PLATFORM"] = env.get("DEPLOY_PLATFORM") or "emergent"
    if not run_tests_first:
        env["SKIP_TESTS"] = "1"

    cmd = ["bash", str(_DEPLOY_SCRIPT), environment]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            cwd=str(_APP_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=900)
        out = stdout.decode("utf-8", errors="replace")
        return {
            "ok":          proc.returncode == 0,
            "exit_code":   proc.returncode,
            "platform":    env["DEPLOY_PLATFORM"],
            "environment": environment,
            "tail":        "\n".join(out.splitlines()[-40:]),
            "full":        out[:16000],
        }
    except asyncio.TimeoutError:
        return {"ok": False, "error": "deploy exceeded 15 min timeout"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def rollback_deploy(steps_back: int = 1) -> dict:
    """Revert last N commits + redeploy + verify.

    Args:
      steps_back: number of commits to revert (default 1, max 10)
    """
    n = max(1, min(int(steps_back or 1), 10))
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "revert", "--no-edit", f"HEAD~{n}..HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(_APP_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        revert_out = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return {
                "ok":         False,
                "error":      "git revert failed",
                "revert_out": revert_out,
            }
    except Exception as e:
        return {"ok": False, "error": f"revert failed: {e}"}

    # Re-deploy with the reverted code.
    deploy_result = await deploy_to_platform(
        platform="", environment="preview",
        run_tests_first=True,
    )
    return {
        "ok":             deploy_result.get("ok", False),
        "reverted_commits": n,
        "revert_out":     revert_out,
        "redeploy":       deploy_result,
    }


TOOL_REGISTRY_PATCH = {
    "deploy_to_platform": {
        "fn": deploy_to_platform,
        "args_spec": {
            "platform":         "str — emergent|hetzner|docker|local",
            "environment":      "str — preview|production",
            "run_tests_first":  "bool — default True (don't skip!)",
        },
        "description": (
            "TIER 3 (CONFIRM required). Runs the 8-step safe deploy: "
            "pytest → coverage → lint → git checkpoint → platform push "
            "→ health check → 3-endpoint smoke test → report. Aborts on "
            "any failure. Read scripts/deploy.sh for the exact script."
        ),
    },
    "rollback_deploy": {
        "fn": rollback_deploy,
        "args_spec": {
            "steps_back": "int — number of commits to revert (1..10)",
        },
        "description": (
            "TIER 3 (CONFIRM required). Reverts the last N commits and "
            "redeploys with the older code. Health-checked after."
        ),
    },
}


def splice_into(tool_registry: dict) -> int:
    tool_registry.update(TOOL_REGISTRY_PATCH)
    return len(TOOL_REGISTRY_PATCH)
