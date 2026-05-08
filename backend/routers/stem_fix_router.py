"""
Stem-Fix Router — Root-Level Refactor Proposals (iter 267 Phase 2).
═══════════════════════════════════════════════════════════════════

Unlike Auto-Fixer which generates *patches* (temporary code injections),
Stem-Fix generates a **structural refactor** of the offending source
file. The core idea: when Sentinel catches an error at `routers/foo.py:142`,
instead of hiding the symptom, Claude analyzes the function + its callers
and returns a clean rewrite that fixes the root cause. Admin approves in
the dashboard, QA Bot regression-tests it, and only then does the rewrite
hit the file.

Flow:
  1. Operator opens an error card in Root Command → clicks "Generate Stem-Fix"
  2. POST /api/admin/stem-fix/generate  →  we extract file+line+traceback,
     read ~80 lines of source context, send to Claude with the
     "structural healing" system prompt
  3. Claude returns a full refactor proposal in strict JSON:
        { target_file, target_function, severity, root_cause, refactor_diff,
          regression_risks, qa_steps }
  4. Stored in db.stem_fixes with status="pending"
  5. GET /api/admin/stem-fix/pending returns the queue
  6. POST /api/admin/stem-fix/{fix_id}/approve writes the refactor to the
     target file (atomic: backup → write → verify import → commit marker)
  7. POST /api/admin/stem-fix/{fix_id}/reject marks as rejected

SAFETY:
  • Never writes outside /app/backend/routers, /app/backend/services, or
    /app/backend/pillars.
  • Backs up the original file to db.stem_fix_backups before touching disk.
  • If Python import fails after write, auto-rollback + mark as failed.

Endpoints:
  POST /api/admin/stem-fix/generate
  GET  /api/admin/stem-fix/pending
  POST /api/admin/stem-fix/{fix_id}/approve
  POST /api/admin/stem-fix/{fix_id}/reject
  GET  /api/admin/stem-fix/{fix_id}
"""
from __future__ import annotations

import ast
import importlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/stem-fix", tags=["Stem Fix"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"

ALLOWED_WRITE_DIRS = [
    "/app/backend/routers",
    "/app/backend/services",
    "/app/backend/pillars",
    "/app/backend/bootstrap",
]


def set_db(db):
    global _db
    _db = db


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            _jwt_secret or os.environ.get("JWT_SECRET", ""),
            algorithms=[_jwt_alg],
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    if not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    """Return the raw Bearer token string (without 'Bearer ' prefix) or None."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1]
    return None


class GenerateRequest(BaseModel):
    error_id: Optional[str] = None
    target_file: Optional[str] = None  # absolute path relative to /app/backend
    target_line: Optional[int] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None


class ApproveRequest(BaseModel):
    confirm: bool = True
    qa_strict: bool = True  # if True, any failing qa_step → auto-rollback


# ══════════════════════════════════════════════════════════════════════
# QA runner — auto-execute Claude's qa_steps after approval
# Each step is a shell-line starting with "curl ..." or "$ curl ...".
# We extract the URL, rewrite any hostname to http://localhost:8001,
# inject the admin Bearer token when needed, run with a 10s timeout,
# and accept HTTP status 2xx|3xx|4xx (4xx is OK for auth-gated endpoints)
# but treat 5xx as a regression failure.
# ══════════════════════════════════════════════════════════════════════

_CURL_URL_RE = re.compile(r"https?://[^\s\"']+")


def _run_qa_steps(qa_steps: list, admin_token: Optional[str]) -> dict:
    """Execute qa_steps against the running server; returns per-step results."""
    import shlex
    import subprocess

    results = []
    passed = 0
    failed = 0

    for raw in (qa_steps or []):
        step = str(raw).strip()
        if step.startswith("$"):
            step = step.lstrip("$").strip()
        if not step.lower().startswith("curl"):
            # Skip instructions that aren't curl commands (e.g., "Start server with…")
            results.append({"cmd": step, "skipped": True, "reason": "not a curl command"})
            continue

        # Rewrite hostnames to our own
        rewritten = _CURL_URL_RE.sub(
            lambda m: re.sub(
                r"^https?://[^/]+",
                "http://localhost:8001",
                m.group(0),
            ),
            step,
        )

        # Force timeout + show status
        cmd = rewritten
        if "-s" not in cmd:
            cmd = cmd.replace("curl ", "curl -s ", 1)
        if "--max-time" not in cmd:
            cmd += " --max-time 8"
        cmd += " -o /dev/null -w 'HTTP_STATUS=%{http_code}'"

        # Inject Bearer token only on endpoints that look authenticated
        # (Claude usually writes `-H 'Authorization: Bearer valid_token'`)
        if admin_token and "Bearer " in cmd and "valid_token" in cmd:
            cmd = cmd.replace("valid_token", admin_token)

        try:
            tokens = shlex.split(cmd)
        except ValueError as e:
            results.append({"cmd": step, "ok": False, "reason": f"shlex parse: {e}"})
            failed += 1
            continue

        try:
            proc = subprocess.run(
                tokens, capture_output=True, text=True, timeout=12
            )
            out = (proc.stdout or "").strip()
            m = re.search(r"HTTP_STATUS=(\d+)", out)
            code = int(m.group(1)) if m else 0
            # 5xx = regression; 2xx/3xx/4xx = acceptable (auth-gated returns 401 etc.)
            ok = 100 <= code < 500
            results.append({
                "cmd": step[:120],
                "status_code": code,
                "ok": ok,
                "stderr": (proc.stderr or "").strip()[:200] if not ok else "",
            })
            if ok:
                passed += 1
            else:
                failed += 1
        except subprocess.TimeoutExpired:
            results.append({"cmd": step[:120], "ok": False, "reason": "timeout"})
            failed += 1
        except Exception as e:
            results.append({"cmd": step[:120], "ok": False, "reason": str(e)[:200]})
            failed += 1

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": len([r for r in results if r.get("skipped")]),
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════════
# Source-code context extraction
# ══════════════════════════════════════════════════════════════════════

def _safe_path(target_file: str) -> Path:
    """Resolve + validate that target_file lives in an allowed directory."""
    p = Path(target_file).resolve()
    for d in ALLOWED_WRITE_DIRS:
        if str(p).startswith(d) and p.is_file():
            return p
    raise HTTPException(
        status_code=400,
        detail=f"target_file must be inside {ALLOWED_WRITE_DIRS}",
    )


def _extract_function_body(path: Path, line: int) -> dict:
    """Find the function/class enclosing `line` and return its source + range."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fall back to a ±30-line window if file is not parseable
        start = max(1, line - 30)
        end = min(len(lines), line + 30)
        return {
            "name": "<unknown>",
            "start_line": start,
            "end_line": end,
            "source": "\n".join(lines[start - 1:end]),
        }

    enclosing = None
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and hasattr(node, "lineno"):
            end = getattr(node, "end_lineno", node.lineno + 50)
            if node.lineno <= line <= end:
                if enclosing is None or node.lineno > enclosing.lineno:
                    enclosing = node

    if enclosing is None:
        start = max(1, line - 30)
        end = min(len(lines), line + 30)
        return {
            "name": "<module-level>",
            "start_line": start,
            "end_line": end,
            "source": "\n".join(lines[start - 1:end]),
        }

    start = enclosing.lineno
    end = getattr(enclosing, "end_lineno", start + 50)
    return {
        "name": enclosing.name,
        "start_line": start,
        "end_line": end,
        "source": "\n".join(lines[start - 1:end]),
    }


# ══════════════════════════════════════════════════════════════════════
# Sandbox — in-memory syntax + lint validation of Claude's output
# BEFORE we show it to the operator. Saves human-review cycles on
# obviously-broken refactors.
# ══════════════════════════════════════════════════════════════════════

def _validate_refactor_in_sandbox(
    original_full: str, start_line: int, end_line: int, new_source: str
) -> tuple[bool, Optional[str]]:
    """Splice `new_source` into `original_full` in memory and check:
      1. AST syntax parse
      2. ruff lint (no E/F errors)
    Returns (ok, error_message).
    """
    if not new_source or len(new_source) < 10:
        return False, "new_function_source too short"

    lines = original_full.splitlines(keepends=True)
    head = "".join(lines[: start_line - 1])
    tail = "".join(lines[end_line:])
    candidate = head + new_source.rstrip() + "\n" + tail

    # 1. AST parse
    try:
        ast.parse(candidate)
    except SyntaxError as e:
        return False, f"SyntaxError: line {e.lineno}: {e.msg}"

    # 2. ruff quick-check (subprocess — fast, isolated)
    try:
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(candidate)
            tmp_path = tf.name
        try:
            result = subprocess.run(
                ["ruff", "check", "--select=E,F", "--no-fix", tmp_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 and result.stdout:
                # Extract first 3 violations for the retry prompt
                violations = [
                    line for line in result.stdout.splitlines()
                    if ":" in line and ("E" in line or "F" in line)
                ][:3]
                if violations:
                    return False, "ruff: " + " | ".join(violations)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except FileNotFoundError:
        # ruff not installed — skip lint, AST is enough
        pass
    except Exception:
        # Don't block on ruff errors
        pass

    return True, None


# ══════════════════════════════════════════════════════════════════════
# Claude call
# ══════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are an expert Python/FastAPI refactoring engineer working on the AUREM platform.

Your job: given an error's root location + source code context, produce a STRUCTURAL REFACTOR (not a patch) of the offending function. A refactor means the function's logic is redesigned to eliminate the class of bug, with the same public signature so callers don't break.

Respond with STRICT JSON only, no prose:
{
  "severity": "critical|high|medium|low",
  "root_cause": "1-2 sentence diagnosis of why this class of bug happens",
  "refactor_strategy": "short description of the redesign approach",
  "regression_risks": ["bullet 1", "bullet 2"],
  "qa_steps": ["curl/test to verify 1", "curl/test to verify 2"],
  "new_function_source": "full Python source of the rewritten function, correctly indented, starts at column 0 (no leading spaces for 'def'/'async def')"
}

Rules:
- `new_function_source` MUST preserve the original function name and argument signature.
- Prefer early-returns, explicit error types, and hard timeouts on any await call.
- Do NOT introduce new top-level imports (move any new imports inside the function).
- Do NOT return anything other than strict JSON."""


async def _claude_generate_refactor(
    function_name: str,
    file_path: str,
    function_source: str,
    error_message: str,
    traceback_text: str,
) -> dict:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"emergentintegrations not installed: {e}",
        )

    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("EMERGENT_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="EMERGENT_LLM_KEY not configured",
        )

    prompt = f"""Target file: {file_path}
Target function: {function_name}

ERROR:
{error_message or '(not provided)'}

TRACEBACK:
{(traceback_text or '(not provided)')[:4000]}

CURRENT FUNCTION SOURCE:
```python
{function_source}
```

Produce the strict JSON refactor response."""

    llm = LlmChat(
        api_key=api_key,
        session_id=f"stem_fix_{uuid.uuid4().hex[:8]}",
        system_message=_SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    user_msg = UserMessage(text=prompt)
    response_text = await llm.send_message(user_msg)

    # Strict JSON extract
    m = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not m:
        raise HTTPException(
            status_code=502,
            detail=f"Claude returned non-JSON response: {response_text[:200]}",
        )
    try:
        return json.loads(m.group())
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Claude JSON parse error: {e}; body={m.group()[:200]}",
        )


# ══════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════

@router.post("/generate")
async def generate(body: GenerateRequest, authorization: Optional[str] = Header(None)):
    """Ask Claude for a root-level refactor proposal. Stored as pending."""
    _verify_admin(authorization)

    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    # Input: either error_id (look up in db.client_errors) or explicit
    # target_file + target_line + error_message.
    target_file = body.target_file
    target_line = body.target_line
    error_message = body.error_message or ""
    traceback_text = body.traceback or ""

    if body.error_id and not (target_file and target_line):
        err = await _db.client_errors.find_one({"id": body.error_id})
        if not err:
            raise HTTPException(status_code=404, detail="error_id not found")
        target_file = err.get("source_file") or err.get("file")
        target_line = err.get("source_line") or err.get("line")
        error_message = error_message or err.get("message", "")
        traceback_text = traceback_text or err.get("stack", "")

    if not target_file or not target_line:
        raise HTTPException(
            status_code=400,
            detail="target_file + target_line required (or an error_id that has them)",
        )

    path = _safe_path(target_file)
    fn_ctx = _extract_function_body(path, int(target_line))
    original_full = path.read_text(encoding="utf-8")

    # ── Sandbox retry loop — up to 3 attempts with Claude ──
    claude_response = None
    sandbox_attempts = []
    last_error = None
    for attempt in range(3):
        if attempt == 0:
            claude_response = await _claude_generate_refactor(
                function_name=fn_ctx["name"],
                file_path=str(path),
                function_source=fn_ctx["source"],
                error_message=error_message,
                traceback_text=traceback_text,
            )
        else:
            # Retry with Claude, passing the sandbox error from last attempt
            claude_response = await _claude_generate_refactor(
                function_name=fn_ctx["name"],
                file_path=str(path),
                function_source=fn_ctx["source"],
                error_message=error_message,
                traceback_text=(
                    f"PREVIOUS REFACTOR ATTEMPT FAILED SANDBOX VALIDATION:\n"
                    f"{last_error}\n\n"
                    f"ORIGINAL TRACEBACK:\n{traceback_text}"
                ),
            )

        new_src = (claude_response or {}).get("new_function_source", "")
        ok, err = _validate_refactor_in_sandbox(
            original_full, fn_ctx["start_line"], fn_ctx["end_line"], new_src
        )
        sandbox_attempts.append(
            {"attempt": attempt + 1, "ok": ok, "error": err}
        )
        if ok:
            break
        last_error = err

    if not (claude_response and sandbox_attempts and sandbox_attempts[-1]["ok"]):
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Claude could not produce a sandbox-valid refactor after 3 attempts",
                "attempts": sandbox_attempts,
            },
        )

    fix_id = f"stemfix-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": fix_id,
        "status": "pending",
        "target_file": str(path),
        "target_function": fn_ctx["name"],
        "start_line": fn_ctx["start_line"],
        "end_line": fn_ctx["end_line"],
        "original_source": fn_ctx["source"],
        "claude_response": claude_response,
        "sandbox_attempts": sandbox_attempts,
        "sandbox_ok": True,
        "error_id": body.error_id,
        "error_message": error_message[:500],
        "created_at": now,
        "updated_at": now,
    }
    await _db.stem_fixes.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "fix_id": fix_id, "stem_fix": doc}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "component": "stem-fix",
        "db_ready": _db is not None,
        "llm_configured": bool(
            os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("EMERGENT_API_KEY")
        ),
        "allowed_write_dirs": ALLOWED_WRITE_DIRS,
    }


@router.get("/pending")
async def pending(authorization: Optional[str] = Header(None)):
    """List all pending + recently-resolved stem fixes (last 24h)."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    items = await _db.stem_fixes.find(
        {},
        {"_id": 0},
        sort=[("created_at", -1)],
        limit=50,
    ).to_list(50)

    by_status = {"pending": [], "approved": [], "rejected": [], "failed": []}
    for it in items:
        by_status.setdefault(it.get("status", "pending"), []).append(it)

    return {
        "ok": True,
        "total": len(items),
        "by_status": by_status,
        "items": items,
    }


@router.get("/{fix_id}")
async def get_one(fix_id: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    item = await _db.stem_fixes.find_one({"id": fix_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="stem_fix not found")
    return {"ok": True, "stem_fix": item}


@router.post("/{fix_id}/reject")
async def reject(fix_id: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    r = await _db.stem_fixes.update_one(
        {"id": fix_id, "status": "pending"},
        {
            "$set": {
                "status": "rejected",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    if r.modified_count == 0:
        raise HTTPException(status_code=404, detail="not pending or not found")
    return {"ok": True, "fix_id": fix_id, "status": "rejected"}


@router.post("/{fix_id}/approve")
async def approve(
    fix_id: str,
    body: ApproveRequest = ApproveRequest(),
    authorization: Optional[str] = Header(None),
):
    """Write the refactor to disk. Atomic with auto-rollback on import failure."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    sf = await _db.stem_fixes.find_one({"id": fix_id})
    if not sf:
        raise HTTPException(status_code=404, detail="stem_fix not found")
    if sf.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"status is {sf.get('status')}, cannot approve")

    new_source = sf.get("claude_response", {}).get("new_function_source", "")
    if not new_source or len(new_source) < 20:
        raise HTTPException(
            status_code=400,
            detail="Claude response has no usable new_function_source",
        )

    path = _safe_path(sf["target_file"])
    start = int(sf["start_line"])
    end = int(sf["end_line"])

    # Backup original file
    original_full = path.read_text(encoding="utf-8")
    await _db.stem_fix_backups.insert_one(
        {
            "fix_id": fix_id,
            "target_file": str(path),
            "backed_up_at": datetime.now(timezone.utc).isoformat(),
            "original_full_source": original_full,
        }
    )

    # Splice — replace lines [start..end] with new_source
    lines = original_full.splitlines(keepends=True)
    head = "".join(lines[: start - 1])
    tail = "".join(lines[end:])
    new_full = head + new_source.rstrip() + "\n" + tail

    # Write
    path.write_text(new_full, encoding="utf-8")

    # Verify syntactic + import correctness
    verify_error: Optional[str] = None
    try:
        ast.parse(new_full)
        # Attempt to reload the module if it's already in sys.modules
        module_path = str(path)
        if "/app/backend/" in module_path:
            rel = module_path.replace("/app/backend/", "").replace(".py", "").replace("/", ".")
            try:
                if rel in importlib.sys.modules:
                    importlib.reload(importlib.sys.modules[rel])
            except Exception as reload_err:
                verify_error = f"reload failed: {reload_err}"
    except SyntaxError as e:
        verify_error = f"SyntaxError: {e}"

    if verify_error:
        # Auto-rollback
        path.write_text(original_full, encoding="utf-8")
        await _db.stem_fixes.update_one(
            {"id": fix_id},
            {
                "$set": {
                    "status": "failed",
                    "failure_reason": verify_error,
                    "rolled_back_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return {
            "ok": False,
            "fix_id": fix_id,
            "status": "failed",
            "reason": verify_error,
            "rolled_back": True,
        }

    # ── Phase 3: QA Self-Verification ──
    # Auto-execute Claude's qa_steps against the running server. If any
    # step returns 5xx (and qa_strict=True), roll the file back.
    qa_steps = sf.get("claude_response", {}).get("qa_steps", []) or []
    qa_result = _run_qa_steps(qa_steps, admin_token=_extract_bearer(authorization))

    now_iso = datetime.now(timezone.utc).isoformat()

    if body.qa_strict and qa_result["failed"] > 0:
        # QA regression — rollback
        path.write_text(original_full, encoding="utf-8")
        # Re-reload module so in-memory state matches disk
        try:
            module_path = str(path)
            if "/app/backend/" in module_path:
                rel = module_path.replace("/app/backend/", "").replace(".py", "").replace("/", ".")
                if rel in importlib.sys.modules:
                    importlib.reload(importlib.sys.modules[rel])
        except Exception:
            pass
        await _db.stem_fixes.update_one(
            {"id": fix_id},
            {
                "$set": {
                    "status": "regression_failed",
                    "qa_result": qa_result,
                    "rolled_back_at": now_iso,
                    "updated_at": now_iso,
                }
            },
        )
        logger.warning(
            f"[STEM-FIX] {fix_id} rolled back after QA regression "
            f"({qa_result['failed']}/{qa_result['total']} failed)"
        )
        return {
            "ok": False,
            "fix_id": fix_id,
            "status": "regression_failed",
            "qa_result": qa_result,
            "rolled_back": True,
        }

    # All QA green — mark verified
    final_status = "verified" if qa_result["passed"] > 0 else "approved"
    await _db.stem_fixes.update_one(
        {"id": fix_id},
        {
            "$set": {
                "status": final_status,
                "applied_at": now_iso,
                "qa_result": qa_result,
                "updated_at": now_iso,
            }
        },
    )

    logger.info(
        f"[STEM-FIX] {fix_id} → {final_status} — "
        f"QA passed {qa_result['passed']}/{qa_result['total']}"
    )
    return {
        "ok": True,
        "fix_id": fix_id,
        "status": final_status,
        "target_file": str(path),
        "target_function": sf["target_function"],
        "qa_result": qa_result,
    }

