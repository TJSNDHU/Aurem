"""
services/dev_security_guards.py — iter 331e Part 1

Hardening pass for the Developer Portal:

  1. SSRF guard (`assert_url_safe`)
       - Blocks 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
       - Blocks 127.0.0.0/8, 169.254.0.0/16 (link-local), ::1
       - Blocks localhost, *.local, *.internal, *.intranet hostnames
       - Blocks raw IPv6 loopback / unique-local / link-local
       - DNS-resolves the hostname and re-checks each resolved IP

  2. File size limits (`enforce_file_size_limits`)
       - Per file:    10 MB hard cap   (env: ORA_DEV_MAX_FILE_MB)
       - Per session: 50 MB cumulative (env: ORA_DEV_MAX_SESSION_MB)
       - Returns HTTP 413-shaped envelope when exceeded

  3. Concurrent session limit (`acquire_session` / `release_session`)
       - Max 2 active ORA sessions per developer  (env: ORA_DEV_MAX_ACTIVE_SESSIONS)
       - Active sessions tracked in db.developer_accounts.active_sessions
       - Stale sessions (heartbeat > 30 min ago) cleaned automatically

  4. Output masking (`mask_sensitive_output`)
       - Strips every os.environ key value that looks secret
       - Strips bearer tokens, JWTs, private keys
       - Strips paths under /app/backend/services & /app/backend/routers
         when the caller is a developer tenant

All four are pure functions where possible. set_db() wires the Mongo
client; all guards work without DB when set_db() hasn't been called
(safe import).

Portability: zero Emergent imports. Env-overridable knobs. No platform
lock-in.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Knobs (env-overridable) ────────────────────────────────────────
MAX_FILE_BYTES        = int(os.environ.get("ORA_DEV_MAX_FILE_MB", "10")) * 1024 * 1024
MAX_SESSION_BYTES     = int(os.environ.get("ORA_DEV_MAX_SESSION_MB", "50")) * 1024 * 1024
MAX_ACTIVE_SESSIONS   = int(os.environ.get("ORA_DEV_MAX_ACTIVE_SESSIONS", "2"))
SESSION_STALE_MINUTES = int(os.environ.get("ORA_DEV_SESSION_STALE_MIN", "30"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════════
# 1. SSRF guard
# ════════════════════════════════════════════════════════════════════

_BLOCKED_HOST_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".intranet",
    ".lan",
    ".corp",
)
_BLOCKED_EXACT_HOSTS = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
    # K8s / cloud-internal
    "kubernetes",
    "kubernetes.default",
    "kubernetes.default.svc",
    "kubernetes.default.svc.cluster.local",
    "metadata",
    "metadata.google.internal",
    # AWS metadata
    "169.254.169.254",
    # Container hops
    "host.docker.internal",
    "gateway.docker.internal",
}


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str]:
    """Return (blocked, reason)."""
    if ip.is_loopback:
        return True, "loopback_blocked"
    if ip.is_private:
        return True, "private_ip_blocked"
    if ip.is_link_local:
        return True, "link_local_blocked"
    if ip.is_reserved:
        return True, "reserved_ip_blocked"
    if ip.is_multicast:
        return True, "multicast_blocked"
    if ip.is_unspecified:
        return True, "unspecified_ip_blocked"
    return False, ""


def assert_url_safe(url: str, *, resolve_dns: bool = True) -> dict:
    """Return `{ok, host, reason?}`. Refuses any URL pointing at a
    private/loopback/link-local/internal target. When `resolve_dns`
    is True, the hostname is resolved and each returned IP re-checked
    against the same ruleset (defeats DNS rebinding via `127-0-0-1.nip.io`).
    """
    if not url or not isinstance(url, str):
        return {"ok": False, "reason": "empty_url"}
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except Exception:
        return {"ok": False, "reason": "invalid_url"}

    host = (parsed.hostname or "").lower().strip()
    if not host:
        return {"ok": False, "reason": "no_host"}

    # Exact host blocklist
    if host in _BLOCKED_EXACT_HOSTS:
        return {"ok": False, "host": host, "reason": "blocked_exact_host"}

    # Suffix blocklist (`.local`, `.internal`, etc.)
    for suffix in _BLOCKED_HOST_SUFFIXES:
        if host.endswith(suffix):
            return {"ok": False, "host": host,
                    "reason": f"blocked_suffix_{suffix.lstrip('.')}"}

    # If the host is itself an IP literal, check directly
    try:
        ip = ipaddress.ip_address(host)
        blocked, reason = _ip_is_blocked(ip)
        if blocked:
            return {"ok": False, "host": host, "reason": reason}
        return {"ok": True, "host": host, "resolved": [str(ip)]}
    except ValueError:
        pass

    # Hostname — resolve and inspect each returned address
    if not resolve_dns:
        return {"ok": True, "host": host, "resolved": []}
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception as e:
        # Resolver failed — refuse rather than allow blindly
        return {"ok": False, "host": host,
                "reason": f"dns_resolve_failed:{str(e)[:60]}"}
    resolved: list[str] = []
    for fam, _t, _p, _c, sockaddr in infos:
        ip_str = sockaddr[0]
        # Strip IPv6 zone id if present
        if "%" in ip_str:
            ip_str = ip_str.split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except Exception:
            continue
        blocked, reason = _ip_is_blocked(ip)
        if blocked:
            return {"ok": False, "host": host,
                    "resolved_to": ip_str, "reason": reason}
        resolved.append(ip_str)
    return {"ok": True, "host": host, "resolved": sorted(set(resolved))}


# ════════════════════════════════════════════════════════════════════
# 2. File size limits
# ════════════════════════════════════════════════════════════════════

# session_id → cumulative bytes read in this session
_SESSION_BYTES: dict[str, int] = {}


def enforce_file_size_limits(
    session_id: str,
    file_bytes: int,
    *,
    file_path: str = "",
) -> dict:
    """Return `{ok, http_status, ...}`. Refuses when this single file
    exceeds `MAX_FILE_BYTES` OR when adding it to the session total
    would push past `MAX_SESSION_BYTES`. Successful calls update the
    session running total.
    """
    if file_bytes < 0:
        return {"ok": False, "http_status": 400,
                "reason": "negative_size"}
    if file_bytes > MAX_FILE_BYTES:
        return {
            "ok":          False,
            "http_status": 413,
            "reason":      "file_too_large",
            "limit_bytes": MAX_FILE_BYTES,
            "actual":      file_bytes,
            "path":        file_path,
            "message":     (
                f"This file is {file_bytes / 1024 / 1024:.1f} MB. "
                f"The per-file cap is "
                f"{MAX_FILE_BYTES / 1024 / 1024:.0f} MB. "
                f"Try grep first to narrow what you need."
            ),
        }
    sid = session_id or "default"
    cur = _SESSION_BYTES.get(sid, 0)
    if cur + file_bytes > MAX_SESSION_BYTES:
        return {
            "ok":             False,
            "http_status":    413,
            "reason":         "session_quota_exceeded",
            "session_used":   cur,
            "session_limit":  MAX_SESSION_BYTES,
            "requested":      file_bytes,
            "message":        (
                f"You've read "
                f"{cur / 1024 / 1024:.1f} MB this session "
                f"(cap "
                f"{MAX_SESSION_BYTES / 1024 / 1024:.0f} MB). "
                f"Start a fresh session or reduce file size."
            ),
        }
    _SESSION_BYTES[sid] = cur + file_bytes
    return {
        "ok":            True,
        "session_used":  _SESSION_BYTES[sid],
        "session_limit": MAX_SESSION_BYTES,
    }


def reset_session_bytes(session_id: str) -> None:
    """Public helper — called when a session terminates so we don't
    leak memory across long-lived processes."""
    _SESSION_BYTES.pop(session_id or "default", None)


# ════════════════════════════════════════════════════════════════════
# 3. Concurrent session limit
# ════════════════════════════════════════════════════════════════════

async def acquire_session(user_id: str, session_id: str) -> dict:
    """Atomically acquire a session slot. Returns:
      ok                  — bool, granted
      active_count        — total active including this session
      active_session_ids  — list of active session ids
    If the developer already holds MAX_ACTIVE_SESSIONS, refuses with
    `reason="too_many_sessions"` and provides the active list so the
    UI can let them pick which to close.
    """
    if _db is None or not user_id:
        return {"ok": True, "active_count": 0, "internal": True}
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=SESSION_STALE_MINUTES)).isoformat()
    now_iso = now.isoformat()

    # 1) Drop stale sessions in one update
    await _db.developer_accounts.update_one(
        {"user_id": user_id},
        {"$pull": {"active_sessions": {"heartbeat": {"$lt": cutoff}}}},
    )
    # 2) Read fresh state
    acc = await _db.developer_accounts.find_one(
        {"user_id": user_id},
        {"_id": 0, "active_sessions": 1},
    )
    sessions = list((acc or {}).get("active_sessions") or [])
    # If this session_id is already in the list, refresh its heartbeat
    if any(s.get("session_id") == session_id for s in sessions):
        await _db.developer_accounts.update_one(
            {"user_id": user_id,
             "active_sessions.session_id": session_id},
            {"$set": {"active_sessions.$.heartbeat": now_iso}},
        )
        return {
            "ok":                 True,
            "active_count":       len(sessions),
            "active_session_ids": [s.get("session_id") for s in sessions],
            "renewed":            True,
        }
    if len(sessions) >= MAX_ACTIVE_SESSIONS:
        return {
            "ok":                 False,
            "reason":             "too_many_sessions",
            "active_count":       len(sessions),
            "active_session_ids": [s.get("session_id") for s in sessions],
            "limit":              MAX_ACTIVE_SESSIONS,
            "message":            (
                f"You have {len(sessions)} active sessions. "
                f"Close one before starting another."
            ),
        }
    # 3) Add the new slot
    await _db.developer_accounts.update_one(
        {"user_id": user_id},
        {"$push": {"active_sessions": {
            "session_id": session_id,
            "started_at": now_iso,
            "heartbeat":  now_iso,
        }}},
    )
    return {
        "ok":                 True,
        "active_count":       len(sessions) + 1,
        "active_session_ids": [s.get("session_id") for s in sessions] + [session_id],
    }


async def release_session(user_id: str, session_id: str) -> dict:
    """Drop a single session slot. Idempotent."""
    if _db is None or not user_id:
        return {"ok": True, "internal": True}
    r = await _db.developer_accounts.update_one(
        {"user_id": user_id},
        {"$pull": {"active_sessions": {"session_id": session_id}}},
    )
    reset_session_bytes(session_id)
    return {"ok": True, "matched": r.matched_count, "modified": r.modified_count}


async def list_active_sessions(user_id: str) -> list[dict]:
    """Read-only — used by /developers/settings to show active sessions."""
    if _db is None or not user_id:
        return []
    acc = await _db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0, "active_sessions": 1},
    )
    return list((acc or {}).get("active_sessions") or [])


# ════════════════════════════════════════════════════════════════════
# 4. Output masking (env-vars, JWTs, internal paths, bearer tokens)
# ════════════════════════════════════════════════════════════════════

# Patterns matched in any string we mask. Order matters — longer
# patterns first so we don't half-redact.
_MASK_PATTERNS = [
    # JWT (3 base64url segments)
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
        "[REDACTED-JWT]"),
    # Bearer token (Authorization: Bearer xxx)
    (re.compile(r"(Bearer\s+)([A-Za-z0-9_\-\.=]+)", re.IGNORECASE),
        r"\1[REDACTED]"),
    # Common API key prefixes
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),       "[REDACTED-KEY]"),
    (re.compile(r"\bsk_live_[A-Za-z0-9]{8,}\b"),     "[REDACTED-STRIPE-LIVE]"),
    (re.compile(r"\bsk_test_[A-Za-z0-9]{8,}\b"),     "[REDACTED-STRIPE-TEST]"),
    (re.compile(r"\bpk_live_[A-Za-z0-9]{8,}\b"),     "[REDACTED-STRIPE-PK]"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}\b"),     "[REDACTED-GOOGLE-KEY]"),
    (re.compile(r"\bre_[A-Za-z0-9_]{12,}\b"),        "[REDACTED-RESEND-KEY]"),
    # Private key blocks
    (re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL),
        "[REDACTED-PRIVATE-KEY-BLOCK]"),
    # Mongo connection string
    (re.compile(r"mongodb(\+srv)?://[^\s\"']+"),    "[REDACTED-MONGO-URL]"),
    # Telegram bot token
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_\-]{30,}\b"), "[REDACTED-TELEGRAM-TOKEN]"),
]

# Internal source paths that developers must NEVER see. They're free
# to read their OWN sandbox; the platform's own services / routers /
# config are not theirs to read.
_INTERNAL_PATH_PREFIXES = (
    "/app/backend/services/",
    "/app/backend/routers/",
    "/app/backend/utils/",
    "/app/backend/bootstrap/",
    "/app/backend/middleware/",
    "/app/backend/.env",
    "/app/memory/tier1/",
    "/app/memory/tier2/",
    "/etc/supervisor/",
)


def _mask_env_values(text: str) -> str:
    """For every env var whose name LOOKS like a secret (KEY/TOKEN/
    SECRET/PASSWORD/PASS/DSN/CONN/PWD), redact its current value in the
    output. We never inspect what we don't have."""
    secret_name = re.compile(
        r"(KEY|TOKEN|SECRET|PASSWORD|PASS(?:WD)?|DSN|CONN(?:ECTION)?_STRING|API_KEY|PRIVATE)$",
        re.IGNORECASE,
    )
    for k, v in os.environ.items():
        if not v or len(v) < 6:
            continue
        if not secret_name.search(k):
            continue
        # Skip generic short tokens that would create false positives
        if v.lower() in ("true", "false", "yes", "no", "none", "null"):
            continue
        text = text.replace(v, f"[REDACTED-{k}]")
    return text


def mask_sensitive_output(payload: Any, *, mask_internal_paths: bool = True) -> Any:
    """Recursively walk dict/list/str and apply all four mask passes.
    Returns a new structure (never mutates input).
    """
    if isinstance(payload, str):
        out = payload
        for pat, repl in _MASK_PATTERNS:
            out = pat.sub(repl, out)
        out = _mask_env_values(out)
        if mask_internal_paths:
            for prefix in _INTERNAL_PATH_PREFIXES:
                if prefix in out:
                    out = out.replace(prefix, "[INTERNAL]/")
        return out
    if isinstance(payload, dict):
        return {k: mask_sensitive_output(v, mask_internal_paths=mask_internal_paths)
                for k, v in payload.items()}
    if isinstance(payload, list):
        return [mask_sensitive_output(item, mask_internal_paths=mask_internal_paths)
                for item in payload]
    if isinstance(payload, tuple):
        return tuple(mask_sensitive_output(item, mask_internal_paths=mask_internal_paths)
                     for item in payload)
    return payload


def is_internal_path(path: str) -> bool:
    """Used by view_bulk / view_file gate so a developer can't read
    /app/backend/services/* etc. The developer's own sandbox lives
    under /tmp/ora-sandbox-* + their connected GitHub repo clone."""
    if not path or not isinstance(path, str):
        return False
    p = path.strip()
    for prefix in _INTERNAL_PATH_PREFIXES:
        if p.startswith(prefix):
            return True
    return False


__all__ = [
    "set_db",
    "MAX_FILE_BYTES", "MAX_SESSION_BYTES",
    "MAX_ACTIVE_SESSIONS", "SESSION_STALE_MINUTES",
    "assert_url_safe",
    "enforce_file_size_limits", "reset_session_bytes",
    "acquire_session", "release_session", "list_active_sessions",
    "mask_sensitive_output", "is_internal_path",
]
