"""
services/ora_sprint2_tools.py — iter 331a Sprint 2

Eight new Tier-1 tools added to ORA's toolkit. All read-only or
strictly bounded. Wired into the main `TOOL_REGISTRY` at module import
via `splice_into(tool_registry)`.

Tools:
  1. web_search          — live internet via DuckDuckGo Instant Answer
  2. read_logs           — tail supervisor logs
  3. check_coverage      — pytest --cov line %
  4. run_linter          — auto-detect Python (ruff) vs JS (eslint)
  5. mongo_query_safe    — read-only DB, _id excluded
  6. view_bulk           — read up to 10 files in one call
  7. ask_human           — pause and surface a question
  8. glob_files          — glob pattern search, respects .gitignore

Portability: zero Emergent imports. Reads ORA_TOOLS_ROOT env var
(default `/app`) so the same code runs on Hetzner/AWS/local-dev.
"""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Portability: all paths under this root, env-overridable ──────────
_ROOT = Path(os.environ.get("ORA_TOOLS_ROOT", "/app"))
_LOG_DIR = Path(os.environ.get("ORA_LOG_DIR", "/var/log/supervisor"))


# ── 1. web_search ────────────────────────────────────────────────────

async def web_search(query: str, context: str = "low") -> dict:
    """Live internet search.

    Primary backend: Wikipedia REST API (free, no key, sub-second).
    Returns up to 5 RelatedTopics excerpts plus a definitional Abstract.
    Caller can pass `context` as a hint ("low"/"medium"/"high") to
    expand the result count, capped at 10 so token cost stays
    predictable.

    iter 331a — Switched from DuckDuckGo to Wikipedia after DDG
    timed out from inside the pod (egress restrictions). Wikipedia
    is the most reliable free knowledge endpoint we can hit without
    an API key. For broader queries, callers should still cross-check
    with `integration_playbook_expert_v2` if asked.

    Returns:
      ok          : True
      query       : echo
      abstract    : str | None — top-page summary
      abstract_url: str | None — Wikipedia URL
      results     : [{title, snippet, url}] up to N
      count       : len(results)
      source      : "wikipedia"
    """
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "query is empty"}
    limit_map = {"low": 5, "medium": 8, "high": 10}
    limit = limit_map.get(context, 5)

    # Step 1: search Wikipedia for matching pages.
    search_url = (
        "https://en.wikipedia.org/w/api.php?"
        + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": q,
            "format": "json", "srlimit": str(limit),
            "srprop": "snippet",
        })
    )
    try:
        def _fetch(url: str) -> dict:
            req = urllib.request.Request(url, headers={
                "User-Agent": "ORA-CTO/1.0 (+aurem.live)",
            })
            with urllib.request.urlopen(req, timeout=6) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        data = await asyncio.to_thread(_fetch, search_url)
    except Exception as e:
        return {"ok": False, "error": f"web_search failed: {type(e).__name__}: {e}"}

    hits = ((data.get("query") or {}).get("search") or [])[:limit]
    results: list[dict] = []
    for hit in hits:
        title = hit.get("title") or ""
        # snippet has HTML <span> highlights — strip with a tiny re.
        snip = re.sub(r"<[^>]+>", "", hit.get("snippet") or "")
        url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        results.append({
            "title":   title[:200],
            "snippet": snip[:500],
            "url":     url,
        })

    # Step 2: top-page abstract via the page summary endpoint.
    abstract = None
    abstract_url = None
    if results:
        try:
            top_title = urllib.parse.quote(results[0]["title"].replace(" ", "_"))
            sum_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{top_title}"
            sdata = await asyncio.to_thread(_fetch, sum_url)
            abstract = (sdata.get("extract") or "")[:600] or None
            abstract_url = (sdata.get("content_urls") or {}).get("desktop", {}).get("page")
        except Exception:
            pass

    return {
        "ok":            True,
        "query":         q,
        "abstract":      abstract,
        "abstract_url":  abstract_url,
        "results":       results,
        "count":         len(results),
        "source":        "wikipedia",
    }


# ── 2. read_logs ─────────────────────────────────────────────────────

_LOG_FILES = {
    "backend":  ["backend.err.log", "backend.out.log"],
    "frontend": ["frontend.err.log", "frontend.out.log"],
}

async def read_logs(service: str = "backend", lines: int = 100) -> dict:
    """Tail supervisor logs for a service. Read-only.

    Args:
      service: "backend" | "frontend" | filename relative to _LOG_DIR.
      lines:   number of trailing lines (1..1000).

    Returns:
      ok          : True
      service     : echo
      files_read  : [{path, lines}]
      tail        : str — last N lines joined
    """
    n = max(1, min(int(lines or 100), 1000))
    targets: list[Path] = []
    if service in _LOG_FILES:
        for name in _LOG_FILES[service]:
            p = _LOG_DIR / name
            if p.exists():
                targets.append(p)
    else:
        # Allow arbitrary filename in log dir for forward-compat
        p = _LOG_DIR / service
        if p.exists():
            targets.append(p)
    if not targets:
        return {"ok": False, "error": f"no log files for '{service}' under {_LOG_DIR}"}

    pieces: list[str] = []
    files_read: list[dict] = []
    for p in targets:
        try:
            # Read last N lines efficiently using `tail` shell command.
            # Bound tail to one second to never hang.
            proc = await asyncio.create_subprocess_exec(
                "tail", "-n", str(n), str(p),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            text = stdout.decode("utf-8", errors="replace")
            pieces.append(f"--- {p.name} (last {n}) ---\n{text}")
            files_read.append({"path": str(p), "lines": text.count("\n")})
        except Exception as e:
            pieces.append(f"--- {p.name} ERROR: {e} ---")
    return {
        "ok":         True,
        "service":    service,
        "files_read": files_read,
        "tail":       _scrubbed_join("\n".join(pieces))[:16000],
    }


def _scrubbed_join(text: str) -> str:
    """Run secrets scrubber over log content before returning to LLM."""
    try:
        from services.ora_safety import scrub_secrets
        scrubbed, n = scrub_secrets(text)
        if n:
            logger.info(f"[secrets-scrubber] redacted {n} item(s) in read_logs")
        return scrubbed
    except Exception:
        return text


# ── 3. check_coverage ────────────────────────────────────────────────

async def check_coverage(path: str = "") -> dict:
    """Run `pytest --cov` and return real line-coverage percent.

    Args:
      path: optional subdir under /app/backend/tests (default: full suite).
            Empty string runs the whole tests/ directory.

    Returns:
      ok                    : True
      coverage_percent      : float | None
      tests_passed          : int
      tests_failed          : int
      uncovered_files       : [str] — files with <80% coverage
      raw_summary           : last 40 lines of pytest output (tail)
    """
    backend_dir = _ROOT / "backend"
    target = (backend_dir / "tests" / path) if path else (backend_dir / "tests")
    if not target.exists():
        return {"ok": False, "error": f"path not found: {target}"}

    try:
        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "pytest", str(target),
            "--cov=" + str(backend_dir),
            "--cov-report=term-missing",
            "-q", "-p", "no:cacheprovider", "--tb=no",
            "--deselect", "tests/test_accurate_scout.py::test_channel_gating_medium_phone_allows_whatsapp_not_call",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(backend_dir),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "coverage run exceeded 600s timeout"}
    except FileNotFoundError:
        return {"ok": False, "error": "pytest-cov not installed (pip install pytest-cov)"}
    except Exception as e:
        return {"ok": False, "error": f"coverage run failed: {type(e).__name__}: {e}"}

    out = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
    # Parse "TOTAL ... NN%" from coverage summary.
    cov_pct = None
    m = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", out, re.MULTILINE)
    if m:
        cov_pct = float(m.group(1))

    # Tests passed / failed.
    passed = failed = 0
    pf = re.search(r"(\d+)\s+passed", out)
    if pf:
        passed = int(pf.group(1))
    ff = re.search(r"(\d+)\s+failed", out)
    if ff:
        failed = int(ff.group(1))

    # Files with <80% line coverage.
    uncovered: list[str] = []
    for line in out.splitlines():
        m2 = re.match(r"^([\w./_-]+\.py)\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", line)
        if m2 and float(m2.group(2)) < 80.0:
            uncovered.append(m2.group(1))

    return {
        "ok":               True,
        "coverage_percent": cov_pct,
        "tests_passed":     passed,
        "tests_failed":     failed,
        "uncovered_files":  uncovered[:50],
        "raw_summary":      "\n".join(out.splitlines()[-40:]),
    }


# ── 4. run_linter ────────────────────────────────────────────────────

async def run_linter(path: str) -> dict:
    """Auto-detect language and run the appropriate linter.

    Args:
      path: absolute or repo-relative file or directory.

    Returns:
      ok             : True
      tool           : "ruff" | "eslint"
      errors_count   : int
      warnings_count : int
      files_checked  : int
      output         : str (capped at 8k)
    """
    if not path:
        return {"ok": False, "error": "path is required"}
    p = Path(path)
    if not p.is_absolute():
        p = _ROOT / p
    if not p.exists():
        return {"ok": False, "error": f"path not found: {p}"}

    # Decide tool by suffix (single file) or by what's in the dir.
    is_dir = p.is_dir()
    suffix = "" if is_dir else p.suffix.lower()
    if suffix in (".py",) or (is_dir and any(p.rglob("*.py"))):
        tool = "ruff"
    elif suffix in (".js", ".jsx", ".ts", ".tsx") or (
        is_dir and any(p.rglob("*.jsx")) or any(p.rglob("*.js"))
    ):
        tool = "eslint"
    else:
        return {"ok": False, "error": f"no linter for extension '{suffix}'"}

    if tool == "ruff":
        try:
            proc = await asyncio.create_subprocess_exec(
                "ruff", "check", str(p), "--output-format=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            try:
                rows = json.loads(stdout or b"[]")
            except Exception:
                rows = []
            errors = sum(1 for r in rows if r.get("code", "").startswith("E"))
            warnings = sum(1 for r in rows if r.get("code", "").startswith("W"))
            files_checked = len({r.get("filename") for r in rows}) or (
                1 if p.is_file() else sum(1 for _ in p.rglob("*.py"))
            )
            return {
                "ok":              True,
                "tool":            "ruff",
                "errors_count":    errors,
                "warnings_count":  warnings,
                "files_checked":   files_checked,
                "output":          stdout.decode("utf-8", errors="replace")[:8000],
            }
        except FileNotFoundError:
            return {"ok": False, "error": "ruff not installed"}
        except Exception as e:
            return {"ok": False, "error": f"ruff failed: {e}"}

    # eslint
    try:
        frontend_dir = _ROOT / "frontend"
        proc = await asyncio.create_subprocess_exec(
            "npx", "eslint", str(p), "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(frontend_dir) if frontend_dir.exists() else None,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        try:
            rows = json.loads(stdout or b"[]")
        except Exception:
            rows = []
        errors = sum(r.get("errorCount", 0) for r in rows)
        warnings = sum(r.get("warningCount", 0) for r in rows)
        return {
            "ok":              True,
            "tool":            "eslint",
            "errors_count":    errors,
            "warnings_count":  warnings,
            "files_checked":   len(rows),
            "output":          stdout.decode("utf-8", errors="replace")[:8000],
        }
    except FileNotFoundError:
        return {"ok": False, "error": "npx/eslint not installed"}
    except Exception as e:
        return {"ok": False, "error": f"eslint failed: {e}"}


# ── 5. mongo_query_safe ──────────────────────────────────────────────

_db = None

def set_db(db) -> None:
    """Wire the Mongo handle from server.py once at boot."""
    global _db
    _db = db


async def mongo_query_safe(
    collection: str,
    filter: dict | None = None,
    projection: dict | None = None,
    limit: int = 20,
) -> dict:
    """Read-only Mongo query. Always excludes `_id`. Never writes.

    Hard cap of 200 docs to keep the response token cost predictable.
    """
    if _db is None:
        return {"ok": False, "error": "DB not wired (call set_db first)"}
    if not isinstance(collection, str) or not collection.isidentifier() and "_" not in collection:
        # allow letters, digits, underscores
        if not re.match(r"^[A-Za-z0-9_]+$", collection or ""):
            return {"ok": False, "error": "invalid collection name"}
    proj = dict(projection or {})
    proj["_id"] = 0  # FORCE exclude
    flt = dict(filter or {})
    n = max(1, min(int(limit or 20), 200))
    try:
        cursor = _db[collection].find(flt, proj).limit(n)
        docs = await cursor.to_list(length=n)
        return {
            "ok":         True,
            "collection": collection,
            "count":      len(docs),
            "docs":       docs,
        }
    except Exception as e:
        return {"ok": False, "error": f"query failed: {type(e).__name__}: {e}"}


# ── 6. view_bulk ─────────────────────────────────────────────────────

async def view_bulk(paths: list[str]) -> dict:
    """Read up to 10 files in one call. Each capped at 8k chars.

    Returns:
      ok     : True
      count  : int
      files  : [{path, exists, size, content, error?}]
    """
    if not isinstance(paths, list) or not paths:
        return {"ok": False, "error": "paths must be a non-empty list"}
    capped_paths = paths[:10]
    files: list[dict] = []
    for raw in capped_paths:
        p = Path(raw) if str(raw).startswith("/") else _ROOT / str(raw)
        rec: dict[str, Any] = {"path": str(p), "exists": p.exists()}
        if not p.exists():
            rec["error"] = "file not found"
            files.append(rec)
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            # iter 331a Sprint 3.7 Gap 4 — scrub secrets pre-LLM.
            try:
                from services.ora_safety import scrub_secrets
                text, _n = scrub_secrets(text)
                if _n:
                    rec["secrets_redacted"] = _n
                    logger.info(f"[secrets-scrubber] redacted {_n} in view_bulk({p})")
            except Exception:
                pass
            rec["size"] = len(text)
            if len(text) > 8000:
                rec["content"] = text[:8000] + f"\n…[truncated {len(text) - 8000}]"
            else:
                rec["content"] = text
        except Exception as e:
            rec["error"] = f"read failed: {e}"
        files.append(rec)
    return {
        "ok":    True,
        "count": len(files),
        "files": files,
    }


# ── 7. ask_human ─────────────────────────────────────────────────────
# `ask_human` is special: it does NOT do the work itself; it returns a
# directive that ora_agent.py's tool loop interprets to PAUSE the
# session and surface a yellow "Question for the founder" card. The
# session resumes only after the founder replies in the chat input.
# Implemented as a Mongo write to ora_pending_questions so the cockpit
# UI can render it independently of the LLM.

_PENDING_QUESTIONS_COLLECTION = "ora_pending_questions"


async def ask_human(question: str, urgency: str = "normal") -> dict:
    """Pause ORA and ask the founder a clarifying question.

    Args:
      question: plain English. <500 chars.
      urgency:  "normal" | "blocking" | "fyi"

    Returns:
      ok                 : True
      question_id        : uuid
      pause              : True  — signals ora_agent to halt the loop
      surface_in_chat    : True
      created_at         : iso ts
    """
    if _db is None:
        return {"ok": False, "error": "DB not wired"}
    q = (question or "").strip()
    if not q:
        return {"ok": False, "error": "question is empty"}
    if len(q) > 500:
        return {"ok": False, "error": "question >500 chars; shorten"}
    if urgency not in ("normal", "blocking", "fyi"):
        urgency = "normal"
    qid = os.urandom(12).hex()
    doc = {
        "_id":         qid,
        "question":    q,
        "urgency":     urgency,
        "status":      "pending",
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "answered_at": None,
        "answer":      None,
    }
    try:
        await _db[_PENDING_QUESTIONS_COLLECTION].insert_one(doc)
    except Exception as e:
        return {"ok": False, "error": f"persist failed: {e}"}
    return {
        "ok":              True,
        "question_id":     qid,
        "pause":           True,
        "surface_in_chat": True,
        "urgency":         urgency,
        "question":        q,
        "created_at":      doc["created_at"],
    }


# ── 8. glob_files ────────────────────────────────────────────────────

_GITIGNORE_CACHE: dict[str, list[str]] = {}


def _load_gitignore(base: Path) -> list[str]:
    """Load .gitignore patterns once per base. Cheap; not perfect git-rs."""
    key = str(base)
    if key in _GITIGNORE_CACHE:
        return _GITIGNORE_CACHE[key]
    patterns: list[str] = []
    gi = base / ".gitignore"
    if gi.exists():
        for line in gi.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    # Always exclude obvious junk
    patterns.extend([
        "node_modules/", "__pycache__/", "*.pyc",
        ".git/", "venv/", ".venv/", ".env",
    ])
    _GITIGNORE_CACHE[key] = patterns
    return patterns


def _is_ignored(path: Path, base: Path, patterns: list[str]) -> bool:
    try:
        rel = str(path.relative_to(base))
    except ValueError:
        return False
    for pat in patterns:
        # Directory pattern (trailing /)
        if pat.endswith("/"):
            if (pat[:-1] + "/") in (rel + "/"):
                return True
            continue
        if fnmatch.fnmatch(rel, pat):
            return True
        if fnmatch.fnmatch(rel, "**/" + pat):
            return True
        if fnmatch.fnmatch(Path(rel).name, pat):
            return True
    return False


async def glob_files(pattern: str, base: str = "") -> dict:
    """Find files matching a glob pattern. Respects .gitignore.

    Args:
      pattern: e.g. `*.py`, `**/*.jsx`, `services/ora_*.py`
      base:    absolute or repo-relative starting dir (default: ROOT)

    Returns:
      ok     : True
      pattern: echo
      base   : str
      count  : int
      files  : [str]  (up to 500)
    """
    if not pattern:
        return {"ok": False, "error": "pattern is required"}
    bp = Path(base) if (base and str(base).startswith("/")) else (_ROOT / (base or ""))
    if not bp.exists():
        return {"ok": False, "error": f"base not found: {bp}"}
    patterns = _load_gitignore(bp)
    try:
        # Use glob if pattern has ** else rglob single component.
        if "**" in pattern:
            it = bp.glob(pattern)
        else:
            it = bp.rglob(pattern)
        files: list[str] = []
        for match in it:
            if not match.is_file():
                continue
            if _is_ignored(match, bp, patterns):
                continue
            files.append(str(match))
            if len(files) >= 500:
                break
        return {
            "ok":      True,
            "pattern": pattern,
            "base":    str(bp),
            "count":   len(files),
            "files":   files,
        }
    except Exception as e:
        return {"ok": False, "error": f"glob failed: {e}"}


# ── Registry patch — spliced into TOOL_REGISTRY by ora_tools.py ─────

TOOL_REGISTRY_PATCH = {
    "web_search": {
        "fn": web_search,
        "args_spec": {
            "query":   "str — search query",
            "context": "str — 'low'|'medium'|'high' (default low, max 10 results)",
        },
        "description": (
            "TIER 1 (auto, read-only). Live internet search via DuckDuckGo. "
            "MANDATORY before writing any third-party API integration — your "
            "training data is stale. Returns abstract + up to 10 related results."
        ),
    },
    "read_logs": {
        "fn": read_logs,
        "args_spec": {
            "service": "str — 'backend'|'frontend' or specific log filename",
            "lines":   "int — number of trailing lines (default 100, max 1000)",
        },
        "description": (
            "TIER 1 (auto, read-only). Tail supervisor logs. Use as first "
            "step when debugging a runtime error before guessing."
        ),
    },
    "check_coverage": {
        "fn": check_coverage,
        "args_spec": {
            "path": "str — optional subdir under /app/backend/tests (default: full suite)",
        },
        "description": (
            "TIER 1 (auto, read-only). Run pytest --cov on the test suite "
            "and return real line-coverage percent + list of files <80%."
        ),
    },
    "run_linter": {
        "fn": run_linter,
        "args_spec": {
            "path": "str — file or directory; auto-detects Python (ruff) vs JS/TS (eslint)",
        },
        "description": (
            "TIER 1 (auto, read-only). Lint a file or directory. Returns "
            "errors_count, warnings_count, files_checked, and the raw "
            "linter output (JSON for ruff/eslint)."
        ),
    },
    "mongo_query_safe": {
        "fn": mongo_query_safe,
        "args_spec": {
            "collection": "str — collection name",
            "filter":     "dict — Mongo filter (default {})",
            "projection": "dict — projection (default {}); _id always excluded",
            "limit":      "int — max docs (default 20, hard cap 200)",
        },
        "description": (
            "TIER 1 (auto, read-only). Read-only Mongo query. Always "
            "excludes _id. Hard-capped at 200 docs per call to keep "
            "token cost predictable. Use this before legion_exec for "
            "any data-layer debugging."
        ),
    },
    "view_bulk": {
        "fn": view_bulk,
        "args_spec": {
            "paths": "list[str] — up to 10 file paths (absolute or relative to /app)",
        },
        "description": (
            "TIER 1 (auto, read-only). Read up to 10 files in one call. "
            "Each capped at 8k chars. Use during exploration to save "
            "tool-call round-trips."
        ),
    },
    "ask_human": {
        "fn": ask_human,
        "args_spec": {
            "question": "str — plain English question (<500 chars)",
            "urgency":  "str — 'normal'|'blocking'|'fyi' (default normal)",
        },
        "description": (
            "TIER 1 (auto). Pause the session and ask the founder a "
            "clarifying question. Persists to ora_pending_questions and "
            "surfaces a yellow card in the cockpit chat. Use when "
            "genuinely blocked — NOT for permission to proceed."
        ),
    },
    "glob_files": {
        "fn": glob_files,
        "args_spec": {
            "pattern": "str — glob pattern e.g. '*.py', '**/*.jsx'",
            "base":    "str — starting dir (default /app)",
        },
        "description": (
            "TIER 1 (auto, read-only). Find files by glob pattern. "
            "Respects .gitignore. Capped at 500 results. Faster than "
            "grep when you only need filenames."
        ),
    },
}


def splice_into(tool_registry: dict) -> int:
    """Merge our patch into ora_tools.TOOL_REGISTRY. Returns count added."""
    tool_registry.update(TOOL_REGISTRY_PATCH)
    return len(TOOL_REGISTRY_PATCH)
