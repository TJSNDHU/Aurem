"""Run pytest skill — invoke pytest on a path, return summary."""
import asyncio
import os
from typing import Any

from .registry import skill


@skill(
    name="run_tests",
    description=(
        "Run pytest on a test file or directory under /app/backend/tests. "
        "Returns pass/fail counts plus the first 2000 chars of output."
    ),
)
async def run_tests(target: str = "backend/tests",
                       timeout_s: int = 60) -> dict[str, Any]:
    if "/" in target and not target.startswith("backend/"):
        raise ValueError("target must be inside backend/")
    cmd = ["python", "-m", "pytest", target, "-q", "--tb=short"]
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd="/app",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(),
                                              timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        return {"ok": False, "target": target, "error": "timeout"}
    out = stdout.decode("utf-8", errors="replace")
    # Parse "X passed, Y failed" from the last line
    last_line = out.strip().split("\n")[-1]
    return {"ok": proc.returncode == 0, "target": target,
             "returncode": proc.returncode, "summary": last_line,
             "output": out[-2000:]}
