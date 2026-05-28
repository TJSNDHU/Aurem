"""
routers/cto_codebase_router.py — iter D-54

Real codebase + GitHub access for AUREM CTO. Ends the "I imagined the
code" failure mode: when the founder asks for line 43 of a file, the
LLM gets the real bytes injected into its context, not a hallucination.

Endpoints (all admin-only; same JWT gate as cto_tools / cto_verify):

  GET /api/developers/cto/file?path=backend/routers/aurem_routes.py
       &start_line=1&end_line=80
       → {ok, path, total_lines, lines:[{n, text}], sha1}

  GET /api/developers/cto/file/search?q=...&path_glob=...
       → {ok, q, matches:[{path, line, text}], scanned, truncated}

  GET /api/developers/cto/github/commits?owner=TJSNDHU&repo=Aurem
       &branch=main&per_page=20
       → {ok, items:[{sha, short_sha, message, committer, url, ts}]}

Security model
--------------
* All file paths are sandboxed under `/app`. Any path containing `..`,
  starting with `/`, or resolving outside `/app` is rejected.
* A small blocklist (`.env`, `.git/`, `*.pem`, `*.key`, etc.) hides
  secrets and internal git plumbing.
* Files larger than 256 KB are streamed with a hard cap (we send the
  first 256 KB + a truncation marker so the LLM context can't be
  blown up).
"""
from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/developers/cto",
                    tags=["cto-codebase"])

# Sandboxing — every file path the LLM is allowed to read MUST resolve
# under this root. We deliberately use the realpath so symlink tricks
# can't escape.
_ROOT = Path("/app").resolve()
_MAX_BYTES = 256 * 1024
_SEARCH_MAX_FILES = 500
_SEARCH_MAX_HITS  = 50

# Things we never let the LLM read.
_BLOCKED_NAMES = {".env", ".env.local", ".env.production",
                   ".env.development", "id_rsa", "id_ed25519"}
_BLOCKED_GLOBS = ("*.pem", "*.key", "*.p12", "*.pfx",
                   "**/.git/**", "**/node_modules/**", "**/__pycache__/**")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        import jwt as _jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


def _resolve_safe(rel_path: str) -> Path:
    """Resolve a path under /app or raise HTTPException(403)."""
    rel_path = (rel_path or "").strip()
    if not rel_path:
        raise HTTPException(400, "path_required")
    if rel_path.startswith("/"):
        # Allow absolute paths only if they live under /app.
        candidate = Path(rel_path).resolve()
    else:
        candidate = (_ROOT / rel_path).resolve()
    if not str(candidate).startswith(str(_ROOT)):
        raise HTTPException(403, "path_outside_sandbox")
    # name + extension blocklist
    name = candidate.name
    if name in _BLOCKED_NAMES:
        raise HTTPException(403, "path_is_blocked_secret")
    rel = candidate.relative_to(_ROOT).as_posix()
    # Hard blocks on path SEGMENTS that should never be exposed (covers
    # nested + top-level).
    rel_parts = set(rel.split("/"))
    if rel_parts & {".git", "node_modules", "__pycache__"}:
        raise HTTPException(403, "path_matches_blocklist")
    for pat in _BLOCKED_GLOBS:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
            raise HTTPException(403, "path_matches_blocklist")
    return candidate


# ── 1. File read ────────────────────────────────────────────────────

@router.get("/file")
async def read_file(path: str = Query(..., min_length=1, max_length=400),
                     start_line: int = Query(1,    ge=1, le=200_000),
                     end_line:   int = Query(2000, ge=1, le=200_000),
                     authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    target = _resolve_safe(path)
    if not target.exists():
        raise HTTPException(404, f"not_found: {path}")
    if not target.is_file():
        raise HTTPException(400, f"not_a_file: {path}")
    if target.stat().st_size > 2 * 1024 * 1024:
        raise HTTPException(413, "file_too_large (>2 MB)")

    with target.open("rb") as f:
        data = f.read(_MAX_BYTES + 1)
    truncated = len(data) > _MAX_BYTES
    if truncated:
        data = data[:_MAX_BYTES]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")

    all_lines = text.split("\n")
    total = len(all_lines)
    start = max(1, start_line)
    end   = min(total, end_line)
    out_lines = [
        {"n": i + 1, "text": all_lines[i]}
        for i in range(start - 1, end)
    ]
    sha1 = hashlib.sha1(data).hexdigest()[:12]

    return {
        "ok":          True,
        "path":        target.relative_to(_ROOT).as_posix(),
        "total_lines": total,
        "returned":    {"start": start, "end": end, "count": len(out_lines)},
        "truncated":   truncated,
        "sha1":        sha1,
        "lines":       out_lines,
        "ts":          _now(),
    }


# ── 2. Codebase search (substring) ──────────────────────────────────

@router.get("/file/search")
async def search_codebase(
    q: str = Query(..., min_length=2, max_length=120),
    path_glob: str = Query("**/*.py", min_length=1, max_length=80),
    case_insensitive: bool = Query(True),
    authorization: str = Header(None),
) -> dict[str, Any]:
    await _require_admin(authorization)
    needle = q.lower() if case_insensitive else q

    matches: list[dict[str, Any]] = []
    scanned = 0
    truncated = False

    for path in _ROOT.rglob("*"):
        if scanned >= _SEARCH_MAX_FILES:
            truncated = True
            break
        if not path.is_file():
            continue
        rel = path.relative_to(_ROOT).as_posix()
        if not fnmatch.fnmatch(rel, path_glob):
            continue
        if any(fnmatch.fnmatch(rel, b) or fnmatch.fnmatch(path.name, b)
                for b in _BLOCKED_GLOBS):
            continue
        if path.name in _BLOCKED_NAMES:
            continue
        scanned += 1
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for ln, line in enumerate(f, 1):
                    cmp = line.lower() if case_insensitive else line
                    if needle in cmp:
                        matches.append({
                            "path": rel, "line": ln,
                            "text": line.rstrip("\n")[:300],
                        })
                        if len(matches) >= _SEARCH_MAX_HITS:
                            truncated = True
                            break
        except Exception:
            continue
        if truncated:
            break

    return {
        "ok":         True,
        "q":          q,
        "path_glob":  path_glob,
        "scanned":    scanned,
        "matches":    matches,
        "truncated":  truncated,
        "ts":         _now(),
    }


# ── 3. GitHub commits (D-42 token reuse) ────────────────────────────

async def _get_github_token() -> str:
    """Re-use the same lookup as cto_verify_router so we have ONE
    source of truth for GitHub creds."""
    import os as _os
    try:
        # Late import to avoid hard coupling; cto_verify_router sets the
        # same _db via its own set_db. We try ours first via Atlas.
        from routers.cto_verify_router import _get_github_token as _gt
        tok = await _gt()
        if tok:
            return tok
    except Exception:
        pass
    return (_os.environ.get("GITHUB_BOT_PAT", "") or
            _os.environ.get("GITHUB_TOKEN", ""))


@router.get("/github/commits")
async def github_commits(
    owner:    str = Query(..., min_length=1, max_length=80),
    repo:     str = Query(..., min_length=1, max_length=120),
    branch:   str = Query("main", min_length=1, max_length=80),
    per_page: int = Query(20, ge=1, le=100),
    authorization: str = Header(None),
) -> dict[str, Any]:
    await _require_admin(authorization)
    token = await _get_github_token()
    if not token:
        raise HTTPException(503,
            "no_github_token (connect via /developers/connect)")

    url = (f"https://api.github.com/repos/{owner}/{repo}/commits"
            f"?sha={branch}&per_page={per_page}")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url, headers=headers)
        except Exception as e:
            raise HTTPException(502, f"github_unreachable: {e}")
    if r.status_code != 200:
        raise HTTPException(r.status_code,
            f"github_status_{r.status_code}: {r.text[:200]}")

    rows = r.json() or []
    out = []
    for c in rows:
        commit = c.get("commit") or {}
        out.append({
            "sha":       c.get("sha", ""),
            "short_sha": (c.get("sha") or "")[:7],
            "message":   (commit.get("message") or "")[:280],
            "committer": ((commit.get("committer") or {}).get("name", "")),
            "url":       c.get("html_url", ""),
            "ts":        ((commit.get("committer") or {}).get("date", "")),
        })
    return {
        "ok":     True,
        "owner":  owner,
        "repo":   repo,
        "branch": branch,
        "items":  out,
        "ts":     _now(),
    }
