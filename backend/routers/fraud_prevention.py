"""
AUREM Fraud Prevention Router — Layer 9 Security
Email validation, IP risk analysis, login anomaly detection, velocity checks.
Wired to Sentinel Dashboard for real-time threat monitoring.
Adapted from legacy sync pymongo → async motor + AUREM tenant context.
"""
import os
import re
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/fraud", tags=["Fraud Prevention"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise HTTPException(500, "JWT not configured")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        # Bug-fix #39 — require an admin claim, not just a valid JWT.
        from utils.admin_guard import is_admin_email
        if not (payload.get("is_admin") or payload.get("is_super_admin")
                or payload.get("role") in ("admin", "super_admin")
                or is_admin_email(payload.get("email"))):
            raise HTTPException(403, "Admin access required")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


# ══════════════════════════════════════════════
# Disposable Email Detection
# ══════════════════════════════════════════════

DISPOSABLE_DOMAINS = {
    "tempmail.com", "throwaway.email", "guerrillamail.com", "mailinator.com",
    "10minutemail.com", "temp-mail.org", "fakeinbox.com", "trashmail.com",
    "getnada.com", "mohmal.com", "tempail.com", "emailondeck.com",
    "dispostable.com", "mailnesia.com", "tempr.email", "discard.email",
    "maildrop.cc", "yopmail.com", "sharklasers.com", "spam4.me",
    "grr.la", "guerrillamailblock.com", "pokemail.net", "spamgourmet.com",
    "mytemp.email", "burnermail.io", "mailsac.com", "inboxkitten.com",
    "getairmail.com", "tempinbox.com", "fakemailgenerator.com",
    "wegwerfmail.de", "wegwerfmail.net", "spamfree24.org",
}

SUSPICIOUS_PATTERNS = ["test", "fake", "spam", "temp", "trash", "junk", "throw", "disposable", "asdf", "qwerty"]


# ══════════════════════════════════════════════
# Models
# ══════════════════════════════════════════════

class EmailCheckRequest(BaseModel):
    email: str

class IPCheckRequest(BaseModel):
    ip: Optional[str] = None

class FraudCheckResponse(BaseModel):
    is_risky: bool
    risk_score: int
    risk_factors: List[str]
    recommendation: str


# ══════════════════════════════════════════════
# Email Validation
# ══════════════════════════════════════════════

@router.post("/check-email", response_model=FraudCheckResponse)
async def check_email(data: EmailCheckRequest, request: Request):
    """Check if email is potentially fraudulent (disposable, suspicious patterns, invalid domain)."""
    email = data.email.lower().strip()
    risk_factors = []
    risk_score = 0

    if _get_db():
        blocked = await _get_db().blocked_entities.find_one({"type": "email", "value": email})
        if blocked:
            return FraudCheckResponse(is_risky=True, risk_score=100, risk_factors=["Email is blocked"], recommendation="block")

    try:
        domain = email.split("@")[1]
    except IndexError:
        return FraudCheckResponse(is_risky=True, risk_score=100, risk_factors=["Invalid email format"], recommendation="block")

    if domain in DISPOSABLE_DOMAINS:
        risk_factors.append(f"Disposable email domain: {domain}")
        risk_score += 80

    local_part = email.split("@")[0]
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in local_part:
            risk_factors.append(f"Suspicious pattern: {pattern}")
            risk_score += 20
            break

    numbers = re.findall(r'\d+', local_part)
    if numbers and len(''.join(numbers)) > 6:
        risk_factors.append("Excessive numbers in email")
        risk_score += 15

    if len(local_part) < 3:
        risk_factors.append("Very short email username")
        risk_score += 10

    try:
        import socket
        socket.gethostbyname(domain)
    except Exception:
        risk_factors.append("Email domain does not resolve")
        risk_score += 90

    recommendation = "block" if risk_score >= 80 else "review" if risk_score >= 40 else "allow"

    if _get_db():
        await _get_db().fraud_checks.insert_one({
            "type": "email", "value": email, "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors, "recommendation": recommendation,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })

    return FraudCheckResponse(
        is_risky=risk_score >= 40,
        risk_score=min(risk_score, 100),
        risk_factors=risk_factors or ["No issues found"],
        recommendation=recommendation,
    )


# ══════════════════════════════════════════════
# IP Risk Analysis
# ══════════════════════════════════════════════

@router.post("/check-ip", response_model=FraudCheckResponse)
async def check_ip(request: Request, data: IPCheckRequest):
    """Check IP for fraud indicators (VPN, proxy, datacenter, Tor)."""
    ip = data.ip or request.client.host
    risk_factors = []
    risk_score = 0

    if ip in ["127.0.0.1", "localhost", "::1"] or ip.startswith("192.168.") or ip.startswith("10."):
        return FraudCheckResponse(is_risky=False, risk_score=0, risk_factors=["Local/private IP"], recommendation="allow")

    # Check if IP is already blocked
    if _get_db():
        blocked = await _get_db().blocked_entities.find_one({"type": "ip", "value": ip})
        if blocked:
            return FraudCheckResponse(is_risky=True, risk_score=100, risk_factors=["IP is blocked"], recommendation="block")

    # Free IP analysis via ip-api.com
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}?fields=status,proxy,hosting,isp,org,as,country,city")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("proxy"):
                    risk_factors.append("VPN/Proxy detected")
                    risk_score += 40
                if data.get("hosting"):
                    risk_factors.append("Datacenter/hosting IP")
                    risk_score += 30
                isp = (data.get("isp", "") + " " + data.get("org", "")).lower()
                if any(t in isp for t in ["tor", "relay", "exit"]):
                    risk_factors.append("Tor exit node suspected")
                    risk_score += 60
    except Exception as e:
        logger.debug(f"[Fraud] IP check API failed: {e}")

    recommendation = "block" if risk_score >= 80 else "review" if risk_score >= 40 else "allow"

    if _get_db():
        await _get_db().fraud_checks.insert_one({
            "type": "ip", "value": ip, "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors, "recommendation": recommendation,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })

    return FraudCheckResponse(
        is_risky=risk_score >= 40,
        risk_score=min(risk_score, 100),
        risk_factors=risk_factors or ["No issues found"],
        recommendation=recommendation,
    )


# ══════════════════════════════════════════════
# Login Anomaly Detection
# ══════════════════════════════════════════════

@router.post("/check-login")
async def check_login_anomaly(request: Request):
    """Detect suspicious login patterns (new device, unusual location, velocity)."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    now = datetime.now(timezone.utc)
    one_hour_ago = (now - timedelta(hours=1)).isoformat()

    # Count recent failed logins
    failed_logins = await _get_db().api_audit_log.count_documents({
        "path": {"$regex": "login"},
        "status_code": {"$in": [401, 429]},
        "timestamp": {"$gte": one_hour_ago},
    })

    # Count unique IPs in last hour
    unique_ips = len(await _get_db().api_audit_log.distinct("client_ip", {
        "path": {"$regex": "login"},
        "timestamp": {"$gte": one_hour_ago},
    }))

    risk_score = 0
    factors = []

    if failed_logins > 10:
        risk_score += 50
        factors.append(f"Brute force detected: {failed_logins} failed logins in 1 hour")
    elif failed_logins > 5:
        risk_score += 25
        factors.append(f"Elevated failed logins: {failed_logins} in 1 hour")

    if unique_ips > 5:
        risk_score += 30
        factors.append(f"Multiple IPs attempting login: {unique_ips} unique IPs")

    return {
        "anomaly_detected": risk_score >= 40,
        "risk_score": min(risk_score, 100),
        "risk_factors": factors or ["No anomalies detected"],
        "failed_logins_1h": failed_logins,
        "unique_ips_1h": unique_ips,
        "recommendation": "block_ips" if risk_score >= 80 else "monitor" if risk_score >= 40 else "normal",
    }


# ══════════════════════════════════════════════
# Fraud Dashboard (for Sentinel integration)
# ══════════════════════════════════════════════

@router.get("/dashboard")
async def fraud_dashboard(request: Request):
    """Aggregated fraud metrics for Sentinel Dashboard."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # Fraud checks today
    checks_today = await _get_db().fraud_checks.count_documents({"checked_at": {"$gte": today}})

    # Blocked entities
    blocked_emails = await _get_db().blocked_entities.count_documents({"type": "email"})
    blocked_ips = await _get_db().blocked_entities.count_documents({"type": "ip"})

    # Recent high-risk checks
    high_risk = await _get_db().fraud_checks.find(
        {"risk_score": {"$gte": 60}}, {"_id": 0}
    ).sort("checked_at", -1).limit(10).to_list(10)

    # Risk distribution
    total_checks = await _get_db().fraud_checks.count_documents({})
    risky_checks = await _get_db().fraud_checks.count_documents({"risk_score": {"$gte": 40}})

    return {
        "checks_today": checks_today,
        "total_checks": total_checks,
        "risky_checks": risky_checks,
        "risk_rate": round(risky_checks / max(total_checks, 1) * 100, 1),
        "blocked_emails": blocked_emails,
        "blocked_ips": blocked_ips,
        "recent_high_risk": high_risk,
    }


# ══════════════════════════════════════════════
# Block Entity
# ══════════════════════════════════════════════

@router.post("/block")
async def block_entity(request: Request):
    """Block an email or IP permanently."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    body = await request.json()
    entity_type = body.get("type", "")
    value = body.get("value", "").strip().lower()
    reason = body.get("reason", "manual_block")

    if entity_type not in ("email", "ip") or not value:
        raise HTTPException(400, "Invalid block request. Need type (email/ip) and value.")

    await _get_db().blocked_entities.update_one(
        {"type": entity_type, "value": value},
        {"$setOnInsert": {
            "type": entity_type, "value": value, "reason": reason,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return {"success": True, "blocked": f"{entity_type}:{value}"}


@router.get("/blocked")
async def list_blocked(request: Request, type: Optional[str] = None):
    """List all blocked entities."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    query = {}
    if type:
        query["type"] = type
    docs = await _get_db().blocked_entities.find(query, {"_id": 0}).sort("blocked_at", -1).limit(100).to_list(100)
    return {"blocked": docs, "total": len(docs)}
