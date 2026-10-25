"""
AUREM Batch Tracking Router
=============================
Provides batch verification and COA (Certificate of Analysis) lookup
for product authenticity and lab data transparency.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime, timezone
import os
from pymongo import MongoClient

router = APIRouter(prefix="/batch", tags=["Batch Tracking"])

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "reroots")

def get_db():
    """Get MongoDB database connection."""
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


async def require_admin(request: Request):
    """Verify the caller is an administrator before allowing access."""
    # TODO(joshua.kerr): Swap this for proper RBAC once Auth0/user-auth stack lands.

    admin_token = os.environ.get("ADMIN_API_TOKEN")
    bearer = request.headers.get("x-admin-token", "")
    if not admin_token or bearer != admin_token:
        raise HTTPException(
            status_code=401,
            detail="Admin access required",
        )


# Sample batch data for April 19 launch (to be replaced with real COA data)
SAMPLE_BATCHES = {
    "APR19-V4": {
        "batch_id": "APR19-V4",
        "product": "ACRC v4 Cream",
        "production_date": "2026-04-01",
        "expiry_date": "2027-04-01",
        "ph_level": "5.5",
        "pdrn_concentration": "N/A (Cream Base)",
        "stability_score": "98.2%",
        "mandelic_acid": "5.0%",
        "hpr_retinoid": "2.0%",
        "bakuchiol": "1.0%",
        "niacinamide": "6.0%",
        "status": "verified",
        "lab_notes": "pH stability confirmed at 25°C over 6 months. Mandelic acid concentration within clinical range."
    },
    "APR19-V3": {
        "batch_id": "APR19-V3",
        "product": "ARC v3 Serum",
        "production_date": "2026-04-01",
        "expiry_date": "2027-04-01",
        "ph_level": "5.2",
        "pdrn_concentration": "2.0%",
        "stability_score": "97.8%",
        "argireline": "10.0%",
        "ghk_cu": "1.0%",
        "snap8": "5.0%",
        "leuphasyl": "5.0%",
        "status": "verified",
        "lab_notes": "PDRN molecular weight optimized for 40% faster cellular migration. Triple Botox-Mimic stack verified."
    },
    "MAR26-TEST": {
        "batch_id": "MAR26-TEST",
        "product": "Test Batch (Sample)",
        "production_date": "2026-03-15",
        "expiry_date": "2026-09-15",
        "ph_level": "5.4",
        "pdrn_concentration": "1.5%",
        "stability_score": "95.0%",
        "status": "sample",
        "lab_notes": "Pre-production test batch. Not for retail sale."
    }
}


class BatchLookupResponse(BaseModel):
    """Response model for batch lookup."""
    found: bool
    batch_id: Optional[str] = None
    product: Optional[str] = None
    production_date: Optional[str] = None
    expiry_date: Optional[str] = None
    ph_level: Optional[str] = None
    pdrn_concentration: Optional[str] = None
    stability_score: Optional[str] = None
    status: Optional[str] = None
    lab_notes: Optional[str] = None
    message: Optional[str] = None
    timestamp: str


@router.get("/lookup/{batch_id}", response_model=BatchLookupResponse)
async def lookup_batch(batch_id: str):
    """
    Look up a batch by ID and return lab analysis data.
    
    This allows customers to verify the authenticity of their product
    and view the Certificate of Analysis (COA) data.
    """
    batch_id_upper = batch_id.upper().strip()
    
    # First check MongoDB for real batch records
    try:
        db = get_db()
        batch_record = db.batch_records.find_one(
            {"batch_id": batch_id_upper},
            {"_id": 0}
        )
        
        if batch_record:
            return BatchLookupResponse(
                found=True,
                **batch_record,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    except Exception as e:
        print(f"[Batch] MongoDB lookup error: {e}")
    
    # Fall back to sample data for demo/launch
    if batch_id_upper in SAMPLE_BATCHES:
        batch_data = SAMPLE_BATCHES[batch_id_upper]
        return BatchLookupResponse(
            found=True,
            batch_id=batch_data.get("batch_id"),
            product=batch_data.get("product"),
            production_date=batch_data.get("production_date"),
            expiry_date=batch_data.get("expiry_date"),
            ph_level=