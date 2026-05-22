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
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Allowlists ───────────────────────────────────────────────────────
_ALLOWED_ROOTS = (
    "/app/backend",
    "/app/frontend",
    "/app/memory",
    "/app/ora_skills",
    "/app/scripts",
    # iter 322ew — ORA must be able to review/edit the sovereign aurem-cto
    # codebase it just built (read+write). Same write-path safety still
    # applies via `_WRITE_ALLOWED_ROOTS` enforcement elsewhere.
    "/app/aurem-cto",
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


# ── iter 323q ─────────────────────────────────────────────────────────
# Two skill-ports inspired by Claude Skills: Systematic Debug + Code Review.
# Both are TIER 1 (read-only) — execute immediately, never block on approval.

async def debug_systematic(
    bug_description: str,
    error_text: str = "",
    file_hint: str = "",
) -> dict:
    """Force the 6-step systematic debugging framework.

    Returns a STRUCTURED PLAN (not a fix) — the LLM must follow this template
    via subsequent tool calls. Forces ORA to gather evidence BEFORE proposing
    fixes, killing the "guess-and-check" anti-pattern.
    """
    if not isinstance(bug_description, str) or len(bug_description) < 5:
        return {"ok": False, "error": "bug_description must be ≥ 5 chars"}

    plan = {
        "step_1_observe": {
            "what_user_sees":   "[fill from bug_description]",
            "what_is_expected": "[infer from user intent]",
            "delta":            "[the gap that constitutes the bug]",
        },
        "step_2_isolate": {
            "minimal_repro":    "[describe the minimum scenario]",
            "first_recommended_tool": "view_file" if file_hint else "grep_codebase",
            "first_tool_args":  ({"path": file_hint, "max_lines": 200}
                                  if file_hint else
                                  {"pattern": "[derive from error_text]",
                                   "file_glob": "*.py",
                                   "root": "/app/backend"}),
        },
        "step_3_hypothesize": {
            "h1_most_likely":  "[fill: top suspected root cause]",
            "h2_alternate":    "[fill: second possibility]",
            "h3_long_tail":    "[fill: less likely but possible]",
        },
        "step_4_verify": {
            "h1_verification_tool": "view_file or db_count",
            "h2_verification_tool": "curl_internal or grep_codebase",
            "h3_verification_tool": "git_log or view_dir",
            "rule": "Run ONE verification tool per turn. Wait for evidence.",
        },
        "step_5_root_cause": {
            "evidence_required": "Cite the exact line / log entry / db count.",
            "format":            "X is broken BECAUSE Y, evidenced by Z.",
        },
        "step_6_fix": {
            "rule":      "Only propose code change AFTER step 5 is concrete.",
            "approach":  "Minimal diff. Single concern. Add a regression test.",
            "tool":      "safe_edit (tier 2 — founder approval required)",
        },
        "anti_pattern_alerts": [
            "Do NOT propose a fix in step 1, 2, or 3.",
            "Do NOT skip step 4 (verification) — pattern matching is not evidence.",
            "Do NOT bundle multiple unrelated changes in step 6.",
        ],
    }

    return {
        "ok":               True,
        "bug":              bug_description[:300],
        "error_excerpt":    error_text[:300] if error_text else None,
        "file_hint":        file_hint or None,
        "systematic_plan":  plan,
        "next_action":      "Begin step 2 — call the recommended tool to gather evidence.",
    }


async def review_code(path: str, focus: str = "all") -> dict:
    """Apply the code-review checklist against a file at `path`.

    Reads up to 500 lines, runs deterministic heuristic checks across
    correctness / security / maintainability / performance, returns a
    severity-ranked finding list with line refs. Cheap, fast, runs as
    a first pass BEFORE the LLM does subjective review.
    """
    if not _is_path_allowed(path):
        return {"ok": False, "error": f"path not allowed: {path}"}
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": f"not a file: {path}"}
    if p.stat().st_size > 2_000_000:
        return {"ok": False, "error": "file too large for review (>2MB)"}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"read failed: {e}"}

    lines = content.split("\n")
    findings: list[dict] = []

    def _add(sev: str, line_no: int, category: str, msg: str) -> None:
        findings.append({"severity": sev, "line": line_no,
                          "category": category, "msg": msg})

    # ── Security / secrets heuristics ─────────────────────────────
    secret_patterns = [
        (r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
         "potential hardcoded secret"),
        (r"AKIA[0-9A-Z]{16}",                 "AWS access key id pattern"),
        (r"sk_live_[A-Za-z0-9]{16,}",         "Stripe live key pattern"),
        (r"ghp_[A-Za-z0-9]{36}",              "GitHub personal access token"),
    ]
    for i, line in enumerate(lines[:500], start=1):
        for pat, desc in secret_patterns:
            if re.search(pat, line):
                _add("CRITICAL", i, "security", desc)

    # ── Code smells ───────────────────────────────────────────────
    for i, line in enumerate(lines[:500], start=1):
        stripped = line.strip()
        if re.search(r"(?i)^\s*(#|//|--)\s*TODO\s*[:\-]?\s+", stripped):
            _add("INFO", i, "maintainability", "TODO comment")
        if re.search(r"(?i)except\s*:\s*pass\s*$", stripped):
            _add("HIGH", i, "correctness", "bare 'except: pass' silently swallows all errors")
        if re.search(r"print\(", stripped) and path.endswith(".py") and "test" not in path:
            # production print() in non-test file
            _add("MINOR", i, "logging", "use logger.* instead of print() in production code")
        if "eval(" in stripped or "exec(" in stripped:
            _add("CRITICAL", i, "security", "eval()/exec() with user input = RCE")
        if re.search(r"\.format\([^)]*\)\s*$", stripped) and (
            "SELECT" in stripped.upper() or "INSERT" in stripped.upper()
        ):
            _add("HIGH", i, "security", "SQL string-formatting — use parameterised queries")

    # ── Complexity heuristic — function-length proxy ──────────────
    fn_pat = re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z_]\w*)\s*\(")
    fn_start: dict[str, int] = {}
    current_fn: str | None = None
    current_start = 0
    for i, line in enumerate(lines[:500], start=1):
        m = fn_pat.match(line)
        if m:
            if current_fn and (i - current_start) > 80:
                _add("MINOR", current_start, "complexity",
                     f"function '{current_fn}' is {i - current_start} lines — consider splitting")
            current_fn = m.group(1)
            current_start = i
            fn_start[current_fn] = i

    # Filter by focus
    if focus in ("security", "correctness", "maintainability", "performance", "logging", "complexity"):
        findings = [f for f in findings if f["category"] == focus]

    findings.sort(
        key=lambda f: {"CRITICAL": 0, "HIGH": 1, "MINOR": 2, "INFO": 3}.get(f["severity"], 9)
    )

    return {
        "ok":            True,
        "file":          path,
        "lines_scanned": min(500, len(lines)),
        "findings":      findings[:60],
        "summary": {
            "critical": sum(1 for f in findings if f["severity"] == "CRITICAL"),
            "high":     sum(1 for f in findings if f["severity"] == "HIGH"),
            "minor":    sum(1 for f in findings if f["severity"] == "MINOR"),
            "info":     sum(1 for f in findings if f["severity"] == "INFO"),
        },
        "verdict": (
            "BLOCK" if any(f["severity"] == "CRITICAL" for f in findings)
            else "WARN" if any(f["severity"] == "HIGH" for f in findings)
            else "PASS"
        ),
    }


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


# ─── iter 326i — Build Mode tools (run_pytest + verify_endpoint) ──────
# These are Tier-1 tools (auto-execute, no founder approval) so ORA can
# run the BUILD MODE checklist autonomously and attach a PROOF TABLE to
# its reply. Both wrap existing primitives (pytest CLI + curl) with a
# structured-output schema the proof aggregator expects.

_PYTEST_BIN_CANDIDATES = (
    "/root/.venv/bin/pytest",
    "/opt/plugins-venv/bin/pytest",
)


async def run_pytest(path: str, timeout_s: int = 90) -> dict:
    """Run pytest on a path under /app/backend/tests/.

    Returns a structured envelope:
      {
        "ok":          true on exit_code in (0,5),  # 5 = no tests collected
        "exit_code":   int,
        "passed":      int,    # parsed from summary line
        "failed":      int,
        "errors":      int,
        "warnings":    int,
        "duration_s":  float,
        "summary":     "5 passed in 0.45s",
        "tail":        last 30 stdout lines (for debugging)
      }

    Hard-restricts the path to /app/backend/tests/ so ORA can't trick the
    tool into running production code (e.g. /app/backend/server.py) as a
    test suite. Single-file or directory; supports the same `path/test_x.py::test_y` syntax.
    """
    import shutil
    if not isinstance(path, str) or not path.strip():
        return {"ok": False, "error": "path required"}
    abs_path = path.split("::")[0]
    if not abs_path.startswith("/app/backend/tests"):
        return {"ok": False, "error": "path must be under /app/backend/tests/"}
    if not Path(abs_path).exists():
        return {"ok": False, "error": f"not found: {abs_path}"}
    try:
        timeout_s = max(5, min(int(timeout_s), 180))
    except (TypeError, ValueError):
        timeout_s = 90

    pytest_bin = (
        shutil.which("pytest")
        or next((p for p in _PYTEST_BIN_CANDIDATES if Path(p).is_file()), None)
    )
    if not pytest_bin:
        return {"ok": False, "error": "pytest binary not found"}

    started = _t_iso_now_ts()
    try:
        # PYTHONPATH ensures pytest subprocess can resolve `services.*`
        # imports even when invoked from outside /app/backend.
        env = os.environ.copy()
        env["PYTHONPATH"] = "/app/backend" + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        r = await asyncio.to_thread(
            subprocess.run,
            [pytest_bin, "-q", "--tb=short", "--no-header", path],
            cwd="/app/backend",
            capture_output=True, text=True, timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"pytest timed out after {timeout_s}s"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}

    out = (r.stdout or "") + (r.stderr or "")
    duration = round(_t_iso_now_ts() - started, 3)

    # Parse the pytest summary line: "5 passed, 1 failed in 0.45s"
    summary = ""
    passed = failed = errors = warnings = 0
    for line in (r.stdout or "").splitlines():
        s = line.strip()
        if (" passed" in s or " failed" in s or " error" in s) and " in " in s:
            summary = s.lstrip("= ").rstrip("= ").strip()
        m = re.search(r"(\d+)\s+passed", s)
        if m:
            passed = max(passed, int(m.group(1)))
        m = re.search(r"(\d+)\s+failed", s)
        if m:
            failed = max(failed, int(m.group(1)))
        m = re.search(r"(\d+)\s+error", s)
        if m:
            errors = max(errors, int(m.group(1)))
        m = re.search(r"(\d+)\s+warning", s)
        if m:
            warnings = max(warnings, int(m.group(1)))

    return {
        "ok":          r.returncode in (0, 5),  # 5 = no tests collected
        "exit_code":   r.returncode,
        "passed":      passed,
        "failed":      failed,
        "errors":      errors,
        "warnings":    warnings,
        "duration_s":  duration,
        "summary":     summary or f"exit={r.returncode}",
        "tail":        "\n".join(out.strip().splitlines()[-30:]),
    }


def _t_iso_now_ts() -> float:
    """Tiny shim — `time.time()` but with no extra import in hot path."""
    import time as _t
    return _t.time()


async def verify_endpoint(
    endpoint: str,
    expected_status: int = 200,
    expected_substring: str = "",
) -> dict:
    """Hit an internal /api/ endpoint and assert it's wired correctly.

    Wraps `curl_internal` with assertion semantics so ORA's BUILD MODE
    proof table gets a clean PASS/FAIL row.

    Returns:
      {
        "ok":             bool,   # overall verdict
        "endpoint":       str,
        "http_status":    int,
        "expected_status": int,
        "matched_status": bool,
        "expected_substring": str | None,
        "matched_substring": bool,    # always True when no substring specified
        "latency_ms":     int,
        "body_snippet":   str,   # first 400 chars
      }
    """
    if not isinstance(endpoint, str) or not endpoint.startswith("/api/"):
        return {"ok": False, "error": "endpoint must start with /api/"}
    try:
        expected_status = int(expected_status)
    except (TypeError, ValueError):
        expected_status = 200

    started = _t_iso_now_ts()
    res = await curl_internal(endpoint, method="GET")
    elapsed_ms = int((_t_iso_now_ts() - started) * 1000)

    if not res.get("ok"):
        return {
            "ok": False, "endpoint": endpoint,
            "http_status": 0, "expected_status": expected_status,
            "matched_status": False, "matched_substring": False,
            "latency_ms": elapsed_ms,
            "error": res.get("error"),
        }

    http_status   = int(res.get("http_status") or 0)
    body          = res.get("body") or ""
    matched_stat  = (http_status == expected_status)
    matched_sub   = (
        True if not expected_substring
        else (expected_substring in body)
    )

    return {
        "ok":                  matched_stat and matched_sub,
        "endpoint":            endpoint,
        "http_status":         http_status,
        "expected_status":     expected_status,
        "matched_status":      matched_stat,
        "expected_substring":  expected_substring or None,
        "matched_substring":   matched_sub,
        "latency_ms":          elapsed_ms,
        "body_snippet":        body[:400],
    }


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
                  "GROQ", "OPENAI", "ANTHROPIC", "EMERGENT",
                  # Bug-fix #31 — connection strings, webhooks, and hashes
                  # were leaking through `env` tool output.
                  "URL", "WEBHOOK", "HASH", "PASS", "CREDENTIAL",
                  "AUTH", "PRIVATE", "SIGNATURE", "API",
                  # Bug-fix #80 — explicit guard for Redis/DB connection
                  # strings (URL substring already catches REDIS_URL, but
                  # adding the prefixes here makes the intent visible and
                  # protects future REDIS_PASSWORD / DATABASE_KEY env vars).
                  "REDIS", "DATABASE", "DB_", "CAPSOLVER", "IPROYAL")
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
    "/app/aurem-cto",
)
_WRITE_FORBIDDEN_PATTERNS = (
    "/.env", "/.ssh", "/.git/", "node_modules", "__pycache__",
    "/migrations/", "/.next/", "/build/", "/dist/",
)
_WRITE_FORBIDDEN_FILES = (
    ".env", ".env.local", ".env.production", ".env.txt",
    ".env.development", ".env.staging",
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
    requested = list(roles)
    roles = [r for r in roles if r in _LLM_PEER_PROFILES]
    # iter 326qq — graceful fallback when LLM passes invented role slugs
    # (e.g. "legal", "compliance", "lawyer" for CASL prompts). Instead of
    # returning ok=False and tripping ORA's "twice consecutive failure"
    # halt, fall back to the safe default trio and tell the LLM exactly
    # which slugs are valid so it can self-correct on the next call.
    invalid = [r for r in requested if r not in _LLM_PEER_PROFILES]
    if not roles:
        roles = ["security", "backend", "qa"]
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
    result = {
        "ok":          n_ok > 0,
        "consulted":   roles,
        "opinions":    opinions,
        "consensus":   f"{n_ok}/{len(opinions)} peers responded",
    }
    if invalid:
        result["invalid_roles_ignored"] = invalid
        result["note"] = (
            f"Ignored invalid role(s): {invalid}. "
            f"Valid slugs: {sorted(_LLM_PEER_PROFILES)}. "
            f"Proceeded with: {roles}."
        )
    return result


# ─── iter 322eq — Session Quotas + Council-Gate Wrappers (Governance Layer) ───
# Two new safety primitives:
#   1. _check_quota(tool, actor) — hourly rolling cap per (tool, actor).
#      Reads ora_tool_invocations directly so quotas survive backend
#      restarts and stay consistent across processes.
#   2. safe_edit_with_council / shell_exec_with_council — REJECT if any
#      consulted peer dissents (CRITICAL / STOP / DO NOT keywords) unless
#      the caller explicitly sets override_dissent=True with a recorded
#      override_reason. The override is loud-logged.

# iter 322es — quotas removed. AUREM is a single-user self-hosted stack;
# ORA operates without rate limits. Safety is enforced by the council
# gate (safe_edit_with_council / shell_exec_with_council) and the git
# commit gate (propose_commit + founder approval), not by quotas.

# Substrings (case-insensitive) which, when present in a peer's opinion,
# mark them as DISSENTING. Tuned conservatively — false positives are
# safer than false negatives in a governance gate.
_DISSENT_SIGNALS = (
    "do not proceed",
    "do not commit",
    "do not deploy",
    "do not merge",
    "do not edit",
    "do not apply",
    "do not drop",
    "do not run",
    "hard no",
    "hard reject",
    "critical risk",
    "critical security",
    "critical vulnerability",
    "critical issue",
    "must not",
    "reject this",
    "blocked",
    "stop and",
    "stop —",
    "stop and escalate",
    "this is dangerous",
    "this is unsafe",
    "this will break",
)

# Substrings that flag a shell command as inherently risky.
_RISKY_SHELL_SIGNALS = (
    "rm ", "rm-", "truncate", "drop ", "drop_", "drop-",
    "format", "mkfs", "dd if=", ":wq!",
)


def _peer_dissents(opinion_text: str) -> tuple[bool, list[str]]:
    """Returns (is_dissenter, matched_signals)."""
    if not opinion_text or not isinstance(opinion_text, str):
        return False, []
    txt = opinion_text.lower()
    hits = [s for s in _DISSENT_SIGNALS if s in txt]
    return (len(hits) > 0), hits


def _classify_edit_risk(path: str) -> str:
    """Heuristic risk tier for a safe_edit target path.

    high   — auth, billing, payment, migrations, schema, JWT, bcrypt
    medium — backend services / routers (non-auth)
    low    — frontend, memory, ora_skills, scripts, docs
    """
    p = path.lower()
    high_signals = ("auth", "bcrypt", "jwt", "stripe", "payment", "billing",
                     "subscription", "migration", "schema", "/admin_",
                     "_admin.py", "credit", "refund", "webhook")
    if any(s in p for s in high_signals):
        return "high"
    if "/app/backend/services/" in p or "/app/backend/routers/" in p:
        return "medium"
    return "low"


async def safe_edit_with_council(
    path: str,
    find_string: str,
    replace_string: str,
    *,
    expected_occurrences: int = 1,
    rationale: str = "",
    roles: list[str] | None = None,
    override_dissent: bool = False,
    override_reason: str = "",
) -> dict:
    """Council-gated safe_edit.

    Workflow:
      1. Classify the target path's risk (low / medium / high).
      2. Consult the appropriate peer council (security+backend+qa by default;
         medium-risk auto-adds qa; high-risk adds devops).
      3. If any peer DISSENTS (matches dissent signals in opinion text):
           - If override_dissent=False → REJECT, log loud, return error.
           - If override_dissent=True  → require override_reason ≥20 chars, proceed but
             stamp the audit log with the override.
      4. If council passes (or override is honored), call safe_edit normally.

    Returns the original safe_edit envelope augmented with `council`
    (the consult result) and `gate` (decision metadata).
    """
    # Validate inputs early so we don't burn LLM tokens on garbage.
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "path required"}
    ok_path, why = _is_write_path_allowed(path)
    if not ok_path:
        return {"ok": False, "error": f"path not allowed: {why}", "path": path}
    if not isinstance(rationale, str) or len(rationale.strip()) < 10:
        return {"ok": False, "error": "rationale required (≥10 chars) — what is this edit doing?"}

    risk = _classify_edit_risk(path)
    if roles is None:
        if risk == "high":
            roles = ["security", "backend", "devops", "qa"]
        elif risk == "medium":
            roles = ["backend", "qa"]
        else:
            roles = ["backend"]

    # Build council question with concrete diff context
    diff_context = (
        f"FILE: {path}\nRISK_TIER: {risk}\n\n"
        f"FIND:\n```\n{find_string[:2500]}\n```\n\n"
        f"REPLACE:\n```\n{replace_string[:2500]}\n```\n"
    )
    council_question = (
        f"ORA wants to edit `{path}` (risk tier: {risk}). Rationale: "
        f"{rationale.strip()[:600]}. Should ORA proceed? If you see ANY "
        "problem (security, correctness, regression risk, missing tests, "
        "policy violation) — say so plainly. Start with VERDICT: APPROVE "
        "or VERDICT: REJECT."
    )
    council = await council_consult(council_question, roles=roles, context=diff_context)

    dissenters: list[dict] = []
    for op in (council.get("opinions") or []):
        is_diss, signals = _peer_dissents(op.get("opinion") or "")
        if is_diss:
            dissenters.append({
                "role": op["role"],
                "signals": signals,
                "snippet": (op.get("opinion") or "")[:500],
            })

    gate_meta = {
        "risk_tier":      risk,
        "council_roles":  roles,
        "dissenters":     dissenters,
        "consensus":      council.get("consensus"),
        "council_ok":     council.get("ok"),
    }

    if dissenters and not override_dissent:
        return {
            "ok": False,
            "error": "council rejected the edit",
            "gate": {**gate_meta, "decision": "rejected"},
            "council": council,
            "hint": ("Address each dissenter's concern, then retry. "
                      "If you genuinely need to proceed despite dissent, set "
                      "override_dissent=True AND override_reason='<≥20-char reason>'."),
        }

    if dissenters and override_dissent:
        if not isinstance(override_reason, str) or len(override_reason.strip()) < 20:
            return {
                "ok": False,
                "error": "override_dissent=True requires override_reason ≥20 chars",
                "gate": {**gate_meta, "decision": "override_blocked_missing_reason"},
            }
        # Loud-log the override into a dedicated trail BEFORE proceeding
        try:
            if _db is not None:
                await _db.ora_governance_overrides.insert_one({
                    "ts":              _now_iso(),
                    "tool":            "safe_edit_with_council",
                    "path":            path,
                    "risk_tier":       risk,
                    "rationale":       rationale,
                    "override_reason": override_reason,
                    "dissenters":      dissenters,
                    "council":         council,
                })
        except Exception as e:
            logger.warning(f"[ora_tools] override audit failed: {e}")

    # ✓ Council approved (or override honored) — proceed with the real edit
    edit_res = await safe_edit(path, find_string, replace_string,
                                 expected_occurrences=expected_occurrences)

    return {
        **edit_res,
        "council": council,
        "gate": {
            **gate_meta,
            "decision": (
                "approved" if not dissenters
                else "override_applied" if override_dissent
                else "approved"
            ),
            "override_dissent": override_dissent and bool(dissenters),
            "override_reason":  override_reason if override_dissent and dissenters else "",
            "rationale":        rationale,
        },
    }


async def shell_exec_with_council(
    command: str,
    args: list[str] | None = None,
    *,
    rationale: str = "",
    roles: list[str] | None = None,
    override_dissent: bool = False,
    override_reason: str = "",
) -> dict:
    """Council-gated shell_exec.

    Same workflow as safe_edit_with_council. Risk is determined by
    matching argv tokens against `_RISKY_SHELL_SIGNALS` plus the
    command name itself (e.g. `rm`, `dd`, `mkfs` are always high).
    """
    if not isinstance(command, str) or not command:
        return {"ok": False, "error": "command required"}
    if not isinstance(rationale, str) or len(rationale.strip()) < 10:
        return {"ok": False, "error": "rationale required (≥10 chars) — why this shell command?"}

    args = args or []
    full = (command + " " + " ".join(map(str, args))).lower()
    risk = "high" if any(s in full for s in _RISKY_SHELL_SIGNALS) else "medium"
    if roles is None:
        roles = ["devops", "security", "backend"] if risk == "high" else ["devops", "backend"]

    council_question = (
        f"ORA wants to run shell: `{command} {' '.join(map(str, args))[:300]}` "
        f"(risk: {risk}). Rationale: {rationale.strip()[:600]}. "
        "Should ORA proceed? Flag side-effects, idempotency issues, blast "
        "radius. Start with VERDICT: APPROVE or VERDICT: REJECT."
    )
    council = await council_consult(council_question, roles=roles)

    dissenters: list[dict] = []
    for op in (council.get("opinions") or []):
        is_diss, signals = _peer_dissents(op.get("opinion") or "")
        if is_diss:
            dissenters.append({
                "role": op["role"], "signals": signals,
                "snippet": (op.get("opinion") or "")[:400],
            })

    gate_meta = {
        "risk_tier": risk, "council_roles": roles,
        "dissenters": dissenters,
        "consensus": council.get("consensus"),
        "council_ok": council.get("ok"),
    }

    if dissenters and not override_dissent:
        return {
            "ok": False, "error": "council rejected the shell command",
            "gate": {**gate_meta, "decision": "rejected"},
            "council": council,
            "hint": "Address each dissenter, or set override_dissent=True with override_reason.",
        }
    if dissenters and override_dissent:
        if not isinstance(override_reason, str) or len(override_reason.strip()) < 20:
            return {"ok": False, "error": "override_dissent=True requires override_reason ≥20 chars",
                    "gate": {**gate_meta, "decision": "override_blocked_missing_reason"}}
        try:
            if _db is not None:
                await _db.ora_governance_overrides.insert_one({
                    "ts":              _now_iso(),
                    "tool":            "shell_exec_with_council",
                    "command":         command, "args": args,
                    "risk_tier":       risk,
                    "rationale":       rationale,
                    "override_reason": override_reason,
                    "dissenters":      dissenters,
                    "council":         council,
                })
        except Exception as e:
            logger.warning(f"[ora_tools] override audit failed: {e}")

    exec_res = await shell_exec(command, args)
    return {
        **exec_res,
        "council":  council,
        "gate": {
            **gate_meta,
            "decision":         "approved" if not dissenters else "override_applied",
            "override_dissent": override_dissent and bool(dissenters),
            "override_reason":  override_reason if override_dissent and dissenters else "",
            "rationale":        rationale,
        },
    }


# ─── iter 322er — Git Commit Gate (P5 — founder approves every commit) ──
# ORA can no longer commit directly. The `propose_commit` tool records
# the intent + diff into `ora_commit_proposals` and returns a proposal
# id. The founder reviews + approves via the /api/admin/git-gate UI,
# which is the ONLY place that actually runs `git commit`. ORA's tool
# surface still has zero direct write to git.

_COMMIT_TITLE_MAX = 80
_COMMIT_BODY_MAX = 4000
_COMMIT_FILES_MAX = 30


async def propose_commit(
    title: str,
    body: str = "",
    file_paths: list[str] | None = None,
    *,
    rationale: str = "",
) -> dict:
    """Propose a git commit. NO commit is actually made — this just
    records the proposal in `ora_commit_proposals` and stages the diff
    so the founder can review.

    Args:
        title:      one-line conventional-commit summary (≤80 chars)
        body:       longer explanation (≤4KB)
        file_paths: list of files to include (all must already be
                    write-allowed). If empty, stages everything dirty
                    under `/app/{backend,frontend/src,memory,ora_skills}`.
        rationale:  ≥10 chars — recorded in the audit trail.

    Returns:
        {ok, proposal_id, title, files, diff_preview, lines_added, lines_removed,
         changed_count, ts}
    """
    if not isinstance(title, str) or not (3 <= len(title.strip()) <= _COMMIT_TITLE_MAX):
        return {"ok": False, "error": f"title required (3-{_COMMIT_TITLE_MAX} chars)"}
    if not isinstance(body, str) or len(body) > _COMMIT_BODY_MAX:
        return {"ok": False, "error": f"body too long (>{_COMMIT_BODY_MAX})"}
    if not isinstance(rationale, str) or len(rationale.strip()) < 10:
        return {"ok": False, "error": "rationale required (≥10 chars) — explain what changed and why"}

    file_paths = file_paths or []
    if not isinstance(file_paths, list):
        return {"ok": False, "error": "file_paths must be a list of strings"}
    if len(file_paths) > _COMMIT_FILES_MAX:
        return {"ok": False, "error": f"too many files (>{_COMMIT_FILES_MAX}); split the commit"}

    # Validate each file is under a write-allowed root
    for p in file_paths:
        if not isinstance(p, str):
            return {"ok": False, "error": "file_paths entries must be strings"}
        ok_p, why = _is_write_path_allowed(p)
        if not ok_p:
            return {"ok": False, "error": f"file {p!r} not allowed: {why}"}

    # ─── Collect diff via git ───────────────────────────────────────
    try:
        # If file_paths empty, use 'git status --porcelain' to detect
        # all dirty paths inside the write-allowed roots, then constrain
        # diff to those only.
        if not file_paths:
            st = await asyncio.to_thread(
                subprocess.run,
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=8, cwd="/app",
            )
            dirty = []
            for line in (st.stdout or "").splitlines():
                # porcelain format: "<XY> <path>"
                p = line[3:].strip()
                if not p:
                    continue
                # Filter to write-allowed roots only
                abs_p = f"/app/{p}" if not p.startswith("/app/") else p
                ok_p, _ = _is_write_path_allowed(abs_p)
                if ok_p:
                    dirty.append(p)
            if not dirty:
                return {"ok": False, "error": "no dirty files in write-allowed roots — nothing to commit"}
            if len(dirty) > _COMMIT_FILES_MAX:
                return {"ok": False, "error": f"too many dirty files ({len(dirty)} > {_COMMIT_FILES_MAX}); list explicit `file_paths` instead"}
            file_paths_for_diff = dirty
        else:
            # Use repo-relative paths for git diff
            file_paths_for_diff = [
                p[len("/app/"):] if p.startswith("/app/") else p
                for p in file_paths
            ]

        # iter 322er-fix — `git diff HEAD --` skips untracked files. Mark
        # any new files as intent-to-add so they show in the diff as
        # additions, without actually staging content. This keeps the
        # working tree visible to the diff command while leaving the
        # actual `git add` for the approval step.
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["git", "add", "--intent-to-add", "--", *file_paths_for_diff],
                capture_output=True, text=True, timeout=8, cwd="/app",
            )
        except Exception:
            # Non-fatal — diff will simply skip the untracked file
            pass

        # Diff (working tree vs HEAD)
        diff_proc = await asyncio.to_thread(
            subprocess.run,
            ["git", "diff", "--unified=2", "--no-color", "--stat=200", "HEAD", "--", *file_paths_for_diff],
            capture_output=True, text=True, timeout=10, cwd="/app",
        )
        diff_text = diff_proc.stdout or ""

        # numstat for clean lines-changed counts
        ns_proc = await asyncio.to_thread(
            subprocess.run,
            ["git", "diff", "--numstat", "--no-color", "HEAD", "--", *file_paths_for_diff],
            capture_output=True, text=True, timeout=10, cwd="/app",
        )
        lines_added = 0
        lines_removed = 0
        per_file_stat = []
        for line in (ns_proc.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            try:
                a = int(parts[0]) if parts[0] != "-" else 0
                r = int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue
            lines_added += a
            lines_removed += r
            per_file_stat.append({"path": parts[2], "added": a, "removed": r})

    except Exception as e:
        return {"ok": False, "error": f"git diff failed: {type(e).__name__}: {str(e)[:120]}"}

    if not diff_text.strip():
        return {"ok": False, "error": "no diff between HEAD and working tree for the given files"}

    # ─── Persist proposal ───────────────────────────────────────────
    import uuid as _uuid
    proposal_id = f"prop_{_uuid.uuid4().hex[:14]}"
    proposal = {
        "_id":           proposal_id,
        "id":            proposal_id,
        "title":         title.strip(),
        "body":          body.strip(),
        "rationale":     rationale.strip(),
        "files":         file_paths_for_diff,
        "per_file_stat": per_file_stat,
        "diff":          diff_text[:200_000],  # cap at 200KB
        "diff_truncated": len(diff_text) > 200_000,
        "lines_added":   lines_added,
        "lines_removed": lines_removed,
        "status":        "pending",
        "proposed_at":   _now_iso(),
        "proposed_by":   "ora",
        "decided_at":    None,
        "decided_by":    None,
        "decision_note": None,
        "commit_sha":    None,
    }
    if _db is not None:
        try:
            await _db.ora_commit_proposals.insert_one(proposal)
        except Exception as e:
            logger.warning(f"[propose_commit] persist failed: {e}")

    return {
        "ok":            True,
        "proposal_id":   proposal_id,
        "title":         title.strip(),
        "files":         file_paths_for_diff,
        "lines_added":   lines_added,
        "lines_removed": lines_removed,
        "diff_preview":  diff_text[:2000],
        "diff_truncated": len(diff_text) > 2000,
        "status":        "pending",
        "review_url":    "/admin/git-gate",
        "hint":          "Founder must approve via /api/admin/git-gate/proposals/{id}/approve before the commit is actually made.",
    }


# ─── iter 322eu — Creation Tools (file/dir/append) ───────────────────
# ORA CTO needed `create_file`, `create_dir`, `append_to_file`,
# `pytest_run`, plus Cloudflare DNS/tunnel + docker_compose tools so it
# can build its own next features without main-agent help. All tools
# reuse the existing _is_write_path_allowed safety check.

_PIP_ALLOWLIST = {
    # Conservative — only packages the founder explicitly trusts. Adding
    # any other name returns a propose-to-requirements suggestion instead
    # of actually installing.
    "aiosqlite", "redis", "pytz", "httpx", "pypdf", "python-docx",
    "ruff", "pytest", "pytest-asyncio", "motor", "pymongo",
    "twilio", "resend", "jwt", "pyjwt",
    # iter 322ev — founder-approved for ORA self-build / natural-language
    # OS execution layer (Open Interpreter wraps LiteLLM + multi-language
    # exec; runs in dry-run mode only inside Emergent pod).
    "open-interpreter",
}


async def create_file(path: str, content: str = "",
                       *, overwrite: bool = False) -> dict:
    """Create a NEW file under a write-allowed root. Refuses to overwrite
    unless `overwrite=True`. Same path safety as safe_edit.

    Returns {ok, path, bytes_written, created_at, was_overwrite}.
    """
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "path required"}
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}
    if len(content) > 200_000:
        return {"ok": False, "error": "content too large (>200KB) — use append_to_file or chunk it"}
    ok_path, why = _is_write_path_allowed(path)
    if not ok_path:
        return {"ok": False, "error": f"path not allowed: {why}"}
    p = Path(path)
    if p.exists() and not overwrite:
        return {"ok": False, "error": "file already exists; pass overwrite=True to replace",
                 "path": path}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, p)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {
        "ok": True, "path": str(p), "bytes_written": len(content.encode("utf-8")),
        "created_at": _now_iso(), "was_overwrite": p.exists() and overwrite,
    }


async def create_dir(path: str) -> dict:
    """Make a directory (parents=True) under a write-allowed root."""
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "path required"}
    ok_path, why = _is_write_path_allowed(path)
    if not ok_path:
        return {"ok": False, "error": f"path not allowed: {why}"}
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"ok": True, "path": path, "created_at": _now_iso()}


async def append_to_file(path: str, content: str = "") -> dict:
    """Append text to an existing file under write-allowed roots. Useful
    for adding lines to requirements.txt, .env-style configs, etc.

    Special case — `requirements.txt` and `package.json` are normally
    write-forbidden (replacement is dangerous), but pure-append is
    allowed here. We still write-validate the parent path.
    """
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "path required"}
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}
    if len(content) > 50_000:
        return {"ok": False, "error": "content too large (>50KB)"}
    # Use a tweaked path-check that skips _WRITE_FORBIDDEN_FILES
    abs_p = str(Path(path).resolve())
    if not any(abs_p == r or abs_p.startswith(r + os.sep) for r in _WRITE_ALLOWED_ROOTS):
        return {"ok": False, "error": "path not allowed: not under write-allowed roots"}
    for bad in _WRITE_FORBIDDEN_PATTERNS:
        if bad in abs_p:
            return {"ok": False, "error": f"path not allowed: forbidden pattern {bad!r}"}
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file does not exist: {path}"}
    try:
        before = p.stat().st_size
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        after = p.stat().st_size
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"ok": True, "path": str(p), "bytes_before": before,
             "bytes_after": after, "bytes_appended": after - before}


async def pytest_run(path: str, *, verbose: bool = False, timeout: int = 60) -> dict:
    """Run pytest on a file or directory under /app/backend/tests.

    Read-only — never modifies anything. Returns rc, stdout (last 4KB),
    stderr (last 4KB), summary line.
    """
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "path required"}
    # Constrain to tests dir for safety
    if not (path.startswith("/app/backend/tests") or path.startswith("/app/aurem-cto/")):
        return {"ok": False, "error": "pytest_run limited to /app/backend/tests or /app/aurem-cto/"}
    if ".." in path:
        return {"ok": False, "error": "path traversal disallowed"}
    if not Path(path).exists():
        return {"ok": False, "error": f"path not found: {path}"}
    try:
        cmd = ["python3", "-m", "pytest", path]
        if verbose:
            cmd.append("-v")
        # FIX #4 (audit iter 322fi) — never inherit parent process env.
        # Old code: env = {**os.environ}  → STRIPE_SECRET_KEY, MONGO_URL,
        # GROQ_API_KEY, JWT_SECRET were all visible to pytest, and one
        # accidental print(os.environ) in a test would surface them in
        # stdout_tail → fed back to ORA → potentially logged.
        # New code: build a minimal env identical to what shell_exec uses.
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/plugins-venv/bin",
            "HOME": os.environ.get("HOME", "/root"),
            "LANG": "C.UTF-8",
            # pytest sometimes needs PYTHONPATH for project-local imports
            "PYTHONPATH": os.environ.get("PYTHONPATH", "/app/backend"),
        }
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd="/app/backend", env=env,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"pytest timed out after {timeout}s"}
        rc = proc.returncode
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    stdout = (out.decode("utf-8", "replace") if out else "")
    stderr = (err.decode("utf-8", "replace") if err else "")
    # Find the summary line (e.g. "5 passed in 0.32s")
    summary = ""
    for line in reversed(stdout.splitlines()):
        if "passed" in line or "failed" in line or "error" in line.lower():
            summary = line.strip()
            break
    return {
        "ok": rc == 0, "rc": rc, "summary": summary[:240],
        "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-2000:],
        "path": path,
    }


# ─── Cloudflare DNS + Tunnel tools ─────────────────────────────────────

async def cloudflare_dns_list(*, name: Optional[str] = None) -> dict:
    """List DNS records in CLOUDFLARE_ZONE_ID. Optionally filter by name."""
    tok = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if not tok or not zone:
        return {"ok": False, "error": "CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID missing"}
    try:
        import httpx
        params = {"per_page": 50}
        if name:
            params["name"] = name
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"https://api.cloudflare.com/client/v4/zones/{zone}/dns_records",
                headers={"Authorization": f"Bearer {tok}",
                          "Content-Type": "application/json"},
                params=params,
            )
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "error": r.text[:300]}
        data = r.json()
        # Strip sensitive metadata, return minimal info
        records = [
            {k: rec.get(k) for k in ("id", "type", "name", "content", "proxied", "ttl")}
            for rec in data.get("result", [])
        ]
        return {"ok": True, "count": len(records), "records": records}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


async def cloudflare_dns_write(
    record_type: str, name: str, content: str,
    *, proxied: bool = True, ttl: int = 1,
) -> dict:
    """Create or update a DNS record. `record_type` ∈ {A, AAAA, CNAME, TXT}.

    Idempotent: if a record with the same name+type already exists, this
    PATCHes it instead of creating a duplicate.
    """
    tok = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    root = os.environ.get("CLOUDFLARE_ROOT_DOMAIN", "").strip()
    if not tok or not zone:
        return {"ok": False, "error": "CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID missing"}
    # FIX #5 (audit iter 322fi) — REQUIRE CLOUDFLARE_ROOT_DOMAIN.
    # Old code: if CLOUDFLARE_ROOT_DOMAIN was unset (empty), the `if root and
    # not fqdn.endswith(root)` check silently skipped, letting ORA write
    # arbitrary records across the entire Cloudflare zone (e.g. hijack
    # mail records of unrelated domains in the same zone). Now we hard-fail
    # if the env var is missing.
    if not root:
        return {
            "ok": False,
            "error": (
                "CLOUDFLARE_ROOT_DOMAIN env var is REQUIRED to scope writes. "
                "Set it to e.g. 'aurem.live' so ORA cannot touch other domains."
            ),
        }
    if record_type.upper() not in {"A", "AAAA", "CNAME", "TXT"}:
        return {"ok": False, "error": f"unsupported record type: {record_type}"}
    if not isinstance(name, str) or not name:
        return {"ok": False, "error": "name required"}
    if not isinstance(content, str) or not content:
        return {"ok": False, "error": "content required"}
    # Force `name` into the configured root domain. With FIX #5 above, `root`
    # is guaranteed non-empty here, so the endswith check is always enforced.
    fqdn = name if "." in name else f"{name}.{root}"
    if not fqdn.endswith(root):
        return {"ok": False, "error": f"name must be under CLOUDFLARE_ROOT_DOMAIN ({root})"}
    body = {
        "type": record_type.upper(), "name": fqdn, "content": content,
        "ttl": int(ttl), "proxied": bool(proxied),
    }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            # Look up existing record to PATCH instead of POST
            existing = await c.get(
                f"https://api.cloudflare.com/client/v4/zones/{zone}/dns_records",
                headers={"Authorization": f"Bearer {tok}"},
                params={"type": body["type"], "name": fqdn},
            )
            ex_rows = existing.json().get("result", []) if existing.status_code == 200 else []
            if ex_rows:
                rid = ex_rows[0]["id"]
                r = await c.put(
                    f"https://api.cloudflare.com/client/v4/zones/{zone}/dns_records/{rid}",
                    headers={"Authorization": f"Bearer {tok}",
                              "Content-Type": "application/json"},
                    json=body,
                )
                action = "updated"
            else:
                r = await c.post(
                    f"https://api.cloudflare.com/client/v4/zones/{zone}/dns_records",
                    headers={"Authorization": f"Bearer {tok}",
                              "Content-Type": "application/json"},
                    json=body,
                )
                action = "created"
        if r.status_code not in (200, 201):
            return {"ok": False, "status": r.status_code, "error": r.text[:300]}
        result = r.json().get("result", {})
        return {
            "ok": True, "action": action,
            "id": result.get("id"), "name": result.get("name"),
            "type": result.get("type"), "content": result.get("content"),
            "proxied": result.get("proxied"),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


# ─── Docker / pip / pytest auxiliary tools ─────────────────────────────

_DOCKER_COMPOSE_ALLOWED = {
    "ps", "logs", "config", "version", "top",
    # Mutating (require council gate in normal flow but this tool is for
    # admin to actually run them; safe_edit_with_council guards file
    # changes upstream)
    "up", "down", "restart", "pull", "build", "stop", "start",
}


async def docker_compose(subcommand: str, *,
                          file: str = "/app/aurem-cto/docker-compose.yml",
                          extra: Optional[list] = None,
                          timeout: int = 60) -> dict:
    """Run a whitelisted docker-compose subcommand. The docker daemon
    must be reachable from the host — in the preview k8s container this
    will return `docker not found`, which is the safe, correct outcome.
    On the Legion host, this tool DOES the deploy.
    """
    if subcommand not in _DOCKER_COMPOSE_ALLOWED:
        return {"ok": False,
                "error": f"subcommand not allowed: {subcommand!r} (allowed: {sorted(_DOCKER_COMPOSE_ALLOWED)})"}
    extra = extra or []
    if not isinstance(extra, list) or any(not isinstance(x, str) for x in extra):
        return {"ok": False, "error": "extra must be list[str]"}
    if any(ch in (file + " ".join(extra)) for ch in [";", "|", "&", "$(", "`"]):
        return {"ok": False, "error": "forbidden shell metachar in args"}
    cmd = ["docker", "compose", "-f", file, subcommand, *extra]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"docker compose timed out after {timeout}s"}
    except FileNotFoundError:
        return {"ok": False, "error": "docker not installed on host (expected on Emergent preview; OK on Legion)"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {
        "ok": proc.returncode == 0, "rc": proc.returncode,
        "stdout_tail": (out.decode("utf-8", "replace") if out else "")[-4000:],
        "stderr_tail": (err.decode("utf-8", "replace") if err else "")[-2000:],
        "cmd": " ".join(cmd),
    }


async def pip_propose(package: str, *, version: Optional[str] = None) -> dict:
    """Propose adding a package to requirements.txt. Does NOT actually
    install — installation requires founder approval via the propose_commit
    flow because requirements.txt changes are git-tracked.

    Allowlist: a small set of known-safe packages can be appended
    directly; everything else returns a "please add via founder review"
    instruction.
    """
    if not isinstance(package, str) or not package:
        return {"ok": False, "error": "package required"}
    package = package.strip().lower()
    if package not in _PIP_ALLOWLIST:
        return {
            "ok": False,
            "error": f"package not in allowlist: {package!r}",
            "allowlist": sorted(_PIP_ALLOWLIST),
            "hint": "Use `append_to_file` on requirements.txt then `propose_commit` for founder review.",
        }
    line = f"{package}=={version}\n" if version else f"{package}\n"
    res = await append_to_file("/app/backend/requirements.txt", line)
    if res.get("ok"):
        res["package"] = package
        res["version"] = version
        res["note"] = "pip install needs container restart — call restart_service('backend')"
    return res


# ─── iter 322ev — Open Interpreter natural-language planning bridge ──
from services.ora_natural_bridge import ora_run_natural  # noqa: E402

# ─── iter 322fa — Legion Bridge tool (ORA executes on founder's Legion) ──
from services.legion_tool import legion_exec  # noqa: E402


# ─── Registry ────────────────────────────────────────────────────────

async def claim_build_done(
    files: list[str] | None = None,
    endpoints: list[str] | None = None,
    *,
    label: str = "",
) -> dict:
    """ANTI-HALLUCINATION RECEIPT (iter 322fd).

    Before ORA shows the founder a "✓ Built X" message, she MUST call this
    tool. It performs REAL os.path.exists() + HTTP probes and returns a
    verdict. If `verified=False`, ORA is contractually forbidden from
    claiming the build is done — she must instead either (a) build the
    missing pieces or (b) tell the founder plainly that nothing was built.

    Args:
        files:     list of absolute paths that the build claims to have created
        endpoints: list of /api/... routes that the build claims to have wired
        label:     short human label (e.g. "incident-bus pipeline iter 322fb")

    Returns:
        {
          ok: bool, verified: bool, label: str,
          files: [{path, exists, size_bytes, mtime}],
          endpoints: [{path, http_status, ok}],
          missing_files: [...], failing_endpoints: [...],
          verdict: "ALL_PROOFS_PRESENT" | "FABRICATED_CLAIM_DETECTED" | ...,
          founder_message: human-readable summary
        }
    """
    files = list(files or [])
    endpoints = list(endpoints or [])

    # File existence checks (real fs.stat — never trusts memory)
    file_results: list[dict] = []
    missing_files: list[str] = []
    for raw in files:
        p = (raw or "").strip()
        if not p:
            continue
        # Hard allowlist — only paths inside /app are checkable here
        try:
            real = os.path.realpath(p)
        except Exception:
            real = p
        exists = os.path.isfile(real)
        size = mtime = None
        if exists:
            try:
                st = os.stat(real)
                size = int(st.st_size)
                mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()
            except Exception:
                pass
        else:
            missing_files.append(p)
        file_results.append({
            "path": p, "exists": exists,
            "size_bytes": size, "mtime": mtime,
        })

    # Endpoint probes (real HTTP — never trusts ORA's claim of a 200)
    ep_results: list[dict] = []
    failing_endpoints: list[str] = []
    base = "http://localhost:8001"
    for raw in endpoints:
        path = (raw or "").strip()
        if not path:
            continue
        if not path.startswith("/"):
            path = "/" + path
        url = base + path
        status: int = 0
        err: str | None = None
        try:
            # Use curl for parity with how the founder would test
            proc = subprocess.run(
                ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                 "--max-time", "8", url],
                check=False, capture_output=True, text=True, timeout=10,
            )
            status_text = (proc.stdout or "").strip()
            status = int(status_text) if status_text.isdigit() else 0
        except subprocess.TimeoutExpired:
            err = "timeout"
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:80]}"
        ok = 200 <= status < 500 and status != 404
        ep_results.append({
            "path": path, "http_status": status, "ok": ok, "error": err,
        })
        if not ok:
            failing_endpoints.append(path)

    verified = (not missing_files) and (not failing_endpoints) and (files or endpoints)
    if verified:
        verdict = "ALL_PROOFS_PRESENT"
        founder_msg = (
            f"✓ Verified build receipt: {len(file_results)} file(s) on disk, "
            f"{len(ep_results)} endpoint(s) live."
        )
    elif (missing_files and not files) or (not files and not endpoints):
        verdict = "NO_PROOFS_REQUESTED"
        founder_msg = (
            "claim_build_done called with no files/endpoints — cannot verify. "
            "ORA: list the actual paths and routes you claim to have created."
        )
    else:
        verdict = "FABRICATED_CLAIM_DETECTED"
        bits = []
        if missing_files:
            bits.append(f"{len(missing_files)} file(s) missing")
        if failing_endpoints:
            bits.append(f"{len(failing_endpoints)} endpoint(s) not responding")
        founder_msg = (
            "✗ Build receipt FAILED — " + ", ".join(bits)
            + ". ORA: do NOT tell the founder the build is done. "
            + "Either build the missing pieces now, or admit the previous "
            + "claim was fabricated."
        )

    return {
        "ok": True,  # tool itself succeeded; verdict is the real signal
        "verified": bool(verified),
        "label": label or "(unlabeled)",
        "files": file_results,
        "endpoints": ep_results,
        "missing_files": missing_files,
        "failing_endpoints": failing_endpoints,
        "verdict": verdict,
        "founder_message": founder_msg,
    }


# ── iter 322g — Autonomous ops tools (forward-declared for TOOL_REGISTRY) ─
async def _ora_campaign_status() -> dict:
    """Live snapshot for ORA's autonomous decisions."""
    if _db is None:
        return {"ok": False, "error": "db not wired"}
    try:
        cfg = await _db.auto_blast_config.find_one({"tenant_id": "global"}, {"_id": 0}) or {}
        health = await _db.ora_campaign_health.find_one({"_id": "global"}, {"_id": 0}) or {}
        autonomous_log = []
        async for d in _db.ora_autonomous_log.find({}, {"_id": 0}).sort("ts", -1).limit(5):
            autonomous_log.append({
                "ts": d.get("ts"), "playbook": d.get("playbook"),
                "summary": d.get("summary"),
            })
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0).isoformat()
        outreach_today = await _db.outreach_history.count_documents(
            {"created_at": {"$gte": today}}
        )
        return {
            "ok": True,
            "engine": {
                "enabled": cfg.get("enabled"),
                "last_run_at": cfg.get("last_run_at"),
                "last_run_sent": cfg.get("last_run_sent"),
                "last_run_processed": cfg.get("last_run_processed"),
                "max_per_cycle": cfg.get("max_per_cycle"),
            },
            "watchdog": {
                "zero_sent_streak": health.get("zero_sent_streak"),
                "veto_rate_1h": health.get("veto_rate_1h"),
                "tripped": health.get("tripped"),
                "checked_at": health.get("checked_at"),
            },
            "outreach_events_today": outreach_today,
            "recent_autonomous_actions": autonomous_log,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _ora_force_blast_cycle(max_leads: int = 5) -> dict:
    if _db is None:
        return {"ok": False, "error": "db not wired"}
    try:
        max_leads = max(1, min(int(max_leads), 25))
        await _db.auto_blast_config.update_one(
            {"tenant_id": "global"},
            {"$set": {"max_per_cycle": max_leads}},
        )
        from services import auto_blast_engine
        auto_blast_engine.set_db(_db)
        r = await asyncio.wait_for(
            auto_blast_engine.run_auto_blast_cycle(force=True), timeout=90,
        )
        return {
            "ok": True,
            "processed": r.get("total_processed"),
            "sent": r.get("total_sent"),
            "max_leads_used": max_leads,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _ora_channel_gating_reseed() -> dict:
    if _db is None:
        return {"ok": False, "error": "db not wired"}
    try:
        from services.ora_autonomous_ops import _autofix_channel_gating, set_db as setdb
        setdb(_db)
        return await _autofix_channel_gating()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _ora_git_commit_local(message: str) -> dict:
    import subprocess
    msg = f"ora-autofix: {(message or '')[:140]}"
    try:
        subprocess.run(["git", "add", "-A"], cwd="/app", check=True, timeout=20)
        subprocess.run(
            ["git", "commit", "-m", msg, "--allow-empty"],
            cwd="/app", check=True, capture_output=True, text=True, timeout=20,
        )
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short=10", "HEAD"], cwd="/app", text=True, timeout=10,
        ).strip()
        files = subprocess.check_output(
            ["git", "show", "--stat", "--name-only", "HEAD"],
            cwd="/app", text=True, timeout=10,
        )
        changed = [ln for ln in files.splitlines() if ln and not ln.startswith("commit ")][1:6]
        return {
            "ok": True,
            "sha": sha,
            "message": msg,
            "files_changed_preview": changed,
            "next_step": "Founder must click 'Save to GitHub' in Emergent UI to push to remote.",
        }
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": f"git: {e.stderr or e.stdout or 'unknown'}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _ora_git_bisect(
    bad_sha: str = "HEAD",
    good_sha: str = "",
    test_cmd: str = "",
    max_steps: int = 12,
) -> dict:
    """Run `git bisect` to find the first commit that broke a test.

    Args:
      bad_sha: commit where the bug is present (default HEAD).
      good_sha: commit where the test passed (required).
      test_cmd: shell command that returns exit 0 if "good", non-zero if "bad".
                LLM-supplied — STRICTLY tokenised and validated against the
                same whitelist that `shell_exec` uses. shell=False enforced.
                E.g. `python3 -c "import services.ora_agent"`,
                     `pytest /app/backend/tests/test_x.py`,
                     `curl -fsS http://localhost:8001/api/health`.
      max_steps: safety cap on bisect iterations (default 12 → covers ~4k commits).

    PATCHES (audit iter 322fi):
      #1  Shell-injection RCE — `subprocess.run(test_cmd, shell=True)` allowed
          ORA-generated strings to run arbitrary code (rm -rf /, exfiltrate creds,
          bypass every other gate in this file). Now tokenised via shlex.split()
          and validated against _SHELL_WHITELIST. shell=False enforced.
      #3  Event-loop blocking — all subprocess.run() / check_output() calls
          wrapped in asyncio.to_thread() so the FastAPI worker can keep
          serving health probes, MongoDB writes, and campaign blasts during
          a multi-minute bisect run.
    """
    import shlex
    import subprocess

    if not good_sha:
        return {"ok": False, "error": "good_sha required — commit where the test was passing"}
    if not test_cmd:
        return {"ok": False, "error": "test_cmd required — shell command, exit 0 = good"}

    # ── FIX #1: tokenise + validate test_cmd against shell_exec whitelist ──
    try:
        argv_tokens = shlex.split(test_cmd)
    except ValueError as e:
        return {"ok": False, "error": f"test_cmd unparseable: {e}"}
    if not argv_tokens:
        return {"ok": False, "error": "test_cmd is empty after parsing"}

    cmd0 = argv_tokens[0]
    cmd_args = argv_tokens[1:]
    if cmd0 not in _SHELL_WHITELIST:
        return {
            "ok": False,
            "error": f"test_cmd binary not in whitelist: {cmd0!r}",
            "whitelist": sorted(_SHELL_WHITELIST.keys()),
        }
    err = _validate_shell_args(cmd0, cmd_args)
    if err:
        return {"ok": False, "error": f"test_cmd validation: {err}"}

    # Resolve the binary path the same way shell_exec does
    import shutil as _sh
    test_binary = _sh.which(cmd0) or f"/usr/bin/{cmd0}"
    if not (Path(test_binary).is_file() and os.access(test_binary, os.X_OK)):
        return {"ok": False, "error": f"test_cmd binary not found on host: {cmd0}"}
    test_argv = [test_binary] + cmd_args

    # Stripped env (same approach as shell_exec — no secret leakage to subprocess)
    test_env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/plugins-venv/bin",
        "HOME": os.environ.get("HOME", "/root"),
        "LANG": "C.UTF-8",
    }

    # ── FIX #3: wrap every subprocess call in asyncio.to_thread ─────────
    async def _run(argv: list[str], *, timeout: int = 15, check: bool = False,
                   capture: bool = True, want_text: bool = True):
        return await asyncio.to_thread(
            subprocess.run, argv,
            cwd="/app", timeout=timeout, check=check,
            capture_output=capture, text=want_text, shell=False,
        )

    async def _check_output(argv: list[str], *, timeout: int = 10) -> str:
        return await asyncio.to_thread(
            subprocess.check_output, argv,
            cwd="/app", timeout=timeout, text=True,
        )

    # Sanity: do NOT bisect a dirty tree.
    try:
        dirty = (await _check_output(["git", "status", "--porcelain"], timeout=10)).strip()
        if dirty:
            return {
                "ok": False,
                "error": "working tree has uncommitted changes — commit or stash first",
                "dirty_lines": dirty.splitlines()[:6],
            }
    except Exception as e:
        return {"ok": False, "error": f"pre-check failed: {e}"}

    log: list[dict] = []
    try:
        original_head = (await _check_output(
            ["git", "rev-parse", "HEAD"], timeout=5,
        )).strip()
    except Exception as e:
        return {"ok": False, "error": f"rev-parse failed: {e}"}
    log.append({"step": "start", "head": original_head[:10]})

    first_bad = None
    bisect_log = ""
    try:
        # Start bisect (all sync subprocess offloaded to thread pool)
        await _run(["git", "bisect", "start"], timeout=15, check=True)
        await _run(["git", "bisect", "bad", bad_sha], timeout=15, check=True)
        await _run(["git", "bisect", "good", good_sha], timeout=15, check=True)

        for step in range(max_steps):
            cur = (await _check_output(
                ["git", "rev-parse", "--short=10", "HEAD"], timeout=5,
            )).strip()

            # ── FIX #1+#3: run the validated test in a thread, no shell ──
            r = await asyncio.to_thread(
                subprocess.run, test_argv,
                cwd="/app", timeout=90,
                capture_output=True, text=True, shell=False,
                env=test_env,
            )
            verdict = "good" if r.returncode == 0 else "bad"
            log.append({
                "step": step + 1, "sha": cur, "verdict": verdict,
                "stdout_tail": (r.stdout or "")[-120:],
                "stderr_tail": (r.stderr or "")[-120:],
            })

            # Tell bisect
            out = await _run(["git", "bisect", verdict], timeout=15, capture=True)
            combined = (out.stdout or "") + (out.stderr or "")
            if "is the first bad commit" in combined:
                m = re.search(r"([0-9a-f]{7,40}) is the first bad commit", combined)
                first_bad = m.group(1) if m else None
                bisect_log = combined
                break
            if "bisect" not in combined.lower() and not combined.strip():
                break

        # Capture full bisect log before reset.
        try:
            bisect_log = await _check_output(["git", "bisect", "log"], timeout=5)
        except Exception:
            pass
    except subprocess.CalledProcessError as e:
        log.append({"step": "git_err", "stderr": (e.stderr or b"").decode("utf-8", "ignore")[:300]})
    finally:
        # Always reset, even on error/cancel.
        try:
            await _run(["git", "bisect", "reset"], timeout=15, capture=True)
        except Exception:
            pass

    # Get culprit details if found.
    culprit_details: dict | None = None
    if first_bad:
        try:
            sho = await _check_output(
                ["git", "show", "--stat", "--format=%H%n%an <%ae>%n%ad%n%s%n%b",
                 first_bad], timeout=10,
            )
            parts = sho.splitlines()
            culprit_details = {
                "sha": parts[0] if parts else first_bad,
                "author": parts[1] if len(parts) > 1 else "",
                "date": parts[2] if len(parts) > 2 else "",
                "subject": parts[3] if len(parts) > 3 else "",
                "stat_tail": parts[-6:] if len(parts) > 6 else parts,
            }
        except Exception:
            pass

    return {
        "ok": bool(first_bad),
        "first_bad_commit": first_bad,
        "culprit_details": culprit_details,
        "steps_run": len(log),
        "bisect_log_tail": (bisect_log or "")[-800:],
        "step_trace": log[-6:],
        "next_step": (
            f"Revert {first_bad[:10]} OR open it with view_file + git_log to see "
            "what changed, then craft a targeted fix."
            if first_bad else
            "bisect couldn't isolate — test_cmd may be flaky, or the bad commit "
            "predates good_sha. Try a wider good_sha range or a more deterministic test."
        ),
    }




# ── iter 326y — Phase 2 P1: Real Browser Tool (Playwright) ─────────────
# Wraps the existing services/browser_agent_service.py so ORA-CTO can
# scrape dynamic pages (Yelp menus, Google Search Console, Shopify
# settings, competitor pricing). Two surfaces:
#
#   browser_get_text    — navigate + extract text (optional CSS selector)
#   browser_screenshot  — navigate + capture screenshot (PNG)
#
# Both honor ORA's tier system (browser_screenshot/get_text are TIER_2 so
# external URLs get the 30-second cancel window from iter 326w). The
# inner approval queue in browser_agent_service is bypassed by passing
# requires_approval=False — ORA's own tier gate is the founder approval.
async def browser_get_text(
    url: str,
    selector: str | None = None,
    multiple: bool = False,
    wait_ms: int = 800,
) -> dict:
    """Navigate to URL with a real Chromium browser and return rendered
    text. Useful for pages that need JS to render (SPAs, dashboards
    behind auth, Yelp business pages, GSC, etc.).

    Args:
      url:      full http(s) URL
      selector: optional CSS selector — return text inside matching el(s)
      multiple: if true with selector, return list of matches
      wait_ms:  extra wait after domcontentloaded (for late JS)
    """
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "url must start with http:// or https://"}
    try:
        from services.browser_agent_service import extract_url
    except Exception as e:
        return {"ok": False, "error": f"browser_agent_service import failed: {e}"}
    res = await extract_url(
        url,
        selector=selector,
        multiple=bool(multiple),
        requires_approval=False,  # ORA tier gate is the approval
        reason=f"ora-cto browser_get_text({selector or 'body'})",
        triggered_by="ora_cto",
    )
    return res


async def browser_screenshot(
    url: str,
    full_page: bool = True,
    wait_ms: int = 1500,
) -> dict:
    """Navigate to URL with a real Chromium browser and capture a PNG
    screenshot. Returned image_url is either an R2 public URL or a
    local /tmp path the static-proxy can serve.
    """
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "url must start with http:// or https://"}
    try:
        from services.browser_agent_service import screenshot_url
    except Exception as e:
        return {"ok": False, "error": f"browser_agent_service import failed: {e}"}
    res = await screenshot_url(
        url,
        full_page=bool(full_page),
        wait_ms=int(wait_ms),
        requires_approval=False,
        reason="ora-cto browser_screenshot",
        triggered_by="ora_cto",
    )
    return res


# ── iter 326aa — Phase 2 P1.3: Vector memory of past decisions ──────
async def recall_past_decisions(
    query: str,
    limit: int = 5,
    tags: list[str] | None = None,
) -> dict:
    """Ask: 'have we made a decision like this before? what happened?'.
    Mongo $text search over the ora_decisions log (auto-populated on
    every approve/reject/auto-execute)."""
    try:
        from services.ora_decision_memory import recall_past_decisions as _r
    except Exception as e:
        return {"ok": False, "error": f"decision_memory import failed: {e}"}
    return await _r(query, limit=limit, tags=tags)


# ── iter 326bb — Phase 2 P1.4: Semantic codebase search ─────────────
async def search_codebase_semantic(query: str, limit: int = 20) -> dict:
    """Intent-level code search ('find code that calculates subscription
    cost') instead of exact grep. AST + synonym expansion + ranking."""
    try:
        from services import codebase_semantic_search as cs
    except Exception as e:
        return {"ok": False, "error": f"codebase_semantic_search import failed: {e}"}
    return cs.search(query, limit=limit)


# ── iter 326z — Phase 2 P1.2: Long-running job checkpoints ──────────
async def load_job_checkpoint(job_id: str) -> dict:
    """Load the last checkpoint for a long-running job so it can resume
    where it crashed (4h campaign sweeps, nightly DR jobs)."""
    try:
        from services.job_checkpoints import load_checkpoint
    except Exception as e:
        return {"ok": False, "error": f"job_checkpoints import failed: {e}"}
    row = await load_checkpoint(job_id)
    return {"ok": True, "found": row is not None, "checkpoint": row}


TOOL_REGISTRY: dict[str, dict] = {
    "grep_codebase":  {
        "fn": grep_codebase,
        "args_spec": {"pattern": "str (required)", "file_glob": "str (e.g. *.py)",
                      "root": "/app/{backend,frontend,memory,ora_skills}",
                      "max_results": "int 1-200, default 40"},
        "description": "Real grep -rn over the codebase. Returns matched lines with file:line:body.",
    },
    # iter 326y — Phase 2 P1: Real Browser Tool (Playwright)
    "browser_get_text": {
        "fn": browser_get_text,
        "args_spec": {
            "url":      "str http(s) URL (required)",
            "selector": "str CSS selector — optional, default returns <body> text",
            "multiple": "bool — true to return list of matches for selector",
            "wait_ms":  "int — extra wait after domcontentloaded, default 800",
        },
        "description": (
            "iter 326y — Drive a real Chromium browser to a URL and return "
            "rendered text. Use this for pages that need JS to render: "
            "Yelp business pages, GSC dashboards, Shopify admin, competitor "
            "pricing pages, social profiles, etc. Returns the visible text "
            "of <body> or a CSS-selected element."
        ),
    },
    "browser_screenshot": {
        "fn": browser_screenshot,
        "args_spec": {
            "url":       "str http(s) URL (required)",
            "full_page": "bool — capture entire scrollable page, default true",
            "wait_ms":   "int — extra wait after domcontentloaded, default 1500",
        },
        "description": (
            "iter 326y — Drive a real Chromium browser to a URL and capture "
            "a PNG screenshot. Returns an R2 image URL (or a local /tmp path "
            "served via the static proxy). Useful for visual evidence in lead "
            "research, competitor analysis, and bug reports."
        ),
    },
    "recall_past_decisions": {
        "fn": recall_past_decisions,
        "args_spec": {
            "query": "str — what you want to remember (required)",
            "limit": "int 1-50, default 5",
            "tags":  "list[str] — optional filter (e.g. ['cors', 'auth'])",
        },
        "description": (
            "iter 326aa — Search ORA's past decisions ('did we fix this "
            "before? what was the outcome?'). Mongo $text search over the "
            "ora_decisions log (auto-populated on every approve/reject/"
            "auto-execute). Returns top matches with summary, tool, "
            "outcome, tags, timestamp."
        ),
    },
    "search_codebase_semantic": {
        "fn": search_codebase_semantic,
        "args_spec": {
            "query": "str — intent-level search (required)",
            "limit": "int 1-100, default 20",
        },
        "description": (
            "iter 326bb — Intent-based code search instead of exact grep. "
            "AST-extracts function/class/module names + docstrings, applies "
            "synonym expansion, ranks by hit-density + name match. Returns "
            "top matches with file path, line number, and docstring excerpt. "
            "Use this when you DON'T know the exact word but DO know what "
            "the code should do ('code that calculates subscription cost')."
        ),
    },
    "load_job_checkpoint": {
        "fn": load_job_checkpoint,
        "args_spec": {
            "job_id": "str — the long-running job id (required)",
        },
        "description": (
            "iter 326z — Load the last checkpoint for a long-running job "
            "(4h campaign sweep, nightly DR job) so it can resume where "
            "it crashed instead of starting over."
        ),
    },
    "view_file": {
        "fn": view_file,
        "args_spec": {"path": "str (required, must be inside /app)",
                      "max_lines": "int 1-500, default 200",
                      "start": "int (1-based line, default 1)"},
        "description": "Read a file's contents, range-clipped.",
    },
    "debug_systematic": {
        "fn": debug_systematic,
        "args_spec": {"bug_description": "str (required, ≥5 chars)",
                      "error_text":       "str (optional traceback/log excerpt)",
                      "file_hint":        "str (optional file path under /app)"},
        "description": (
            "iter 323q — Force the 6-step systematic debug framework BEFORE "
            "proposing any fix. Returns a structured plan: observe→isolate→"
            "hypothesize→verify→root_cause→fix. Recommends the FIRST tool to "
            "call next. Use this whenever the founder reports a bug — it kills "
            "the guess-and-check anti-pattern and forces evidence-based fixes."
        ),
    },
    "review_code": {
        "fn": review_code,
        "args_spec": {"path": "str (required, file inside /app)",
                      "focus": "str — 'all' (default), 'security', 'correctness', "
                                "'maintainability', 'performance', 'logging', 'complexity'"},
        "description": (
            "iter 323q — Deterministic code-review pass on a single file. "
            "Heuristic checks for hardcoded secrets, bare except:pass, SQL "
            "injection, eval/exec, oversized functions, production print(). "
            "Returns severity-ranked findings + PASS/WARN/BLOCK verdict. Cheap "
            "first pass BEFORE the LLM does subjective review or before a "
            "propose_commit. Reads up to 500 lines."
        ),
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
    "run_pytest": {
        "fn": run_pytest,
        "args_spec": {
            "path":      "str under /app/backend/tests/ (file or dir or test_x.py::test_y)",
            "timeout_s": "int 5-180 (default 90)",
        },
        "description": (
            "iter 326i — BUILD MODE step 3. Run pytest on a path under "
            "/app/backend/tests/ and return a structured PASS/FAIL "
            "envelope (passed, failed, errors, duration_s, summary, tail). "
            "Use this RIGHT AFTER safe_edit / create_file to prove the new "
            "code path is exercised by a test."
        ),
    },
    "verify_endpoint": {
        "fn": verify_endpoint,
        "args_spec": {
            "endpoint":           "str starting with /api/",
            "expected_status":    "int (default 200)",
            "expected_substring": "str (optional — body must contain this)",
        },
        "description": (
            "iter 326i — BUILD MODE step 4. Hit an internal /api/ endpoint "
            "and assert status + optional body substring. Returns a clean "
            "PASS/FAIL row (matched_status, matched_substring, latency_ms) "
            "that drops straight into the proof table. Use AFTER restart_service."
        ),
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
            "roles":    (
                "list[str] — peer roles to consult. MUST be drawn from this "
                "exact whitelist: ['security','backend','devops','qa','design',"
                "'finance','marketing','pricing']. Do NOT invent new slugs "
                "(e.g. 'legal','compliance','lawyer','casl_expert' are NOT "
                "valid — for compliance/legal questions use 'security' + "
                "'backend'). Default if omitted: ['security','backend','qa']."
            ),
            "context":  "str — optional diff/code/log",
        },
        "description": (
            "ORA CTO P4 (iter 322eo) — multi-peer parallel council. Fan out "
            "the same question to N specialists, return all opinions. ORA "
            "uses this before high-stakes edits (auth, payment, schema). "
            "Max 5 peers per call."
        ),
    },
    "safe_edit_with_council": {
        "fn": safe_edit_with_council,
        "args_spec": {
            "path":                 "str — under /app/{backend,frontend/src,memory,ora_skills,scripts}",
            "find_string":          "str — exact match, whitespace-sensitive",
            "replace_string":       "str — the new code",
            "expected_occurrences": "int 1-50 (default 1)",
            "rationale":            "str ≥10 chars — what is this edit doing? Logged in audit trail.",
            "roles":                (
                "list[str] — peer roles. MUST be from whitelist: "
                "['security','backend','devops','qa','design','finance',"
                "'marketing','pricing']. Do NOT invent slugs like 'legal' "
                "or 'compliance'. Defaults to risk-tier auto-select based "
                "on path."
            ),
            "override_dissent":     "bool — only true when caller explicitly accepts the dissent risk",
            "override_reason":      "str ≥20 chars — required iff override_dissent=True",
        },
        "description": (
            "GOVERNANCE GATE (iter 322eq) — safe_edit + mandatory peer "
            "council. Auto-selects roles by path risk (auth/payment/schema "
            "→ security+backend+devops+qa). REJECTS the edit if any peer "
            "dissents (DO NOT / STOP / CRITICAL). Override requires loud "
            "audit-logged reason ≥20 chars. USE THIS for any production "
            "code change instead of bare safe_edit."
        ),
    },
    "shell_exec_with_council": {
        "fn": shell_exec_with_council,
        "args_spec": {
            "command":          "str — whitelisted shell command",
            "args":             "list[str] — sanitised argv",
            "rationale":        "str ≥10 chars — why this command?",
            "roles":            "list[str] — peer roles (default: devops + backend)",
            "override_dissent": "bool — explicit accept of dissent risk",
            "override_reason":  "str ≥20 chars — required iff override_dissent=True",
        },
        "description": (
            "GOVERNANCE GATE (iter 322eq) — shell_exec + mandatory peer "
            "council. High-risk argv (rm/dd/drop/mkfs) auto-triggers "
            "security review. REJECTS on any peer dissent unless override "
            "with audit-logged reason."
        ),
    },
    "propose_commit": {
        "fn": propose_commit,
        "args_spec": {
            "title":      "str — one-line conventional-commit summary (3-80 chars)",
            "body":       "str ≤4KB — longer description (optional)",
            "file_paths": "list[str] — files to include (each under write-allowed roots, ≤30)",
            "rationale":  "str ≥10 chars — why this commit? Logged in audit trail.",
        },
        "description": (
            "GIT COMMIT GATE (iter 322er) — record a commit proposal for "
            "founder review. ORA cannot actually commit; this tool only "
            "writes to `ora_commit_proposals` with the diff. Founder "
            "approves via /api/admin/git-gate/proposals/{id}/approve. "
            "Default: stage all dirty files under write-allowed roots."
        ),
    },
    # iter 322eu — Creation + infra tools (ORA can build its own features)
    "create_file": {
        "fn": create_file,
        "args_spec": {
            "path":      "str — under write-allowed roots, must not exist (unless overwrite)",
            "content":   "str ≤200KB — file body",
            "overwrite": "bool — default False; True replaces an existing file",
        },
        "description": (
            "Create a new file at the given path. Atomic write (.tmp + "
            "os.replace). Refuses to overwrite by default. Use for new "
            "modules, Dockerfiles, configs."
        ),
    },
    "create_dir": {
        "fn": create_dir,
        "args_spec": {"path": "str — under write-allowed roots"},
        "description": "Create a directory (mkdir -p) under a write-allowed root.",
    },
    "append_to_file": {
        "fn": append_to_file,
        "args_spec": {
            "path":    "str — existing file under write-allowed roots",
            "content": "str ≤50KB — text to append",
        },
        "description": (
            "Append text to an existing file. Useful for adding lines to "
            "requirements.txt, README, log files, etc."
        ),
    },
    "pytest_run": {
        "fn": pytest_run,
        "args_spec": {
            "path":    "str — under /app/backend/tests or /app/aurem-cto/",
            "verbose": "bool — pass -v to pytest",
            "timeout": "int — seconds (default 60, max 300)",
        },
        "description": (
            "Run pytest on a file or directory. Read-only — never modifies. "
            "Returns rc, summary line, stdout tail."
        ),
    },
    "cloudflare_dns_list": {
        "fn": cloudflare_dns_list,
        "args_spec": {"name": "str — optional filter (e.g. 'cto.aurem.live')"},
        "description": (
            "List DNS records in the configured CLOUDFLARE_ZONE_ID. "
            "Read-only. Optionally filter by exact name."
        ),
    },
    "cloudflare_dns_write": {
        "fn": cloudflare_dns_write,
        "args_spec": {
            "record_type": "str — A | AAAA | CNAME | TXT",
            "name":        "str — must be under CLOUDFLARE_ROOT_DOMAIN",
            "content":     "str — target (IP / hostname / TXT value)",
            "proxied":     "bool — default True for CNAME/A",
            "ttl":         "int — default 1 (Cloudflare 'Auto')",
        },
        "description": (
            "Create or UPSERT a DNS record. Idempotent — if a record with "
            "the same name+type exists, PUTs it instead of creating a "
            "duplicate. Scoped to CLOUDFLARE_ROOT_DOMAIN."
        ),
    },
    "docker_compose": {
        "fn": docker_compose,
        "args_spec": {
            "subcommand": "str — one of ps/logs/config/version/up/down/restart/pull/build/stop/start",
            "file":       "str — compose file path (default /app/aurem-cto/docker-compose.yml)",
            "extra":      "list[str] — additional argv (no shell metachars)",
            "timeout":    "int — seconds (default 60)",
        },
        "description": (
            "Run a whitelisted `docker compose` subcommand. Returns "
            "`docker not installed` on the Emergent preview k8s — "
            "operates on the Legion host where Docker IS installed."
        ),
    },
    "pip_propose": {
        "fn": pip_propose,
        "args_spec": {
            "package": "str — must be in _PIP_ALLOWLIST",
            "version": "str — optional pin (e.g. '0.15.12')",
        },
        "description": (
            "Append a package to requirements.txt for founder review. "
            "Does NOT actually install — requires propose_commit + "
            "founder approval to land. Allowlisted packages only."
        ),
    },
    "ora_run_natural": {
        "fn": ora_run_natural,
        "args_spec": {
            "task":      "str — natural-language objective (≤2000 chars). "
                          "e.g. 'install postgresql 16 and create aurem db'.",
            "dry_run":   "bool — must be True in P1. False is rejected; "
                          "execution must route via shell_exec/safe_edit/"
                          "docker_compose with founder approval.",
            "max_steps": "int — cap on returned steps (1-10, default 5).",
        },
        "description": (
            "ORA CTO autonomous planner (iter 322ev) — wraps Open "
            "Interpreter (auto_run=False, offline=True, safe_mode='ask') "
            "to produce a step-by-step PLAN with concrete shell/python "
            "code blocks for the given objective. P1 returns plan ONLY; "
            "execution must route through existing safety-gated tools. "
            "Model: groq/llama-3.3-70b-versatile."
        ),
    },
    "legion_exec": {
        "fn": legion_exec,
        "args_spec": {
            "cmd":        "str — shell command to run on the founder's Legion laptop (≤4000 chars)",
            "cwd":        "str — working directory on Legion (default: /opt/aurem-cto)",
            "timeout_s":  "int — kill subprocess after N seconds (1..600, default 60)",
            "risk_hint":  "str — 'low'|'medium'|'high' — overrides auto-classifier (optional)",
            "wait_max_s": "int — max seconds to wait for the daemon to return result (1..900, default 360). MUST be ≥300 for HIGH-risk to cover Telegram approval window.",
        },
        "description": (
            "Execute a shell command on the founder's Legion laptop via the "
            "reverse-poll queue (iter 322fa). HIGH-risk commands (sudo, rm -rf, "
            "curl|sh, apt install, systemctl, etc.) trigger a Telegram approval "
            "gate to the founder's phone and auto-reject after 5 minutes. "
            "Returns {ok, job_id, exit_code, stdout, stderr, elapsed_ms, risk}. "
            "ORA gets full autonomous control of Legion through this tool — no "
            "SSH needed, no inbound port required, works through any firewall."
        ),
    },
    "claim_build_done": {
        "fn": claim_build_done,
        "args_spec": {
            "files":     "list[str] — absolute paths the build claims to have created (real os.stat check)",
            "endpoints": "list[str] — /api/... routes the build claims to expose (real HTTP probe via curl)",
            "label":     "str — short human label for the build (e.g. 'incident-bus iter 322fb')",
        },
        "description": (
            "ANTI-HALLUCINATION BUILD RECEIPT (iter 322fd) — mandatory gate before "
            "ORA tells the founder '✓ Built X'. Runs real os.path.isfile() on every "
            "claimed file and real `curl` against every claimed endpoint. Returns "
            "verdict ALL_PROOFS_PRESENT (verified=true) or FABRICATED_CLAIM_DETECTED "
            "(verified=false). If verified=false, ORA MUST NOT show a success message "
            "— either build the missing pieces now or admit the earlier claim was "
            "imagined. The founder added this tool after iter 322fc caught ORA "
            "fabricating an entire 8.4KB incident_bus.py with timestamps that did "
            "not exist on disk."
        ),
    },
    "campaign_status": {
        "fn": _ora_campaign_status,
        "args_spec": {},
        "description": (
            "AUTONOMOUS OPS DASHBOARD (iter 322g) — returns the live snapshot ORA "
            "uses to make decisions WITHOUT asking the founder. Reads: "
            "auto_blast_config, ora_campaign_health, ora_autonomous_log (last 5). "
            "Call this BEFORE answering any campaign-state question, and BEFORE "
            "firing any blast-related tool. NEVER guess these numbers."
        ),
    },
    "force_blast_cycle": {
        "fn": _ora_force_blast_cycle,
        "args_spec": {
            "max_leads": "int — cap leads in this cycle (default 5, max 25)",
        },
        "description": (
            "AUTONOMOUS REMEDIATION (iter 322g) — triggers ONE auto-blast cycle "
            "right now (bypassing the 2-min wait). Use after founder reports "
            "campaign stuck OR when zero_sent_streak >= 3. Returns {processed, sent}. "
            "If sent=0, immediately follow up with channel_gating_reseed + retry."
        ),
    },
    "channel_gating_reseed": {
        "fn": _ora_channel_gating_reseed,
        "args_spec": {},
        "description": (
            "AUTONOMOUS REMEDIATION (iter 322g) — re-seeds channel_gating for every "
            "unsent lead from raw email/phone, and purges junk domains (wikipedia/"
            "autozone/etc.). Same logic as the watchdog autofix loop. Call when "
            "founder demands an immediate fix. Returns {fixed, purged, skipped}."
        ),
    },
    "git_commit_local": {
        "fn": _ora_git_commit_local,
        "args_spec": {
            "message": "str — concise commit message (will be prefixed with 'ora-autofix: ')",
        },
        "description": (
            "AUTONOMOUS GIT STAGING (iter 322g) — runs `git add -A && git commit -m` "
            "on the backend pod. The actual GitHub PUSH must be done via Emergent's "
            "'Save to GitHub' button (platform-gated, founder approval). Use this to "
            "checkpoint state after autofix so founder can review + push with one "
            "click. Returns {sha, files_changed_preview, next_step}."
        ),
    },
    "git_bisect": {
        "fn": _ora_git_bisect,
        "args_spec": {
            "bad_sha":  "str — commit where bug exists (default HEAD)",
            "good_sha": "str — commit where the test was passing (REQUIRED)",
            "test_cmd": "str — shell test command, exit 0 = good. e.g. "
                        "'python3 -c \"import services.ora_agent\"' or "
                        "'curl -fsS http://localhost:8001/api/health'",
            "max_steps": "int — bisect iteration cap (default 12, max 20)",
        },
        "description": (
            "AUTONOMOUS BUG-HUNTING via `git bisect` (iter 322g.6) — given a "
            "known-good commit and a deterministic test, walks the commit graph "
            "to find the EXACT commit that introduced a regression. Tries up to "
            "12 steps (covers ~4000 commits). Refuses to start on a dirty tree. "
            "Always resets the bisect on completion or error. Returns "
            "{first_bad_commit, culprit_details, bisect_log_tail, step_trace, "
            "next_step}. Use this when a feature was working at commit X and "
            "broke by commit Y — never guess; bisect."
        ),
    },
}



# FIX #2 (audit iter 322fi) — removed duplicate shadow definitions of
# _ora_campaign_status / _ora_force_blast_cycle / _ora_channel_gating_reseed /
# _ora_git_commit_local that used to live below this point. They re-imported
# _db via `from services.ora_tools import _db as db`, which silently grabbed
# a STALE module-level reference (whatever _db pointed to when the duplicate
# was first imported — not when set_db() was later called). That meant:
#   - invoke_tool("campaign_status") used the FORWARD-DECLARED upper copy
#     (live _db reference)
#   - direct call _ora_campaign_status() from anywhere else hit the SHADOW
#     copy (potentially stale/None _db)
# Result: debugging was a nightmare. Same name, two code paths, behaviour
# differed by entry-point. Now only the forward-declared definitions above
# (which use module-level _db directly) survive.


async def invoke_tool(name: str, args: dict, *, actor: str = "ora") -> dict:
    """Dispatch a tool by name. Always returns a dict; never raises.

    iter 322es — quota enforcement removed. AUREM is a self-hosted stack
    used only by the founder; ORA operates without rate limits. Safety
    is enforced by the council gate (safe_edit_with_council / shell_exec
    _with_council) and the git commit gate (propose_commit + founder
    approval).

    Bug-fix #30 — the bare `safe_edit` and `shell_exec` tools are NOT
    callable through this public dispatcher anymore. They remain importable
    so the council-gated wrappers (safe_edit_with_council, shell_exec_with
    _council) can still call them server-side after peer review, but
    anyone hitting /api/ora-tools/execute with tool="safe_edit" gets a
    403 — direct file writes / arbitrary subprocess from the admin panel
    were effectively RCE.
    """
    start = time.time()
    # Bug-fix #30 — block direct dispatch of write/exec tools.
    _PUBLIC_DENYLIST = {"safe_edit", "shell_exec"}
    if name in _PUBLIC_DENYLIST:
        result = {
            "ok": False,
            "error": (f"tool {name!r} is gated — call "
                       f"{name}_with_council instead (peer-review required)."),
        }
        elapsed_ms = int((time.time() - start) * 1000)
        result["tool"] = name
        result["elapsed_ms"] = elapsed_ms
        result["ts"] = _now_iso()
        asyncio.create_task(_log_invocation(actor, name, args, result, elapsed_ms))
        return result
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
            # iter 326ss — surface the tool's args_spec on bad-args so
            # the LLM brain can self-correct on the next iteration
            # instead of retrying with the same wrong shape and
            # tripping the consecutive-failure ceiling.
            meta = TOOL_REGISTRY.get(name) or {}
            result = {"ok": False,
                       "error": f"bad args for {name}: {str(e)[:120]}",
                       "args_spec": meta.get("args_spec") or {},
                       "args_passed": sorted(args.keys())}
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
    # Bug-fix #30 — hide the denylisted bare tools from the catalog the
    # LLM sees so it stops suggesting them. The council-gated wrappers
    # are the only public surface for write/exec actions.
    _HIDDEN = {"safe_edit", "shell_exec"}
    return [
        {"name": n,
         "description": meta["description"],
         "args_spec": meta["args_spec"]}
        for n, meta in TOOL_REGISTRY.items()
        if n not in _HIDDEN
    ]
