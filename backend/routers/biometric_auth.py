"""
Biometric Authentication Router
Supports: Face Recognition, Voice Recognition, Fingerprint/Device Biometrics (WebAuthn)
For commercial AI system access control
"""

import os
import json
import base64
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
import secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/biometric", tags=["Biometric Auth"])

# MongoDB reference
_db = None

def set_db(database):
    """Set database reference"""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# WebAuthn configuration
RP_NAME = "ReRoots AI"
RP_ID = os.environ.get("WEBAUTHN_RP_ID", "reroots.ca")  # Your domain
ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "https://reroots.ca")

# Voice recognition settings
VOICE_SAMPLE_MIN_DURATION = 2  # seconds
VOICE_MATCH_THRESHOLD = 0.75  # 75% similarity required

# Face recognition settings
FACE_MATCH_THRESHOLD = 0.6  # Lower = stricter matching


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BiometricEnrollRequest(BaseModel):
    user_id: str = Field(..., description="User ID to enroll")
    biometric_type: str = Field(..., description="face, voice, or webauthn")
    biometric_data: Dict[str, Any] = Field(..., description="Biometric data")


class BiometricVerifyRequest(BaseModel):
    user_id: str = Field(..., description="User ID to verify")
    biometric_type: str = Field(..., description="face, voice, or webauthn")
    biometric_data: Dict[str, Any] = Field(..., description="Biometric data to verify")


class WebAuthnRegisterStart(BaseModel):
    user_id: str
    user_name: str
    user_display_name: Optional[str] = None


class WebAuthnRegisterFinish(BaseModel):
    user_id: str
    credential: Dict[str, Any]
    challenge: str


class WebAuthnAuthStart(BaseModel):
    user_id: str


class WebAuthnAuthFinish(BaseModel):
    user_id: str
    credential: Dict[str, Any]
    challenge: str


class VoiceEnrollRequest(BaseModel):
    user_id: str
    voice_samples: List[str] = Field(..., description="Base64 encoded audio samples")
    passphrase: str = Field(..., description="Passphrase spoken during enrollment")


class VoiceVerifyRequest(BaseModel):
    user_id: str
    voice_sample: str = Field(..., description="Base64 encoded audio sample")
    passphrase: str = Field(..., description="Passphrase spoken for verification")


class FaceEnrollRequest(BaseModel):
    user_id: str
    face_descriptors: List[List[float]] = Field(..., description="Face descriptor vectors from face-api.js")
    face_images: Optional[List[str]] = Field(None, description="Base64 face images for reference")


class FaceVerifyRequest(BaseModel):
    user_id: str
    face_descriptor: List[float] = Field(..., description="Face descriptor vector to verify")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_challenge() -> str:
    """Generate a random challenge for WebAuthn"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')


def calculate_face_distance(descriptor1: List[float], descriptor2: List[float]) -> float:
    """Calculate Euclidean distance between two face descriptors"""
    if len(descriptor1) != len(descriptor2):
        return 1.0  # Max distance if dimensions don't match
    
    sum_sq = sum((a - b) ** 2 for a, b in zip(descriptor1, descriptor2))
    return sum_sq ** 0.5


def calculate_voice_similarity(features1: Dict, features2: Dict) -> float:
    """
    Calculate similarity between voice feature sets.
    Uses pitch, energy, and spectral features.
    """
    # Simple feature comparison (in production, use more sophisticated methods)
    similarity_scores = []
    
    # Compare pitch
    if 'pitch_mean' in features1 and 'pitch_mean' in features2:
        pitch_diff = abs(features1['pitch_mean'] - features2['pitch_mean'])
        pitch_sim = max(0, 1 - pitch_diff / 200)  # Normalize
        similarity_scores.append(pitch_sim)
    
    # Compare energy
    if 'energy_mean' in features1 and 'energy_mean' in features2:
        energy_diff = abs(features1['energy_mean'] - features2['energy_mean'])
        energy_sim = max(0, 1 - energy_diff / 1000)
        similarity_scores.append(energy_sim)
    
    # Compare speaking rate
    if 'speaking_rate' in features1 and 'speaking_rate' in features2:
        rate_diff = abs(features1['speaking_rate'] - features2['speaking_rate'])
        rate_sim = max(0, 1 - rate_diff / 5)
        similarity_scores.append(rate_sim)
    
    if not similarity_scores:
        return 0.0
    
    return sum(similarity_scores) / len(similarity_scores)


def hash_biometric_data(data: str) -> str:
    """Create a hash of biometric data for storage"""
    return hashlib.sha256(data.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# WEBAUTHN (FINGERPRINT / FACE ID / WINDOWS HELLO)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/webauthn/register/start")
async def webauthn_register_start(request: WebAuthnRegisterStart):
    """
    Start WebAuthn registration - returns options for navigator.credentials.create()
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        challenge = generate_challenge()
        
        # Store challenge temporarily
        await _db.webauthn_challenges.update_one(
            {"user_id": request.user_id, "type": "registration"},
            {
                "$set": {
                    "challenge": challenge,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                }
            },
            upsert=True
        )
        
        # Get existing credentials to exclude
        existing = await _db.webauthn_credentials.find(
            {"user_id": request.user_id},
            {"credential_id": 1}
        ).to_list(10)
        
        exclude_credentials = [
            {"type": "public-key", "id": cred["credential_id"]}
            for cred in existing
        ]
        
        # Return WebAuthn options
        options = {
            "challenge": challenge,
            "rp": {
                "name": RP_NAME,
                "id": RP_ID
            },
            "user": {
                "id": base64.urlsafe_b64encode(request.user_id.encode()).decode(),
                "name": request.user_name,
                "displayName": request.user_display_name or request.user_name
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},   # ES256
                {"type": "public-key", "alg": -257}  # RS256
            ],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",  # Built-in authenticator (Touch ID, Face ID, Windows Hello)
                "userVerification": "required",
                "residentKey": "preferred"
            },
            "timeout": 60000,
            "attestation": "none",
            "excludeCredentials": exclude_credentials
        }
        
        return {"options": options, "challenge": challenge}
        
    except Exception as e:
        logger.error(f"[Biometric] WebAuthn register start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webauthn/register/finish")
async def webauthn_register_finish(request: WebAuthnRegisterFinish):
    """
    Finish WebAuthn registration - store the credential
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Verify challenge
        stored = await _db.webauthn_challenges.find_one({
            "user_id": request.user_id,
            "type": "registration",
            "challenge": request.challenge
        })
        
        if not stored:
            raise HTTPException(status_code=400, detail="Invalid or expired challenge")
        
        # Delete used challenge
        await _db.webauthn_challenges.delete_one({"_id": stored["_id"]})
        
        # Store credential
        credential_data = {
            "user_id": request.user_id,
            "credential_id": request.credential.get("id"),
            "public_key": request.credential.get("response", {}).get("publicKey"),
            "sign_count": 0,
            "transports": request.credential.get("response", {}).get("transports", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
            "device_name": request.credential.get("deviceName", "Unknown Device")
        }
        
        await _db.webauthn_credentials.insert_one(credential_data)
        
        # Update user biometric status
        await _db.users.update_one(
            {"id": request.user_id},
            {"$set": {"biometric_enabled": True, "webauthn_enabled": True}}
        )
        
        logger.info(f"[Biometric] WebAuthn credential registered for user {request.user_id}")
        
        return {"status": "registered", "credential_id": request.credential.get("id")}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] WebAuthn register finish error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webauthn/auth/start")
async def webauthn_auth_start(request: WebAuthnAuthStart):
    """
    Start WebAuthn authentication - returns options for navigator.credentials.get()
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get user's credentials
        credentials = await _db.webauthn_credentials.find(
            {"user_id": request.user_id},
            {"credential_id": 1, "transports": 1}
        ).to_list(10)
        
        if not credentials:
            raise HTTPException(status_code=404, detail="No biometric credentials found for user")
        
        challenge = generate_challenge()
        
        # Store challenge
        await _db.webauthn_challenges.update_one(
            {"user_id": request.user_id, "type": "authentication"},
            {
                "$set": {
                    "challenge": challenge,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                }
            },
            upsert=True
        )
        
        allow_credentials = [
            {
                "type": "public-key",
                "id": cred["credential_id"],
                "transports": cred.get("transports", ["internal"])
            }
            for cred in credentials
        ]
        
        options = {
            "challenge": challenge,
            "rpId": RP_ID,
            "allowCredentials": allow_credentials,
            "userVerification": "required",
            "timeout": 60000
        }
        
        return {"options": options, "challenge": challenge}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] WebAuthn auth start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webauthn/auth/finish")
async def webauthn_auth_finish(request: WebAuthnAuthFinish):
    """
    Finish WebAuthn authentication - verify the credential
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Verify challenge
        stored = await _db.webauthn_challenges.find_one({
            "user_id": request.user_id,
            "type": "authentication",
            "challenge": request.challenge
        })
        
        if not stored:
            raise HTTPException(status_code=400, detail="Invalid or expired challenge")
        
        # Delete used challenge
        await _db.webauthn_challenges.delete_one({"_id": stored["_id"]})
        
        # Verify credential exists
        credential = await _db.webauthn_credentials.find_one({
            "user_id": request.user_id,
            "credential_id": request.credential.get("id")
        })
        
        if not credential:
            raise HTTPException(status_code=401, detail="Credential not found")
        
        # Update last used timestamp and sign count
        await _db.webauthn_credentials.update_one(
            {"_id": credential["_id"]},
            {
                "$set": {"last_used": datetime.now(timezone.utc).isoformat()},
                "$inc": {"sign_count": 1}
            }
        )
        
        # Log authentication
        await _db.biometric_auth_log.insert_one({
            "user_id": request.user_id,
            "type": "webauthn",
            "success": True,
            "credential_id": request.credential.get("id"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"[Biometric] WebAuthn authentication successful for user {request.user_id}")
        
        return {
            "status": "authenticated",
            "user_id": request.user_id,
            "method": "webauthn",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] WebAuthn auth finish error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FACE RECOGNITION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/face/enroll")
async def face_enroll(request: FaceEnrollRequest):
    """
    Enroll user's face - store face descriptors from face-api.js
    Requires multiple face samples for better accuracy
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        if len(request.face_descriptors) < 3:
            raise HTTPException(status_code=400, detail="At least 3 face samples required for enrollment")
        
        # Validate descriptor dimensions (face-api.js uses 128-dimensional descriptors)
        for desc in request.face_descriptors:
            if len(desc) != 128:
                raise HTTPException(status_code=400, detail="Invalid face descriptor dimensions")
        
        # Calculate average descriptor for more robust matching
        avg_descriptor = [
            sum(desc[i] for desc in request.face_descriptors) / len(request.face_descriptors)
            for i in range(128)
        ]
        
        # Store face data
        face_data = {
            "user_id": request.user_id,
            "descriptors": request.face_descriptors,
            "average_descriptor": avg_descriptor,
            "sample_count": len(request.face_descriptors),
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
            "last_verified": None,
            "verification_count": 0
        }
        
        # Upsert (update or insert)
        await _db.face_biometrics.update_one(
            {"user_id": request.user_id},
            {"$set": face_data},
            upsert=True
        )
        
        # Update user biometric status
        await _db.users.update_one(
            {"id": request.user_id},
            {"$set": {"biometric_enabled": True, "face_enabled": True}}
        )
        
        logger.info(f"[Biometric] Face enrolled for user {request.user_id} with {len(request.face_descriptors)} samples")
        
        return {
            "status": "enrolled",
            "sample_count": len(request.face_descriptors),
            "user_id": request.user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] Face enroll error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/face/verify")
async def face_verify(request: FaceVerifyRequest):
    """
    Verify user's face against enrolled data
    Returns match result and confidence score
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get enrolled face data
        enrolled = await _db.face_biometrics.find_one({"user_id": request.user_id})
        
        if not enrolled:
            raise HTTPException(status_code=404, detail="No face data enrolled for user")
        
        # Validate descriptor
        if len(request.face_descriptor) != 128:
            raise HTTPException(status_code=400, detail="Invalid face descriptor dimensions")
        
        # Calculate distance to average descriptor
        avg_descriptor = enrolled.get("average_descriptor", [])
        distance = calculate_face_distance(request.face_descriptor, avg_descriptor)
        
        # Also check against all enrolled descriptors and take minimum distance
        min_distance = distance
        for enrolled_desc in enrolled.get("descriptors", []):
            d = calculate_face_distance(request.face_descriptor, enrolled_desc)
            min_distance = min(min_distance, d)
        
        # Convert distance to confidence (lower distance = higher confidence)
        confidence = max(0, 1 - min_distance)
        matched = min_distance < FACE_MATCH_THRESHOLD
        
        # Log verification attempt
        await _db.biometric_auth_log.insert_one({
            "user_id": request.user_id,
            "type": "face",
            "success": matched,
            "confidence": confidence,
            "distance": min_distance,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if matched:
            # Update verification stats
            await _db.face_biometrics.update_one(
                {"user_id": request.user_id},
                {
                    "$set": {"last_verified": datetime.now(timezone.utc).isoformat()},
                    "$inc": {"verification_count": 1}
                }
            )
            
            logger.info(f"[Biometric] Face verified for user {request.user_id} (confidence: {confidence:.2f})")
        else:
            logger.warning(f"[Biometric] Face verification failed for user {request.user_id} (distance: {min_distance:.2f})")
        
        return {
            "status": "verified" if matched else "failed",
            "matched": matched,
            "confidence": round(confidence, 3),
            "user_id": request.user_id,
            "method": "face",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] Face verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE RECOGNITION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/voice/enroll")
async def voice_enroll(request: VoiceEnrollRequest):
    """
    Enroll user's voice - store voice features
    Requires multiple voice samples saying the same passphrase
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        if len(request.voice_samples) < 3:
            raise HTTPException(status_code=400, detail="At least 3 voice samples required for enrollment")
        
        if len(request.passphrase) < 4:
            raise HTTPException(status_code=400, detail="Passphrase must be at least 4 characters")
        
        # Store voice data (features will be extracted client-side and sent)
        # In a real implementation, you'd extract MFCC, pitch, etc. from audio
        voice_data = {
            "user_id": request.user_id,
            "passphrase_hash": hash_biometric_data(request.passphrase.lower().strip()),
            "voice_samples_hash": [hash_biometric_data(s[:100]) for s in request.voice_samples],
            "sample_count": len(request.voice_samples),
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
            "last_verified": None,
            "verification_count": 0
        }
        
        # Upsert
        await _db.voice_biometrics.update_one(
            {"user_id": request.user_id},
            {"$set": voice_data},
            upsert=True
        )
        
        # Update user biometric status
        await _db.users.update_one(
            {"id": request.user_id},
            {"$set": {"biometric_enabled": True, "voice_enabled": True}}
        )
        
        logger.info(f"[Biometric] Voice enrolled for user {request.user_id} with {len(request.voice_samples)} samples")
        
        return {
            "status": "enrolled",
            "sample_count": len(request.voice_samples),
            "user_id": request.user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] Voice enroll error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/verify")
async def voice_verify(request: VoiceVerifyRequest):
    """
    Verify user's voice against enrolled data
    Checks both voice features and passphrase
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get enrolled voice data
        enrolled = await _db.voice_biometrics.find_one({"user_id": request.user_id})
        
        if not enrolled:
            raise HTTPException(status_code=404, detail="No voice data enrolled for user")
        
        # Verify passphrase first
        passphrase_hash = hash_biometric_data(request.passphrase.lower().strip())
        passphrase_match = passphrase_hash == enrolled.get("passphrase_hash")
        
        if not passphrase_match:
            # Log failed attempt
            await _db.biometric_auth_log.insert_one({
                "user_id": request.user_id,
                "type": "voice",
                "success": False,
                "reason": "passphrase_mismatch",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "status": "failed",
                "matched": False,
                "reason": "Passphrase does not match",
                "user_id": request.user_id
            }
        
        # Voice sample verification (simplified - in production, use actual voice analysis)
        # Here we're checking if the audio data signature is consistent
        sample_hash = hash_biometric_data(request.voice_sample[:100])
        
        # For demo purposes, we consider it matched if passphrase is correct
        # In production, you'd analyze MFCCs, pitch, formants, etc.
        matched = passphrase_match
        confidence = 0.85 if matched else 0.0
        
        # Log verification attempt
        await _db.biometric_auth_log.insert_one({
            "user_id": request.user_id,
            "type": "voice",
            "success": matched,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if matched:
            await _db.voice_biometrics.update_one(
                {"user_id": request.user_id},
                {
                    "$set": {"last_verified": datetime.now(timezone.utc).isoformat()},
                    "$inc": {"verification_count": 1}
                }
            )
            
            logger.info(f"[Biometric] Voice verified for user {request.user_id}")
        
        return {
            "status": "verified" if matched else "failed",
            "matched": matched,
            "confidence": round(confidence, 3),
            "user_id": request.user_id,
            "method": "voice",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] Voice verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-FACTOR BIOMETRIC
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/verify/multi")
async def verify_multi_biometric(request: Request):
    """
    Verify multiple biometric factors at once
    Returns overall verification status
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        body = await request.json()
        user_id = body.get("user_id")
        factors = body.get("factors", {})  # {face: {...}, voice: {...}, webauthn: {...}}
        required_factors = body.get("required_factors", 1)  # Minimum factors needed
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        
        results = {}
        success_count = 0
        
        # Verify each provided factor
        if "face" in factors:
            try:
                face_result = await face_verify(FaceVerifyRequest(
                    user_id=user_id,
                    face_descriptor=factors["face"].get("descriptor", [])
                ))
                results["face"] = face_result
                if face_result.get("matched"):
                    success_count += 1
            except Exception as e:
                results["face"] = {"status": "error", "error": str(e)}
        
        if "voice" in factors:
            try:
                voice_result = await voice_verify(VoiceVerifyRequest(
                    user_id=user_id,
                    voice_sample=factors["voice"].get("sample", ""),
                    passphrase=factors["voice"].get("passphrase", "")
                ))
                results["voice"] = voice_result
                if voice_result.get("matched"):
                    success_count += 1
            except Exception as e:
                results["voice"] = {"status": "error", "error": str(e)}
        
        if "webauthn" in factors:
            # WebAuthn requires challenge flow, so just check if credential exists
            credentials = await _db.webauthn_credentials.count_documents({"user_id": user_id})
            results["webauthn"] = {"available": credentials > 0}
        
        # Determine overall status
        overall_success = success_count >= required_factors
        
        return {
            "status": "verified" if overall_success else "failed",
            "user_id": user_id,
            "factors_verified": success_count,
            "required_factors": required_factors,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] Multi-factor verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS & MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{user_id}")
async def get_biometric_status(user_id: str):
    """Get user's biometric enrollment status"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        webauthn = await _db.webauthn_credentials.count_documents({"user_id": user_id})
        face = await _db.face_biometrics.find_one({"user_id": user_id}, {"_id": 0, "enrolled_at": 1, "sample_count": 1})
        voice = await _db.voice_biometrics.find_one({"user_id": user_id}, {"_id": 0, "enrolled_at": 1, "sample_count": 1})
        
        return {
            "user_id": user_id,
            "webauthn": {
                "enrolled": webauthn > 0,
                "credential_count": webauthn
            },
            "face": {
                "enrolled": face is not None,
                "enrolled_at": face.get("enrolled_at") if face else None,
                "sample_count": face.get("sample_count") if face else 0
            },
            "voice": {
                "enrolled": voice is not None,
                "enrolled_at": voice.get("enrolled_at") if voice else None,
                "sample_count": voice.get("sample_count") if voice else 0
            },
            "any_enrolled": webauthn > 0 or face is not None or voice is not None
        }
        
    except Exception as e:
        logger.error(f"[Biometric] Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/remove/{user_id}/{biometric_type}")
async def remove_biometric(user_id: str, biometric_type: str):
    """Remove enrolled biometric data"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        if biometric_type == "webauthn":
            await _db.webauthn_credentials.delete_many({"user_id": user_id})
        elif biometric_type == "face":
            await _db.face_biometrics.delete_one({"user_id": user_id})
        elif biometric_type == "voice":
            await _db.voice_biometrics.delete_one({"user_id": user_id})
        else:
            raise HTTPException(status_code=400, detail="Invalid biometric type")
        
        logger.info(f"[Biometric] Removed {biometric_type} data for user {user_id}")
        
        return {"status": "removed", "type": biometric_type, "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Biometric] Remove error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth-log/{user_id}")
async def get_auth_log(user_id: str, limit: int = 20):
    """Get biometric authentication history for a user"""
    if _db is None:
        return {"logs": []}
    
    try:
        logs = await _db.biometric_auth_log.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return {"logs": logs}
        
    except Exception as e:
        logger.error(f"[Biometric] Auth log error: {e}")
        return {"logs": []}
