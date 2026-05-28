"""
routers/cto_verify_router.py — iter D-52

Auto-verification surface for AUREM CTO. Founder's pain: the chat used
to *claim* "pushed to GitHub / deployed to aurem.live" without any
system-level proof. This router gives the frontend three honest probes:

  POST /api/developers/cto/verify/code
       body: {"language": "python"|"javascript", "source": str}
       → {"valid": bool, "error": str}

  POST /api/developers/cto/verify/github
       body: {"owner": str, "repo": str, "branch": "main",
              "since_iso": "2026-..." (optional — defaults to last 60s),
              "expected_sha": str (optional)}
       → {"found": bool, "sha": str, "message": str, "url": str,
          "committed_at": str}

  POST /api/developers/cto/verify/deploy
       body: {"target_url": "https://aurem.live",
              "expected_iter": "D-52",
              "timeout_s": int (default 120)}
       → {"found": bool, "iter": str, "elapsed_s": float,
          "last_seen": dict}

All three are admin-only (same JWT gate as `cto_tools_router`). Every
call is audited to `cto_verify_runs` so we can prove later what was
checked, by whom, with what result.

Design notes
------------
* Code-check is offline (`py_compile.compile_command` + a tiny JS
  tokenizer for syntax). No network, sub-second.
* GitHub-check uses the founder's stored OAuth/PAT (same one D-42/D-47
  power Save-to-GitHub) — we *never* trust the chat's claim of a SHA.
* Deploy-check polls the target's `/api/version` every 5 s up to
  `timeout_s`. We short-circuit on first match. Pure HTTP — no SSH.
"""
from __future__ import annotations

import asyncio
import ast
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/developers/cto/verify", tags=["cto-verify"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(tool: str, actor: str,
                  payload: dict[str, Any], result: dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        await _db.cto_verify_runs.insert_one({
            "tool": tool, "actor": actor, "ts": _now(),
            "input": payload, "result": result,
        })
    except Exception as e:
        logger.warning(f"[cto-verify] audit insert failed: {e}")


async def _require_admin(authorization: str | None) -> str:
    """Same admin gate as cto_tools_router — decode platform admin JWT,
    fall back to developer JWT with admin role. Plain JWT in/out, no
    Emergent imports."""
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


# ── 1. Code syntax verification ──────────────────────────────────────

class CodeBody(BaseModel):
    language: str = Field(..., pattern="^(python|javascript|js|jsx|tsx|ts)$")
    source:   str = Field(..., min_length=1, max_length=200_000)


def _verify_python(src: str) -> tuple[bool, str]:
    try:
        ast.parse(src)
        return True, ""
    except SyntaxError as e:
        return False, f"line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# Minimal JS/JSX syntactic sanity — looks for unbalanced braces/brackets
# and common fatal patterns. Not a full parser; just enough that the
# obvious LLM hallucinations ("```js\n<fake>") get caught as RED.
_JS_BAD_PATTERNS = (
    re.compile(r"^\s*<unfinished>",        re.M),
    re.compile(r"^\s*\.\.\.\s*$",          re.M),  # placeholder body
)


def _verify_js(src: str) -> tuple[bool, str]:
    # Reject empty / clearly-truncated bodies
    if not src.strip():
        return False, "empty source"
    for pat in _JS_BAD_PATTERNS:
        if pat.search(src):
            return False, "placeholder / unfinished code"

    # Balance braces, parens, brackets (skipping content inside strings
    # and line/block comments).
    pairs = {"{": "}", "(": ")", "[": "]"}
    closers = {v: k for k, v in pairs.items()}
    stack: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # line comment
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            i = src.find("\n", i)
            i = n if i == -1 else i + 1
            continue
        # block comment
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i = src.find("*/", i + 2)
            i = n if i == -1 else i + 2
            continue
        # string literal
        if c in ("'", '"', "`"):
            quote = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2; continue
                if src[i] == quote:
                    i += 1; break
                i += 1
            continue
        if c in pairs:
            stack.append(c); i += 1; continue
        if c in closers:
            if not stack or stack[-1] != closers[c]:
                return False, f"unbalanced '{c}' at offset {i}"
            stack.pop(); i += 1; continue
        i += 1
    if stack:
        return False, f"unclosed '{stack[-1]}' at end of file"
    return True, ""


@router.post("/code")
async def verify_code(body: CodeBody,
                       authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    lang = body.language.lower()
    if lang == "python":
        ok, err = _verify_python(body.source)
    else:  # js/jsx/tsx/ts/javascript
        ok, err = _verify_js(body.source)
    out = {"valid": ok, "error": err, "language": lang,
            "checked_bytes": len(body.source.encode("utf-8")),
            "ts": _now()}
    await _audit("verify_code", actor,
                  {"language": lang, "bytes": out["checked_bytes"]}, out)
    return out


# ── 2. GitHub push verification ──────────────────────────────────────

class GithubBody(BaseModel):
    owner:        str = Field(..., min_length=1, max_length=80)
    repo:         str = Field(..., min_length=1, max_length=120)
    branch:       str = "main"
    since_iso:    str = ""   # default: last 60s
    expected_sha: str = ""


async def _get_github_token() -> str:
    """Lookup the founder's GitHub token. D-42 stores it in
    `developer_github_links` (per-developer OAuth) and falls back to
    `GITHUB_BOT_PAT` env."""
    import os as _os
    if _db is not None:
        try:
            row = await _db.developer_github_links.find_one(
                {}, {"_id": 0, "access_token": 1},
                sort=[("connected_at", -1)],
            )
            if row and row.get("access_token"):
                return row["access_token"]
        except Exception:
            pass
    return _os.environ.get("GITHUB_BOT_PAT", "") or \
           _os.environ.get("GITHUB_TOKEN", "")


@router.post("/github")
async def verify_github(body: GithubBody,
                         authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    token = await _get_github_token()
    if not token:
        out = {"found": False, "error": "no_github_token",
                "hint": "Connect GitHub at /developers/connect first.",
                "ts": _now()}
        await _audit("verify_github", actor, body.model_dump(), out)
        return out

    since = body.since_iso.strip()
    if not since:
        since = (datetime.now(timezone.utc)
                  - timedelta(seconds=60)).isoformat()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = (f"https://api.github.com/repos/{body.owner}/{body.repo}"
            f"/commits?sha={body.branch}&since={since}&per_page=5")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url, headers=headers)
        except Exception as e:
            out = {"found": False, "error": f"github_unreachable: {e}",
                    "ts": _now()}
            await _audit("verify_github", actor, body.model_dump(), out)
            return out

    if r.status_code != 200:
        out = {"found": False, "error": f"github_status_{r.status_code}",
                "detail": r.text[:300], "ts": _now()}
        await _audit("verify_github", actor, body.model_dump(), out)
        return out

    items = r.json() or []
    if not items:
        out = {"found": False, "error": "no_recent_commit",
                "since": since, "ts": _now()}
        await _audit("verify_github", actor, body.model_dump(), out)
        return out

    top = items[0]
    sha = top.get("sha", "")
    expected = body.expected_sha.strip()
    if expected and not sha.startswith(expected[:7]):
        out = {"found": False, "error": "sha_mismatch",
                "actual_sha": sha, "expected_sha": expected, "ts": _now()}
        await _audit("verify_github", actor, body.model_dump(), out)
        return out

    out = {
        "found": True,
        "sha":   sha,
        "short_sha": sha[:7],
        "message": (top.get("commit") or {}).get("message", "")[:160],
        "url":     top.get("html_url", ""),
        "committed_at": ((top.get("commit") or {})
                          .get("committer") or {}).get("date", ""),
        "ts": _now(),
    }
    await _audit("verify_github", actor, body.model_dump(), out)
    return out


# ── 3. Deploy / version polling verification ─────────────────────────

class DeployBody(BaseModel):
    target_url:    str = Field(..., min_length=8, max_length=300)
    expected_iter: str = Field(..., min_length=1, max_length=40)
    timeout_s:     int = Field(120, ge=5, le=600)
    poll_every_s:  int = Field(5,   ge=2, le=30)


@router.post("/deploy")
async def verify_deploy(body: DeployBody,
                         authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    deadline = time.monotonic() + body.timeout_s
    last_seen: dict[str, Any] = {}
    elapsed = 0.0
    found = False
    url = body.target_url.rstrip("/") + "/api/version"

    async with httpx.AsyncClient(timeout=8.0) as client:
        while time.monotonic() < deadline:
            t0 = time.monotonic()
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    last_seen = r.json()
                    if (last_seen.get("iter") or "") == body.expected_iter:
                        found = True
                        elapsed = round(t0 - (deadline - body.timeout_s), 2)
                        break
            except Exception as e:
                last_seen = {"error": f"{type(e).__name__}: {e}"}
            await asyncio.sleep(body.poll_every_s)

    if not found:
        elapsed = round(body.timeout_s, 2)

    out = {
        "found":      found,
        "iter":       last_seen.get("iter", ""),
        "expected":   body.expected_iter,
        "elapsed_s":  elapsed,
        "last_seen":  last_seen,
        "ts":         _now(),
    }
    await _audit("verify_deploy", actor, body.model_dump(),
                  {k: v for k, v in out.items() if k != "last_seen"})
    return out
