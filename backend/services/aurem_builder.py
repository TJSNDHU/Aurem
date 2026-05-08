"""
AUREM Internal Builder (Iteration 211)
=======================================
Self-building code pipeline. An admin sends a natural-language feature
description; Claude (Opus 4.6 via EMERGENT_LLM_KEY) plans + writes the code,
we run a lightweight security pass + syntax check, write the files, and verify
they import cleanly. Everything is logged to `build_log` for the dashboard.

Pipeline
--------
    description
        → Claude (planner + coder)
        → extract_files()
        → path whitelist + syntax check (py_compile)
        → light security grep (Shannon-style patterns)
        → write files to disk
        → import sanity check on each new Python module
        → background hot-reload kick if needed
        → log to build_log

Safety rails (non-negotiable)
-----------------------------
• Writes only under ALLOWED_ROOTS (backend/routers, backend/services,
  frontend/src, backend/tests, /app/memory). Anything else → REJECTED.
• Forbidden filenames: server.py, registry.py, .env, requirements.txt,
  package.json (Claude must not rewrite infra).
• No `os.system`, `subprocess.run(shell=True)`, `eval(`, `exec(` in generated
  code (Shannon-style static check).
• Full audit row persisted with file list, status, cost estimate.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import py_compile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────
ALLOWED_ROOTS: List[str] = [
    "/app/backend/routers/",
    "/app/backend/services/",
    "/app/backend/tests/",
    "/app/frontend/src/",
    "/app/memory/",
]

FORBIDDEN_FILES = {
    "/app/backend/server.py",
    "/app/backend/.env",
    "/app/backend/requirements.txt",
    "/app/frontend/.env",
    "/app/frontend/package.json",
    "/app/backend/routers/registry.py",
}

# Shannon-style forbidden patterns (regex) in generated code.
FORBIDDEN_PATTERNS = [
    (r"\beval\s*\(", "uses eval()"),
    (r"\bexec\s*\(", "uses exec()"),
    (r"os\.system\s*\(", "uses os.system()"),
    (r"subprocess\.(?:run|Popen|call|check_output)\([^)]*shell\s*=\s*True", "uses shell=True subprocess"),
    (r"rm\s+-rf\s+/", "contains destructive rm -rf /"),
    (r"DROP\s+DATABASE", "contains DROP DATABASE"),
    (r"[\"']sk-[A-Za-z0-9-]{20,}[\"']", "contains a hardcoded secret-looking key"),
]

FILE_HEADER_RE = re.compile(r"^FILE:\s*(\S+)\s*$", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9+_-]*)\n(.*?)```", re.DOTALL)

DEFAULT_MODEL = os.environ.get("AUREM_BUILDER_MODEL", "claude-sonnet-4-5-20250929")
DEFAULT_PROVIDER = "anthropic"

# Fallback chain — if the primary model 502s / budget-exceeds, retry down the list.
# Each entry is (provider, model). First entry is the primary.
MODEL_FALLBACK_CHAIN = [
    ("anthropic", DEFAULT_MODEL),
    ("anthropic", "claude-3-5-sonnet-20241022"),
    ("openai",    "gpt-4o"),
]

BUILDER_SYSTEM_PROMPT = """You are AUREM's internal architect + coder.

AUREM Stack:
- Backend: FastAPI (Python 3.11) at /app/backend/
  - Routers in /app/backend/routers/, each exposes `router = APIRouter(...)`
    and may expose `set_db(db)`. New routers must be registered in registry.py
    by the human (you do NOT touch registry.py).
  - Services (business logic) in /app/backend/services/.
  - All backend routes MUST be prefixed with `/api`.
  - MongoDB access via motor; DB is passed in through `set_db(db)`.
  - Exclude `_id` from every response (use `projection={"_id": 0}` or pop it).
- Frontend: React 18 at /app/frontend/src/
  - ALWAYS use `process.env.REACT_APP_BACKEND_URL` for API calls.
  - Shadcn UI available at `/app/frontend/src/components/ui/*`.
- Testing: pytest files live in /app/backend/tests/.
- Env: never emit hardcoded secrets; use `os.environ.get(...)`.

Rules:
1. Reuse existing services — do not rebuild what already exists.
2. Follow existing patterns (imports, logger, router pattern).
3. Do NOT modify server.py, registry.py, .env, requirements.txt, package.json.
4. CASL compliant — no PII sent to 3rd parties without consent.
5. No breaking changes.
6. Add `data-testid` attributes on all new interactive React elements.

Output format — STRICT (parser reads these headers literally):

FILE: /absolute/path/to/file.py
```python
<complete file contents here, no ellipses, no placeholders>
```

FILE: /absolute/path/to/another.jsx
```jsx
<complete file contents here>
```

TEST:
```bash
<one-line curl command or pytest invocation the human can run>
```

If the change requires registry.py or .env edits, DO NOT write them —
instead include a short `NOTE:` line listing the manual step the human
must do (e.g., `NOTE: register "routers.X_router" in routers/registry.py`).
"""


# ─────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────
def extract_files(claude_text: str) -> Dict[str, str]:
    """
    Parse Claude output into {path: code}. Pairs each `FILE: <path>` marker
    with the next ``` fenced block. Ignores orphan blocks.
    """
    files: Dict[str, str] = {}
    # Walk the text finding FILE: markers + the next code fence after each.
    markers = [(m.start(), m.group(1).strip()) for m in FILE_HEADER_RE.finditer(claude_text)]
    fences = list(CODE_FENCE_RE.finditer(claude_text))

    for idx, (pos, path) in enumerate(markers):
        # Find the first fence that starts AFTER this marker and BEFORE the next marker.
        next_marker_pos = markers[idx + 1][0] if idx + 1 < len(markers) else len(claude_text)
        for f in fences:
            if f.start() > pos and f.end() <= next_marker_pos + 10:
                files[path] = f.group(1).rstrip() + "\n"
                break
    return files


def extract_test_command(claude_text: str) -> Optional[str]:
    """Extract the TEST: ```bash ...``` block. Returns None if absent."""
    m = re.search(r"TEST:\s*```(?:bash|sh)?\n(.*?)```", claude_text, re.DOTALL)
    if not m:
        return None
    return m.group(1).strip().splitlines()[0] if m.group(1).strip() else None


def extract_notes(claude_text: str) -> List[str]:
    """Collect every `NOTE: ...` line Claude added."""
    return [m.group(1).strip() for m in re.finditer(r"^NOTE:\s*(.+)$", claude_text, re.MULTILINE)]


# ─────────────────────────────────────────────────────────────
# Safety checks
# ─────────────────────────────────────────────────────────────
def _is_path_allowed(abs_path: str) -> bool:
    if abs_path in FORBIDDEN_FILES:
        return False
    return any(abs_path.startswith(root) for root in ALLOWED_ROOTS)


def security_scan(code: str) -> List[str]:
    """Return a list of human-readable security issues found in `code`."""
    issues: List[str] = []
    for pattern, label in FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            issues.append(label)
    return issues


def syntax_check(file_path: str, code: str) -> Optional[str]:
    """
    For .py files, byte-compile in a tempfile to catch SyntaxError.
    Returns None on success, error string on failure.
    """
    if not file_path.endswith(".py"):
        return None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        try:
            py_compile.compile(tmp_path, doraise=True)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return None
    except py_compile.PyCompileError as e:
        return str(e)
    except Exception as e:
        return f"syntax check crashed: {e}"


# ─────────────────────────────────────────────────────────────
# Claude call
# ─────────────────────────────────────────────────────────────
# Error types that should trigger failover to the next model in the chain.
# Anything else (prompt error, content violation, etc.) should NOT fail over.
_FAILOVER_SUBSTRINGS = (
    "badgatewayerror",
    "502",
    "budget has been exceeded",
    "budget_exceeded",
    "model not found",
    "model_not_found",
    "not supported",
    "serviceunavailable",
    "503",
    "timeout",
)


def _should_failover(err: BaseException) -> bool:
    text = f"{type(err).__name__}: {err}".lower()
    return any(sub in text for sub in _FAILOVER_SUBSTRINGS)


async def _call_claude(
    description: str,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    extra_context: str = "",
) -> str:
    """
    Ask the planner+coder LLM to plan + write code. Returns raw text.
    Walks MODEL_FALLBACK_CHAIN on 502 / budget-exceeded / unknown-model
    errors so a single upstream hiccup doesn't fail the whole build.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("EMERGENT_API_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    prompt = f"""Build this feature for AUREM:

{description}

{extra_context}

Produce the files now. Remember: FILE: <path> + ```lang ... ``` blocks.
Include a TEST: block with ONE curl/pytest line the human can run to verify.
""".strip()

    # Build the ordered try-list: the caller-requested model first,
    # then the rest of the chain skipping duplicates.
    seen = set()
    chain: list[tuple[str, str]] = []
    for p, m in [(provider, model)] + MODEL_FALLBACK_CHAIN:
        key = (p, m)
        if key in seen:
            continue
        seen.add(key)
        chain.append(key)

    last_err: Optional[BaseException] = None
    for idx, (p, m) in enumerate(chain):
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"aurem-builder-{uuid4().hex[:8]}",
                system_message=BUILDER_SYSTEM_PROMPT,
            ).with_model(p, m)
            response = await chat.send_message(UserMessage(text=prompt))
            if idx > 0:
                logger.warning(
                    f"[AuremBuilder] primary model(s) failed; succeeded on "
                    f"fallback #{idx}: {p}/{m}"
                )
            return response if isinstance(response, str) else str(response)
        except Exception as e:
            last_err = e
            if not _should_failover(e):
                logger.warning(f"[AuremBuilder] {p}/{m} non-retryable error: {e}")
                raise
            logger.warning(f"[AuremBuilder] {p}/{m} failed ({type(e).__name__}); trying next")

    # All chain exhausted
    raise last_err if last_err else RuntimeError("All model fallbacks exhausted")


# ─────────────────────────────────────────────────────────────
# Self-repair
# ─────────────────────────────────────────────────────────────
async def _repair_code(
    file_path: str,
    original_code: str,
    error_message: str,
    model: str = DEFAULT_MODEL,
) -> Optional[str]:
    """Ask Claude to produce a corrected version of `original_code`.
    Uses the same fallback chain as _call_claude on 502/budget errors."""
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("EMERGENT_API_KEY")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        repair_prompt = f"""The file `{file_path}` you produced failed with this error:

{error_message}

Fix ONLY this file. Return exactly one fenced code block with the corrected
complete file contents. No prose, no FILE: header, just one ``` fenced block.
Code to fix:
```
{original_code}
```
"""
        # Build fallback chain starting with requested model
        seen = set()
        chain: list[tuple[str, str]] = []
        for p, m in [(DEFAULT_PROVIDER, model)] + MODEL_FALLBACK_CHAIN:
            if (p, m) in seen:
                continue
            seen.add((p, m))
            chain.append((p, m))

        last_err: Optional[BaseException] = None
        for idx, (p, m) in enumerate(chain):
            try:
                chat = LlmChat(
                    api_key=api_key,
                    session_id=f"aurem-repair-{uuid4().hex[:8]}",
                    system_message="You are a precise code-fixer. Respond with one code block only.",
                ).with_model(p, m)
                txt = await chat.send_message(UserMessage(text=repair_prompt))
                if idx > 0:
                    logger.warning(f"[AuremBuilder] repair succeeded on fallback #{idx}: {p}/{m}")
                match = CODE_FENCE_RE.search(txt if isinstance(txt, str) else str(txt))
                return match.group(1).rstrip() + "\n" if match else None
            except Exception as e:
                last_err = e
                if not _should_failover(e):
                    raise
                logger.warning(f"[AuremBuilder] repair {p}/{m} failed ({type(e).__name__}); trying next")

        if last_err:
            logger.warning(f"[AuremBuilder] repair failed after chain exhausted: {last_err}")
        return None
    except Exception as e:
        logger.warning(f"[AuremBuilder] repair failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Import sanity check for new Python files
# ─────────────────────────────────────────────────────────────
def _import_sanity(file_path: str) -> Optional[str]:
    """Try importing the module by its path. Returns error or None."""
    if not file_path.endswith(".py"):
        return None
    rel = file_path.replace("/app/backend/", "").replace(".py", "").replace("/", ".")
    if rel.startswith("."):
        rel = rel[1:]
    try:
        import importlib
        # Invalidate caches so newly written file is picked up.
        importlib.invalidate_caches()
        importlib.import_module(rel)
        return None
    except Exception as e:
        return f"ImportError on `{rel}`: {e}"


# ─────────────────────────────────────────────────────────────
# Write + verify each file, with self-repair
# ─────────────────────────────────────────────────────────────
async def _process_file(
    file_path: str,
    code: str,
    max_repair_attempts: int = 2,
) -> Dict[str, Any]:
    """Security + syntax + write + import check, with up to N repair attempts."""
    report: Dict[str, Any] = {
        "path": file_path,
        "ok": False,
        "security_issues": [],
        "syntax_error": None,
        "import_error": None,
        "repair_attempts": 0,
        "written": False,
    }

    if not _is_path_allowed(file_path):
        report["syntax_error"] = f"path not allowed: {file_path}"
        return report

    # 1) Security
    issues = security_scan(code)
    report["security_issues"] = issues
    if issues:
        return report

    # 2) Syntax (Python only) with repair loop
    current_code = code
    attempts = 0
    while attempts <= max_repair_attempts:
        err = syntax_check(file_path, current_code)
        if err is None:
            break
        report["syntax_error"] = err
        report["repair_attempts"] = attempts + 1
        fixed = await _repair_code(file_path, current_code, err)
        if not fixed:
            return report
        current_code = fixed
        attempts += 1
    else:
        return report

    # 2b) SmolMachines sandbox (advisory by default). Skips if SANDBOX_URL unset.
    try:
        from services.sandbox_client import run_code as _sandbox_run, SANDBOX_MODE
        if file_path.endswith(".py"):
            sb = await _sandbox_run(current_code, language="python")
            report["sandbox"] = {
                "ok": sb.get("ok"),
                "skipped": sb.get("skipped"),
                "reason": sb.get("reason"),
                "exit_code": sb.get("exit_code"),
                "mode": sb.get("mode", SANDBOX_MODE),
            }
            if not sb.get("ok") and not sb.get("skipped") and SANDBOX_MODE == "enforce":
                report["syntax_error"] = f"sandbox rejected: {sb.get('reason') or sb.get('stderr', '')[:160]}"
                return report
    except Exception as _e:
        report["sandbox"] = {"ok": None, "reason": f"probe crashed: {_e}"}

    # 3) Write
    try:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(current_code)
        report["written"] = True
    except Exception as e:
        report["syntax_error"] = f"write failed: {e}"
        return report

    # 4) Import sanity (non-fatal but reported)
    imp_err = _import_sanity(file_path)
    if imp_err:
        report["import_error"] = imp_err

    report["ok"] = report["written"] and not report["security_issues"] and report["syntax_error"] is None
    return report


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────
def new_build_id() -> str:
    return uuid4().hex[:12]


async def build_feature(
    db,
    description: str,
    admin: str = "admin",
    model: str = DEFAULT_MODEL,
    build_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Plan → code → verify → write → log. Returns structured result."""
    build_id = build_id or new_build_id()
    started_at = datetime.now(timezone.utc)
    result: Dict[str, Any] = {
        "build_id": build_id,
        "description": description,
        "model": model,
        "started_at": started_at.isoformat(),
        "files": [],
        "notes": [],
        "test_command": None,
        "status": "running",
        "error": None,
    }
    try:
        raw = await _call_claude(description, model=model)
        result["claude_raw_len"] = len(raw)
        result["notes"] = extract_notes(raw)
        result["test_command"] = extract_test_command(raw)

        files = extract_files(raw)
        if not files:
            result["status"] = "failed"
            result["error"] = "Claude produced no FILE: blocks"
        else:
            for path, code in files.items():
                rep = await _process_file(path, code)
                result["files"].append(rep)
            any_failed = any(not f["ok"] for f in result["files"])
            result["status"] = "failed" if any_failed else "success"
    except Exception as e:
        logger.exception("[AuremBuilder] build_feature crashed")
        result["status"] = "failed"
        result["error"] = str(e)

    finished_at = datetime.now(timezone.utc)
    result["finished_at"] = finished_at.isoformat()
    result["duration_s"] = round((finished_at - started_at).total_seconds(), 2)
    # Rough cost estimate: Opus ~ $15/MTok input + $75/MTok output; assume 1-1.5 k tokens/call.
    result["cost_estimate_usd"] = round(
        (result.get("claude_raw_len", 0) / 4 * 0.000075), 4
    )
    result["admin"] = admin

    # Persist audit log (best-effort, no _id echo)
    try:
        if db is not None:
            row = dict(result)
            # If a row was pre-inserted (async queue mode), update it in place.
            existing = await db.build_log.find_one({"build_id": build_id}, projection={"_id": 1})
            if existing:
                await db.build_log.update_one({"build_id": build_id}, {"$set": row})
            else:
                await db.build_log.insert_one(row)
    except Exception as e:
        logger.warning(f"[AuremBuilder] build_log insert failed: {e}")

    return result


async def get_stats(db) -> Dict[str, Any]:
    """Aggregate build_log into dashboard stats."""
    if db is None:
        return {"total": 0, "success": 0, "failed": 0, "success_rate_pct": 0,
                "cost_today_usd": 0.0, "last_build": None}
    total = await db.build_log.count_documents({})
    success = await db.build_log.count_documents({"status": "success"})
    failed = await db.build_log.count_documents({"status": "failed"})
    today_iso = datetime.now(timezone.utc).date().isoformat()
    today_docs = await db.build_log.find(
        {"started_at": {"$regex": f"^{today_iso}"}},
        {"_id": 0, "cost_estimate_usd": 1},
    ).to_list(length=200)
    cost_today = round(sum((d.get("cost_estimate_usd") or 0) for d in today_docs), 4)
    last = await db.build_log.find_one(
        {}, sort=[("started_at", -1)], projection={"_id": 0},
    )
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate_pct": round((success / total) * 100, 1) if total else 0,
        "cost_today_usd": cost_today,
        "last_build": last,
    }


async def list_recent(db, limit: int = 20) -> List[Dict[str, Any]]:
    if db is None:
        return []
    cursor = db.build_log.find({}, projection={"_id": 0}).sort("started_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
