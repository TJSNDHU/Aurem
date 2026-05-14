"""
Security Patterns Router
========================
Read-only access to the AUREM-SEC-PATTERNS-V1 playbook from the live
broadcast collection, plus a `/scan` endpoint that runs every detect
regex against a given file path and returns the matches.

Mounted at /api/admin/security-patterns. Admin-gated.
"""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/sec-patterns",
    tags=["security-patterns"],
)


# ── Admin gate ────────────────────────────────────────────────────────
def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    import jwt as _jwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    from utils.admin_guard import is_admin_email
    if not (payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin")
            or is_admin_email(payload.get("email"))):
        raise HTTPException(403, "Admin access required")
    return payload


# ── DB accessor ──────────────────────────────────────────────────────
_db = None


def set_db(db):
    global _db
    _db = db


# ── Pattern catalog (mirrors /app/memory/SECURITY_PATTERNS.md) ───────
# Format: id, name, detect regex (Python multiline), severity.
PATTERNS: List[Dict] = [
    {"id": "PAT-01", "name": "bare-decode admin gate", "severity": "critical",
     "regex": r"def\s+_?verify_admin[\s\S]{0,300}?return\s+payload",
     "anti_match": r"is_admin",
     "hint": "Add `is_admin/is_super_admin/role` check before returning payload."},
    {"id": "PAT-02", "name": "empty-string JWT_SECRET fallback", "severity": "critical",
     "regex": r"""JWT_SECRET["'],\s*["']["']""",
     "hint": "Drop the empty fallback; raise 500 when env var missing."},
    {"id": "PAT-04", "name": "hardcoded credential default", "severity": "critical",
     "regex": r"""os\.environ\.get\(["'][A-Z_]*(PASSWORD|KEY|SECRET|TOKEN)["'],\s*["'][^"']{6,}["']\)""",
     "hint": "Strict-require the env var; do not commit defaults."},
    {"id": "PAT-05", "name": "email claim grants admin", "severity": "critical",
     "regex": r"""or\s+payload\.get\(["']email["']\)""",
     "hint": "Use is_admin_email() helper, not raw `email` truthiness."},
    {"id": "PAT-06", "name": "client-side JWT atob for routing", "severity": "high",
     "regex": r"""atob\(\s*\w+\.split\(['"]\.['"]\)\[1\]""",
     "hint": "Navigate based on server response, not local JWT decode."},
    {"id": "PAT-08", "name": "open redirect", "severity": "critical",
     "regex": r"""RedirectResponse\([^)]*(redirect_url|state_data\[)""",
     "anti_match": r"_safe_redirect|ALLOWLIST",
     "hint": "Allowlist redirect origins."},
    {"id": "PAT-09", "name": "XSS via document.write", "severity": "critical",
     "regex": r"""\.document\.write\([\s\S]{0,500}\$\{[^}]*(topic|title|name|message)\b""",
     "anti_match": r"safeTitle|_esc\(",
     "hint": "HTML-escape interpolated values."},
    {"id": "PAT-10", "name": "webhook sig short-circuit", "severity": "critical",
     "regex": r"""if\s+os\.environ\.get\(["'][^"']+_API_KEY["']\)\s+and\s+sig\s+and\s+not\s+_verify""",
     "hint": "Reject missing-sig and invalid-sig separately."},
    {"id": "PAT-12", "name": "plaintext password reset token in Mongo", "severity": "critical",
     "regex": r"""password_resets[\s\S]{0,200}\$set[\s\S]{0,80}["']token["']:\s*\w""",
     "anti_match": r"token_hash",
     "hint": "Store sha256 hash, lookup by hash."},
    {"id": "PAT-14", "name": "encryption key default fallback", "severity": "critical",
     "regex": r"""ENCRYPTION_KEY\s*=\s*os\.environ\.get\([^,]+,\s*["'][^"']{8,}["']\)""",
     "hint": "Strict-require AUREM_ENCRYPTION_KEY."},
    {"id": "PAT-16", "name": "sync SDK in async route", "severity": "high",
     "regex": r"""async\s+def[\s\S]{0,400}\b(stripe\.[A-Z]\w+\.\w+|client\.messages\.create)\(""",
     "anti_match": r"to_thread|run_in_executor|_stripe_call",
     "hint": "Wrap in asyncio.to_thread or run_in_executor."},
    {"id": "PAT-17", "name": "unbounded defaultdict accumulator", "severity": "high",
     "regex": r"""defaultdict\((list|int|set)\)""",
     "anti_match": r"TTLCache",
     "hint": "Use cachetools.TTLCache with maxsize+ttl."},
    {"id": "PAT-21", "name": "Mongo find without _id projection", "severity": "medium",
     "regex": r"""find_one\([^)]+\)\s*\n(?![^\n]*"_id"\s*:\s*0)""",
     "anti_match": r"""\{"_id"\s*:\s*0""",
     "hint": "Always project {\"_id\": 0} or use response_model."},
    {"id": "PAT-26", "name": "hardcoded founder email", "severity": "medium",
     "regex": r"""teji\.ss1986@gmail\.com""",
     "anti_match": r"FOUNDER_EMAIL|memory/",
     "hint": "Read from FOUNDER_EMAIL env var."},
    {"id": "PAT-27", "name": "JWT in WebSocket query param", "severity": "high",
     "regex": r"""websocket\.query_params\.get\(["']token["']\)""",
     "hint": "Accept token via first websocket message after accept()."},
]


@router.get("")
async def list_patterns(_=Depends(_require_admin)):
    """Return the catalog of detection patterns (no playbook body)."""
    return {
        "skill_id": "AUREM-SEC-PATTERNS-V1",
        "count": len(PATTERNS),
        "patterns": [
            {"id": p["id"], "name": p["name"], "severity": p["severity"],
             "hint": p.get("hint", "")}
            for p in PATTERNS
        ],
    }


@router.get("/playbook")
async def playbook_body(_=Depends(_require_admin)):
    """Return the full SECURITY_PATTERNS.md body from the broadcast."""
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    doc = await _db.ora_skills_library.find_one(
        {"id": "AUREM-SEC-PATTERNS-V1"}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Playbook not seeded — run scripts/seed_security_patterns_skill.py")
    return {
        "id": doc["id"],
        "version": doc.get("version", "1"),
        "byte_size": doc.get("byte_size"),
        "body_sha256": doc.get("body_sha256"),
        "body": doc.get("body", ""),
        "updated_at": str(doc.get("updated_at", "")),
    }


@router.post("/scan")
async def scan_file(body: dict, _=Depends(_require_admin)):
    """Scan a single file path against every pattern.

    Body: `{"path": "/app/backend/routes/auth.py"}`
    Returns a list of matches with file/line/pattern.
    Limited to /app/backend, /app/frontend, /app/scripts for safety.
    """
    raw = (body or {}).get("path") or ""
    if not raw:
        raise HTTPException(400, "Missing 'path'")
    p = Path(raw).resolve()
    allowed_roots = ("/app/backend", "/app/frontend", "/app/scripts", "/app/memory")
    if not any(str(p).startswith(r) for r in allowed_roots):
        raise HTTPException(400, f"Path must be under {allowed_roots}")
    if not p.exists() or not p.is_file():
        raise HTTPException(404, f"File not found: {p}")
    try:
        src = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(500, f"Read failed: {e}")

    findings: List[Dict] = []
    for pat in PATTERNS:
        rx = re.compile(pat["regex"], re.MULTILINE)
        anti = pat.get("anti_match")
        anti_rx = re.compile(anti, re.MULTILINE) if anti else None
        for m in rx.finditer(src):
            # Skip when the file already has an anti-match marker
            # somewhere — the patch has already been applied.
            if anti_rx and anti_rx.search(src):
                continue
            line_no = src.count("\n", 0, m.start()) + 1
            snippet = src[max(0, m.start() - 60): m.end() + 60].replace("\n", " ⏎ ")
            findings.append({
                "pattern_id": pat["id"],
                "name": pat["name"],
                "severity": pat["severity"],
                "line": line_no,
                "snippet": snippet[:240],
                "hint": pat.get("hint", ""),
            })
    return {
        "path": str(p),
        "patterns_run": len(PATTERNS),
        "findings": findings,
        "clean": len(findings) == 0,
    }


@router.post("/scan-paths")
async def scan_many(body: dict, _=Depends(_require_admin)):
    """Scan a list of file paths. Body: `{"paths": ["/app/backend/..."]}`"""
    paths = (body or {}).get("paths") or []
    if not isinstance(paths, list):
        raise HTTPException(400, "'paths' must be a list")
    if len(paths) > 200:
        raise HTTPException(400, "Max 200 paths per scan")
    out = []
    for p in paths:
        try:
            sub = await scan_file({"path": p}, _=None)  # type: ignore
            out.append(sub)
        except HTTPException as e:
            out.append({"path": p, "error": e.detail})
    return {"count": len(out), "results": out}
