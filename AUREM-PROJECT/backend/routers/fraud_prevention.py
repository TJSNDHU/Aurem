"""
Fraud Prevention API - Free Features
- Email validation (disposable email detection)
- IP risk analysis (VPN/Proxy/TOR detection)
- Device fingerprinting
- Order velocity checks
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import httpx
import hashlib
import os

router = APIRouter(prefix="/api/fraud", tags=["Fraud Prevention"])

# MongoDB setup
from pymongo import MongoClient
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "reroots")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections
fraud_checks = db["fraud_checks"]
device_fingerprints = db["device_fingerprints"]
order_velocity = db["order_velocity"]
blocked_entities = db["blocked_entities"]

# ============ DISPOSABLE EMAIL DOMAINS ============
# Common disposable/temporary email domains (expandable list)
DISPOSABLE_DOMAINS = {
    "tempmail.com", "throwaway.email", "guerrillamail.com", "mailinator.com",
    "10minutemail.com", "temp-mail.org", "fakeinbox.com", "trashmail.com",
    "getnada.com", "mohmal.com", "tempail.com", "emailondeck.com",
    "dispostable.com", "mailnesia.com", "tempr.email", "discard.email",
    "maildrop.cc", "yopmail.com", "sharklasers.com", "spam4.me",
    "grr.la", "guerrillamailblock.com", "pokemail.net", "spamgourmet.com",
    "mytemp.email", "mt2015.com", "thankyou2010.com", "trash-mail.at",
    "wegwerfmail.de", "wegwerfmail.net", "wegwerfmail.org", "spam.la",
    "spamfree24.org", "spamfree24.de", "spamfree24.eu", "spamfree24.info",
    "getairmail.com", "tempinbox.com", "fakemailgenerator.com", "tempmailaddress.com",
    "burnermail.io", "mailsac.com", "inboxkitten.com", "33mail.com",
    "anonaddy.com", "simplelogin.io", "duck.com", "relay.firefox.com",
    # Add more as needed
}

# Suspicious email patterns
SUSPICIOUS_PATTERNS = [
    "test", "fake", "spam", "temp", "trash", "junk", "throw",
    "disposable", "random", "asdf", "qwerty", "12345"
]


# ============ MODELS ============
class EmailCheckRequest(BaseModel):
    email: str

class IPCheckRequest(BaseModel):
    ip: Optional[str] = None  # If not provided, use request IP

class DeviceFingerprintRequest(BaseModel):
    fingerprint: str
    user_agent: str
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None

class VelocityCheckRequest(BaseModel):
    email: str
    ip: str
    device_fingerprint: Optional[str] = None
    order_value: Optional[float] = 0

class FraudCheckResponse(BaseModel):
    is_risky: bool
    risk_score: int  # 0-100
    risk_factors: List[str]
    recommendation: str  # "allow", "review", "block"


# ============ EMAIL VALIDATION ============
@router.post("/check-email", response_model=FraudCheckResponse)
async def check_email(data: EmailCheckRequest):
    """
    Check if email is potentially fraudulent:
    - Disposable email detection
    - Suspicious pattern detection
    - Domain validation
    """
    email = data.email.lower().strip()
    risk_factors = []
    risk_score = 0
    
    # Check if already blocked
    if blocked_entities.find_one({"type": "email", "value": email}):
        return FraudCheckResponse(
            is_risky=True,
            risk_score=100,
            risk_factors=["Email is blocked"],
            recommendation="block"
        )
    
    # Extract domain
    try:
        domain = email.split("@")[1]
    except IndexError:
        return FraudCheckResponse(
            is_risky=True,
            risk_score=100,
            risk_factors=["Invalid email format"],
            recommendation="block"
        )
    
    # Check disposable domains
    if domain in DISPOSABLE_DOMAINS:
        risk_factors.append(f"Disposable email domain: {domain}")
        risk_score += 80
    
    # Check for suspicious patterns in email
    local_part = email.split("@")[0]
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in local_part.lower():
            risk_factors.append(f"Suspicious pattern in email: {pattern}")
            risk_score += 20
            break
    
    # Check for excessive numbers (e.g., user123456789@...)
    import re
    numbers = re.findall(r'\d+', local_part)
    if numbers and len(''.join(numbers)) > 6:
        risk_factors.append("Excessive numbers in email")
        risk_score += 15
    
    # Check for very short local part
    if len(local_part) < 3:
        risk_factors.append("Very short email username")
        risk_score += 10
    
    # Check domain MX records (basic check via DNS)
    try:
        import socket
        socket.gethostbyname(domain)
    except socket.gaierror:
        risk_factors.append("Email domain does not exist")
        risk_score += 90
    
    # Determine recommendation
    if risk_score >= 80:
        recommendation = "block"
    elif risk_score >= 40:
        recommendation = "review"
    else:
        recommendation = "allow"
    
    # Log the check
    fraud_checks.insert_one({
        "type": "email",
        "value": email,
        "risk_score": min(risk_score, 100),
        "risk_factors": risk_factors,
        "recommendation": recommendation,
        "timestamp": datetime.utcnow()
    })
    
    return FraudCheckResponse(
        is_risky=risk_score >= 40,
        risk_score=min(risk_score, 100),
        risk_factors=risk_factors if risk_factors else ["No issues found"],
        recommendation=recommendation
    )


# ============ IP RISK ANALYSIS ============
@router.post("/check-ip", response_model=FraudCheckResponse)
async def check_ip(request: Request, data: IPCheckRequest):
    """
    Check IP for fraud indicators:
    - VPN/Proxy detection
    - TOR exit node detection
    - Datacenter IP detection
    - Geolocation analysis
    """
    # Get IP from request if not provided
    ip = data.ip or request.client.host
    
    # Handle localhost/private IPs
    if ip in ["127.0.0.1", "localhost", "::1"] or ip.startswith("192.168.") or ip.startswith("10."):
        return FraudCheckResponse(
            is_risky=False,
            risk_score=0,
            risk_factors=["Local/private IP - skipping check"],
            recommendation="allow"
        )
    
    # Check if already blocked
    if blocked_entities.find_one({"type": "ip", "value": ip}):
        return FraudCheckResponse(
            is_risky=True,
            risk_score=100,
            risk_factors=["IP is blocked"],
            recommendation="block"
        )
    
    risk_factors = []
    risk_score = 0
    geo_data = {}
    
    # Use free IP-API for geolocation and proxy detection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # ip-api.com - free tier (45 requests/minute)
            response = await client.get(
                f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,city,isp,org,as,proxy,hosting,query"
            )
            if response.status_code == 200:
                geo_data = response.json()
                
                if geo_data.get("status") == "success":
                    # Check if proxy/VPN
                    if geo_data.get("proxy", False):
                        risk_factors.append("VPN/Proxy detected")
                        risk_score += 50
                    
                    # Check if hosting/datacenter IP
                    if geo_data.get("hosting", False):
                        risk_factors.append("Datacenter/Hosting IP detected")
                        risk_score += 40
                    
                    # Check for suspicious ISPs
                    isp = geo_data.get("isp", "").lower()
                    suspicious_isps = ["tor", "vpn", "proxy", "anonymous", "hide", "mask"]
                    for s in suspicious_isps:
                        if s in isp:
                            risk_factors.append(f"Suspicious ISP: {geo_data.get('isp')}")
                            risk_score += 30
                            break
    except Exception as e:
        print(f"IP check API error: {e}")
        # Don't block on API failure
    
    # Additional check using ipinfo.io (free tier)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://ipinfo.io/{ip}/json")
            if response.status_code == 200:
                ipinfo_data = response.json()
                
                # Check for bogon (invalid public IP)
                if ipinfo_data.get("bogon", False):
                    risk_factors.append("Invalid/Bogon IP address")
                    risk_score += 60
                
                # Store org for reference
                org = ipinfo_data.get("org", "")
                if any(kw in org.lower() for kw in ["vpn", "proxy", "tor", "hosting"]):
                    if "VPN/Proxy detected" not in risk_factors:
                        risk_factors.append(f"Suspicious organization: {org}")
                        risk_score += 35
    except Exception as e:
        print(f"IPInfo check error: {e}")
    
    # Determine recommendation
    if risk_score >= 70:
        recommendation = "block"
    elif risk_score >= 30:
        recommendation = "review"
    else:
        recommendation = "allow"
    
    # Log the check
    fraud_checks.insert_one({
        "type": "ip",
        "value": ip,
        "risk_score": min(risk_score, 100),
        "risk_factors": risk_factors,
        "geo_data": geo_data,
        "recommendation": recommendation,
        "timestamp": datetime.utcnow()
    })
    
    return FraudCheckResponse(
        is_risky=risk_score >= 30,
        risk_score=min(risk_score, 100),
        risk_factors=risk_factors if risk_factors else ["No issues found"],
        recommendation=recommendation
    )


# ============ DEVICE FINGERPRINTING ============
@router.post("/register-device")
async def register_device(request: Request, data: DeviceFingerprintRequest):
    """
    Register and analyze device fingerprint for fraud patterns
    """
    ip = request.client.host
    
    # Check if this fingerprint is already associated with blocked accounts
    blocked_device = blocked_entities.find_one({
        "type": "device",
        "value": data.fingerprint
    })
    
    if blocked_device:
        return {
            "status": "blocked",
            "message": "Device is blocked",
            "risk_score": 100
        }
    
    # Check how many accounts use this device
    existing = list(device_fingerprints.find({
        "fingerprint": data.fingerprint
    }))
    
    risk_factors = []
    risk_score = 0
    
    # Multiple accounts from same device
    unique_emails = set(d.get("email") for d in existing if d.get("email"))
    if len(unique_emails) > 3:
        risk_factors.append(f"Device used by {len(unique_emails)} different accounts")
        risk_score += 40
    
    # Check for rapid account creation
    recent_registrations = [
        d for d in existing 
        if d.get("timestamp") and d["timestamp"] > datetime.utcnow() - timedelta(hours=24)
    ]
    if len(recent_registrations) > 2:
        risk_factors.append("Multiple accounts created from this device in 24h")
        risk_score += 50
    
    # Store fingerprint
    device_fingerprints.update_one(
        {"fingerprint": data.fingerprint, "email": data.email},
        {
            "$set": {
                "fingerprint": data.fingerprint,
                "user_agent": data.user_agent,
                "screen_resolution": data.screen_resolution,
                "timezone": data.timezone,
                "language": data.language,
                "platform": data.platform,
                "user_id": data.user_id,
                "email": data.email,
                "ip": ip,
                "timestamp": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    return {
        "status": "registered",
        "is_risky": risk_score >= 30,
        "risk_score": min(risk_score, 100),
        "risk_factors": risk_factors if risk_factors else ["Device looks clean"],
        "recommendation": "block" if risk_score >= 70 else "review" if risk_score >= 30 else "allow"
    }


# ============ ORDER VELOCITY CHECK ============
@router.post("/velocity-check", response_model=FraudCheckResponse)
async def velocity_check(request: Request, data: VelocityCheckRequest):
    """
    Check order velocity for fraud patterns:
    - Too many orders from same email/IP/device
    - Unusual order patterns
    - High-value orders from new accounts
    """
    risk_factors = []
    risk_score = 0
    
    now = datetime.utcnow()
    time_windows = {
        "1_hour": timedelta(hours=1),
        "24_hours": timedelta(hours=24),
        "7_days": timedelta(days=7)
    }
    
    # Check email velocity
    for window_name, window in time_windows.items():
        email_orders = order_velocity.count_documents({
            "email": data.email,
            "timestamp": {"$gte": now - window}
        })
        
        limits = {"1_hour": 3, "24_hours": 10, "7_days": 30}
        if email_orders >= limits[window_name]:
            risk_factors.append(f"High order velocity: {email_orders} orders from email in {window_name}")
            risk_score += 30
    
    # Check IP velocity
    for window_name, window in time_windows.items():
        ip_orders = order_velocity.count_documents({
            "ip": data.ip,
            "timestamp": {"$gte": now - window}
        })
        
        limits = {"1_hour": 5, "24_hours": 15, "7_days": 50}
        if ip_orders >= limits[window_name]:
            risk_factors.append(f"High order velocity: {ip_orders} orders from IP in {window_name}")
            risk_score += 25
    
    # Check device velocity if provided
    if data.device_fingerprint:
        for window_name, window in time_windows.items():
            device_orders = order_velocity.count_documents({
                "device_fingerprint": data.device_fingerprint,
                "timestamp": {"$gte": now - window}
            })
            
            limits = {"1_hour": 3, "24_hours": 8, "7_days": 25}
            if device_orders >= limits[window_name]:
                risk_factors.append(f"High order velocity: {device_orders} orders from device in {window_name}")
                risk_score += 35
    
    # Check for high-value order from new account
    first_order = order_velocity.find_one(
        {"email": data.email},
        sort=[("timestamp", 1)]
    )
    
    if not first_order and data.order_value and data.order_value > 200:
        risk_factors.append(f"High-value first order: ${data.order_value}")
        risk_score += 25
    
    # Record this velocity check
    order_velocity.insert_one({
        "email": data.email,
        "ip": data.ip,
        "device_fingerprint": data.device_fingerprint,
        "order_value": data.order_value,
        "timestamp": now
    })
    
    # Determine recommendation
    if risk_score >= 60:
        recommendation = "block"
    elif risk_score >= 25:
        recommendation = "review"
    else:
        recommendation = "allow"
    
    return FraudCheckResponse(
        is_risky=risk_score >= 25,
        risk_score=min(risk_score, 100),
        risk_factors=risk_factors if risk_factors else ["Order velocity normal"],
        recommendation=recommendation
    )


# ============ COMPREHENSIVE FRAUD CHECK ============
@router.post("/full-check")
async def full_fraud_check(request: Request, email: str, device_fingerprint: Optional[str] = None, order_value: Optional[float] = 0):
    """
    Run all fraud checks and return combined risk assessment
    """
    ip = request.client.host
    
    results = {
        "email_check": None,
        "ip_check": None,
        "velocity_check": None,
        "combined_risk_score": 0,
        "risk_factors": [],
        "recommendation": "allow"
    }
    
    # Email check
    email_result = await check_email(EmailCheckRequest(email=email))
    results["email_check"] = email_result.dict()
    results["combined_risk_score"] += email_result.risk_score * 0.3
    if email_result.risk_factors != ["No issues found"]:
        results["risk_factors"].extend(email_result.risk_factors)
    
    # IP check
    ip_result = await check_ip(request, IPCheckRequest(ip=ip))
    results["ip_check"] = ip_result.dict()
    results["combined_risk_score"] += ip_result.risk_score * 0.4
    if ip_result.risk_factors != ["No issues found"]:
        results["risk_factors"].extend(ip_result.risk_factors)
    
    # Velocity check
    velocity_result = await velocity_check(request, VelocityCheckRequest(
        email=email,
        ip=ip,
        device_fingerprint=device_fingerprint,
        order_value=order_value
    ))
    results["velocity_check"] = velocity_result.dict()
    results["combined_risk_score"] += velocity_result.risk_score * 0.3
    if velocity_result.risk_factors != ["Order velocity normal"]:
        results["risk_factors"].extend(velocity_result.risk_factors)
    
    # Round combined score
    results["combined_risk_score"] = round(results["combined_risk_score"])
    
    # Determine final recommendation
    if results["combined_risk_score"] >= 60:
        results["recommendation"] = "block"
    elif results["combined_risk_score"] >= 30:
        results["recommendation"] = "review"
    else:
        results["recommendation"] = "allow"
    
    if not results["risk_factors"]:
        results["risk_factors"] = ["All checks passed"]
    
    return results


# ============ ADMIN ENDPOINTS ============
@router.get("/admin/recent-checks")
async def get_recent_fraud_checks(limit: int = 50):
    """Get recent fraud checks for admin review"""
    checks = list(fraud_checks.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit))
    
    return {"checks": checks}


@router.get("/admin/high-risk")
async def get_high_risk_entities(min_score: int = 50):
    """Get entities with high risk scores"""
    high_risk = list(fraud_checks.find(
        {"risk_score": {"$gte": min_score}},
        {"_id": 0}
    ).sort("risk_score", -1).limit(100))
    
    return {"high_risk_entities": high_risk}


@router.post("/admin/block")
async def block_entity(entity_type: str, value: str, reason: str = "Manual block"):
    """Block an email, IP, or device"""
    if entity_type not in ["email", "ip", "device"]:
        raise HTTPException(status_code=400, detail="Invalid entity type")
    
    blocked_entities.update_one(
        {"type": entity_type, "value": value},
        {
            "$set": {
                "type": entity_type,
                "value": value,
                "reason": reason,
                "blocked_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    return {"status": "blocked", "type": entity_type, "value": value}


@router.delete("/admin/unblock")
async def unblock_entity(entity_type: str, value: str):
    """Unblock an entity"""
    result = blocked_entities.delete_one({"type": entity_type, "value": value})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entity not found in blocklist")
    
    return {"status": "unblocked", "type": entity_type, "value": value}


@router.get("/admin/blocked")
async def get_blocked_entities():
    """Get all blocked entities"""
    blocked = list(blocked_entities.find({}, {"_id": 0}))
    return {"blocked_entities": blocked}


@router.get("/admin/stats")
async def get_fraud_stats():
    """Get fraud prevention statistics"""
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    
    stats = {
        "total_checks_24h": fraud_checks.count_documents({"timestamp": {"$gte": day_ago}}),
        "total_checks_7d": fraud_checks.count_documents({"timestamp": {"$gte": week_ago}}),
        "blocked_24h": fraud_checks.count_documents({
            "timestamp": {"$gte": day_ago},
            "recommendation": "block"
        }),
        "review_24h": fraud_checks.count_documents({
            "timestamp": {"$gte": day_ago},
            "recommendation": "review"
        }),
        "blocked_entities": blocked_entities.count_documents({}),
        "unique_devices": device_fingerprints.count_documents({}),
        "by_type": {
            "email": fraud_checks.count_documents({"type": "email", "timestamp": {"$gte": week_ago}}),
            "ip": fraud_checks.count_documents({"type": "ip", "timestamp": {"$gte": week_ago}})
        }
    }
    
    return stats
