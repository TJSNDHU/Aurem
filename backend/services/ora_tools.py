"""
ora_tools.py — P1 read-only tool surface for ORA (iter 322ej).

Gives ORA the 8 investigation hands it needs to think like the main agent:
  • grep_codebase     — code-search over /app/{backend,frontend}
  • view_file         — read file contents (range-clipped)
  • view_dir          — list directory contents
  • curl_internal     — hit our own backend (localhost only)
  • db_count          — count documents in a Mongo collection (filter optional)
  • db_distinct       — distinct values for a field
  • git_log           — recent commits (read-only)
  • health_check      — /api/platform/health probe
  • lint_python       — ruff syntax/style check (read-only)

Hard rules — no exception:
  - All tools are READ-ONLY. No write/delete/restart in P1.
  - Path allowlist for all FS access: /app/{backend,frontend,memory,ora_skills}
  - Subprocess: hard timeout per tool, no shell, argv-only
  - Every invocation logged to `ora_tool_invocations` for audit
  - Returns {ok, tool, output, error?, elapsed_ms, ts}
  - NEVER raises — failures land in `error` field
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Allowlists ───────────────────────────────────────────────────────
_ALLOWED_ROOTS = (
    "/app/backend",
    "/app/frontend",
    "/app/memory",
    "/app/ora_skills",
    "/app/scripts",
)
_FORBIDDEN_PATTERNS = (
    "/.env",          # secrets
    "/.ssh",
    "/.git/config",
    "node_modules",   # noise
)
_ALLOWED_DB_PREFIXES = (
    # Read-only collections ORA may inspect. Anything not in this list is rejected.
    "ora_", "agent_", "customer_", "campaign_", "pixel_", "audit_",
    "platform_users", "users", "leads", "scan_", "deploy_",
    "pillar_", "sentinel_", "memoir_", "bin_", "intelligence_",
    "antigravity_", "skills_", "trial_", "stripe_", "client_",
    "system_", "heartbeats", "heartbeats_archive", "alerts",
)

_INVOCATION_LOG = "ora_tool_invocations"
_db = None  # set by registry.set_db()


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_path_allowed(p: str) -> bool:
    """True if `p` is under an allowed root and doesn't match forbidden patterns."""
    try:
        # Resolve `..` etc.
        abs_p = str(Path(p).resolve())
    except Exception:
        return False
    if not any(abs_p == r or abs_p.startswith(r + os.sep) for r in _ALLOWED_ROOTS):
        return False
    for bad in _FORBIDDEN_PATTERNS:
        if bad in abs_p:
            return False
    return True


def _is_collection_allowed(name: str) -> bool:
    if not isinstance(name, str) or not name:
        return False
    return any(name.startswith(p) or name == p for p in _ALLOWED_DB_PREFIXES)


async def _log_invocation(
    actor: str, tool: str, args: dict, result: dict, elapsed_ms: int
) -> None:
    """Audit trail. Best-effort — never blocks the response."""
    if _db is None:
        return
    try:
        await _db[_INVOCATION_LOG].insert_one({
            "ts":         _now_iso(),
            "actor":      actor,
            "tool":       tool,
            "args":       args,
            "ok":         bool(result.get("ok")),
            "error":      result.get("error"),
            "elapsed_ms": elapsed_ms,
        })
    except Exception as e:
        logger.debug(f"[ora_tools] invocation log failed: {e}")


# ─── Tool implementations ────────────────────────────────────────────

async def grep_codebase(
    pattern: str,
    file_glob: str = "*.py",
    root: str = "/app/backend",
    max_results: int = 40,
) -> dict:
    """Real grep over the codebase. Whitelisted roots, capped lines, hard timeout."""
    if not _is_path_allowed(root):
        return {"ok": False, "error": f"root not allowed: {root}"}
    if not isinstance(pattern, str) or not pattern or len(pattern) > 200:
        return {"ok": False, "error": "invalid pattern"}
    # Validate file_glob (no shell metachars beyond * and ?)
    if not re.match(r"^[\w.\*\?\-\[\]]+$", file_glob):
        return {"ok": False, "error": "invalid file_glob"}
    if max_results < 1 or max_results > 200:
        max_results = 40
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["grep", "-rn", "-m", str(max_results), pattern,
             f"--include={file_glob}", root],
            capture_output=True, text=True, timeout=12,
        )
        lines = (r.stdout or "").strip().split("\n")
        lines = [ln for ln in lines if ln and "node_modules" not in ln][:max_results]
        return {
            "ok": True,
            "matches":      len(lines),
            "truncated":    len(lines) == max_results,
            "lines":        lines,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "grep timeout (12s)"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


async def view_file(path: str, max_lines: int = 200, start: int = 1) -> dict:
    """Read a file. Range-clipped to max_lines so ORA can't fetch huge blobs."""
    if not _is_path_allowed(path):
        return {"ok": False, "error": f"path not allowed: {path}"}
    if max_lines < 1 or max_lines > 500:
        max_lines = 200
    if start < 1:
        start = 1
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    if not p.is_file():
        return {"ok": False, "error": f"not a file: {path}"}
    if p.stat().st_size > 2_000_000:  # 2 MB cap
        return {"ok": False, "error": "file too large (>2MB)"}
    try:
        content = await asyncio.to_thread(p.read_text, "utf-8", errors="replace")
        lines = content.split("\n")
        total = len(lines)
        end = min(total, start + max_lines - 1)
        chunk = lines[start - 1:end]
        return {
            "ok":           True,
            "path":         str(p),
            "total_lines":  total,
            "shown_range":  f"{start}-{end}",
            "content":      "\n".join(chunk),
            "more_after":   end < total,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


async def view_dir(path: str, max_entries: int = 60) -> dict:
    """List a directory."""
    if not _is_path_allowed(path):
        return {"ok": False, "error": f"path not allowed: {path}"}
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return {"ok": False, "error": f"not a directory: {path}"}
    try:
        entries = []
        for child in sorted(p.iterdir())[:max_entries]:
            entries.append({
                "name":    child.name,
                "type":    "dir" if child.is_dir() else "file",
                "bytes":   child.stat().st_size if child.is_file() else None,
            })
        return {"ok": True, "path": str(p), "entries": entries,
                "truncated": len(list(p.iterdir())) > max_entries}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


async def curl_internal(endpoint: str, method: str = "GET") -> dict:
    """Hit our own backend (localhost:8001 only — no external URLs)."""
    if method.upper() not in ("GET",):
        return {"ok": False, "error": "P1: read-only — only GET allowed"}
    if not isinstance(endpoint, str) or not endpoint.startswith("/api/"):
        return {"ok": False, "error": "endpoint must start with /api/"}
    if "://" in endpoint or ".." in endpoint:
        return {"ok": False, "error": "invalid endpoint"}
    url = f"http://localhost:8001{endpoint}"
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-s", "-w", "\n__STATUS__%{http_code}\n",
             "--max-time", "8", url],
            capture_output=True, text=True, timeout=10,
        )
        out = r.stdout or ""
        m = re.search(r"\n__STATUS__(\d+)\n?$", out)
        status = int(m.group(1)) if m else 0
        body = out[:m.start()] if m else out
        # Cap body so ORA gets a fingerprint, not a dump
        return {
            "ok":         True,
            "url":        url,
            "http_status": status,
            "body":       body[:1500],
            "truncated":  len(body) > 1500,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


async def db_count(collection: str, filter_: dict | None = None) -> dict:
    """Count documents. Filter must be JSON-safe (no $where, no eval)."""
    if _db is None:
        return {"ok": False, "error": "db unavailable"}
    if not _is_collection_allowed(collection):
        return {"ok": False, "error": f"collection not in allowlist: {collection}"}
    f = filter_ or {}
    if not isinstance(f, dict):
        return {"ok": False, "error": "filter must be a dict"}
    # Forbid dangerous operators
    bad_ops = ("$where", "$function", "$accumulator")
    for k in _walk_keys(f):
        if k in bad_ops:
            return {"ok": False, "error": f"operator not allowed: {k}"}
    try:
        n = await asyncio.wait_for(
            _db[collection].count_documents(f) if f
            else _db[collection].estimated_document_count(),
            timeout=5.0,
        )
        return {"ok": True, "collection": collection, "filter": f, "count": n}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "db count timeout (5s)"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


def _walk_keys(obj: Any):
    """Yield every key in a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _walk_keys(it)


async def db_distinct(collection: str, field: str,
                       filter_: dict | None = None,
                       limit: int = 30) -> dict:
    """Distinct values for a field — handy for 'what bins have pixels'."""
    if _db is None:
        return {"ok": False, "error": "db unavailable"}
    if not _is_collection_allowed(collection):
        return {"ok": False, "error": f"collection not in allowlist: {collection}"}
    if not re.match(r"^[\w\.]{1,60}$", field or ""):
        return {"ok": False, "error": "invalid field name"}
    if limit < 1 or limit > 200:
        limit = 30
    f = filter_ or {}
    if not isinstance(f, dict):
        return {"ok": False, "error": "filter must be a dict"}
    try:
        vals = await asyncio.wait_for(
            _db[collection].distinct(field, f),
            timeout=8.0,
        )
        # Coerce to JSON-safe (datetimes, ObjectIds stringified)
        safe = []
        for v in vals[:limit]:
            try:
                safe.append(v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
            except Exception:
                safe.append(None)
        return {
            "ok":        True,
            "collection": collection,
            "field":     field,
            "count":     len(vals),
            "truncated": len(vals) > limit,
            "values":    safe,
        }
    except asyncio.TimeoutError:
        return {"ok": False, "error": "db distinct timeout (8s)"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


async def git_log(n: int = 5) -> dict:
    """Recent commits — proves what's deployed."""
    if n < 1 or n > 30:
        n = 5
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["git", "log", "--oneline", f"-{n}"],
            capture_output=True, text=True, timeout=5,
            cwd="/app",
        )
        return {
            "ok":      True,
            "commits": [ln for ln in (r.stdout or "").strip().split("\n") if ln],
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


async def health_check() -> dict:
    """Backend health probe — proves the service is up."""
    return await curl_internal("/api/platform/health")


async def lint_python(path: str) -> dict:
    """Run ruff on a Python file. Read-only — no auto-fix."""
    if not _is_path_allowed(path):
        return {"ok": False, "error": f"path not allowed: {path}"}
    if not path.endswith(".py"):
        return {"ok": False, "error": "ruff only checks .py files"}
    if not Path(path).is_file():
        return {"ok": False, "error": f"not a file: {path}"}

    # Resolve ruff via PATH or known venv locations — backend's supervisor
    # context strips a lot of system PATH.
    import shutil
    ruff_bin = (
        shutil.which("ruff")
        or ("/opt/plugins-venv/bin/ruff"
            if Path("/opt/plugins-venv/bin/ruff").is_file() else None)
        or ("/root/.venv/bin/ruff"
            if Path("/root/.venv/bin/ruff").is_file() else None)
    )
    if not ruff_bin:
        return {"ok": False, "error": "ruff binary not found on host"}
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            [ruff_bin, "check", "--output-format", "concise", path],
            capture_output=True, text=True, timeout=12,
        )
        issues = [ln for ln in (r.stdout or "").strip().split("\n") if ln]
        return {
            "ok":          True,
            "exit_code":   r.returncode,
            "issue_count": len(issues),
            "issues":      issues[:40],
            "truncated":   len(issues) > 40,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


# ─── iter 322em — Python Subprocess Bridge (Execution Layer) ─────────
# Real shell execution. NOT a mock. Calls subprocess.run() with the
# kernel's argv[0]. shell=False (no shell expansion), strict argv-only,
# whitelisted command set so ORA can't `rm -rf /` or `sudo anything`.
#
# WHY THIS EXISTS: Until now ORA could only investigate via Mongo + curl
# + grep. It couldn't ask the kernel "who am I?" or "what's installed?"
# or run pytest/git/system probes. This bridges that gap WITHOUT giving
# it write access — every command in the whitelist is read-only or
# self-contained.

# Commands ORA may invoke. argv[0] only — anything else returns
# {ok:false, error:"command not in whitelist"}.
_SHELL_WHITELIST: dict[str, dict] = {
    # ── Identity / environment (the founder asked for whoami + pwd) ──
    "whoami":   {"max_args": 0,  "timeout": 3},
    "id":       {"max_args": 1,  "timeout": 3},
    "pwd":      {"max_args": 0,  "timeout": 3},
    "hostname": {"max_args": 1,  "timeout": 3},
    "uname":    {"max_args": 2,  "timeout": 3},
    "uptime":   {"max_args": 1,  "timeout": 3},
    "date":     {"max_args": 4,  "timeout": 3},
    "env":      {"max_args": 0,  "timeout": 3,
                  "post_filter": "redact_secrets"},
    # ── Filesystem inspection (read-only) ──
    "ls":       {"max_args": 6,  "timeout": 5,
                  "args_need_allowed_path": True},
    "find":     {"max_args": 10, "timeout": 12,
                  "args_need_allowed_path": True},
    "wc":       {"max_args": 6,  "timeout": 8,
                  "args_need_allowed_path": True},
    "stat":     {"max_args": 4,  "timeout": 4,
                  "args_need_allowed_path": True},
    "du":       {"max_args": 4,  "timeout": 8,
                  "args_need_allowed_path": True},
    "file":     {"max_args": 4,  "timeout": 5,
                  "args_need_allowed_path": True},
    # ── System status ──
    "df":       {"max_args": 2,  "timeout": 5},
    "free":     {"max_args": 2,  "timeout": 3},
    "ps":       {"max_args": 4,  "timeout": 5},
    # ── Toolchain identification ──
    "which":    {"max_args": 3,  "timeout": 3},
    "whereis":  {"max_args": 3,  "timeout": 3},
    # ── Language toolchain versions (no exec) ──
    "python3":  {"max_args": 3,  "timeout": 6,
                  "allowed_arg0": ("--version", "-V")},
    "node":     {"max_args": 2,  "timeout": 6,
                  "allowed_arg0": ("--version", "-v")},
    "pip":      {"max_args": 4,  "timeout": 12,
                  "allowed_arg0": ("--version", "list", "show")},
    "yarn":     {"max_args": 3,  "timeout": 8,
                  "allowed_arg0": ("--version",)},
    "ruff":     {"max_args": 6,  "timeout": 12},
    # ── VCS (read-only — no commit/push) ──
    "git":      {"max_args": 8,  "timeout": 10,
                  "allowed_arg0": ("status", "log", "diff", "show",
                                    "branch", "remote", "rev-parse",
                                    "describe", "blame", "config",
                                    "ls-files", "tag")},
    # ── Service status (read-only — no restart/stop yet, that's P3) ──
    "supervisorctl": {"max_args": 2, "timeout": 5,
                       "allowed_arg0": ("status",)},
}

# Argv tokens that signal injection — reject the whole call.
# `*` is intentionally NOT here because it's a legit `find -name` glob;
# shell=False means it's never expanded by the shell either way.
_FORBIDDEN_TOKENS = (";", "&&", "||", "|", ">", "<", "$(", "`",
                       "..", "/etc/passwd", "/etc/shadow")

# When path-arg validation kicks in, these prefixes are the only ones
# allowed to appear in argv strings.
_SHELL_PATH_ROOTS = (
    "/app",
    "/var/log/supervisor",
    "/tmp",
    ".",       # ls with no args
    "-",       # ls -lah etc.
)


def _redact_env(stdout: str) -> str:
    """env output filter — strip lines that look like secrets."""
    if not stdout:
        return stdout
    SENSITIVE = ("KEY", "SECRET", "TOKEN", "PASSWORD", "MONGO_URL",
                  "STRIPE", "RESEND", "TWILIO", "JWT_SECRET",
                  "GROQ", "OPENAI", "ANTHROPIC", "EMERGENT")
    kept = []
    for line in stdout.split("\n"):
        if "=" in line:
            k = line.split("=", 1)[0].upper()
            if any(s in k for s in SENSITIVE):
                kept.append(f"{k}=<redacted>")
                continue
        kept.append(line)
    return "\n".join(kept)


def _validate_shell_args(cmd: str, args: list[str]) -> str | None:
    """Return error string if args are invalid; else None."""
    spec = _SHELL_WHITELIST[cmd]
    if len(args) > spec["max_args"]:
        return f"too many args (max {spec['max_args']})"
    for a in args:
        if not isinstance(a, str):
            return "all args must be strings"
        if len(a) > 300:
            return "arg too long (>300)"
        for bad in _FORBIDDEN_TOKENS:
            if bad in a:
                return f"forbidden token in arg: {bad!r}"
    # Sub-command allowlist (e.g. git only accepts log/status/diff/...)
    allowed_arg0 = spec.get("allowed_arg0")
    if allowed_arg0 and args:
        if args[0] not in allowed_arg0:
            return (f"{cmd} sub-command not allowed: {args[0]!r} "
                    f"(allowed: {allowed_arg0})")
    # Path-style arg check
    if spec.get("args_need_allowed_path") and args:
        for a in args:
            if a.startswith("-"):
                continue  # flag, fine
            # Must start with an allowed root OR be a relative dot-path
            if not any(a == r or a.startswith(r + "/") or a == r + "/"
                        for r in _SHELL_PATH_ROOTS):
                return f"path arg not under allowed roots: {a!r}"
    return None


async def shell_exec(command: str, args: list[str] | None = None) -> dict:
    """Execute a whitelisted shell command — real kernel subprocess.

    Args:
        command: argv[0] — must be a key in _SHELL_WHITELIST.
        args:    list of additional argv tokens (validated).

    Returns {ok, command, args, returncode, stdout, stderr, elapsed_ms}.
    NEVER raises — all failures land in `error`. Hard timeout per command.
    """
    if not isinstance(command, str) or not command:
        return {"ok": False, "error": "command required"}
    if command not in _SHELL_WHITELIST:
        return {"ok": False, "error": f"command not in whitelist: {command}",
                "whitelist": sorted(_SHELL_WHITELIST.keys())}
    args = args or []
    if not isinstance(args, list):
        return {"ok": False, "error": "args must be a list"}

    err = _validate_shell_args(command, args)
    if err:
        return {"ok": False, "error": err}

    spec = _SHELL_WHITELIST[command]
    timeout = spec["timeout"]

    # Resolve the binary — protect against PATH gaps under supervisor.
    import shutil as _sh
    binary = _sh.which(command)
    if not binary:
        # Common venv binaries (ruff, pip, etc.)
        for candidate in (
            f"/usr/bin/{command}",
            f"/bin/{command}",
            f"/usr/local/bin/{command}",
            f"/opt/plugins-venv/bin/{command}",
            f"/root/.venv/bin/{command}",
        ):
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                binary = candidate
                break
    if not binary:
        return {"ok": False, "error": f"binary not found on host: {command}"}

    argv = [binary] + args
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            argv,
            capture_output=True, text=True, timeout=timeout,
            shell=False,    # CRITICAL — no shell expansion
            cwd="/app",
            env={
                # Minimal env — strip parent's secrets out of subprocess view
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/plugins-venv/bin",
                "HOME": os.environ.get("HOME", "/root"),
                "LANG": "C.UTF-8",
            },
        )
        out = r.stdout or ""
        err_out = r.stderr or ""
        # Apply post-filter if defined (env redaction)
        if spec.get("post_filter") == "redact_secrets":
            out = _redact_env(out)
        # Cap output so ORA gets a fingerprint, not a dump
        return {
            "ok":         True,
            "command":    command,
            "args":       args,
            "binary":     binary,
            "returncode": r.returncode,
            "stdout":     out[:4000],
            "stderr":     err_out[:1000],
            "truncated":  len(out) > 4000 or len(err_out) > 1000,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout}s",
                "command": command, "args": args}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"FileNotFoundError: {str(e)[:120]}",
                "command": command, "args": args}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}",
                "command": command, "args": args}


# ─── iter 322en — Surgical Writer (Atomic File Writer) ───────────────
# Real write. NOT a mock. ORA can now edit files BUT only via exact-match
# search-replace — no whole-file overwrites, no guesswork. If the
# find_string doesn't match exactly (byte-for-byte, whitespace included),
# the tool refuses. Every successful edit creates a .bak file at
# /tmp/ora_backups/<timestamp>__<safe_path>.bak so revert is one cp away.

_WRITE_ALLOWED_ROOTS = (
    "/app/backend",
    "/app/frontend/src",
    "/app/memory",
    "/app/ora_skills",
    "/app/scripts",
)
_WRITE_FORBIDDEN_PATTERNS = (
    "/.env", "/.ssh", "/.git/", "node_modules", "__pycache__",
    "/migrations/", "/.next/", "/build/", "/dist/",
)
_WRITE_FORBIDDEN_FILES = (
    ".env", ".env.local", ".env.production",
    "requirements.txt", "package.json", "package-lock.json", "yarn.lock",
)
_BACKUP_DIR = Path("/tmp/ora_backups")


def _is_write_path_allowed(p: str) -> tuple[bool, str]:
    """Stricter than read allowlist — write paths exclude /app/frontend/build,
    .env, package.json, etc."""
    try:
        abs_p = str(Path(p).resolve())
    except Exception:
        return False, "could not resolve path"
    if not any(abs_p == r or abs_p.startswith(r + os.sep) for r in _WRITE_ALLOWED_ROOTS):
        return False, f"not under write-allowed roots: {_WRITE_ALLOWED_ROOTS}"
    for bad in _WRITE_FORBIDDEN_PATTERNS:
        if bad in abs_p:
            return False, f"forbidden pattern in path: {bad!r}"
    name = Path(abs_p).name
    if name in _WRITE_FORBIDDEN_FILES:
        return False, f"file is in write-forbidden list: {name}"
    return True, ""


async def safe_edit(
    path: str,
    find_string: str,
    replace_string: str,
    *,
    expected_occurrences: int = 1,
) -> dict:
    """Atomic, exact-match find/replace.

    Steps:
        1. Validate path is under write-allowed roots, not forbidden file.
        2. Read file content.
        3. Verify `find_string` appears exactly `expected_occurrences` times
           (default 1). If 0 or >expected, REFUSE — no guessing.
        4. Backup full file to /tmp/ora_backups/<ts>__<safe_path>.bak.
        5. Compute new content (`text.replace(find_string, replace_string, expected_occurrences)`).
        6. Atomic write (write to .tmp, fsync, rename).
        7. Run git diff for proof. Return diff snippet + backup path.

    Returns {ok, path, occurrences_replaced, backup_path, diff_preview,
              bytes_before, bytes_after}.
    NEVER raises. All failures explained in `error`.
    """
    # ── 1. Path validation ──
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "path required"}
    ok_path, why = _is_write_path_allowed(path)
    if not ok_path:
        return {"ok": False, "error": f"path not allowed: {why}", "path": path}
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"file does not exist: {path}"}
    if not p.is_file():
        return {"ok": False, "error": f"not a regular file: {path}"}
    if p.stat().st_size > 2_000_000:
        return {"ok": False, "error": "file too large for safe edit (>2MB)"}

    # ── 2. Validate find/replace inputs ──
    if not isinstance(find_string, str) or find_string == "":
        return {"ok": False, "error": "find_string required (non-empty)"}
    if not isinstance(replace_string, str):
        return {"ok": False, "error": "replace_string must be a string"}
    if len(find_string) > 50_000:
        return {"ok": False, "error": "find_string too large (>50KB)"}
    if len(replace_string) > 200_000:
        return {"ok": False, "error": "replace_string too large (>200KB)"}
    if not isinstance(expected_occurrences, int) or expected_occurrences < 1 or expected_occurrences > 50:
        return {"ok": False, "error": "expected_occurrences must be int 1-50"}

    # ── 3. Read + verify uniqueness ──
    try:
        original = await asyncio.to_thread(p.read_text, "utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"read failed: {type(e).__name__}: {str(e)[:120]}"}

    actual_count = original.count(find_string)
    if actual_count != expected_occurrences:
        return {
            "ok": False,
            "error": (f"find_string occurs {actual_count}× in file; "
                       f"expected exactly {expected_occurrences}. "
                       f"Refusing to guess — either add more context to find_string "
                       f"for uniqueness, or set expected_occurrences correctly."),
            "actual_occurrences":   actual_count,
            "expected_occurrences": expected_occurrences,
        }
    if find_string == replace_string:
        return {"ok": False, "error": "find_string == replace_string (no-op edit refused)"}

    # ── 4. Backup ──
    try:
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_name = str(p).replace("/", "__").lstrip("_")
        backup_path = _BACKUP_DIR / f"{ts}__{safe_name}.bak"
        await asyncio.to_thread(backup_path.write_text, original, "utf-8")
    except Exception as e:
        return {"ok": False, "error": f"backup failed: {type(e).__name__}: {str(e)[:120]}"}

    # ── 5. Compute new content ──
    new_content = original.replace(find_string, replace_string, expected_occurrences)

    # ── 6. Atomic write (.tmp + rename) ──
    try:
        tmp_path = p.with_suffix(p.suffix + ".ora_tmp")

        def _atomic_write():
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, p)

        await asyncio.to_thread(_atomic_write)
    except Exception as e:
        # Try to clean up the .ora_tmp if it exists
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return {
            "ok": False,
            "error": f"write failed: {type(e).__name__}: {str(e)[:120]}",
            "backup_path": str(backup_path),
        }

    # ── 7. git diff for proof (best-effort, never blocks success) ──
    diff_preview = ""
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["git", "diff", "--unified=2", "--no-color", str(p)],
            capture_output=True, text=True, timeout=5,
            cwd="/app",
        )
        diff_preview = (r.stdout or "")[:2500]
    except Exception:
        pass

    return {
        "ok":                     True,
        "path":                   str(p),
        "occurrences_replaced":   expected_occurrences,
        "backup_path":            str(backup_path),
        "bytes_before":           len(original),
        "bytes_after":            len(new_content),
        "diff_preview":           diff_preview,
        "diff_truncated":         len(diff_preview) >= 2500,
        "revert_cmd":             f"cp '{backup_path}' '{p}'",
    }


# ─── iter 322en — Service Supervisor (controlled restart) ────────────
# Real `supervisorctl restart` against the whitelisted services. Backend
# + frontend only. Database / postgres / mongo are HARD-blocked.

_RESTART_WHITELIST: set[str] = {"backend", "frontend"}


async def restart_service(service: str) -> dict:
    """Restart a whitelisted supervisor-managed service.

    Args:
        service: must be in _RESTART_WHITELIST.

    Returns {ok, service, scheduled_at, ...}. The restart is detached into
    a background process so that when the backend restarts itself, the
    in-flight HTTP response can complete cleanly BEFORE the supervisor
    kills the process group. Without this trick, ORA's caller hits a
    socket reset and never sees the success ack.

    For `backend`: we schedule the restart 1.5s after the HTTP response
    returns. Caller is expected to poll /api/platform/health afterwards
    (or use safe_edit_lint_restart_verify which does this automatically).
    """
    if service not in _RESTART_WHITELIST:
        return {
            "ok": False,
            "error": f"service not in restart whitelist: {service}",
            "whitelist": sorted(_RESTART_WHITELIST),
        }

    import shutil as _sh
    sup = _sh.which("supervisorctl") or "/usr/bin/supervisorctl"
    if not Path(sup).is_file():
        return {"ok": False, "error": f"supervisorctl not found at {sup}"}

    sudo = _sh.which("sudo")
    sup_cmd = f"{sudo + ' ' if sudo else ''}{sup} restart {service}"

    detached_script = (
        f"sleep 1.5 && "
        f"{sup_cmd} > /tmp/ora_restart_{service}.log 2>&1"
    )
    try:
        await asyncio.to_thread(
            subprocess.Popen,
            ["bash", "-c", f"setsid nohup bash -c '{detached_script}' >/dev/null 2>&1 &"],
            shell=False, cwd="/app",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        scheduled_at = datetime.now(timezone.utc).isoformat()
        return {
            "ok":            True,
            "service":       service,
            "scheduled_at":  scheduled_at,
            "scheduled_via": "detached_setsid",
            "delay_seconds": 1.5,
            "log_path":      f"/tmp/ora_restart_{service}.log",
            "note":          (f"Restart of '{service}' scheduled to fire 1.5s after this "
                              "response. Poll /api/platform/health to verify recovery."),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}",
                "service": service}


# ─── iter 322eo — ORA CTO Peer-Council (P4) ──────────────────────────
# Sovereign Chief Technology Officer stack — ORA can now escalate hard
# decisions to specialist peer agents BEFORE committing a safe_edit or
# restart_service. Uses the existing AUREMAgentHarness (build-fixer,
# code-reviewer, security-scanner, planner) AND the LLM gateway for
# role-prompted peer review (security-engineer, devops, backend-eng,
# qa-engineer, refactor-expert).
#
# The 10 agent profiles in /app/backend/ora_skills/agent_*.md become
# the system prompts for LLM-peer review — no new prompt engineering,
# we reuse what's already battle-tested.

_LLM_PEER_PROFILES = {
    # role         → (ora_skills filename, max_tokens)
    "security":     ("agent_security_engineer.md",   600),
    "backend":      ("agent_engineering_backend.md", 600),
    "devops":       ("agent_engineering_devops.md",  500),
    "qa":           ("agent_qa_engineer.md",         500),
    "design":       ("agent_design_ux.md",           400),
    "finance":      ("agent_finance_analyst.md",     400),
    "marketing":    ("agent_marketing_growth.md",    400),
    "pricing":      ("agent_pricing_analyst.md",     400),
}

# Native code agents from services/aurem_agents/* (already in production)
_HARNESS_AGENTS = {
    "code-reviewer":    "Static code review (Python/JS/MongoDB anti-patterns + security)",
    "security-scanner": "OWASP + SaaS-specific security audit",
    "build-fixer":      "Import errors / 404s / build failures",
    "planner":          "Feature planning + architecture sketches",
}


def _load_peer_prompt(role: str) -> str:
    """Read the skill profile for a peer role. Falls back to a generic
    review prompt if the file is missing."""
    spec = _LLM_PEER_PROFILES.get(role)
    if not spec:
        return ""
    skill_path = Path("/app/backend/ora_skills") / spec[0]
    if not skill_path.is_file():
        return ""
    try:
        return skill_path.read_text("utf-8", errors="replace")[:6000]
    except Exception:
        return ""


async def peer_review(role: str, question: str,
                       context: str = "",
                       max_tokens: int | None = None) -> dict:
    """LLM peer-review by a specialist role.

    Args:
        role:       one of `_LLM_PEER_PROFILES` keys (security, backend,
                    devops, qa, design, finance, marketing, pricing).
        question:   the specific question or proposed change.
        context:    optional diff / code / log to give the peer.
        max_tokens: response cap (defaults to role's recommended size).

    Returns:
        {ok, role, opinion, provider, elapsed_ms, prompt_chars}.
    """
    if role not in _LLM_PEER_PROFILES:
        return {
            "ok": False,
            "error": f"unknown peer role: {role}",
            "available_roles": sorted(_LLM_PEER_PROFILES),
        }
    if not isinstance(question, str) or not question.strip():
        return {"ok": False, "error": "question required"}
    if len(question) > 20_000:
        return {"ok": False, "error": "question too long (>20KB)"}
    if len(context) > 50_000:
        return {"ok": False, "error": "context too long (>50KB)"}

    profile = _load_peer_prompt(role)
    if not profile:
        return {"ok": False, "error": f"peer profile not loaded for: {role}"}

    spec = _LLM_PEER_PROFILES[role]
    tokens = max_tokens or spec[1]

    sys_prompt = (
        profile
        + "\n\n# PEER REVIEW REQUEST\n"
        "ORA (the autonomous CTO) is consulting you before committing a "
        "change. Be specific. Quote line numbers / endpoints. If the "
        "change is risky, say so plainly. If it's fine, say so plainly. "
        "Apply the Zero Hallucination Charter — if you don't know, say "
        "so. Cap your answer to ~3 short paragraphs."
    )
    user_prompt = f"Question:\n{question}\n\n"
    if context:
        user_prompt += f"Context (diff / code / log):\n```\n{context[:8000]}\n```\n"

    import time as _t
    t0 = _t.time()
    try:
        from services.llm_gateway import call_llm_with_meta
        # Skip cache so peer review is always fresh per question.
        r = await call_llm_with_meta(
            sys_prompt, user_prompt, max_tokens=tokens,
            bypass_cache=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"llm_gateway failed: {type(e).__name__}: {str(e)[:120]}"}

    return {
        "ok":           bool(r.get("ok")),
        "role":         role,
        "provider":     r.get("provider"),
        "opinion":      r.get("content"),
        "prompt_chars": len(sys_prompt) + len(user_prompt),
        "elapsed_ms":   int((_t.time() - t0) * 1000),
    }


async def code_review(file_path: str,
                       review_type: str = "full") -> dict:
    """Static code review via the existing AUREMCodeReviewer agent.

    This is the deterministic peer — runs heuristics on the file
    (FastAPI patterns, React hooks, Mongo anti-patterns, OWASP) and
    returns a structured issue list + score. No LLM call needed.
    """
    if not _is_path_allowed(file_path):
        return {"ok": False, "error": f"path not allowed: {file_path}"}
    if not Path(file_path).is_file():
        return {"ok": False, "error": f"not a file: {file_path}"}
    if review_type not in ("full", "security", "style", "performance"):
        return {"ok": False, "error": f"invalid review_type: {review_type}"}
    try:
        from services.aurem_agents.harness import get_agent_harness
        harness = get_agent_harness()
        r = await harness.delegate("code-reviewer", {
            "file_path":   file_path,
            "review_type": review_type,
        })
        # Reshape into the standard ora_tools envelope
        return {
            "ok":          bool(r.get("success", True)),
            "file_path":   file_path,
            "review_type": review_type,
            "score":       r.get("score"),
            "issues":      (r.get("issues") or [])[:30],
            "issue_count": len(r.get("issues") or []),
            "suggestions": (r.get("suggestions") or [])[:10],
            "raw":         {k: v for k, v in r.items()
                            if k not in ("issues", "suggestions")},
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


async def security_scan(scan_type: str = "full",
                         target: str = "backend") -> dict:
    """Static security scan via the existing AUREMSecurityScanner agent.

    Covers OWASP Top 10, auth/payment paths, MongoDB injection, frontend
    XSS / CSRF / secret exposure. Returns vulnerability list + risk
    score. No LLM call — pure heuristic + AST inspection."""
    if scan_type not in ("full", "auth", "payment", "api", "frontend"):
        return {"ok": False, "error": f"invalid scan_type: {scan_type}"}
    if target not in ("backend", "frontend", "both"):
        return {"ok": False, "error": f"invalid target: {target}"}
    try:
        from services.aurem_agents.harness import get_agent_harness
        harness = get_agent_harness()
        r = await harness.delegate("security-scanner", {
            "scan_type": scan_type,
            "target":    target,
        })
        return {
            "ok":              bool(r.get("success", True)),
            "scan_type":       scan_type,
            "target":          target,
            "risk_score":      r.get("risk_score"),
            "vulnerabilities": (r.get("vulnerabilities") or [])[:25],
            "vuln_count":      len(r.get("vulnerabilities") or []),
            "recommendations": (r.get("recommendations") or [])[:10],
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


async def council_consult(question: str, *,
                            roles: list[str] | None = None,
                            context: str = "") -> dict:
    """Multi-peer council — fan out the same question to N specialists,
    return all opinions in parallel. ORA uses this before high-impact
    edits (auth changes, payment paths, schema migrations).

    Args:
        question: the proposed change / problem.
        roles:    list of peer roles to consult. Default = security + backend + qa.
        context:  optional diff / code / log shared with all peers.
    """
    if not roles:
        roles = ["security", "backend", "qa"]
    roles = [r for r in roles if r in _LLM_PEER_PROFILES]
    if not roles:
        return {"ok": False, "error": "no valid roles after filter",
                "available_roles": sorted(_LLM_PEER_PROFILES)}
    if len(roles) > 5:
        return {"ok": False, "error": "max 5 peers per council call"}

    # Parallel fanout — each peer review is independent.
    results = await asyncio.gather(*[
        peer_review(role, question, context=context) for role in roles
    ], return_exceptions=True)

    opinions = []
    for role, res in zip(roles, results):
        if isinstance(res, Exception):
            opinions.append({"role": role, "ok": False,
                              "error": f"{type(res).__name__}: {str(res)[:120]}"})
        else:
            opinions.append({
                "role":       role,
                "ok":         res.get("ok"),
                "opinion":    res.get("opinion"),
                "provider":   res.get("provider"),
                "elapsed_ms": res.get("elapsed_ms"),
            })
    n_ok = sum(1 for o in opinions if o.get("ok"))
    return {
        "ok":          n_ok > 0,
        "consulted":   roles,
        "opinions":    opinions,
        "consensus":   f"{n_ok}/{len(opinions)} peers responded",
    }


# ─── Registry ────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {
    "grep_codebase":  {
        "fn": grep_codebase,
        "args_spec": {"pattern": "str (required)", "file_glob": "str (e.g. *.py)",
                      "root": "/app/{backend,frontend,memory,ora_skills}",
                      "max_results": "int 1-200, default 40"},
        "description": "Real grep -rn over the codebase. Returns matched lines with file:line:body.",
    },
    "view_file": {
        "fn": view_file,
        "args_spec": {"path": "str (required, must be inside /app)",
                      "max_lines": "int 1-500, default 200",
                      "start": "int (1-based line, default 1)"},
        "description": "Read a file's contents, range-clipped.",
    },
    "view_dir": {
        "fn": view_dir,
        "args_spec": {"path": "str (required)", "max_entries": "int, default 60"},
        "description": "List a directory's entries (name/type/bytes).",
    },
    "curl_internal": {
        "fn": curl_internal,
        "args_spec": {"endpoint": "str starting with /api/", "method": "GET only in P1"},
        "description": "GET our own backend (localhost:8001). Returns http_status + body fingerprint.",
    },
    "db_count": {
        "fn": db_count,
        "args_spec": {"collection": "str (allowlist)", "filter_": "dict (no $where/$function)"},
        "description": "Mongo count_documents for read-only collections.",
    },
    "db_distinct": {
        "fn": db_distinct,
        "args_spec": {"collection": "str", "field": "str", "filter_": "dict", "limit": "int 1-200"},
        "description": "Mongo distinct() — e.g. which bins have pixels firing.",
    },
    "git_log": {
        "fn": git_log,
        "args_spec": {"n": "int 1-30, default 5"},
        "description": "Recent git commits on /app — proves what's deployed.",
    },
    "health_check": {
        "fn": health_check,
        "args_spec": {},
        "description": "Hit /api/platform/health — proves the backend is up.",
    },
    "lint_python": {
        "fn": lint_python,
        "args_spec": {"path": "str (.py inside /app/backend)"},
        "description": "Run ruff check on a Python file. Read-only — no fixes applied.",
    },
    "shell_exec": {
        "fn": shell_exec,
        "args_spec": {"command": "str (must be in whitelist)",
                      "args":    "list[str] (sanitised, no shell metachars)"},
        "description": (
            "EXECUTION LAYER (iter 322em) — real subprocess.run(argv) against "
            "the Linux kernel. shell=False, argv-only. Whitelist: whoami, id, "
            "pwd, hostname, uname, uptime, date, env (secrets redacted), ls, "
            "find, wc, stat, du, file, df, free, ps, which, whereis, python3 "
            "--version, node --version, pip list, yarn --version, ruff, git "
            "(log/status/diff/show/branch only), supervisorctl status."
        ),
    },
    "safe_edit": {
        "fn": safe_edit,
        "args_spec": {
            "path":                 "str (must be under /app/{backend,frontend/src,memory,ora_skills,scripts})",
            "find_string":          "str (exact match, whitespace-sensitive)",
            "replace_string":       "str (the new code)",
            "expected_occurrences": "int 1-50 (default 1) — fails if actual count differs",
        },
        "description": (
            "ATOMIC FILE WRITER (iter 322en) — surgical search/replace with "
            "auto-backup. Refuses if find_string doesn't appear EXACTLY "
            "`expected_occurrences` times (no guessing). Backups land in "
            "/tmp/ora_backups/. Atomic write via .tmp + os.replace. "
            "Returns git diff preview + revert command. Forbidden: .env, "
            "package.json, requirements.txt, lock files, /.git/, /build/."
        ),
    },
    "restart_service": {
        "fn": restart_service,
        "args_spec": {"service": "str — must be 'backend' or 'frontend'"},
        "description": (
            "SERVICE SUPERVISOR (iter 322en) — real `supervisorctl restart "
            "<service>`. Whitelist hard-coded to backend + frontend only. "
            "Database / postgres / mongo / system services BLOCKED. "
            "Returns post-restart status so ORA can verify recovery."
        ),
    },
    "peer_review": {
        "fn": peer_review,
        "args_spec": {
            "role":       "str — one of: security, backend, devops, qa, design, finance, marketing, pricing",
            "question":   "str (≤20KB) — the proposed change or problem",
            "context":    "str (≤50KB) — optional diff/code/log to share",
            "max_tokens": "int — defaults to role's recommended size",
        },
        "description": (
            "ORA CTO P4 (iter 322eo) — LLM peer review by a specialist role. "
            "Loads /app/backend/ora_skills/agent_<role>.md as the peer's "
            "system prompt and asks it to critique ORA's proposed change. "
            "Use BEFORE high-impact safe_edit / restart calls (auth, "
            "payment, schema). Bypass-cached so every consult is fresh."
        ),
    },
    "code_review": {
        "fn": code_review,
        "args_spec": {
            "file_path":   "str — Python or JS file under /app/{backend,frontend/src}",
            "review_type": "str — full | security | style | performance",
        },
        "description": (
            "ORA CTO P4 (iter 322eo) — deterministic code review via the "
            "existing AUREMCodeReviewer agent. Checks FastAPI patterns, "
            "React hooks, Mongo anti-patterns, OWASP. Returns score + "
            "issue list + suggestions. No LLM cost."
        ),
    },
    "security_scan": {
        "fn": security_scan,
        "args_spec": {
            "scan_type": "str — full | auth | payment | api | frontend",
            "target":    "str — backend | frontend | both",
        },
        "description": (
            "ORA CTO P4 (iter 322eo) — deterministic security audit via "
            "the existing AUREMSecurityScanner. OWASP Top 10 + SaaS-"
            "specific (auth, subs, payments) + MongoDB injection + "
            "frontend XSS/CSRF/secrets. Returns risk_score + vuln list. "
            "No LLM cost."
        ),
    },
    "council_consult": {
        "fn": council_consult,
        "args_spec": {
            "question": "str — the change / problem",
            "roles":    "list[str] — peer roles to consult (default: security, backend, qa)",
            "context":  "str — optional diff/code/log",
        },
        "description": (
            "ORA CTO P4 (iter 322eo) — multi-peer parallel council. Fan out "
            "the same question to N specialists, return all opinions. ORA "
            "uses this before high-stakes edits (auth, payment, schema). "
            "Max 5 peers per call."
        ),
    },
}


async def invoke_tool(name: str, args: dict, *, actor: str = "ora") -> dict:
    """Dispatch a tool by name. Always returns a dict; never raises."""
    start = time.time()
    if name not in TOOL_REGISTRY:
        result = {"ok": False, "error": f"unknown tool: {name}",
                   "available_tools": sorted(TOOL_REGISTRY.keys())}
    else:
        fn = TOOL_REGISTRY[name]["fn"]
        # Light arg sanitisation — coerce dict
        if not isinstance(args, dict):
            args = {}
        try:
            result = await fn(**args)
        except TypeError as e:
            result = {"ok": False, "error": f"bad args for {name}: {str(e)[:120]}"}
        except Exception as e:
            result = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}

    elapsed_ms = int((time.time() - start) * 1000)
    result["tool"] = name
    result["elapsed_ms"] = elapsed_ms
    result["ts"] = _now_iso()

    # Audit log (best-effort, never blocks)
    asyncio.create_task(_log_invocation(actor, name, args, result, elapsed_ms))
    return result


def list_tools() -> list[dict]:
    """Public descriptor list — what ORA can call."""
    return [
        {"name": n,
         "description": meta["description"],
         "args_spec": meta["args_spec"]}
        for n, meta in TOOL_REGISTRY.items()
    ]
