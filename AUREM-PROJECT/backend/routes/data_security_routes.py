"""
Data Security Routes for Reroots
GDPR compliance, data retention, and security endpoints.

Features:
- GDPR data deletion endpoint
- Data retention policy
- Monthly cleanup cron job
- Audit logging
"""

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import hashlib
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customer", tags=["customer-security"])

# Database reference
_db = None


def set_db(database):
    """Set database reference"""
    global _db
    _db = database


class DeleteDataRequest(BaseModel):
    email: EmailStr
    confirmation: str  # Must be "DELETE MY DATA"


class DeleteDataResponse(BaseModel):
    deleted: bool
    collections_cleared: int
    timestamp: str
    email_hash: str


# ============================================================
# GDPR DATA DELETION ENDPOINT
# ============================================================

@router.get("/delete-my-data")
async def delete_customer_data_get(
    request: Request,
    email: str = Query(..., description="Email address to delete")
):
    """
    GDPR Compliance: Delete all customer data by email (GET method for simplicity).
    
    Collections cleared:
    - reroots_customer_profiles
    - reroots_chat_sessions
    - reroots_chat_messages
    - ai_audit_log
    
    Returns deletion confirmation with email hash for records.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    email = email.lower().strip()
    
    # Validate email format
    if '@' not in email or '.' not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    deleted_counts = {}
    collections_cleared = 0
    
    try:
        # 1. Delete from reroots_customer_profiles
        result = await _db.reroots_customer_profiles.delete_many({"customer_email": email})
        deleted_counts["reroots_customer_profiles"] = result.deleted_count
        if result.deleted_count > 0:
            collections_cleared += 1
        
        # Also try alternate field name
        result2 = await _db.reroots_customer_profiles.delete_many({"email": email})
        deleted_counts["reroots_customer_profiles"] += result2.deleted_count
        
        # 2. Delete from reroots_chat_sessions
        result = await _db.reroots_chat_sessions.delete_many({"customer_email": email})
        deleted_counts["reroots_chat_sessions"] = result.deleted_count
        if result.deleted_count > 0:
            collections_cleared += 1
        
        # 3. Delete from reroots_chat_messages
        result = await _db.reroots_chat_messages.delete_many({"customer_email": email})
        deleted_counts["reroots_chat_messages"] = result.deleted_count
        if result.deleted_count > 0:
            collections_cleared += 1
        
        # 4. Delete from ai_audit_log
        result = await _db.ai_audit_log.delete_many({"email": email})
        deleted_counts["ai_audit_log"] = result.deleted_count
        if result.deleted_count > 0:
            collections_cleared += 1
        
        # Also check reroots_ai_audit
        result = await _db.reroots_ai_audit.delete_many({"email": email})
        deleted_counts["reroots_ai_audit"] = result.deleted_count
        
        # Generate email hash for audit log (never store the actual email)
        email_hash = hashlib.sha256(email.encode()).hexdigest()[:16]
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Log the deletion to gdpr_deletion_log (only hash + timestamp)
        await _db.gdpr_deletion_log.insert_one({
            "email_hash": email_hash,
            "timestamp": timestamp,
            "ip_address_hash": hashlib.sha256(
                (request.client.host or "unknown").encode()
            ).hexdigest()[:16],
            "collections_cleared": collections_cleared,
            "record_counts": deleted_counts
        })
        
        logger.info(f"[GDPR] Data deletion completed for hash:{email_hash} - {collections_cleared} collections")
        
        return DeleteDataResponse(
            deleted=True,
            collections_cleared=collections_cleared,
            timestamp=timestamp,
            email_hash=email_hash
        )
        
    except Exception as e:
        logger.error(f"[GDPR] Data deletion failed: {e}")
        raise HTTPException(status_code=500, detail="Deletion failed - please contact support")


@router.post("/delete-my-data")
async def delete_customer_data_post(request: Request, body: DeleteDataRequest):
    """
    GDPR Compliance: Delete all customer data by email (POST method with confirmation).
    Customer must confirm by typing "DELETE MY DATA".
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    if body.confirmation != "DELETE MY DATA":
        raise HTTPException(
            status_code=400, 
            detail="Please type 'DELETE MY DATA' to confirm deletion"
        )
    
    # Delegate to GET handler
    return await delete_customer_data_get(request, email=body.email)


@router.get("/data-retention-policy")
async def get_data_retention_policy():
    """Get the data retention policy information."""
    return {
        "policy": {
            "chat_sessions": "90 days - automatically deleted",
            "customer_profiles": "Until deletion requested via GDPR endpoint",
            "orders": "7 years (Canadian tax law requirement)",
            "ai_audit_logs": "180 days - automatically deleted",
            "auto_heal_logs": "30 days - automatically deleted",
            "security_logs": "1 year"
        },
        "gdpr_rights": [
            "Right to access your data",
            "Right to rectification",
            "Right to erasure (use /api/customer/delete-my-data)",
            "Right to data portability",
            "Right to object to processing"
        ],
        "contact": "privacy@reroots.ca",
        "data_location": "Canada (MongoDB Atlas)",
        "encryption": "AES-256 for sensitive fields"
    }


# ============================================================
# DATA RETENTION CRON JOB
# Runs 1st of every month at 2am EST
# ============================================================

async def run_monthly_data_cleanup() -> dict:
    """
    Monthly data retention cleanup job.
    
    Deletes:
    - reroots_chat_sessions older than 90 days
    - ai_audit_log older than 180 days
    - auto_heal_log older than 30 days
    
    Logs results to maintenance_log and sends WhatsApp summary.
    """
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    now = datetime.now(timezone.utc)
    results = {
        "timestamp": now.isoformat(),
        "deletions": {}
    }
    
    try:
        # 1. Delete chat sessions older than 90 days
        cutoff_90 = now - timedelta(days=90)
        result = await _db.reroots_chat_sessions.delete_many({
            "created_at": {"$lt": cutoff_90.isoformat()}
        })
        results["deletions"]["chat_sessions_90d"] = result.deleted_count
        
        # Also try datetime format
        result2 = await _db.reroots_chat_sessions.delete_many({
            "created_at": {"$lt": cutoff_90}
        })
        results["deletions"]["chat_sessions_90d"] += result2.deleted_count
        
        # 2. Delete ai_audit_log older than 180 days
        cutoff_180 = now - timedelta(days=180)
        result = await _db.ai_audit_log.delete_many({
            "timestamp": {"$lt": cutoff_180.isoformat()}
        })
        results["deletions"]["ai_audit_180d"] = result.deleted_count
        
        result2 = await _db.reroots_ai_audit.delete_many({
            "timestamp": {"$lt": cutoff_180.isoformat()}
        })
        results["deletions"]["ai_audit_180d"] += result2.deleted_count
        
        # 3. Delete auto_heal_log older than 30 days
        cutoff_30 = now - timedelta(days=30)
        result = await _db.auto_heal_log.delete_many({
            "timestamp": {"$lt": cutoff_30.isoformat()}
        })
        results["deletions"]["auto_heal_30d"] = result.deleted_count
        
        # Calculate totals
        total_deleted = sum(results["deletions"].values())
        results["total_deleted"] = total_deleted
        results["success"] = True
        
        # Log to maintenance_log
        await _db.maintenance_log.insert_one({
            "job": "monthly_data_cleanup",
            "timestamp": now.isoformat(),
            "results": results["deletions"],
            "total_deleted": total_deleted
        })
        
        logger.info(f"[DATA_RETENTION] Monthly cleanup completed: {total_deleted} records deleted")
        
        # Send WhatsApp summary
        try:
            from services.twilio_service import send_whatsapp_message
            admin_phone = os.environ.get("ADMIN_WHATSAPP", "+14168869408")
            message = (
                f"Monthly cleanup completed:\n"
                f"- Chat sessions: {results['deletions'].get('chat_sessions_90d', 0)}\n"
                f"- Audit logs: {results['deletions'].get('ai_audit_180d', 0)}\n"
                f"- Auto-heal logs: {results['deletions'].get('auto_heal_30d', 0)}\n"
                f"Total: {total_deleted} records"
            )
            await send_whatsapp_message(admin_phone, message)
        except Exception as e:
            logger.warning(f"[DATA_RETENTION] WhatsApp notification failed: {e}")
        
        return results
        
    except Exception as e:
        logger.error(f"[DATA_RETENTION] Monthly cleanup failed: {e}")
        return {"success": False, "error": str(e)}


async def cleanup_old_chat_sessions(days: int = 90):
    """Delete chat sessions older than specified days."""
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    try:
        result = await _db.reroots_chat_sessions.delete_many({
            "created_at": {"$lt": cutoff.isoformat()}
        })
        
        logger.info(f"[SECURITY] Cleaned up {result.deleted_count} old chat sessions")
        
        return {
            "success": True,
            "deleted": result.deleted_count,
            "cutoff_date": cutoff.isoformat()
        }
        
    except Exception as e:
        logger.error(f"[SECURITY] Cleanup failed: {e}")
        return {"success": False, "error": str(e)}


async def cleanup_old_audit_logs(days: int = 180):
    """Delete AI audit logs older than specified days."""
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    try:
        result = await _db.ai_audit_log.delete_many({
            "timestamp": {"$lt": cutoff.isoformat()}
        })
        
        result2 = await _db.reroots_ai_audit.delete_many({
            "timestamp": {"$lt": cutoff.isoformat()}
        })
        
        total = result.deleted_count + result2.deleted_count
        logger.info(f"[SECURITY] Cleaned up {total} old audit logs")
        
        return {
            "success": True,
            "deleted": total
        }
        
    except Exception as e:
        logger.error(f"[SECURITY] Audit log cleanup failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# ADMIN ENDPOINT - View deletion logs (for compliance audits)
# ============================================================

@router.get("/admin/gdpr-logs")
async def get_gdpr_logs(limit: int = Query(50, le=200)):
    """
    Admin endpoint: Get GDPR deletion logs for compliance audits.
    Returns only email hashes, never actual emails.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    try:
        logs = await _db.gdpr_deletion_log.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return {
            "logs": logs,
            "count": len(logs),
            "note": "Email addresses are hashed for privacy - original emails not stored"
        }
        
    except Exception as e:
        logger.error(f"[GDPR] Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve logs")
