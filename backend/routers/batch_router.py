"""
ReRoots Batch Tracking Router
=============================
Provides batch verification and COA (Certificate of Analysis) lookup
for product authenticity and lab data transparency.
"""

from fastapi import APIRouter, HTTPException
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
            ph_level=batch_data.get("ph_level"),
            pdrn_concentration=batch_data.get("pdrn_concentration"),
            stability_score=batch_data.get("stability_score"),
            status=batch_data.get("status"),
            lab_notes=batch_data.get("lab_notes"),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    # Not found
    return BatchLookupResponse(
        found=False,
        message=f"Batch '{batch_id}' not found. Please check your batch ID and try again.",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/sample-ids")
async def get_sample_batch_ids():
    """
    Get a list of sample batch IDs for testing.
    This endpoint is for development/demo purposes.
    """
    return {
        "sample_batch_ids": list(SAMPLE_BATCHES.keys()),
        "note": "Use these IDs to test the batch verification feature",
        "april_19_batches": ["APR19-V4", "APR19-V3"]
    }


class BatchRecord(BaseModel):
    """Model for creating/updating batch records."""
    batch_id: str
    product: str
    production_date: str
    expiry_date: str
    ph_level: str
    pdrn_concentration: Optional[str] = "N/A"
    stability_score: str
    status: str = "verified"
    lab_notes: Optional[str] = ""
    additional_data: Optional[Dict] = {}


@router.post("/admin/create")
async def create_batch_record(batch: BatchRecord):
    """
    Admin endpoint to create a new batch record.
    This is used when new production batches are completed.
    """
    try:
        db = get_db()
        
        # Check if batch already exists
        existing = db.batch_records.find_one({"batch_id": batch.batch_id.upper()})
        if existing:
            raise HTTPException(status_code=400, detail=f"Batch {batch.batch_id} already exists")
        
        # Create record
        record = {
            "batch_id": batch.batch_id.upper(),
            "product": batch.product,
            "production_date": batch.production_date,
            "expiry_date": batch.expiry_date,
            "ph_level": batch.ph_level,
            "pdrn_concentration": batch.pdrn_concentration,
            "stability_score": batch.stability_score,
            "status": batch.status,
            "lab_notes": batch.lab_notes,
            "additional_data": batch.additional_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "admin"
        }
        
        db.batch_records.insert_one(record)
        
        return {
            "success": True,
            "message": f"Batch {batch.batch_id} created successfully",
            "batch_id": batch.batch_id.upper()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")


@router.get("/admin/list")
async def list_batch_records():
    """
    Admin endpoint to list all batch records.
    """
    try:
        db = get_db()
        batches = list(db.batch_records.find({}, {"_id": 0}).sort("created_at", -1).limit(100))
        
        # Also include sample batches count
        return {
            "database_batches": batches,
            "sample_batches_available": len(SAMPLE_BATCHES),
            "total": len(batches) + len(SAMPLE_BATCHES)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list batches: {str(e)}")
