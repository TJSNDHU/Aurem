"""
Biometric Authentication System
- Stores face descriptors in MongoDB (persistent across devices)
- PIN backup for fallback authentication
- Secure biometric data management
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import bcrypt
from datetime import datetime
import numpy as np

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BiometricSetupRequest(BaseModel):
    email: str
    face_descriptor: List[float]  # 128-dimensional face embedding
    pin: str  # 4-6 digit PIN

class BiometricVerifyFaceRequest(BaseModel):
    email: str
    face_descriptor: List[float]

class BiometricVerifyPinRequest(BaseModel):
    email: str
    pin: str

class BiometricResponse(BaseModel):
    success: bool
    message: str
    email: Optional[str] = None

# ═══════════════════════════════════════════════════════════════════════════════
# BIOMETRIC SETUP (During Signup)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/biometric/setup", response_model=BiometricResponse)
async def setup_biometric(request: BiometricSetupRequest):
    """
    Store user's biometric data (face descriptor + PIN) in MongoDB
    Called after user signs up with email/password
    """
    try:
        from server import db
        
        # Validate PIN (4-6 digits)
        if not request.pin.isdigit() or len(request.pin) < 4 or len(request.pin) > 6:
            raise HTTPException(status_code=400, detail="PIN must be 4-6 digits")
        
        # Validate face descriptor
        if len(request.face_descriptor) != 128:
            raise HTTPException(status_code=400, detail="Invalid face descriptor")
        
        # Hash the PIN
        pin_hash = bcrypt.hashpw(request.pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Check if user exists
        user = await db.users.find_one({"email": request.email}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Store biometric data
        biometric_data = {
            "face_descriptor": request.face_descriptor,
            "pin_hash": pin_hash,
            "setup_date": datetime.utcnow().isoformat(),
            "enabled": True
        }
        
        # Update user document
        result = await db.users.update_one(
            {"email": request.email},
            {"$set": {"biometric": biometric_data}}
        )
        
        if result.modified_count > 0:
            return BiometricResponse(
                success=True,
                message="Biometric authentication setup successful",
                email=request.email
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save biometric data")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Biometric Setup] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# FACE VERIFICATION (Login Attempt)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/biometric/verify-face", response_model=BiometricResponse)
async def verify_face(request: BiometricVerifyFaceRequest):
    """
    Verify face descriptor against stored biometric data
    Returns success if face matches within threshold
    """
    try:
        from server import db
        
        # Get user's stored biometric data
        user = await db.users.find_one({"email": request.email}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if "biometric" not in user or not user["biometric"].get("enabled"):
            raise HTTPException(status_code=400, detail="Biometric not setup for this user")
        
        stored_descriptor = user["biometric"]["face_descriptor"]
        
        # Calculate Euclidean distance
        stored = np.array(stored_descriptor)
        current = np.array(request.face_descriptor)
        distance = np.linalg.norm(stored - current)
        
        # Threshold: 0.6 is standard for face-api.js
        # Lower distance = better match
        if distance < 0.6:
            confidence = round((1 - distance) * 100, 2)
            return BiometricResponse(
                success=True,
                message=f"Face verified (confidence: {confidence}%)",
                email=request.email
            )
        else:
            confidence = round((1 - distance) * 100, 2)
            return BiometricResponse(
                success=False,
                message=f"Face not recognized (confidence: {confidence}%)"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Face Verify] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PIN VERIFICATION (Fallback Authentication)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/biometric/verify-pin", response_model=BiometricResponse)
async def verify_pin(request: BiometricVerifyPinRequest):
    """
    Verify PIN as fallback when face recognition fails
    """
    try:
        from server import db
        
        # Get user's stored PIN hash
        user = await db.users.find_one({"email": request.email}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if "biometric" not in user or "pin_hash" not in user["biometric"]:
            raise HTTPException(status_code=400, detail="PIN not setup for this user")
        
        stored_pin_hash = user["biometric"]["pin_hash"]
        
        # Verify PIN
        if bcrypt.checkpw(request.pin.encode('utf-8'), stored_pin_hash.encode('utf-8')):
            return BiometricResponse(
                success=True,
                message="PIN verified successfully",
                email=request.email
            )
        else:
            return BiometricResponse(
                success=False,
                message="Incorrect PIN"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PIN Verify] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK BIOMETRIC STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/biometric/status/{email}")
async def biometric_status(email: str):
    """
    Check if user has biometric authentication enabled
    """
    try:
        from server import db
        
        user = await db.users.find_one({"email": email}, {"_id": 0, "biometric": 1})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        has_biometric = "biometric" in user and user["biometric"].get("enabled", False)
        
        return {
            "email": email,
            "biometric_enabled": has_biometric,
            "setup_date": user.get("biometric", {}).get("setup_date") if has_biometric else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Biometric Status] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
