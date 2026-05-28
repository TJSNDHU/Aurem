"""
routers/github_save_router.py — iter D-47

Backend for the chat composer "Save to GitHub" dialog. Reuses the
encrypted access_token saved by the D-42 OAuth flow (or PAT path) in
`developer_github_links`.

Endpoints
---------
GET  /api/developers/github/repos                       → list user's repos
GET  /api/developers/github/repos/{owner}/{repo}/branches → list branches
POST /api/developers/github/commit                       → commit two files
                                                            (manifest.json +
                                                             aurem-chat-<id>.md)
                                                            to a chosen
                                                            owner/repo:branch
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from utils.require_auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/developers/github",
    tags=["github-save"],
    dependencies=[Depends(require_auth)],
)

_db = None
GITHUB_API = "https://api.github.com"


def set_db(database):
    global _db
    _db = database


async def _get_user_token(user_id: str) -> str | None:
    """Fetch + decrypt the encrypted GitHub access token saved by
    D-42's OAuth flow (or the PAT path)."""
    if _db is None:
        return None
    row = await _db.developer_github_links.find_one(
        {"user_id": user_id}, {"_id": 0, "pat_enc": 1},
    )
    if not row:
        return None
    enc = row.get("pat_enc") or ""
    if not enc:
        return None
    # Try real decrypt first, then fall back to the b64 path used when
    # encryption was unavailable at save time.
    try:
        from services.byok_store import _decrypt as _dec  # type: ignore
        plain = _dec(enc)
        if plain:
            return plain
    except Exception:
        pass
    if enc.startswith("b64:"):
        try:
            return base64.b64decode(enc[4:]).decode("utf-8")
        except Exception:
            return None
    return None


async def _gh_get(token: str, path: str, **params: Any) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{GITHUB_API}{path}", headers=headers, params=params)
    return r


# ── Repos ──────────────────────────────────────────────────────────

@router.get("/repos")
async def list_repos(user=Depends(require_auth)) -> dict[str, Any]:
    uid = user.get("user_id") or user.get("id") or user.get("email")
    token = await _get_user_token(uid) if uid else None
    if not token:
        raise HTTPException(401, "github_not_linked")
    r = await _gh_get(token, "/user/repos",
                      per_page=100, sort="updated", affiliation="owner,collaborator")
    if r.status_code != 200:
        raise HTTPException(r.status_code,
                            f"github_repos_failed: {r.text[:200]}")
    items = []
    for repo in r.json():
        items.append({
            "name":        repo.get("name"),
            "full_name":   repo.get("full_name"),
            "default_branch": repo.get("default_branch"),
            "private":     repo.get("private"),
            "owner":       (repo.get("owner") or {}).get("login"),
            "updated_at":  repo.get("updated_at"),
        })
    return {"items": items, "total": len(items)}


@router.get("/repos/{owner}/{repo}/branches")
async def list_branches(owner: str, repo: str,
                         user=Depends(require_auth)) -> dict[str, Any]:
    uid = user.get("user_id") or user.get("id") or user.get("email")
    token = await _get_user_token(uid) if uid else None
    if not token:
        raise HTTPException(401, "github_not_linked")
    r = await _gh_get(token, f"/repos/{owner}/{repo}/branches", per_page=100)
    if r.status_code != 200:
        raise HTTPException(r.status_code,
                            f"github_branches_failed: {r.text[:200]}")
    items = [{"name": b.get("name"),
              "sha":  (b.get("commit") or {}).get("sha")}
             for b in r.json()]
    return {"items": items, "owner": owner, "repo": repo}


# ── Commit ─────────────────────────────────────────────────────────

class CommitBody(BaseModel):
    owner:      str = Field(..., min_length=1, max_length=80)
    repo:       str = Field(..., min_length=1, max_length=120)
    branch:     str = Field("main", min_length=1, max_length=200)
    project_id: str = Field(..., min_length=1, max_length=80)
    message:    str = Field("Save from AUREM CTO chat", max_length=240)


def _chat_to_markdown(project: dict, chat_history: list[dict]) -> str:
    title = project.get("title") or project.get("name") or project.get("project_id")
    out = [f"# {title}", "",
           f"_Exported from AUREM CTO at {datetime.now(timezone.utc).isoformat()}_",
           "", "---", ""]
    for msg in chat_history or []:
        role = (msg.get("role") or "user").upper()
        content = msg.get("content") or ""
        out.append(f"### {role}")
        out.append("")
        out.append(content)
        out.append("")
    return "\n".join(out)


async def _gh_put_file(token: str, owner: str, repo: str, branch: str,
                        path: str, content_b64: str, message: str,
                        existing_sha: str | None) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body: dict[str, Any] = {
        "message": message, "branch": branch, "content": content_b64,
    }
    if existing_sha:
        body["sha"] = existing_sha
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.put(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            headers=headers, json=body,
        )
    return {"status_code": r.status_code, "body": r.json() if r.text else {}}


async def _gh_existing_sha(token: str, owner: str, repo: str,
                            branch: str, path: str) -> str | None:
    r = await _gh_get(token, f"/repos/{owner}/{repo}/contents/{path}",
                       ref=branch)
    if r.status_code != 200:
        return None
    return (r.json() or {}).get("sha")


@router.post("/commit")
async def commit_project(body: CommitBody,
                         authorization: str = Header(None),
                         user=Depends(require_auth)) -> dict[str, Any]:
    uid = user.get("user_id") or user.get("id") or user.get("email")
    if not uid:
        raise HTTPException(401, "user_unknown")
    token = await _get_user_token(uid)
    if not token:
        raise HTTPException(401, "github_not_linked")
    if _db is None:
        raise HTTPException(503, "db_unavailable")

    # Load project + chat. We're lenient with collection names because
    # the project schema is still in flux this iteration.
    project = await _db.onboarding_projects.find_one(
        {"project_id": body.project_id, "user_id": uid}, {"_id": 0},
    ) or {}
    chat_doc = await _db.dev_cto_chats.find_one(
        {"project_id": body.project_id, "user_id": uid}, {"_id": 0},
    ) or {}
    chat_history = chat_doc.get("messages", [])

    # Build the two artefacts.
    manifest = {
        "project_id":  body.project_id,
        "title":       project.get("title") or project.get("name"),
        "stack":       project.get("stack"),
        "domain":      project.get("domain"),
        "updated_at":  datetime.now(timezone.utc).isoformat(),
        "saved_by":    "aurem-cto",
        "saved_from":  "/developers/chat",
    }
    manifest_b64 = base64.b64encode(
        json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
    ).decode("ascii")
    chat_md_b64  = base64.b64encode(
        _chat_to_markdown(project, chat_history).encode("utf-8"),
    ).decode("ascii")

    path_manifest = f"aurem/{body.project_id}/manifest.json"
    path_chat     = f"aurem/{body.project_id}/aurem-chat.md"

    # Get existing SHAs (so the PUT becomes an update instead of refused).
    sha_man = await _gh_existing_sha(token, body.owner, body.repo,
                                      body.branch, path_manifest)
    sha_chat = await _gh_existing_sha(token, body.owner, body.repo,
                                       body.branch, path_chat)

    r1 = await _gh_put_file(token, body.owner, body.repo, body.branch,
                              path_manifest, manifest_b64, body.message,
                              sha_man)
    if r1["status_code"] not in (200, 201):
        raise HTTPException(r1["status_code"],
                            f"commit_manifest_failed: {r1['body']}")
    r2 = await _gh_put_file(token, body.owner, body.repo, body.branch,
                              path_chat, chat_md_b64,
                              body.message + " (chat history)", sha_chat)
    if r2["status_code"] not in (200, 201):
        raise HTTPException(r2["status_code"],
                            f"commit_chat_failed: {r2['body']}")

    commit_sha = (r2["body"].get("commit") or {}).get("sha") \
              or (r1["body"].get("commit") or {}).get("sha")
    html_url = ((r2["body"].get("commit") or {}).get("html_url")) \
            or ((r1["body"].get("commit") or {}).get("html_url")) \
            or f"https://github.com/{body.owner}/{body.repo}/tree/{body.branch}"

    return {
        "ok":         True,
        "owner":      body.owner,
        "repo":       body.repo,
        "branch":     body.branch,
        "files":      [path_manifest, path_chat],
        "commit_sha": commit_sha,
        "view_url":   html_url,
    }
