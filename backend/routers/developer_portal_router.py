"""
routers/developer_portal_router.py — iter 331d

Tenant-facing + admin endpoints for the Developer Portal foundation:

Tenant:
  POST  /api/developers/signup
  POST  /api/developers/verify-otp
  POST  /api/developers/login
  GET   /api/developers/me
  POST  /api/developers/byok
  POST  /api/developers/pixel-domain
  POST  /api/developers/share/upload-request

Admin:
  GET   /api/admin/developers
  GET   /api/admin/shares
  POST  /api/admin/shares/{request_id}/approve
  POST  /api/admin/shares/{request_id}/reject

Portability: zero Emergent imports. Plain FastAPI + Pydantic.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db
    try:
        from services import developer_portal_core as _D
        _D.set_db(db)
    except Exception:
        pass


def _client_ip(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for", "") or request.client.host or ""
    return (ip.split(",")[0] or "0.0.0.0").strip()


def _hash_password(plain: str) -> str:
    """bcrypt-shaped fallback hash. The platform already has stronger
    auth elsewhere — this is the dev-portal specific hash."""
    try:
        import bcrypt
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    except Exception:
        # Last resort — never log this, never let it ship without bcrypt.
        salt = secrets.token_hex(16)
        return f"sha256${salt}${hashlib.sha256(f'{salt}{plain}'.encode()).hexdigest()}"


def _verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        import bcrypt
        if hashed.startswith("$2"):
            return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        pass
    if hashed.startswith("sha256$"):
        _, salt, want = hashed.split("$", 2)
        return hmac.compare_digest(
            want,
            hashlib.sha256(f"{salt}{plain}".encode()).hexdigest(),
        )
    return False


# ── Tenant: signup + OTP + login ───────────────────────────────────

class SignupBody(BaseModel):
    email: str
    name: str
    password: str = Field(min_length=8)
    github_username: str = ""
    build_intent: str = ""
    referral_code: str = ""


@router.post("/api/developers/signup")
async def signup(body: SignupBody, request: Request) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.developer_portal_core import create_signup
    pw_hash = _hash_password(body.password)
    r = await create_signup(
        email=body.email,
        name=body.name,
        password_hash=pw_hash,
        github_username=body.github_username,
        build_intent=body.build_intent,
        referral_code=body.referral_code,
        ip=_client_ip(request),
    )
    if not r.get("ok"):
        raise HTTPException(400, r.get("message") or r.get("error") or "signup_failed")
    # Don't echo the password hash back
    r.pop("password_hash", None)
    return r


class OtpBody(BaseModel):
    email: str
    otp: str


@router.post("/api/developers/verify-otp")
async def verify_otp_route(body: OtpBody) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.developer_portal_core import verify_otp
    r = await verify_otp(email=body.email, otp=body.otp)
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "verify_failed")
    return r


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/api/developers/login")
async def login(body: LoginBody) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    acc = await _db.developer_accounts.find_one(
        {"email": body.email.strip().lower()},
        {"_id": 0},
    )
    if not acc:
        raise HTTPException(401, "invalid_credentials")
    if not acc.get("email_verified"):
        raise HTTPException(403, "email_not_verified")
    if not _verify_password(body.password, acc.get("password_hash", "")):
        raise HTTPException(401, "invalid_credentials")
    if acc.get("abuse_flagged"):
        raise HTTPException(403, "account_under_review")
    from services.developer_portal_core import issue_jwt
    token = issue_jwt(acc["user_id"], acc["email"])
    return {
        "ok":               True,
        "user_id":          acc["user_id"],
        "email":            acc["email"],
        "tokens_remaining": acc.get("tokens_remaining", 0),
        "jwt":              token,
    }


async def _current_dev(authorization: str | None) -> dict:
    """iter 332b D-5 — admin tokens auto-bootstrap a developer account.

    Founder uses platform_token (admin JWT). When they visit /developers,
    we still want a real developer row for them so the page renders with
    profile, settings, BYOK, etc. — instead of bouncing them to /signup.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    from services.developer_portal_core import (
        decode_dev_jwt, get_account, get_or_create_account_for_admin,
    )

    # First try as a real developer JWT.
    payload = decode_dev_jwt(token)
    if payload and payload.get("kind") == "developer":
        acc = await get_account(payload["sub"])
        if acc and not acc.get("abuse_flagged"):
            return acc
        if acc and acc.get("abuse_flagged"):
            raise HTTPException(403, "account_under_review")

    # Fall back to platform admin JWT — auto-bootstrap a dev row.
    # iter 332b D-6 — the previous import `from utils.auth import _decode_token`
    # silently failed (no such symbol exists in utils.auth), so the admin
    # bypass never actually ran. Switched to a direct jwt.decode against
    # JWT_SECRET / JWT_ALGORITHM so platform admins land on /developers
    # with their existing admin session.
    admin_payload: dict | None = None
    try:
        import jwt as _jwt  # PyJWT
        from config import JWT_SECRET, JWT_ALGORITHM
        admin_payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        admin_payload = None
    if admin_payload and (admin_payload.get("is_admin") or
                            admin_payload.get("is_super_admin")):
        admin_email = (admin_payload.get("email")
                        or admin_payload.get("sub") or "")
        acc = await get_or_create_account_for_admin(admin_email)
        if acc:
            return acc

    raise HTTPException(401, "invalid_or_expired_token")


@router.get("/api/developers/me")
async def me(authorization: str = Header(None)) -> dict[str, Any]:
    return await _current_dev(authorization)


# ── BYOK ───────────────────────────────────────────────────────────

class ByokBody(BaseModel):
    """All keys optional but at least one of the providers must be set.
    iter 332b D-10 — expanded from {anthropic, deepseek, gemini} to the
    full set so the dev portal can support OpenAI, Groq, Mistral, and
    any OpenAI-compatible custom endpoint."""
    anthropic:        str = ""
    openai:           str = ""
    deepseek:         str = ""
    gemini:           str = ""
    groq:             str = ""
    mistral:          str = ""
    custom_url:       str = ""
    custom_model:     str = ""
    custom_api_key:   str = ""


@router.post("/api/developers/byok")
async def byok(body: ByokBody, authorization: str = Header(None)) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.developer_portal_core import save_byok_keys
    r = await save_byok_keys(me["user_id"], body.model_dump())
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "byok_failed")
    return r


# ── AUREM CTO chat (iter 332b D-10) ───────────────────────────────

class ChatMsg(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: list[ChatMsg]
    # iter D-32 — onboarding wiring. Optional so legacy /api/developers/cto/chat
    # callers still work; when project_id is set we debit the wallet and
    # PATCH the project after each turn.
    project_id: str = ""
    model_tier: str = "cheap"  # "cheap" or "frontier"
    # iter D-79 — Plan/Execute toggle. "execute" = current behavior
    # (LLM can emit [[SKILL]] tags that fire real actions). "plan" =
    # LLM is forced into a propose-only mode; we strip + ignore any
    # skill tags so nothing executes server-side. Lets founders draft
    # a change with the agent before letting it run anything.
    mode: str = "execute"


@router.post("/api/developers/cto/chat")
async def cto_chat(body: ChatBody,
                    authorization: str = Header(None)) -> dict[str, Any]:
    """Developer-facing chat. Uses BYOK if configured, otherwise the
    platform's DeepSeek+Groq free tier. Deducts 1 token per reply."""
    account = await _current_dev(authorization)
    from services.dev_cto_chat import cto_chat as _do_chat
    msgs = [m.model_dump() for m in body.messages]
    if not msgs or msgs[-1].get("role") != "user":
        raise HTTPException(400, "last message must be from user")
    r = await _do_chat(account=account, messages=msgs, mode=body.mode)
    if not r.get("ok"):
        return r
    return r


@router.post("/api/developers/cto/chat/stream")
async def cto_chat_stream_route(body: ChatBody,
                                 authorization: str = Header(None)):
    """Streaming counterpart of /chat. Returns text/event-stream of
    JSON events: meta → token (1..n) → done, OR a single error event.
    Frontend can flush tokens to the UI as they arrive — feels 10× faster.

    iter 332b D-15.
    iter 332b D-19 — wraps the generator so we can persist the full
    conversation (user msg + assistant reply) once the stream finishes.
    """
    from fastapi.responses import StreamingResponse
    account = await _current_dev(authorization)
    from services.dev_cto_chat import cto_chat_stream as _stream
    msgs = [m.model_dump() for m in body.messages]
    if not msgs or msgs[-1].get("role") != "user":
        raise HTTPException(400, "last message must be from user")

    user_id = account["user_id"]
    user_msg = msgs[-1]
    captured_reply: list[str] = []
    import json as _json

    # ── iter D-32: debit token wallet BEFORE streaming starts ─────────
    # If a project_id is supplied, this turn is part of the onboarding
    # build flow. We charge cheap=1 / frontier=5 atomically. On HTTP 402
    # we abort the stream with a single error event so the UI can show
    # the paywall instead of replaying the LLM.
    debit_info = None
    if body.project_id:
        from services.onboarding_wallet import debit_for_chat_turn
        debit_info = await debit_for_chat_turn(
            user_id=user_id, project_id=body.project_id,
            model_tier=body.model_tier,
        )
        if not debit_info.get("ok"):
            async def _err_stream():
                evt = {"type": "error", "code": "insufficient_tokens",
                       "balance": debit_info.get("balance", 0),
                       "cost":    debit_info.get("cost", 1)}
                yield f"data: {_json.dumps(evt)}\n\n"
            return StreamingResponse(_err_stream(),
                                      media_type="text/event-stream",
                                      headers={"Cache-Control": "no-cache, no-store",
                                               "X-Accel-Buffering": "no"})

    async def _wrapped():
        async for raw in _stream(account=account, messages=msgs, mode=body.mode):
            # Sniff token deltas so we can rebuild the full assistant reply.
            if raw.startswith("data: "):
                try:
                    evt = _json.loads(raw[6:].strip())
                    if evt.get("type") == "token" and evt.get("content"):
                        captured_reply.append(evt["content"])
                except Exception:
                    pass
            yield raw
        # Stream finished — persist the turn. Best-effort, never raises.
        try:
            reply_text = "".join(captured_reply).strip()
            if reply_text and _db is not None:
                from datetime import datetime, timezone
                await _db.developer_chat_sessions.update_one(
                    {"user_id": user_id, "session_id": "default"},
                    {"$push": {"messages": {
                        "$each": [
                            {"role": "user", "content": user_msg.get("content", "")},
                            {"role": "assistant", "content": reply_text},
                        ]
                    }},
                     "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                     "$setOnInsert": {"user_id": user_id,
                                       "session_id": "default",
                                       "created_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )
            # iter D-32 — derive progress + manifest hints from the reply
            # and PATCH the project doc so the customer sees the bar advance.
            if body.project_id and reply_text:
                try:
                    from services.onboarding_wallet import apply_progress_from_reply
                    await apply_progress_from_reply(
                        user_id=user_id, project_id=body.project_id,
                        reply_text=reply_text,
                    )
                except Exception as _prog_err:
                    logger.warning(f"[cto_chat_stream] progress patch failed: {_prog_err}")
        except Exception as _persist_err:
            logger.warning(f"[cto_chat_stream] persist failed: {_persist_err}")

    return StreamingResponse(
        _wrapped(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",   # tell nginx not to buffer SSE
        },
    )


@router.get("/api/developers/cto/chat/history")
async def cto_chat_history(authorization: str = Header(None)) -> dict[str, Any]:
    """Returns the developer's persisted chat history so refresh/logout
    never wipes a build session. iter 332b D-19."""
    me = await _current_dev(authorization)
    if _db is None:
        return {"messages": []}
    row = await _db.developer_chat_sessions.find_one(
        {"user_id": me["user_id"], "session_id": "default"},
        {"_id": 0, "messages": 1},
    )
    msgs = (row or {}).get("messages") or []
    # Cap to last 200 turns so an extreme history doesn't choke the UI.
    return {"messages": msgs[-200:]}


@router.delete("/api/developers/cto/chat/history")
async def cto_chat_history_clear(authorization: str = Header(None)) -> dict[str, Any]:
    """Founder asked for a "start fresh" button. iter 332b D-19."""
    me = await _current_dev(authorization)
    if _db is None:
        return {"ok": True, "cleared": 0}
    res = await _db.developer_chat_sessions.update_one(
        {"user_id": me["user_id"], "session_id": "default"},
        {"$set": {"messages": [], "updated_at":
                  __import__("datetime").datetime.now(
                      __import__("datetime").timezone.utc).isoformat()}},
    )
    return {"ok": True, "cleared": int(res.modified_count)}


# ── Projects + uploads (iter 332b D-20) ────────────────────────────
#
# Save-as-project flow: when CTO finishes a build the developer clicks
# "Save project" → POSTs title + optional domain. We persist a row that
# *snapshots* the current chat history and a file-attachments list so
# the dev can reopen the build later from the sidebar.
#
# Uploads: chat-attached files are written to /app/data/dev_uploads/
# under the dev's user_id. Served back via /api/developers/cto/uploads/
# {file_id} with ownership check.

from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path

_UPLOAD_ROOT = Path(os.environ.get("DEV_UPLOAD_ROOT", "/app/data/dev_uploads"))
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB / file


class ProjectSaveBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    domain: str | None = Field(default=None, max_length=253)


@router.post("/api/developers/projects")
async def save_project(body: ProjectSaveBody,
                        authorization: str = Header(None)) -> dict[str, Any]:
    """Snapshot the current chat session as a saved project. Domain is
    optional and stored verbatim — no DNS check here, the dev can wire
    it up later from /developers/connect."""
    me = await _current_dev(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")
    session = await _db.developer_chat_sessions.find_one(
        {"user_id": me["user_id"], "session_id": "default"},
        {"_id": 0, "messages": 1},
    )
    messages = (session or {}).get("messages") or []
    project_id = "proj_" + secrets.token_urlsafe(9)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id":      me["user_id"],
        "project_id":   project_id,
        "title":        body.title.strip(),
        "domain":       (body.domain or "").strip() or None,
        "messages":     messages,
        "created_at":   now,
        "updated_at":   now,
    }
    await _db.developer_projects.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "project": doc}


@router.get("/api/developers/projects")
async def list_projects(authorization: str = Header(None)) -> dict[str, Any]:
    """List the dev's saved projects, newest first. iter 332b D-20."""
    me = await _current_dev(authorization)
    if _db is None:
        return {"projects": []}
    cursor = _db.developer_projects.find(
        {"user_id": me["user_id"]},
        {"_id": 0, "project_id": 1, "title": 1, "domain": 1,
         "created_at": 1, "updated_at": 1},
    ).sort("created_at", -1).limit(50)
    rows = await cursor.to_list(length=50)
    return {"projects": rows}


@router.get("/api/developers/projects/{project_id}")
async def load_project(project_id: str,
                        authorization: str = Header(None)) -> dict[str, Any]:
    """Load one project (with full message history). Click-to-resume in
    the sidebar uses this. Ownership-checked: a dev can only load their
    own projects. iter 332b D-20."""
    me = await _current_dev(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")
    row = await _db.developer_projects.find_one(
        {"user_id": me["user_id"], "project_id": project_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "project_not_found")
    return row


@router.delete("/api/developers/projects/{project_id}")
async def delete_project(project_id: str,
                          authorization: str = Header(None)) -> dict[str, Any]:
    me = await _current_dev(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")
    res = await _db.developer_projects.delete_one(
        {"user_id": me["user_id"], "project_id": project_id},
    )
    if res.deleted_count == 0:
        raise HTTPException(404, "project_not_found")
    return {"ok": True}


@router.post("/api/developers/cto/uploads")
async def upload_attachment(
    file: UploadFile = File(...),
    authorization: str = Header(None),
) -> dict[str, Any]:
    """Chat attachment upload. Stores under /app/data/dev_uploads/{user_id}/.
    25 MB hard cap. Returns a stable URL the chat can render inline.
    iter 332b D-20."""
    me = await _current_dev(authorization)
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty_file")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file_too_large_25mb")
    file_id = secrets.token_urlsafe(12)
    user_dir = _UPLOAD_ROOT / me["user_id"]
    user_dir.mkdir(parents=True, exist_ok=True)
    # Preserve the file extension so the browser sniffs the right MIME.
    suffix = Path(file.filename or "").suffix[:16]
    disk_path = user_dir / f"{file_id}{suffix}"
    disk_path.write_bytes(raw)
    meta = {
        "user_id":      me["user_id"],
        "file_id":      file_id,
        "filename":     file.filename or "upload",
        "mime":         file.content_type or "application/octet-stream",
        "size":         len(raw),
        "path":         str(disk_path),
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }
    if _db is not None:
        await _db.developer_uploads.insert_one(dict(meta))
    return {
        "ok":       True,
        "file_id":  file_id,
        "filename": meta["filename"],
        "mime":     meta["mime"],
        "size":     meta["size"],
        "url":      f"/api/developers/cto/uploads/{file_id}",
    }


@router.get("/api/developers/cto/uploads/{file_id}")
async def get_upload(file_id: str,
                      authorization: str = Header(None)):
    """Authenticated download. A dev can only fetch files they
    uploaded. iter 332b D-20."""
    me = await _current_dev(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")
    row = await _db.developer_uploads.find_one(
        {"user_id": me["user_id"], "file_id": file_id},
        {"_id": 0, "path": 1, "mime": 1, "filename": 1},
    )
    if not row:
        raise HTTPException(404, "upload_not_found")
    disk = Path(row["path"])
    if not disk.exists():
        raise HTTPException(410, "upload_purged")
    return FileResponse(
        path=str(disk),
        media_type=row.get("mime") or "application/octet-stream",
        filename=row.get("filename") or file_id,
    )


# ── Pixel domain validation ────────────────────────────────────────


# ── GitHub PAT link / unlink / me  (iter 332b D-30) ─────────────────
#
# Why PAT not OAuth: OAuth requires a callback URL + client_id/secret
# rotation. PAT works the moment the dev pastes it.
# The token is stored AES-encrypted via the SAME fernet path the BYOK
# keys use (see services.byok_store) so we never log/return plaintext.

class GitHubLinkBody(BaseModel):
    pat: str = Field(..., min_length=20, max_length=200)


@router.get("/api/developers/github/me")
async def github_me(authorization: str = Header(None)) -> dict[str, Any]:
    """Returns {login, avatar, repos_count} if the dev has linked
    GitHub, or 404 if not. Iter 332b D-30."""
    me = await _current_dev(authorization)
    if _db is None:
        raise HTTPException(404, "not_linked")
    row = await _db.developer_github_links.find_one(
        {"user_id": me["user_id"]},
        {"_id": 0, "login": 1, "avatar_url": 1, "repos_count": 1,
         "linked_at": 1},
    )
    if not row:
        raise HTTPException(404, "not_linked")
    return {
        "login":       row.get("login"),
        "avatar":      row.get("avatar_url"),
        "repos_count": row.get("repos_count", 0),
        "linked_at":   row.get("linked_at"),
    }


@router.post("/api/developers/github/link")
async def github_link(body: GitHubLinkBody,
                       authorization: str = Header(None)) -> dict[str, Any]:
    """Validate the PAT against api.github.com/user, then encrypt & store.
    Returns the same shape as GET /github/me on success."""
    me = await _current_dev(authorization)
    pat = body.pat.strip()
    if not (pat.startswith("github_pat_") or pat.startswith("ghp_")):
        raise HTTPException(400, "bad_token_format")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("https://api.github.com/user",
                             headers={"Authorization": f"Bearer {pat}",
                                      "Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                raise HTTPException(401, "github_rejected_token")
            user = r.json()
            r2 = await c.get("https://api.github.com/user/repos?per_page=1",
                              headers={"Authorization": f"Bearer {pat}"})
            # Repos count comes from the user record (public_repos only).
            # The /user/repos probe just confirms the scope grants access.
            if r2.status_code >= 400:
                raise HTTPException(403, "github_repo_scope_missing")
            repos_count = int(user.get("public_repos", 0))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[github-link] probe failed: {e}")
        raise HTTPException(502, "github_unreachable")

    # Encrypt the PAT using the BYOK fernet helper (reuse — keeps key
    # rotation centralized). Falls back to a base64 wrap if the helper
    # isn't available (dev mode).
    try:
        from services.byok_store import _encrypt as _enc
        ct = _enc(pat)
    except Exception:
        import base64 as _b64
        ct = "b64:" + _b64.b64encode(pat.encode()).decode()

    if _db is not None:
        await _db.developer_github_links.update_one(
            {"user_id": me["user_id"]},
            {"$set": {
                "user_id":     me["user_id"],
                "pat_enc":     ct,
                "login":       user.get("login"),
                "avatar_url":  user.get("avatar_url"),
                "repos_count": repos_count,
                "linked_at":   datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    return {
        "login":       user.get("login"),
        "avatar":      user.get("avatar_url"),
        "repos_count": repos_count,
        "linked_at":   datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/api/developers/github/link")
async def github_unlink(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _current_dev(authorization)
    if _db is None:
        return {"ok": True}
    await _db.developer_github_links.delete_one({"user_id": me["user_id"]})
    return {"ok": True}


# ── GitHub OAuth (one-click connect)  (iter D-42) ────────────────────
#
# Replaces the manual PAT paste with a popup-based OAuth 2.0
# authorization-code flow. Token still lands in the SAME
# `developer_github_links` collection used by the PAT path so the
# codebase indexer + deploy pipeline keep working without changes.
#
# Required env vars (set in /admin/integrations or .env):
#   GITHUB_CLIENT_ID
#   GITHUB_CLIENT_SECRET
#   GITHUB_OAUTH_REDIRECT_URI   (optional — defaults to
#                                {request.base_url}api/developers/github/oauth/callback)
#
# Flow:
#   1. Frontend (logged-in dev) calls GET /github/oauth/start.
#      We mint a CSRF `state` + PKCE verifier, store them tied to the
#      AUREM user_id in `developer_github_oauth_states` (TTL 10min),
#      and return {auth_url}.
#   2. Frontend opens auth_url in a popup. GitHub redirects back to
#      /github/oauth/callback?code=…&state=… (NO Authorization header
#      — the popup is a top-level GET).
#   3. Callback validates state, exchanges code for access_token,
#      fetches /user, upserts into developer_github_links, returns
#      a tiny HTML page that postMessage's the parent window and
#      closes itself.

import base64 as _b64
import hashlib as _hashlib
from urllib.parse import urlencode as _urlencode

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL     = "https://github.com/login/oauth/access_token"
_GITHUB_USER_API      = "https://api.github.com/user"


def _gh_oauth_env() -> dict[str, str | None]:
    return {
        "client_id":     os.environ.get("GITHUB_CLIENT_ID", "").strip() or None,
        "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", "").strip() or None,
        "redirect_uri":  os.environ.get("GITHUB_OAUTH_REDIRECT_URI", "").strip() or None,
    }


def _gh_pkce_pair() -> tuple[str, str]:
    """Returns (verifier, S256-challenge) per RFC 7636. GitHub only
    accepts S256."""
    verifier = secrets.token_urlsafe(64)
    digest = _hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _b64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _gh_resolve_redirect(request: Request) -> str:
    env = _gh_oauth_env()["redirect_uri"]
    if env:
        return env
    # Fall back to request base URL — works in preview and prod.
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/developers/github/oauth/callback"


@router.get("/api/developers/github/oauth/start")
async def github_oauth_start(request: Request,
                              authorization: str = Header(None)) -> dict[str, Any]:
    """Mint state + PKCE, persist them, return the authorize URL the
    frontend should open in a popup."""
    me = await _current_dev(authorization)
    env = _gh_oauth_env()
    if not env["client_id"] or not env["client_secret"]:
        raise HTTPException(
            503,
            "github_oauth_not_configured: set GITHUB_CLIENT_ID + "
            "GITHUB_CLIENT_SECRET in admin integrations.",
        )

    state = secrets.token_urlsafe(32)
    verifier, challenge = _gh_pkce_pair()
    redirect_uri = _gh_resolve_redirect(request)

    if _db is not None:
        await _db.developer_github_oauth_states.insert_one({
            "state":        state,
            "code_verifier": verifier,
            "user_id":      me["user_id"],
            "redirect_uri": redirect_uri,
            "created_at":   datetime.now(timezone.utc),
        })

    params = {
        "client_id":              env["client_id"],
        "redirect_uri":           redirect_uri,
        "state":                  state,
        "scope":                  "repo read:user",
        "allow_signup":           "true",
        "code_challenge_method":  "S256",
        "code_challenge":         challenge,
    }
    return {"auth_url": f"{_GITHUB_AUTHORIZE_URL}?{_urlencode(params)}"}


def _gh_popup_html(*, status: str, message: str,
                     login: str = "", target_origin: str = "*") -> str:
    """Tiny HTML page that postMessage's the opener and self-closes.

    We deliberately use targetOrigin="*" by default ONLY when we cannot
    know the SPA origin (callback hits API origin which may differ from
    frontend). The frontend listener still verifies `event.origin`
    against its own backend origin AND the payload's `source` field, so
    this is safe."""
    import json as _json
    payload = _json.dumps({
        "source": "aurem-github-oauth",
        "status": status,
        "message": message,
        "login":  login,
    })
    safe_msg = message.replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html><html><head>
<title>GitHub connected</title>
<style>body{{font:14px/1.5 system-ui;color:#1f2937;padding:32px;max-width:480px;margin:auto}}</style>
</head><body>
<h3>{'GitHub connected' if status == 'success' else 'GitHub connection failed'}</h3>
<p>{safe_msg}</p>
<p style="color:#6b7280">You can close this window.</p>
<script>
(function(){{
  try {{
    if (window.opener && window.opener !== window) {{
      window.opener.postMessage({payload!s}, "{target_origin}");
    }}
  }} catch(e){{}}
  setTimeout(function(){{ try{{ window.close(); }}catch(e){{}} }}, 800);
}})();
</script>
</body></html>"""


@router.get("/api/developers/github/oauth/callback")
async def github_oauth_callback(request: Request,
                                  code: str | None = None,
                                  state: str | None = None,
                                  error: str | None = None,
                                  error_description: str | None = None):
    """GitHub redirects the popup here. We exchange code → token,
    fetch /user, upsert into developer_github_links, and return a
    self-closing HTML page that postMessage's the opener."""
    from fastapi.responses import HTMLResponse
    env = _gh_oauth_env()

    # Surface explicit GitHub errors first (user clicked Cancel, etc).
    if error:
        msg = error_description or error
        return HTMLResponse(_gh_popup_html(status="error", message=f"GitHub: {msg}"))

    if not code or not state:
        return HTMLResponse(_gh_popup_html(
            status="error", message="Missing code or state in callback."))

    if not env["client_id"] or not env["client_secret"]:
        return HTMLResponse(_gh_popup_html(
            status="error",
            message="OAuth credentials not configured on the server."))

    # Look up the state we minted in /start. One-time use → delete on read.
    state_doc = None
    if _db is not None:
        state_doc = await _db.developer_github_oauth_states.find_one(
            {"state": state})
        if state_doc:
            await _db.developer_github_oauth_states.delete_one(
                {"_id": state_doc["_id"]})

    if not state_doc:
        return HTMLResponse(_gh_popup_html(
            status="error",
            message="Invalid or expired state — please try again."))

    # Reject states older than 10 minutes (replay-attack window).
    created = state_doc.get("created_at")
    if created and (datetime.now(timezone.utc) - created).total_seconds() > 600:
        return HTMLResponse(_gh_popup_html(
            status="error", message="OAuth session expired — please try again."))

    user_id      = state_doc["user_id"]
    verifier     = state_doc["code_verifier"]
    redirect_uri = state_doc.get("redirect_uri") or _gh_resolve_redirect(request)

    # Exchange code for access token.
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=10.0) as c:
            tok_r = await c.post(
                _GITHUB_TOKEN_URL,
                data={
                    "client_id":     env["client_id"],
                    "client_secret": env["client_secret"],
                    "code":          code,
                    "redirect_uri":  redirect_uri,
                    "code_verifier": verifier,
                },
                headers={"Accept": "application/json"},
            )
        if tok_r.status_code != 200:
            return HTMLResponse(_gh_popup_html(
                status="error",
                message=f"GitHub token exchange failed (HTTP {tok_r.status_code})."))
        tok = tok_r.json()
        access_token = tok.get("access_token")
        scope_str    = tok.get("scope", "")
        if not access_token:
            err = tok.get("error_description") or tok.get("error") or "no_access_token"
            return HTMLResponse(_gh_popup_html(
                status="error", message=f"GitHub: {err}"))

        # Fetch user profile to confirm token + capture login/avatar.
        async with _httpx.AsyncClient(timeout=10.0) as c:
            usr_r = await c.get(
                _GITHUB_USER_API,
                headers={"Authorization": f"Bearer {access_token}",
                         "Accept": "application/vnd.github+json"})
        if usr_r.status_code != 200:
            return HTMLResponse(_gh_popup_html(
                status="error",
                message=f"GitHub /user fetch failed (HTTP {usr_r.status_code})."))
        user = usr_r.json()
    except Exception as e:
        logger.warning(f"[github-oauth] callback http error: {e}")
        return HTMLResponse(_gh_popup_html(
            status="error", message="GitHub unreachable — please try again."))

    # Encrypt + store in the SAME collection used by the PAT path so
    # codebase indexer + deploy keep working unchanged.
    try:
        from services.byok_store import _encrypt as _enc
        ct = _enc(access_token)
    except Exception:
        ct = "b64:" + _b64.b64encode(access_token.encode()).decode()

    repos_count = int(user.get("public_repos", 0))
    if _db is not None:
        await _db.developer_github_links.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id":     user_id,
                "pat_enc":     ct,
                "login":       user.get("login"),
                "avatar_url":  user.get("avatar_url"),
                "repos_count": repos_count,
                "scope":       scope_str,
                "auth_method": "oauth",
                "linked_at":   datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    return HTMLResponse(_gh_popup_html(
        status="success",
        message=f"Connected as @{user.get('login') or 'github-user'}.",
        login=user.get("login") or "",
    ))


# ── Pixel domain validation (legacy section) ──────────────────────

class PixelDomainBody(BaseModel):
    domain: str


@router.post("/api/developers/pixel-domain")
async def pixel_domain(
    body: PixelDomainBody,
    authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.developer_portal_core import validate_pixel_domain
    v = validate_pixel_domain(body.domain)
    if not v["ok"]:
        raise HTTPException(400, v.get("message") or v.get("reason"))
    if _db is not None:
        await _db.developer_accounts.update_one(
            {"user_id": me["user_id"]},
            {"$set": {"pixel_domain": v["domain"]}},
        )
    return {"ok": True, "domain": v["domain"]}


# ── Screenshot share request ───────────────────────────────────────

class ShareUploadBody(BaseModel):
    screenshot_url: str
    platform: str = ""   # twitter | linkedin | other
    note: str = ""


@router.post("/api/developers/share/upload-request")
async def share_upload(
    body: ShareUploadBody,
    authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    if not body.screenshot_url or not body.screenshot_url.startswith("http"):
        raise HTTPException(400, "screenshot_url must be a public URL")
    if _db is None:
        raise HTTPException(503, "db not ready")
    import uuid as _uuid
    req_id = _uuid.uuid4().hex[:16]
    await _db.developer_share_requests.insert_one({
        "request_id":     req_id,
        "user_id":        me["user_id"],
        "screenshot_url": body.screenshot_url,
        "platform":       body.platform or "other",
        "note":           body.note[:500] if body.note else "",
        "status":         "pending",
        "submitted_at":   datetime.now(timezone.utc).isoformat(),
        "reviewed_at":    None,
        "tokens_awarded": 0,
    })
    return {
        "ok":         True,
        "request_id": req_id,
        "status":     "pending",
        "message":    "Submitted for review. We'll add 2500 tokens within 24 hours of approval.",
    }


# ── Admin endpoints ────────────────────────────────────────────────

def _ensure_admin(request: Request) -> None:
    try:
        from routers.admin_ora_router import _ensure_admin as _outer
    except Exception as e:
        raise HTTPException(503, f"admin gate unavailable: {e}")
    # Let HTTPException (401/403) bubble up untouched — don't mask
    # auth failures behind a generic 503.
    return _outer(request)


@router.get("/api/admin/developers")
async def admin_developers_list(
    request: Request, limit: int = 50,
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cursor = _db.developer_accounts.find(
        {},
        {"_id": 0, "password_hash": 0, "byok_keys": 0,
         "signup_ip": 0},
        sort=[("created_at", -1)],
        limit=max(1, min(int(limit), 500)),
    )
    rows = await cursor.to_list(length=500)
    flagged = await _db.developer_accounts.count_documents({"abuse_flagged": True})
    total = await _db.developer_accounts.estimated_document_count()
    return {"ok": True, "total": total, "flagged": flagged, "rows": rows}


# iter 332b D-8 — 24h sparkline + CSV export.

@router.get("/api/admin/developers/timeseries")
async def admin_developers_timeseries(request: Request) -> dict[str, Any]:
    """24 hourly buckets of new dev signups (oldest first)."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    cursor = _db.developer_accounts.find(
        {"created_at": {"$gte": cutoff}},
        {"_id": 0, "created_at": 1},
    )
    buckets = [0] * 24
    total_24h = 0
    async for d in cursor:
        ts = d.get("created_at") or ""
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            hours_ago = int((now - t).total_seconds() // 3600)
            if 0 <= hours_ago < 24:
                buckets[23 - hours_ago] += 1
                total_24h += 1
        except Exception:
            continue
    return {"ok": True, "buckets": buckets, "total_24h": total_24h,
            "generated_at": now.isoformat()}


@router.get("/api/admin/developers/export.csv")
async def admin_developers_export_csv(request: Request):
    """Stream every signup as CSV. Same projection as the list endpoint
    so secrets never leak."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    import csv
    import io
    from fastapi.responses import StreamingResponse
    cursor = _db.developer_accounts.find(
        {},
        {"_id": 0, "email": 1, "name": 1, "plan": 1,
         "email_verified": 1, "github_username": 1,
         "tokens_remaining": 1, "tokens_total_used": 1,
         "abuse_flagged": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "name", "plan", "verified", "github",
                "tokens_remaining", "tokens_used", "abuse_flagged",
                "signed_up"])
    async for r in cursor:
        w.writerow([
            r.get("email", ""), r.get("name", ""), r.get("plan", ""),
            "yes" if r.get("email_verified") else "no",
            r.get("github_username", ""),
            r.get("tokens_remaining", 0), r.get("tokens_total_used", 0),
            "yes" if r.get("abuse_flagged") else "no",
            (r.get("created_at") or "")[:10],
        ])
    buf.seek(0)
    fname = f"aurem-developer-signups-{datetime.now(timezone.utc).date()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/admin/shares")
async def admin_shares_list(
    request: Request, status: str = "pending",
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cursor = _db.developer_share_requests.find(
        {"status": status},
        {"_id": 0},
        sort=[("submitted_at", -1)],
        limit=200,
    )
    rows = await cursor.to_list(length=200)
    return {"ok": True, "status": status, "count": len(rows), "rows": rows}


@router.post("/api/admin/shares/{request_id}/approve")
async def admin_share_approve(request_id: str, request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    req = await _db.developer_share_requests.find_one(
        {"request_id": request_id}, {"_id": 0},
    )
    if not req:
        raise HTTPException(404, "share_request_not_found")
    if req.get("status") != "pending":
        raise HTTPException(400, f"already_{req['status']}")
    from services.developer_portal_core import SHARE_REWARD_TOKENS
    # Award tokens
    await _db.developer_accounts.update_one(
        {"user_id": req["user_id"]},
        {"$inc": {"tokens_remaining": SHARE_REWARD_TOKENS}},
    )
    await _db.developer_share_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": "approved",
                   "reviewed_at": datetime.now(timezone.utc).isoformat(),
                   "tokens_awarded": SHARE_REWARD_TOKENS}},
    )
    return {"ok": True, "request_id": request_id,
             "tokens_awarded": SHARE_REWARD_TOKENS}


@router.post("/api/admin/shares/{request_id}/reject")
async def admin_share_reject(
    request_id: str,
    request: Request,
    reason: str = "",
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    r = await _db.developer_share_requests.update_one(
        {"request_id": request_id, "status": "pending"},
        {"$set": {"status": "rejected",
                   "reviewed_at": datetime.now(timezone.utc).isoformat(),
                   "rejection_reason": (reason or "")[:200]}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "share_request_not_pending")
    return {"ok": True, "request_id": request_id, "status": "rejected"}


# ── iter 331e — Concurrent session control + email-seq admin trigger ─

class SessionAcquireBody(BaseModel):
    session_id: str


@router.post("/api/developers/session/acquire")
async def acquire_session_route(
    body: SessionAcquireBody, authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.dev_security_guards import acquire_session
    r = await acquire_session(me["user_id"], body.session_id)
    if not r.get("ok"):
        raise HTTPException(
            429,
            r.get("message") or r.get("reason") or "too_many_sessions",
        )
    return r


@router.post("/api/developers/session/release")
async def release_session_route(
    body: SessionAcquireBody, authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.dev_security_guards import release_session
    return await release_session(me["user_id"], body.session_id)


@router.get("/api/developers/sessions")
async def list_sessions_route(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.dev_security_guards import (
        list_active_sessions, MAX_ACTIVE_SESSIONS,
    )
    rows = await list_active_sessions(me["user_id"])
    return {"ok": True, "active": rows, "limit": MAX_ACTIVE_SESSIONS}


@router.post("/api/admin/developers/email-sequence/run")
async def admin_run_email_sequence(request: Request) -> dict[str, Any]:
    """Founder-triggered run of the Day 3 / 7 / 25 email cron."""
    _ensure_admin(request)
    from services.developer_email_sequence import (
        run_sequence_tick, set_db as _set_seq_db,
    )
    if _db is not None:
        _set_seq_db(_db)
    return await run_sequence_tick()


@router.get("/api/admin/developers/health")
async def admin_developers_health(request: Request) -> dict[str, Any]:
    """iter 331f — Developer Portal pulse for the ORA Cockpit tile."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    now = _dt.now(_tz.utc)
    day_start = (now - _td(hours=24)).isoformat()

    total_devs = await _db.developer_accounts.estimated_document_count()
    verified = await _db.developer_accounts.count_documents({"email_verified": True})
    abuse_flagged = await _db.developer_accounts.count_documents({"abuse_flagged": True})

    # Aggregate active sessions across all accounts (sum of array lengths)
    pipe = [
        {"$project": {
            "_id": 0,
            "n": {"$size": {"$ifNull": ["$active_sessions", []]}},
        }},
        {"$group": {"_id": None, "total": {"$sum": "$n"}}},
    ]
    active_sessions = 0
    try:
        agg = await _db.developer_accounts.aggregate(pipe).to_list(length=1)
        if agg:
            active_sessions = int(agg[0].get("total") or 0)
    except Exception:
        pass

    # Token balances
    tokens_pipe = [
        {"$group": {
            "_id": None,
            "remaining": {"$sum": "$tokens_remaining"},
            "used":      {"$sum": "$tokens_total_used"},
        }},
    ]
    tokens_remaining_total = 0
    tokens_used_total = 0
    try:
        agg2 = await _db.developer_accounts.aggregate(tokens_pipe).to_list(length=1)
        if agg2:
            tokens_remaining_total = int(agg2[0].get("remaining") or 0)
            tokens_used_total = int(agg2[0].get("used") or 0)
    except Exception:
        pass

    # 24-h block counters from audit log + abuse table
    ssrf_blocks_today = await _db.ora_tool_audit.count_documents({
        "ts": {"$gte": day_start},
        "result.blocked_by": "ssrf_guard",
    }) if "ora_tool_audit" in await _db.list_collection_names() else 0

    sessions_refused_today = await _db.ora_tool_audit.count_documents({
        "ts": {"$gte": day_start},
        "result.reason": "too_many_sessions",
    }) if "ora_tool_audit" in await _db.list_collection_names() else 0

    abuse_blocks_today = await _db.developer_abuse_flags.count_documents({
        "timestamp": {"$gte": day_start},
    })

    # Email sequence 24h
    emails_sent_today = await _db.developer_email_sequence_log.count_documents({
        "ts": {"$gte": day_start},
    })

    # Token deductions 24h
    token_calls_today = await _db.developer_tokens.count_documents({
        "timestamp": {"$gte": day_start},
    })

    # Status classification
    if abuse_blocks_today >= 3 or ssrf_blocks_today >= 10:
        status = "red"
    elif abuse_blocks_today >= 1 or ssrf_blocks_today >= 1 or sessions_refused_today >= 5:
        status = "yellow"
    else:
        status = "green"

    return {
        "ok": True,
        "status": status,
        "developers": {
            "total":         total_devs,
            "verified":      verified,
            "abuse_flagged": abuse_flagged,
        },
        "sessions": {
            "active_total":      active_sessions,
            "refused_today":     sessions_refused_today,
        },
        "tokens": {
            "remaining_total": tokens_remaining_total,
            "used_total":      tokens_used_total,
            "calls_today":     token_calls_today,
        },
        "blocks_today": {
            "ssrf":      ssrf_blocks_today,
            "abuse":     abuse_blocks_today,
            "sessions":  sessions_refused_today,
        },
        "emails_sent_today": emails_sent_today,
        "generated_at": now.isoformat(),
    }


@router.get("/api/developers/me/purchases")
async def developers_me_purchases(
    authorization: str = Header(None),
) -> dict[str, Any]:
    """iter 331g — last N receipts for the dashboard 'Recent purchases' strip."""
    me = await _current_dev(authorization)
    if _db is None:
        return {"ok": True, "rows": []}
    cursor = _db.payment_transactions.find(
        {"user_id": me["user_id"]},
        {"_id": 0, "session_id": 1, "tier": 1, "amount_usd": 1,
         "payment_status": 1, "credited": 1, "created_at": 1},
    ).sort("created_at", -1).limit(3)
    rows = await cursor.to_list(length=3)
    return {"ok": True, "rows": rows}


@router.get("/api/developers/openapi.json", include_in_schema=False)
async def developers_openapi(request: Request) -> dict[str, Any]:
    """Filtered OpenAPI schema for the Swagger UI page. Builds against
    THIS router's routes only — bypasses the rest of the codebase
    (which has at least one route without a response class that breaks
    the global schema). Adds a `BearerAuth` security scheme.
    """
    from fastapi.openapi.utils import get_openapi
    try:
        full = get_openapi(
            title="AUREM CTO — Developer Portal API",
            version="1.0",
            description=(
                "REST endpoints available to developer-portal tenants. "
                "Authenticate with the JWT you receive from "
                "`POST /api/developers/verify-otp` and paste it into "
                "the Authorize dialog above."
            ),
            routes=router.routes,
        )
    except Exception as e:
        logger.warning(f"[dev-openapi] schema build failed: {e}")
        full = {"openapi": "3.0.0",
                "info": {"title": "AUREM CTO — Developer Portal API",
                          "version": "1.0"},
                "paths": {}, "components": {}}

    paths = {
        k: v for k, v in (full.get("paths") or {}).items()
        if k.startswith("/api/developers/")
        and not k.startswith("/api/developers/openapi")
        and not k.startswith("/api/admin/")
    }
    return {
        "openapi": full.get("openapi", "3.0.0"),
        "info":    full.get("info", {
            "title":   "AUREM CTO — Developer Portal API",
            "version": "1.0",
        }),
        "paths":   paths,
        "components": {
            **(full.get("components") or {}),
            "securitySchemes": {
                "BearerAuth": {
                    "type":   "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": (
                        "Paste the JWT returned by /api/developers/verify-otp."
                    ),
                },
            },
        },
        "security": [{"BearerAuth": []}],
    }



# ── iter 331g — Public landing-page count + Stripe Batch C ──

@router.get("/api/developers/public/stats")
async def developers_public_stats() -> dict[str, Any]:
    """Public count for the landing-page beta ticker. NO auth."""
    if _db is None:
        return {"verified_developers": 0}
    n = await _db.developer_accounts.count_documents({"email_verified": True})
    return {"verified_developers": int(n)}


@router.get("/api/developers/packages")
async def developers_packages() -> dict[str, Any]:
    """Public — packages with prices. Used by /developers/tokens."""
    from services.developer_stripe import package_table
    return {"ok": True, "packages": package_table()}


class CheckoutStartBody(BaseModel):
    tier: str
    origin_url: str


@router.post("/api/developers/checkout/start")
async def developers_checkout_start(
    body: CheckoutStartBody,
    authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.developer_stripe import start_checkout, set_db as _set_pay_db
    if _db is not None:
        _set_pay_db(_db)
    r = await start_checkout(
        user_id=me["user_id"], email=me["email"],
        tier=body.tier, origin_url=body.origin_url,
    )
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "checkout_failed")
    return r


@router.get("/api/developers/checkout/status/{session_id}")
async def developers_checkout_status(
    session_id: str,
    authorization: str = Header(None),
) -> dict[str, Any]:
    await _current_dev(authorization)
    from services.developer_stripe import get_status, set_db as _set_pay_db
    if _db is not None:
        _set_pay_db(_db)
    return await get_status(session_id)


@router.post("/api/webhook/stripe", include_in_schema=False)
async def stripe_webhook(request: Request) -> dict[str, Any]:
    """Stripe webhook — verifies the signature, dedupes on event.id,
    routes the event to the credit/grace handlers."""
    from services.developer_stripe import process_webhook_event, set_db as _set_pay_db
    if _db is not None:
        _set_pay_db(_db)
    raw_body = await request.body()
    signature = request.headers.get("Stripe-Signature") or ""

    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or ""
        webhook_url = (
            (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
            + "/api/webhook/stripe"
        )
        client = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
        webhook_resp = await client.handle_webhook(raw_body, signature)
    except Exception as e:
        logger.warning(f"[dev-stripe] webhook signature/parse failed: {e}")
        raise HTTPException(400, "invalid_signature")

    event_id   = webhook_resp.event_id or ""
    event_type = webhook_resp.event_type or ""
    session_id = webhook_resp.session_id
    raw_event  = getattr(webhook_resp, "raw_event", None) or {}

    if not event_id:
        # No id means we cannot dedupe — refuse rather than risk
        # double-credit on retry.
        return {"ok": False, "reason": "no_event_id"}

    return await process_webhook_event(
        event_id=event_id, event_type=event_type,
        session_id=session_id, raw_event=raw_event if isinstance(raw_event, dict) else None,
    )

