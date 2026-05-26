"""
aurem_cto.services.codebase_indexer — Gap 1 (iter D-33)

Pulls the latest files from a customer's GitHub repo using the existing
BYOK PAT they already saved, indexes routes / models / components /
dependencies, and exposes a single `build_context_block(user_id)` call
that the dev-CTO chat injects into the system prompt before each turn.

The customer never has to explain their codebase again.

External deps allowed by DEPENDENCIES.md: httpx, fastapi, motor.
Host imports used: none beyond what the parent services already touch.

Public surface:
  - async refresh_index(user_id, repo_url, pat) -> dict   (returns summary)
  - async build_context_block(user_id, max_chars=6000) -> str | None
  - GET /aurem-cto/codebase/index  (auth)  → cached index for the caller

Storage: `aurem_cto_codebase_index` — one document per user. Schema:
  { user_id, repo_owner, repo_name, default_branch, refreshed_at,
    file_count, total_bytes,
    files: [{ path, sha, size, lang, role: routes|models|components|deps|other,
              snippet (first 800 chars) }],
    deps:  { python: [...], node: [...] } }
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Header

from .db import get_db
from .auth import current_dev

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/codebase", tags=["AUREM CTO Codebase"])


GITHUB_API = "https://api.github.com"
INDEX_TTL_SECONDS = 600          # avoid hammering GitHub on every turn
MAX_FILES = 80                    # cap memory; LLM context budget is small
MAX_BYTES_PER_FILE = 12_000       # only first chunk goes into the index
ROLE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(^|/)(routers?|api|server|app)\.py$"), "routes"),
    (re.compile(r"(^|/)routers/.+\.py$"),                "routes"),
    (re.compile(r"(^|/)(models|schemas)/.+\.py$"),       "models"),
    (re.compile(r"(^|/)(components|pages|app)/.+\.(tsx?|jsx?)$"), "components"),
    (re.compile(r"(^|/)(requirements\.txt|pyproject\.toml|package\.json)$"), "deps"),
]


def _detect_role(path: str) -> str:
    for rx, role in ROLE_RULES:
        if rx.search(path):
            return role
    return "other"


def _detect_lang(path: str) -> str:
    if path.endswith(".py"):  return "python"
    if path.endswith((".ts", ".tsx", ".js", ".jsx")):  return "js"
    if path.endswith((".json",)):  return "json"
    if path.endswith((".md",)):  return "md"
    if path.endswith((".yml", ".yaml")):  return "yaml"
    return "other"


async def _gh_get(client: httpx.AsyncClient, url: str, pat: str) -> Any:
    headers = {"Accept": "application/vnd.github+json",
               "Authorization": f"Bearer {pat}",
               "X-GitHub-Api-Version": "2022-11-28"}
    r = await client.get(url, headers=headers, timeout=15.0)
    if r.status_code == 401:
        raise HTTPException(401, "github_pat_invalid")
    if r.status_code == 404:
        raise HTTPException(404, "github_repo_not_found")
    if r.status_code >= 500:
        raise HTTPException(502, f"github_upstream_{r.status_code}")
    r.raise_for_status()
    return r.json()


_REPO_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/.]+)")


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    m = _REPO_RE.search(repo_url or "")
    if not m:
        raise HTTPException(400, "invalid_repo_url")
    return m.group("owner"), m.group("name")


async def refresh_index(user_id: str, repo_url: str, pat: str) -> dict[str, Any]:
    """Hits GitHub, walks the tree, writes the index doc. Returns summary."""
    db = get_db()
    if db is None:
        raise HTTPException(503, "db_not_ready")
    owner, name = _parse_repo_url(repo_url)
    async with httpx.AsyncClient() as c:
        repo = await _gh_get(c, f"{GITHUB_API}/repos/{owner}/{name}", pat)
        branch = repo.get("default_branch", "main")
        tree = await _gh_get(
            c, f"{GITHUB_API}/repos/{owner}/{name}/git/trees/{branch}?recursive=1",
            pat,
        )
        entries = [t for t in (tree.get("tree") or [])
                   if t.get("type") == "blob"][:MAX_FILES]

        # Fetch contents in parallel — but be polite (10 concurrent).
        sem = asyncio.Semaphore(10)
        files: list[dict] = []
        deps = {"python": [], "node": []}

        async def fetch_one(entry):
            path = entry["path"]
            sha  = entry["sha"]
            size = entry.get("size", 0)
            role = _detect_role(path)
            lang = _detect_lang(path)
            async with sem:
                try:
                    raw_url = (f"{GITHUB_API}/repos/{owner}/{name}"
                                f"/contents/{path}?ref={branch}")
                    blob = await _gh_get(c, raw_url, pat)
                    content = blob.get("content") or ""
                    encoding = blob.get("encoding", "base64")
                    if encoding == "base64":
                        import base64 as _b64
                        try:
                            txt = _b64.b64decode(content).decode(
                                "utf-8", errors="replace")
                        except Exception:
                            txt = ""
                    else:
                        txt = content
                    snippet = txt[:MAX_BYTES_PER_FILE]
                except HTTPException:
                    snippet = ""
                except Exception as e:
                    logger.debug(f"[indexer] {path} skipped: {e}")
                    snippet = ""
            f = {
                "path":    path,
                "sha":     sha,
                "size":    size,
                "lang":    lang,
                "role":    role,
                "snippet": snippet,
            }
            files.append(f)
            # Dependency surfaces (best-effort parse).
            if path.endswith("requirements.txt"):
                deps["python"] = [
                    ln.split("==")[0].strip()
                    for ln in snippet.splitlines()
                    if ln.strip() and not ln.startswith("#")
                ][:80]
            elif path.endswith("package.json"):
                try:
                    import json as _json
                    pj = _json.loads(snippet) if snippet else {}
                    deps["node"] = sorted(
                        list((pj.get("dependencies") or {}).keys())
                        + list((pj.get("devDependencies") or {}).keys())
                    )[:80]
                except Exception:
                    pass

        await asyncio.gather(*(fetch_one(e) for e in entries))

    doc = {
        "user_id":        user_id,
        "repo_owner":     owner,
        "repo_name":      name,
        "default_branch": branch,
        "refreshed_at":   time.time(),
        "file_count":     len(files),
        "total_bytes":    sum(f["size"] or 0 for f in files),
        "files":          files,
        "deps":           deps,
    }
    await db.aurem_cto_codebase_index.update_one(
        {"user_id": user_id},
        {"$set": doc},
        upsert=True,
    )
    return {
        "ok": True,
        "owner": owner,
        "name":  name,
        "branch": branch,
        "file_count": len(files),
        "python_deps": deps["python"][:10],
        "node_deps":   deps["node"][:10],
    }


def _format_context_block(doc: dict, max_chars: int = 6000) -> str:
    """Renders the cached index into the system-prompt block AUREM CTO
    reads at the top of every turn. Trims to `max_chars` so we never
    blow the context budget."""
    parts: list[str] = []
    parts.append(
        f"\n\nCUSTOMER CODEBASE CONTEXT (auto-injected — repo "
        f"{doc.get('repo_owner')}/{doc.get('repo_name')}@"
        f"{doc.get('default_branch','main')}, "
        f"{doc.get('file_count', 0)} files):"
    )
    deps = doc.get("deps") or {}
    if deps.get("python"):
        parts.append("Python deps: " + ", ".join(deps["python"][:30]))
    if deps.get("node"):
        parts.append("Node deps: " + ", ".join(deps["node"][:30]))

    by_role: dict[str, list[dict]] = {}
    for f in (doc.get("files") or []):
        by_role.setdefault(f.get("role", "other"), []).append(f)

    role_caps = {"routes": 6, "models": 4, "components": 4,
                 "deps": 0, "other": 0}
    for role in ("routes", "models", "components"):
        items = by_role.get(role, [])[: role_caps[role]]
        if not items:
            continue
        parts.append(f"\n— {role.upper()} ({len(items)} shown):")
        for f in items:
            snippet = (f.get("snippet") or "").strip()
            if not snippet:
                continue
            preview = snippet[:600].replace("```", "´´´")
            parts.append(f"### {f['path']}\n```{f.get('lang','')}\n{preview}\n```")

    block = "\n".join(parts)
    if len(block) > max_chars:
        block = block[:max_chars] + "\n…(context trimmed)"
    return block


async def build_context_block(user_id: str,
                               max_chars: int = 6000) -> Optional[str]:
    """Returns the system-prompt context block, or None if the user
    has no fresh index. Re-uses cached doc; the periodic refresh job
    handles staleness."""
    db = get_db()
    if db is None:
        return None
    doc = await db.aurem_cto_codebase_index.find_one(
        {"user_id": user_id}, {"_id": 0},
    )
    if not doc:
        return None
    return _format_context_block(doc, max_chars=max_chars)


async def _fetch_user_pat(user_id: str) -> Optional[str]:
    """Whitelisted host import #1: services.byok_store fernet decrypt."""
    db = get_db()
    if db is None:
        return None
    row = await db.developer_accounts.find_one(
        {"user_id": user_id, "github_pat_enc": {"$ne": None}},
        {"_id": 0, "github_pat_enc": 1, "github_repo_url": 1},
    )
    if not row:
        return None
    try:
        from services.byok_store import _decrypt  # whitelisted
        return _decrypt(row["github_pat_enc"])
    except Exception as e:
        logger.warning(f"[indexer] PAT decrypt failed for {user_id}: {e}")
        return None


# ─── HTTP surface ────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_route(authorization: str = Header(None)) -> dict:
    """Customer (or the chat-stream pre-hook) calls this to re-pull
    the index. Auto-grabs the saved PAT + repo URL from
    developer_accounts."""
    me = await current_dev(authorization)
    pat = await _fetch_user_pat(me["user_id"])
    if not pat:
        raise HTTPException(400, "no_github_pat_saved")
    db = get_db()
    row = await db.developer_accounts.find_one(
        {"user_id": me["user_id"]},
        {"_id": 0, "github_repo_url": 1},
    )
    repo_url = (row or {}).get("github_repo_url")
    if not repo_url:
        raise HTTPException(400, "no_github_repo_saved")
    return await refresh_index(me["user_id"], repo_url, pat)


@router.get("/index")
async def get_index(authorization: str = Header(None)) -> dict:
    me = await current_dev(authorization)
    db = get_db()
    if db is None:
        raise HTTPException(503, "db_not_ready")
    doc = await db.aurem_cto_codebase_index.find_one(
        {"user_id": me["user_id"]},
        {"_id": 0, "files.snippet": 0},   # keep payload small for the UI
    )
    if not doc:
        return {"indexed": False}
    return {"indexed": True, **doc}
