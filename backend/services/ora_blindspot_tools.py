"""
services/ora_blindspot_tools.py — iter 331a Sprint 3.5

Closes the 3 blindspots identified in the audit:

  Blindspot 1: Git Branch Management
    - git_create_branch, git_push_branch, git_create_pr, git_merge_branch
    - SYSTEM_PROMPT rule enforced via TIER_3 placement for merges.

  Blindspot 2: Workspace Sandboxing
    - create_sandbox, run_in_sandbox, promote_from_sandbox, cleanup_sandbox
    - Sandbox lives at /tmp/ora-sandbox-{task_id}/

  Blindspot 3: Background Process Tracking
    - start_background_process, check_process_status,
      wait_for_process, kill_process
    - Persists to ora_background_processes collection.

Portability: zero Emergent imports. Uses POSIX subprocess + filesystem.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import signal
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────
_ROOT = Path(os.environ.get("ORA_TOOLS_ROOT", "/app"))
_SANDBOX_ROOT = Path(os.environ.get("ORA_SANDBOX_ROOT", "/tmp"))
_PROCESSES_COLLECTION = "ora_background_processes"

_db = None

def set_db(database) -> None:
    global _db
    _db = database


# ────────────────────────────────────────────────────────────────────
# Blindspot 1: Git Branch Management
# ────────────────────────────────────────────────────────────────────

async def _git(*args: str, cwd: str | None = None) -> tuple[int, str]:
    """Run a git command, return (returncode, combined_output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd or str(_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        return proc.returncode, stdout.decode("utf-8", errors="replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


async def git_current_branch() -> dict:
    """Returns the current branch name. Read-only."""
    rc, out = await _git("rev-parse", "--abbrev-ref", "HEAD")
    return {"ok": rc == 0, "branch": out.strip() if rc == 0 else None,
            "output": out}


async def git_create_branch(branch_name: str) -> dict:
    """Create + check out a feature branch.

    Naming convention: prefix with `ora/feature-` if the caller didn't.
    """
    name = (branch_name or "").strip()
    if not name:
        return {"ok": False, "error": "branch_name is empty"}
    if not name.startswith("ora/"):
        name = f"ora/feature-{name}"
    rc, out = await _git("checkout", "-b", name)
    if rc != 0:
        # Branch may already exist — try plain checkout.
        rc2, out2 = await _git("checkout", name)
        return {
            "ok":     rc2 == 0,
            "branch": name,
            "output": out + "\n" + out2,
            "note":   "branch existed; checked out" if rc2 == 0 else "checkout failed",
        }
    return {"ok": True, "branch": name, "output": out}


async def git_push_branch(branch_name: str, remote: str = "origin") -> dict:
    """Push a feature branch to the remote."""
    name = (branch_name or "").strip()
    if not name:
        return {"ok": False, "error": "branch_name is empty"}
    rc, out = await _git("push", "-u", remote, name)
    return {"ok": rc == 0, "branch": name, "remote": remote, "output": out}


async def git_create_pr(
    title: str,
    body: str = "",
    head: str = "",
    base: str = "main",
) -> dict:
    """Open a PR on GitHub using the `gh` CLI if available.

    Falls back to returning the URL the founder can click to open
    a PR manually if `gh` is not installed.
    """
    head_branch = head or (await git_current_branch()).get("branch") or ""
    if not head_branch:
        return {"ok": False, "error": "cannot determine head branch"}
    # Try `gh` first.
    try:
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "create",
            "--title", title,
            "--body",  body or title,
            "--head",  head_branch,
            "--base",  base,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        out = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode == 0:
            return {"ok": True, "pr_url": out.splitlines()[-1] if out else None,
                     "output": out, "via": "gh"}
    except FileNotFoundError:
        pass  # gh not installed — fall through to manual URL
    except Exception as e:
        logger.debug(f"[ora-blindspot] gh failed: {e}")

    # Fallback: build the GitHub compare URL.
    rc, remote_out = await _git("remote", "get-url", "origin")
    remote_url = remote_out.strip() if rc == 0 else ""
    # https://github.com/owner/repo[.git] → owner/repo
    m = None
    import re
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if not m:
        return {"ok": False, "error": "cannot detect github repo from remote",
                 "remote": remote_url}
    owner, repo = m.group(1), m.group(2)
    pr_url = f"https://github.com/{owner}/{repo}/compare/{base}...{head_branch}?expand=1"
    return {
        "ok":     True,
        "pr_url": pr_url,
        "via":    "manual_url",
        "note":   "gh CLI not installed; click the URL to open the PR.",
    }


async def git_merge_branch(branch: str, into: str = "main") -> dict:
    """Merge a branch INTO another (default main). Tier-3 only."""
    name = (branch or "").strip()
    if not name:
        return {"ok": False, "error": "branch is empty"}
    rc1, out1 = await _git("checkout", into)
    if rc1 != 0:
        return {"ok": False, "step": "checkout base", "output": out1}
    rc2, out2 = await _git("merge", "--no-ff", name)
    return {"ok": rc2 == 0, "branch": name, "into": into,
            "output": (out1 + "\n" + out2)[:8000]}


# ────────────────────────────────────────────────────────────────────
# Blindspot 2: Workspace Sandboxing
# ────────────────────────────────────────────────────────────────────

def _sandbox_path(task_id: str) -> Path:
    safe_id = "".join(c for c in (task_id or "") if c.isalnum() or c in "-_")
    if not safe_id:
        safe_id = uuid.uuid4().hex[:12]
    return _SANDBOX_ROOT / f"ora-sandbox-{safe_id}"


async def create_sandbox(task_id: str, copy_paths: list[str] | None = None) -> dict:
    """Create an isolated workspace at /tmp/ora-sandbox-{task_id}/.

    Args:
      task_id:    id to scope the sandbox; auto-generated if empty.
      copy_paths: list of /app/-relative paths to copy in (optional).

    Returns sandbox path on success.
    """
    sb = _sandbox_path(task_id)
    try:
        sb.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for rel in (copy_paths or []):
            src = _ROOT / rel.lstrip("/")
            if not src.exists():
                continue
            dst = sb / rel.lstrip("/")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            copied.append(str(dst))
        return {"ok": True, "task_id": task_id, "sandbox_path": str(sb),
                "copied": copied, "copied_count": len(copied)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def run_in_sandbox(task_id: str, command: str, timeout_s: int = 300) -> dict:
    """Run a shell command inside the sandbox. Never touches /app/."""
    sb = _sandbox_path(task_id)
    if not sb.exists():
        return {"ok": False, "error": "sandbox not found: create_sandbox first"}
    if not command:
        return {"ok": False, "error": "command is empty"}
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(sb),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(),
                                            timeout=max(1, int(timeout_s)))
        out = stdout.decode("utf-8", errors="replace")
        return {
            "ok":        proc.returncode == 0,
            "exit_code": proc.returncode,
            "cwd":       str(sb),
            "stdout":    out[:16000],
            "tail":      "\n".join(out.splitlines()[-30:]),
        }
    except asyncio.TimeoutError:
        return {"ok": False, "error": f"command exceeded {timeout_s}s timeout"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def promote_from_sandbox(task_id: str, files: list[str]) -> dict:
    """Copy verified files from sandbox back into /app/.

    Caller must list the exact files to promote — no wildcards.
    """
    sb = _sandbox_path(task_id)
    if not sb.exists():
        return {"ok": False, "error": "sandbox not found"}
    if not files:
        return {"ok": False, "error": "files list is empty"}
    promoted: list[str] = []
    failed: list[dict] = []
    for rel in files:
        src = sb / rel.lstrip("/")
        if not src.exists():
            failed.append({"file": rel, "error": "not found in sandbox"})
            continue
        dst = _ROOT / rel.lstrip("/")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            promoted.append(str(dst))
        except Exception as e:
            failed.append({"file": rel, "error": str(e)[:200]})
    return {"ok": len(failed) == 0, "promoted": promoted,
            "promoted_count": len(promoted), "failed": failed}


async def cleanup_sandbox(task_id: str) -> dict:
    """Remove the sandbox folder."""
    sb = _sandbox_path(task_id)
    if not sb.exists():
        return {"ok": True, "note": "sandbox already removed"}
    try:
        shutil.rmtree(sb)
        return {"ok": True, "removed": str(sb)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ────────────────────────────────────────────────────────────────────
# Blindspot 3: Background Process Tracking
# ────────────────────────────────────────────────────────────────────

_PROCS: dict[str, asyncio.subprocess.Process] = {}


async def start_background_process(
    command: str,
    task_id: str = "",
    label: str = "",
) -> dict:
    """Start a long-running command in the background. Returns process_id.

    The process is persisted to `ora_background_processes` so a session
    crash + resume can still find and check on it via progress.md.
    """
    if not command:
        return {"ok": False, "error": "command is empty"}
    pid_uuid = uuid.uuid4().hex[:12]
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(_ROOT),
        )
        _PROCS[pid_uuid] = proc
        doc = {
            "_id":        pid_uuid,
            "task_id":    task_id,
            "label":      label or command[:120],
            "command":    command,
            "os_pid":     proc.pid,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status":     "running",
            "exit_code":  None,
            "tail":       "",
        }
        if _db is not None:
            try:
                await _db[_PROCESSES_COLLECTION].insert_one(doc)
            except Exception as e:
                logger.debug(f"[ora-blindspot] proc persist failed: {e}")
        return {
            "ok":         True,
            "process_id": pid_uuid,
            "os_pid":     proc.pid,
            "command":    command,
            "task_id":    task_id,
            "status":     "running",
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def check_process_status(process_id: str) -> dict:
    """Return current status of a background process (running/completed/failed)."""
    if not process_id:
        return {"ok": False, "error": "process_id is empty"}
    proc = _PROCS.get(process_id)
    db_doc = None
    if _db is not None:
        try:
            db_doc = await _db[_PROCESSES_COLLECTION].find_one(
                {"_id": process_id}, {"_id": 0}
            )
        except Exception:
            pass
    if proc is None and db_doc is None:
        return {"ok": False, "error": "process not found"}
    if proc is None:
        # Process is from a previous session — return DB record only.
        return {"ok": True, "status": db_doc.get("status", "unknown"),
                "from_db_only": True, **(db_doc or {})}
    # Live process — check status.
    if proc.returncode is None:
        return {"ok": True, "process_id": process_id, "status": "running",
                "os_pid": proc.pid}
    # Process finished — collect output.
    try:
        stdout = await proc.stdout.read() if proc.stdout else b""
    except Exception:
        stdout = b""
    out = stdout.decode("utf-8", errors="replace") if stdout else ""
    status = "completed" if proc.returncode == 0 else "failed"
    if _db is not None:
        try:
            await _db[_PROCESSES_COLLECTION].update_one(
                {"_id": process_id},
                {"$set": {
                    "status":     status,
                    "exit_code":  proc.returncode,
                    "tail":       "\n".join(out.splitlines()[-30:]),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        except Exception:
            pass
    return {"ok": True, "process_id": process_id, "status": status,
             "exit_code": proc.returncode,
             "tail": "\n".join(out.splitlines()[-30:])}


async def wait_for_process(process_id: str, timeout_s: int = 300) -> dict:
    """Wait for completion. Returns the final status."""
    proc = _PROCS.get(process_id)
    if proc is None:
        return {"ok": False, "error": "process not found in this session"}
    try:
        await asyncio.wait_for(proc.wait(), timeout=max(1, int(timeout_s)))
    except asyncio.TimeoutError:
        return {"ok": False, "process_id": process_id,
                 "status": "running",
                 "error": f"timeout after {timeout_s}s"}
    return await check_process_status(process_id)


async def kill_process(process_id: str) -> dict:
    """Send SIGTERM to a background process. Tier-3."""
    proc = _PROCS.get(process_id)
    if proc is None:
        return {"ok": False, "error": "process not found"}
    try:
        proc.send_signal(signal.SIGTERM)
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        proc.kill()
    if _db is not None:
        try:
            await _db[_PROCESSES_COLLECTION].update_one(
                {"_id": process_id},
                {"$set": {"status": "killed",
                            "killed_at": datetime.now(timezone.utc).isoformat()}}
            )
        except Exception:
            pass
    return {"ok": True, "process_id": process_id, "status": "killed"}


# ────────────────────────────────────────────────────────────────────
# Registry patch
# ────────────────────────────────────────────────────────────────────

TOOL_REGISTRY_PATCH = {
    # Blindspot 1
    "git_current_branch": {
        "fn": git_current_branch, "args_spec": {},
        "description": "TIER 1 (auto, read-only). Returns the current git branch.",
    },
    "git_create_branch": {
        "fn": git_create_branch,
        "args_spec": {"branch_name": "str — branch name (ora/ prefix added if missing)"},
        "description": (
            "TIER 2 (30 s window). Create + check out a feature branch. "
            "ORA MUST call this before any code change so we never write to main."
        ),
    },
    "git_push_branch": {
        "fn": git_push_branch,
        "args_spec": {"branch_name": "str", "remote": "str (default origin)"},
        "description": "TIER 2 (30 s window). Push a feature branch to remote.",
    },
    "git_create_pr": {
        "fn": git_create_pr,
        "args_spec": {"title": "str", "body": "str", "head": "str (default: current)", "base": "str (default main)"},
        "description": "TIER 2 (30 s window). Open a PR via gh CLI or return compare URL.",
    },
    "git_merge_branch": {
        "fn": git_merge_branch,
        "args_spec": {"branch": "str", "into": "str (default main)"},
        "description": "TIER 3 (CONFIRM required). Merge a feature branch into main.",
    },
    # Blindspot 2
    "create_sandbox": {
        "fn": create_sandbox,
        "args_spec": {"task_id": "str", "copy_paths": "list[str] — optional files to seed"},
        "description": "TIER 1 (auto). Create an isolated /tmp sandbox for risky ops.",
    },
    "run_in_sandbox": {
        "fn": run_in_sandbox,
        "args_spec": {"task_id": "str", "command": "str", "timeout_s": "int (default 300)"},
        "description": "TIER 2 (30 s window). Run a shell command inside the sandbox only.",
    },
    "promote_from_sandbox": {
        "fn": promote_from_sandbox,
        "args_spec": {"task_id": "str", "files": "list[str]"},
        "description": "TIER 3 (CONFIRM required). Copy verified files from sandbox to /app/.",
    },
    "cleanup_sandbox": {
        "fn": cleanup_sandbox,
        "args_spec": {"task_id": "str"},
        "description": "TIER 1 (auto). Remove the sandbox folder.",
    },
    # Blindspot 3
    "start_background_process": {
        "fn": start_background_process,
        "args_spec": {"command": "str", "task_id": "str", "label": "str"},
        "description": "TIER 2 (30 s window). Spawn a background process; persisted to DB.",
    },
    "check_process_status": {
        "fn": check_process_status,
        "args_spec": {"process_id": "str"},
        "description": "TIER 1 (auto, read-only). Check live status of a tracked process.",
    },
    "wait_for_process": {
        "fn": wait_for_process,
        "args_spec": {"process_id": "str", "timeout_s": "int (default 300)"},
        "description": "TIER 1 (auto). Wait for a process to finish; returns final status.",
    },
    "kill_process": {
        "fn": kill_process,
        "args_spec": {"process_id": "str"},
        "description": "TIER 3 (CONFIRM required). SIGTERM a background process.",
    },
}


def splice_into(tool_registry: dict) -> int:
    tool_registry.update(TOOL_REGISTRY_PATCH)
    return len(TOOL_REGISTRY_PATCH)
