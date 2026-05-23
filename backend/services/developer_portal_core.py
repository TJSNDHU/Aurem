"""
services/developer_portal_core.py — iter 331d (final foundation)

Backend foundation for the Developer Portal:
  • Mongo schemas for 6 new collections (lazy index creation)
  • Signup state machine: pending → OTP-sent → verified → active
  • BYOK encryption via existing credential_crypto.encrypt_credentials
  • Token deduction tied to invoke_tool dispatcher
  • Token wall enforcement (HTTP 402 when balance hits 0)
  • Abuse pattern detection (port scan / crypto miner / SQLi / mass mail)
  • Per-developer rate limits (10/min, 100/day on free tier)
  • Pixel domain validation (no localhost / private IP / .local)
  • OTP send + verify (uses services.email_service.send_email if available)
  • 45-day inactive sandbox cleanup

Portability: zero Emergent imports. All knobs env-overridable.

Public API:
    set_db(database)
    ensure_indexes()
    create_signup(email, name, github_username, build_intent, referral_code, ip)
    verify_otp(email, otp)
    issue_jwt(user_id, email) -> str
    decode_dev_jwt(token) -> dict
    get_account(user_id) -> dict
    deduct_tokens(user_id, action_type, tool_name, session_id) -> dict
    enforce_token_wall(user_id) -> {ok, tokens_remaining, ...}
    check_abuse_pattern(user_id, command) -> {ok, blocked, matched}
    check_rate_limit(user_id) -> {ok, limit_remaining}
    encrypt_byok(plain_keys) / decrypt_byok(envelope)
    validate_pixel_domain(domain) -> {ok, reason}
    award_referral_bonus(referrer_code, new_user_id)
    cleanup_inactive_sandboxes(max_age_days=45)
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import re
import secrets
import shutil
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Configuration ───────────────────────────────────────────────────
FREE_TOKEN_GRANT       = int(os.environ.get("ORA_FREE_TOKEN_GRANT", "1000"))
REFERRED_TOKEN_GRANT   = int(os.environ.get("ORA_REFERRED_TOKEN_GRANT", "1500"))
REFERRAL_BONUS_TOKENS  = int(os.environ.get("ORA_REFERRAL_BONUS_TOKENS", "500"))
SHARE_REWARD_TOKENS    = int(os.environ.get("ORA_SHARE_REWARD_TOKENS", "2500"))
TOKEN_EXPIRY_DAYS      = int(os.environ.get("ORA_TOKEN_EXPIRY_DAYS", "30"))
RATE_LIMIT_PER_MIN     = int(os.environ.get("ORA_DEV_RATE_PER_MIN", "10"))
RATE_LIMIT_PER_DAY     = int(os.environ.get("ORA_DEV_RATE_PER_DAY", "100"))
JWT_SECRET             = os.environ.get("JWT_SECRET") or os.environ.get("DEV_JWT_SECRET", "dev-jwt-fallback-change-me")
JWT_TTL_DAYS           = int(os.environ.get("DEV_JWT_TTL_DAYS", "30"))
OTP_TTL_SECONDS        = int(os.environ.get("ORA_OTP_TTL_SECONDS", "600"))   # 10 minutes
OTP_MAX_ATTEMPTS       = int(os.environ.get("ORA_OTP_MAX_ATTEMPTS", "5"))
SIGNUP_RATE_PER_IP_HR  = int(os.environ.get("ORA_SIGNUP_PER_IP_HR", "5"))
SANDBOX_INACTIVE_DAYS  = int(os.environ.get("ORA_SANDBOX_INACTIVE_DAYS", "45"))
SANDBOX_ROOT           = Path(os.environ.get("ORA_SANDBOX_ROOT", "/tmp"))

# Token cost table (per action type)
TOKEN_COSTS = {
    "chat":          1,
    "file_read":     2,
    "file_edit":     2,
    "test_run":      3,
    "deploy":        5,
    "fork_context": 10,
}

# Default cost when invoke_tool fires a tool we haven't categorised yet.
DEFAULT_TOOL_COST = 1


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════════
# Mongo schema + indexes
# ════════════════════════════════════════════════════════════════════

async def ensure_indexes() -> None:
    """Idempotent. Safe to call on every startup."""
    if _db is None:
        return
    try:
        await _db.developer_accounts.create_index("email", unique=True)
        await _db.developer_accounts.create_index("user_id", unique=True)
        await _db.developer_accounts.create_index("referral_code", unique=True, sparse=True)
        await _db.developer_accounts.create_index("pixel_key", sparse=True)
        await _db.developer_tokens.create_index([("user_id", 1), ("timestamp", -1)])
        await _db.developer_projects.create_index([("user_id", 1), ("status", 1)])
        await _db.developer_share_requests.create_index([("status", 1), ("submitted_at", -1)])
        await _db.developer_pixel_events.create_index([("developer_id", 1), ("timestamp", -1)])
        await _db.developer_abuse_flags.create_index([("user_id", 1), ("timestamp", -1)])
        await _db.developer_otp_codes.create_index("email")
        await _db.developer_otp_codes.create_index("expires_at", expireAfterSeconds=0)
        await _db.developer_rate_limits.create_index("user_id")
        await _db.developer_rate_limits.create_index("ip")
        # iter 331g — Stripe collections
        await _db.payment_transactions.create_index("session_id", unique=True)
        await _db.payment_transactions.create_index([("user_id", 1), ("created_at", -1)])
        await _db.stripe_events_processed.create_index("event_id", unique=True)
        logger.info("[developer-portal] indexes ensured")
    except Exception as e:
        logger.warning(f"[developer-portal] index creation failed: {e}")


# ════════════════════════════════════════════════════════════════════
# Anti-bot signup throttle
# ════════════════════════════════════════════════════════════════════

async def signup_anti_bot_check(ip: str, email: str) -> dict:
    """Reject signups from an IP that's hit > SIGNUP_RATE_PER_IP_HR
    in the last hour. Also rejects obvious throwaway-email patterns.
    """
    if _db is None:
        return {"ok": True}
    # Per-IP rate window (1 hour)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    try:
        count = await _db.developer_accounts.count_documents({
            "signup_ip": ip, "created_at": {"$gte": cutoff},
        })
    except Exception:
        count = 0
    if count >= SIGNUP_RATE_PER_IP_HR:
        return {
            "ok":   False,
            "reason": "signup_rate_per_ip",
            "message": "Too many signups from this IP. Try again in an hour.",
        }
    # Obvious-junk patterns
    bad_patterns = (
        r"@mailinator\.|@10minutemail\.|@guerrillamail\.|@yopmail\.",
        r"\+\+",
    )
    for pat in bad_patterns:
        if re.search(pat, email or "", re.IGNORECASE):
            return {
                "ok":     False,
                "reason": "disposable_email",
                "message": "Please use a real email — disposable addresses aren't allowed.",
            }
    return {"ok": True}


# ════════════════════════════════════════════════════════════════════
# Signup + OTP flow
# ════════════════════════════════════════════════════════════════════

def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _generate_referral_code(email: str) -> str:
    # Stable but pretty (lowercase, 8 chars).
    h = hashlib.sha256(email.lower().encode()).hexdigest()[:6]
    return f"r{h}"


async def _send_email(to: str, subject: str, body: str, html: str | None = None) -> bool:
    """Best-effort email via Resend wrapper. Returns True on success."""
    try:
        from services.email_service_resend import send_email
        html_body = html or f"<pre style='font-family:system-ui'>{body}</pre>"
        ok, _ = await send_email(to=to, subject=subject, html=html_body, text=body)
        if not ok:
            # Log the OTP/body so the founder can still test locally
            logger.info(f"[developer-portal] EMAIL FALLBACK TO={to} SUBJ='{subject}' BODY='{body[:200]}'")
        return ok
    except Exception as e:
        logger.warning(f"[developer-portal] email send fallback: {e}")
        logger.info(f"[developer-portal] EMAIL FALLBACK TO={to} SUBJ='{subject}' BODY='{body[:200]}'")
        return False


def _welcome_email_html(name: str, login_url: str, connect_url: str) -> tuple[str, str]:
    """Returns (subject, html) for the Day-0 welcome email."""
    subject = "Welcome to AUREM CTO — Your 1000 tokens are ready"
    display_name = (name or "there").split()[0]
    html = f"""<!doctype html>
<html><body style="font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
                   background:#0b1020;color:#e7ecff;margin:0;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#10172a;
              border:1px solid #1e2a4a;border-radius:14px;padding:32px;">
    <h1 style="font-size:22px;margin:0 0 8px;letter-spacing:-0.01em;">
      Welcome to AUREM CTO, {display_name}.
    </h1>
    <p style="color:#9aa6c7;line-height:1.55;margin:0 0 18px;">
      Your account is verified and <strong style="color:#7ad9b6;">1,000 free
      tokens</strong> have been added to your balance. Enough to ship your
      first small project end-to-end.
    </p>

    <div style="background:#0b1224;border:1px solid #1a2547;border-radius:10px;
                padding:18px;margin:18px 0;">
      <p style="margin:0 0 10px;color:#cfd8f5;font-weight:600;">Get started in 3 steps</p>
      <ol style="padding-left:18px;margin:0;color:#9aa6c7;line-height:1.7;">
        <li><a href="{login_url}" style="color:#7ad9b6;text-decoration:none;">
            Log in to your dashboard</a> — see your token balance + project list.</li>
        <li><a href="{connect_url}" style="color:#7ad9b6;text-decoration:none;">
            Connect your GitHub</a> — so ORA can read your repos (read-only by default).</li>
        <li>Tell AUREM CTO what you want to build. Chat, edit, test, deploy — all
            inside one window.</li>
      </ol>
    </div>

    <p style="color:#9aa6c7;line-height:1.55;margin:18px 0 0;font-size:13px;">
      Token costs are transparent: chat = 1 token, file edit = 2, test = 3,
      deploy = 5. You can <strong>bring your own LLM keys</strong> (BYOK) any
      time and tokens stop deducting for your own calls.
    </p>

    <p style="color:#6a7aab;font-size:12px;margin-top:28px;text-align:center;">
      Reply to this email if you get stuck. A real human reads every reply.
    </p>
  </div>
</body></html>"""
    return subject, html


async def _send_welcome_email(email: str, name: str) -> bool:
    """Day-0 welcome email — sent once on OTP verify success."""
    site = os.environ.get("FRONTEND_URL") or os.environ.get("SITE_URL") or "https://aurem.live"
    site = site.rstrip("/")
    login_url   = f"{site}/developers/login"
    connect_url = f"{site}/developers/connect"
    subject, html = _welcome_email_html(name, login_url, connect_url)
    text = (
        f"Welcome to AUREM CTO, {(name or 'there').split()[0]}.\n\n"
        f"Your account is verified and 1,000 free tokens are ready.\n\n"
        f"Get started in 3 steps:\n"
        f"  1. Log in: {login_url}\n"
        f"  2. Connect GitHub: {connect_url}\n"
        f"  3. Tell AUREM CTO what you want to build.\n\n"
        f"Token costs: chat=1, file edit=2, test=3, deploy=5. BYOK any time.\n\n"
        f"Reply to this email if you get stuck."
    )
    return await _send_email(to=email, subject=subject, body=text, html=html)


async def create_signup(
    email: str,
    name: str,
    password_hash: str,
    github_username: str = "",
    build_intent: str = "",
    referral_code: str = "",
    ip: str = "0.0.0.0",
) -> dict:
    """Create a new pending account + send OTP. Returns:
      ok, user_id, otp_sent (bool), expires_in_seconds
    """
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    email = (email or "").strip().lower()
    if not email or "@" not in email or len(name) < 1:
        return {"ok": False, "error": "email and name are required"}

    # Anti-bot first
    gate = await signup_anti_bot_check(ip, email)
    if not gate["ok"]:
        return gate

    # Existing account?
    existing = await _db.developer_accounts.find_one({"email": email}, {"_id": 0})
    if existing and existing.get("email_verified"):
        return {"ok": False, "error": "email_already_registered",
                 "message": "An account with this email already exists. Please log in."}

    user_id = uuid.uuid4().hex[:24]
    own_code = _generate_referral_code(email)

    # Resolve referrer (best-effort)
    referred_by = None
    grant = FREE_TOKEN_GRANT
    if referral_code:
        ref = await _db.developer_accounts.find_one(
            {"referral_code": referral_code.lower().strip()},
            {"_id": 0, "user_id": 1},
        )
        if ref:
            referred_by = ref["user_id"]
            grant = REFERRED_TOKEN_GRANT

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS)
    ).isoformat()

    doc = {
        "user_id":              user_id,
        "email":                email,
        "email_verified":       False,
        "name":                 name,
        "password_hash":        password_hash,
        "github_username":      github_username or "",
        "github_connected":     False,
        "mongodb_connected":    False,
        "vscode_connected":     False,
        "byok_keys":            None,
        "tokens_remaining":     grant,
        "tokens_total_used":    0,
        "free_tokens_expire_at": expires_at,
        "pixel_key":            f"DEV-{user_id[:8]}-{secrets.token_urlsafe(6)}",
        "pixel_verified":       False,
        "pixel_domain":         None,
        "referral_code":        own_code,
        "referred_by":          referred_by,
        "subscription_status":  "free",
        "abuse_flagged":        False,
        "build_intent":         build_intent[:500] if build_intent else "",
        "signup_ip":            ip[:64],
        "created_at":           _iso(),
        "last_active_at":       _iso(),
    }
    try:
        await _db.developer_accounts.insert_one(doc)
    except Exception as e:
        # Race: another insert beat us — likely duplicate email.
        return {"ok": False, "error": f"could not create account: {e}"}

    # OTP issue
    otp = _generate_otp()
    otp_doc = {
        "email":       email,
        "otp_hash":    hashlib.sha256(otp.encode()).hexdigest(),
        "expires_at":  datetime.now(timezone.utc) + timedelta(seconds=OTP_TTL_SECONDS),
        "attempts":    0,
        "issued_at":   _iso(),
    }
    await _db.developer_otp_codes.insert_one(otp_doc)
    sent = await _send_email(
        to=email,
        subject="Your AUREM verification code",
        body=f"Welcome to AUREM. Your verification code is: {otp}\n\n"
              f"This code expires in {OTP_TTL_SECONDS // 60} minutes.",
    )
    return {
        "ok":                True,
        "user_id":           user_id,
        "tokens_granted":    grant,
        "referred_by":       referred_by,
        "referral_code":     own_code,
        "otp_sent":          sent,
        "otp_ttl_seconds":   OTP_TTL_SECONDS,
        # NB: for local testing we expose the OTP. In production, set
        # ORA_OTP_REVEAL_IN_RESPONSE=0 so this is omitted.
        "_otp_for_testing":  otp if os.environ.get("ORA_OTP_REVEAL_IN_RESPONSE", "1") == "1" else None,
    }


async def verify_otp(email: str, otp: str) -> dict:
    """Verify OTP. On success: mark account email_verified=true, mint
    a JWT, and award the referral bonus to the referrer (if any)."""
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    email = (email or "").strip().lower()
    if not email or not otp:
        return {"ok": False, "error": "email and otp required"}

    record = await _db.developer_otp_codes.find_one(
        {"email": email}, sort=[("issued_at", -1)],
    )
    if not record:
        return {"ok": False, "error": "no_otp_pending"}
    if record.get("attempts", 0) >= OTP_MAX_ATTEMPTS:
        return {"ok": False, "error": "too_many_attempts"}

    # Increment attempt count
    await _db.developer_otp_codes.update_one(
        {"_id": record["_id"]}, {"$inc": {"attempts": 1}}
    )

    expected = record.get("otp_hash")
    submitted_hash = hashlib.sha256(otp.encode()).hexdigest()
    if not hmac.compare_digest(expected or "", submitted_hash):
        return {"ok": False, "error": "wrong_otp"}

    # Check expiry
    exp = record.get("expires_at")
    if exp:
        if isinstance(exp, str):
            try:
                exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            except Exception:
                exp = None
        # Mongo returns datetimes as tz-naive UTC — normalize before compare
        if isinstance(exp, datetime) and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and exp < datetime.now(timezone.utc):
            return {"ok": False, "error": "otp_expired"}

    # OTP good — verify the account
    account = await _db.developer_accounts.find_one_and_update(
        {"email": email},
        {"$set": {"email_verified": True, "last_active_at": _iso()}},
        return_document=True,
    )
    if not account:
        return {"ok": False, "error": "account_missing"}

    # Burn the OTP
    await _db.developer_otp_codes.delete_one({"_id": record["_id"]})

    # Award referrer bonus
    if account.get("referred_by"):
        await award_referral_bonus(
            referrer_user_id=account["referred_by"],
            new_user_id=account["user_id"],
        )

    # Day-0 welcome email — fire-and-forget so OTP verify stays snappy
    try:
        import asyncio as _aio
        _aio.create_task(_send_welcome_email(
            email=account["email"],
            name=account.get("name", ""),
        ))
    except Exception as _we:
        logger.debug(f"[developer-portal] welcome email skipped: {_we}")

    # Mint JWT
    token = issue_jwt(account["user_id"], account["email"])
    return {
        "ok":               True,
        "user_id":          account["user_id"],
        "email":            account["email"],
        "tokens_remaining": account.get("tokens_remaining", 0),
        "jwt":              token,
        "jwt_ttl_days":     JWT_TTL_DAYS,
    }


async def award_referral_bonus(referrer_user_id: str, new_user_id: str) -> dict:
    if _db is None:
        return {"ok": False}
    r = await _db.developer_accounts.update_one(
        {"user_id": referrer_user_id},
        {"$inc": {"tokens_remaining": REFERRAL_BONUS_TOKENS},
         "$push": {"referrals_awarded": {"new_user_id": new_user_id,
                                            "awarded_at": _iso(),
                                            "tokens": REFERRAL_BONUS_TOKENS}}},
    )
    return {"ok": True, "matched": r.matched_count, "modified": r.modified_count}


# ════════════════════════════════════════════════════════════════════
# JWT (minimal, no external lib — HMAC-SHA256)
# ════════════════════════════════════════════════════════════════════

def issue_jwt(user_id: str, email: str) -> str:
    """Mint a developer JWT. We use the platform-wide JWT_SECRET if
    set, else a documented fallback. PyJWT is preferred if installed."""
    payload = {
        "sub":     user_id,
        "email":   email,
        "kind":    "developer",
        "iat":     int(time.time()),
        "exp":     int(time.time()) + JWT_TTL_DAYS * 86400,
    }
    try:
        import jwt  # PyJWT
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    except Exception:
        # Tiny fallback: base64url(payload).hex(hmac)
        import base64
        import json
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
        sig = hmac.new(JWT_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return f"{body.decode()}.{sig}"


def decode_dev_jwt(token: str) -> dict:
    """Decode + verify a developer JWT. Returns the payload or {} on failure."""
    if not token:
        return {}
    try:
        import jwt
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        # Fallback path matches issue_jwt() fallback
        try:
            import base64
            import json
            body_b64, sig = token.split(".")
            expected_sig = hmac.new(JWT_SECRET.encode(), body_b64.encode(),
                                       hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_sig, sig):
                return {}
            padded = body_b64 + "=" * (-len(body_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
            if payload.get("exp", 0) < int(time.time()):
                return {}
            return payload
        except Exception:
            return {}


async def get_account(user_id: str) -> dict | None:
    if _db is None:
        return None
    return await _db.developer_accounts.find_one(
        {"user_id": user_id},
        {"_id": 0, "password_hash": 0, "byok_keys": 0},
    )


# ════════════════════════════════════════════════════════════════════
# BYOK encryption — re-uses services.credential_crypto (Fernet)
# ════════════════════════════════════════════════════════════════════

def encrypt_byok(plain_keys: dict) -> dict:
    """Encrypt the dict of provider keys. Wraps credential_crypto."""
    from services.credential_crypto import encrypt_credentials
    return encrypt_credentials(plain_keys)


def decrypt_byok(envelope: dict) -> dict:
    from services.credential_crypto import decrypt_credentials
    return decrypt_credentials(envelope)


async def save_byok_keys(user_id: str, plain_keys: dict) -> dict:
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    # Drop empty values to keep the envelope small
    clean = {k: v for k, v in (plain_keys or {}).items() if v and isinstance(v, str)}
    if not clean:
        return {"ok": False, "error": "at_least_one_key_required"}
    if not set(clean) & {"anthropic", "deepseek", "gemini"}:
        return {"ok": False,
                "error": "must_include_anthropic_or_deepseek_or_gemini"}
    envelope = encrypt_byok(clean)
    await _db.developer_accounts.update_one(
        {"user_id": user_id},
        {"$set": {"byok_keys": envelope, "byok_updated_at": _iso(),
                   "last_active_at": _iso()}},
    )
    return {"ok": True, "providers": sorted(clean.keys()),
            "encrypted": True}


# ════════════════════════════════════════════════════════════════════
# Token deduction + token wall
# ════════════════════════════════════════════════════════════════════

# Map common tool names to action_type categories
_TOOL_TO_ACTION = {
    "view_file":       "file_read",
    "view_bulk":       "file_read",
    "view_dir":        "file_read",
    "grep_codebase":   "file_read",
    "glob_files":      "file_read",
    "mongo_query_safe": "file_read",
    "read_logs":       "file_read",
    "search_codebase_semantic": "file_read",
    "semantic_memory_search": "file_read",
    "create_file":     "file_edit",
    "safe_edit":       "file_edit",
    "run_pytest":      "test_run",
    "check_coverage":  "test_run",
    "run_linter":      "test_run",
    "deploy_to_platform": "deploy",
    "rollback_deploy": "deploy",
    "fork_context":    "fork_context",
}


def cost_for_tool(tool_name: str) -> int:
    action = _TOOL_TO_ACTION.get(tool_name)
    if action and action in TOKEN_COSTS:
        return TOKEN_COSTS[action]
    return DEFAULT_TOOL_COST


async def deduct_tokens(
    user_id: str,
    tool_name: str,
    session_id: str = "",
) -> dict:
    """Atomic decrement. Returns the post-deduction balance.

    Best-effort: if the user doesn't exist in developer_accounts, this
    is a no-op (so internal ORA/founder sessions keep working).
    """
    if _db is None or not user_id:
        return {"ok": True, "deducted": 0, "internal": True}
    cost = cost_for_tool(tool_name)
    # Atomic check-and-decrement
    res = await _db.developer_accounts.find_one_and_update(
        {"user_id": user_id, "tokens_remaining": {"$gte": cost}},
        {"$inc": {"tokens_remaining": -cost,
                   "tokens_total_used": cost},
         "$set": {"last_active_at": _iso()}},
        projection={"_id": 0, "tokens_remaining": 1},
        return_document=True,
    )
    if not res:
        # Not enough balance — leave the row alone, signal token wall
        cur = await _db.developer_accounts.find_one(
            {"user_id": user_id}, {"_id": 0, "tokens_remaining": 1}
        )
        if cur is None:
            return {"ok": True, "deducted": 0, "internal": True}
        return {
            "ok":               False,
            "error":            "insufficient_tokens",
            "tokens_remaining": int(cur.get("tokens_remaining", 0)),
            "needed":           cost,
        }
    # Log the deduction
    try:
        await _db.developer_tokens.insert_one({
            "user_id":      user_id,
            "action_type":  _TOOL_TO_ACTION.get(tool_name, "other"),
            "tool_name":    tool_name,
            "tokens_used":  cost,
            "session_id":   session_id or "",
            "timestamp":    _iso(),
        })
    except Exception:
        pass
    return {
        "ok":               True,
        "deducted":         cost,
        "tokens_remaining": int(res.get("tokens_remaining", 0)),
    }


async def enforce_token_wall(user_id: str) -> dict:
    """Caller checks this BEFORE running an expensive operation.
    Returns ok=False if wall has hit (no tokens left).
    """
    if _db is None or not user_id:
        return {"ok": True, "tokens_remaining": -1, "internal": True}
    acc = await _db.developer_accounts.find_one(
        {"user_id": user_id},
        {"_id": 0, "tokens_remaining": 1, "free_tokens_expire_at": 1},
    )
    if not acc:
        return {"ok": True, "internal": True}
    remaining = int(acc.get("tokens_remaining", 0))
    if remaining <= 0:
        return {
            "ok":               False,
            "error":            "token_wall",
            "tokens_remaining": 0,
            "options": {
                "share_for_tokens":  f"+{SHARE_REWARD_TOKENS} tokens via screenshot review",
                "buy_starter":       "$9 → 10,000 tokens",
                "buy_builder":       "$39 → 50,000 tokens",
                "subscribe":         "$99/mo → unlimited",
            },
        }
    return {"ok": True, "tokens_remaining": remaining}


# ════════════════════════════════════════════════════════════════════
# Abuse pattern detection
# ════════════════════════════════════════════════════════════════════

_ABUSE_PATTERNS = [
    (re.compile(r"\bnmap\b|\bmasscan\b|\bzmap\b", re.IGNORECASE),
        "port_scanning"),
    (re.compile(r"\bxmrig\b|\bcryptonight\b|\bminerd\b|monero|stratum\+tcp",
                re.IGNORECASE),
        "crypto_mining"),
    (re.compile(r"\bUNION\s+SELECT\b|\bOR\s+1=1\b|';\s*DROP\s+TABLE\b",
                re.IGNORECASE),
        "sql_injection"),
    (re.compile(r"\bsmtplib\.|mass\s+email|spam.*send|bulk.*email.*loop",
                re.IGNORECASE),
        "mass_email_outside_aurem"),
    (re.compile(r"hping3|tcpdump\s+-i\s+any|nc\s+-l\s+-p\s+\d+\s+-e",
                re.IGNORECASE),
        "network_recon"),
]


async def check_abuse_pattern(user_id: str, command: str) -> dict:
    """Check a shell command against abuse patterns. If matched: persist
    flag, send Telegram alert, return blocked=True.
    """
    if not command:
        return {"ok": True, "blocked": False}
    for pat, label in _ABUSE_PATTERNS:
        if pat.search(command):
            doc = {
                "user_id":         user_id,
                "command_excerpt": (command or "")[:300],
                "pattern_matched": label,
                "timestamp":       _iso(),
                "action_taken":    "blocked",
            }
            if _db is not None:
                try:
                    await _db.developer_abuse_flags.insert_one(doc)
                    await _db.developer_accounts.update_one(
                        {"user_id": user_id},
                        {"$set": {"abuse_flagged": True,
                                    "abuse_flagged_at": _iso()}},
                    )
                except Exception:
                    pass
            # Telegram alert (best-effort)
            try:
                from services.telegram_bot_service import send_telegram_alert
                msg = (
                    f"🚨 Developer abuse — user={user_id} pattern={label}\n"
                    f"Command: {command[:200]}\n"
                    f"Account auto-flagged."
                )
                result = send_telegram_alert(msg)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass
            return {
                "ok":      False,
                "blocked": True,
                "matched": label,
                "message": f"Blocked: matches '{label}' abuse pattern. "
                           f"Account flagged for review.",
            }
    return {"ok": True, "blocked": False}


# ════════════════════════════════════════════════════════════════════
# Per-developer rate limiting
# ════════════════════════════════════════════════════════════════════

async def check_rate_limit(user_id: str) -> dict:
    """Returns ok=False with 429-shaped detail if the user exceeds:
      - RATE_LIMIT_PER_MIN per rolling 60s
      - RATE_LIMIT_PER_DAY per rolling 24h
    """
    if _db is None or not user_id:
        return {"ok": True, "internal": True}
    # Paid users get unlimited
    acc = await _db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0, "subscription_status": 1},
    )
    if acc and acc.get("subscription_status") == "paid":
        return {"ok": True, "tier": "paid"}

    now = datetime.now(timezone.utc)
    minute_ago = (now - timedelta(seconds=60)).isoformat()
    day_ago    = (now - timedelta(hours=24)).isoformat()

    minute_count = await _db.developer_tokens.count_documents({
        "user_id": user_id, "timestamp": {"$gte": minute_ago},
    })
    if minute_count >= RATE_LIMIT_PER_MIN:
        return {
            "ok":     False,
            "error":  "rate_limit_per_min",
            "limit":  RATE_LIMIT_PER_MIN,
            "count":  minute_count,
            "window": "60s",
        }
    day_count = await _db.developer_tokens.count_documents({
        "user_id": user_id, "timestamp": {"$gte": day_ago},
    })
    if day_count >= RATE_LIMIT_PER_DAY:
        return {
            "ok":     False,
            "error":  "rate_limit_per_day",
            "limit":  RATE_LIMIT_PER_DAY,
            "count":  day_count,
            "window": "24h",
        }
    return {"ok": True,
            "minute_used": minute_count, "day_used": day_count}


# ════════════════════════════════════════════════════════════════════
# Pixel domain validation
# ════════════════════════════════════════════════════════════════════

def validate_pixel_domain(raw: str) -> dict:
    """Reject localhost, private IP ranges, .local TLDs. Returns
    {ok, domain, reason}. The pixel must run on a real public domain
    so growth-loop attribution is meaningful."""
    if not raw or not isinstance(raw, str):
        return {"ok": False, "reason": "domain_required"}
    candidate = raw.strip().lower()
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except Exception:
        return {"ok": False, "reason": "invalid_url"}
    host = (parsed.hostname or "").lower().strip()
    if not host:
        return {"ok": False, "reason": "invalid_host"}
    # Localhost / loopback
    if host in ("localhost", "ip6-localhost"):
        return {"ok": False, "reason": "localhost_blocked",
                "message": "Localhost domains aren't allowed. Use your real public domain."}
    if host.endswith(".local") or host.endswith(".localhost"):
        return {"ok": False, "reason": "local_tld_blocked"}
    # Private IP ranges
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return {"ok": False, "reason": "private_ip_blocked",
                    "message": "Private/internal IPs aren't allowed for pixels."}
    except ValueError:
        # Not an IP — must look like a real host (at least one dot,
        # ≥2 chars after last dot)
        if "." not in host or len(host.rsplit(".", 1)[-1]) < 2:
            return {"ok": False, "reason": "not_a_real_domain"}
    return {"ok": True, "domain": host}


# ════════════════════════════════════════════════════════════════════
# Sandbox cleanup cron (45 days idle)
# ════════════════════════════════════════════════════════════════════

async def cleanup_inactive_sandboxes(max_age_days: int = SANDBOX_INACTIVE_DAYS) -> dict:
    """Walk /tmp/ora-sandbox-* and delete folders not touched in
    `max_age_days`. Returns counts."""
    if not SANDBOX_ROOT.exists():
        return {"ok": True, "scanned": 0, "removed": 0}
    cutoff_ts = time.time() - max_age_days * 86400
    removed: list[str] = []
    scanned = 0
    for entry in SANDBOX_ROOT.iterdir():
        if not entry.name.startswith("ora-sandbox-"):
            continue
        scanned += 1
        try:
            mtime = entry.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime < cutoff_ts:
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink(missing_ok=True)
                removed.append(str(entry))
            except Exception as e:
                logger.debug(f"[sandbox-cleanup] could not remove {entry}: {e}")
    if removed:
        logger.info(f"[sandbox-cleanup] removed {len(removed)} stale sandboxes")
    return {"ok": True, "scanned": scanned, "removed": len(removed),
             "removed_paths": removed[:50]}


__all__ = [
    "set_db", "ensure_indexes",
    "TOKEN_COSTS", "DEFAULT_TOOL_COST", "cost_for_tool",
    "signup_anti_bot_check",
    "create_signup", "verify_otp", "award_referral_bonus",
    "issue_jwt", "decode_dev_jwt", "get_account",
    "encrypt_byok", "decrypt_byok", "save_byok_keys",
    "deduct_tokens", "enforce_token_wall",
    "check_abuse_pattern", "check_rate_limit",
    "validate_pixel_domain",
    "cleanup_inactive_sandboxes",
    "_send_welcome_email", "_welcome_email_html",
]
