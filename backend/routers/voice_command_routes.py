"""
AUREM Voice Command API
"Hi Aurem" Wake-Word Interface
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["Voice Commands"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceCommandRequest(BaseModel):
    transcript: str
    business_id: str = "ABC-001"


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/command")
async def process_voice_command(
    request: VoiceCommandRequest,
    user = Depends(get_current_user)
):
    """
    Process "Hi Ora" voice command
    
    Commands:
    - "what's the revenue today?"
    - "show me the leads"
    - "recover those carts"
    - "sync the system"
    - "are there any bugs?"
    
    Returns:
        {
            "understood": bool,
            "command": str,
            "response_text": str,  # For TTS
            "response_data": dict,  # For UI
            "ui_navigation": str,   # Where to navigate
            "success": bool
        }
    """
    from services.voice_wake_word import get_voice_processor
    
    processor = get_voice_processor(db)
    
    result = await processor.process_voice_command(
        transcript=request.transcript,
        business_id=request.business_id,
        user_id=user["user_id"]
    )
    
    return result


@router.get("/commands")
async def list_available_commands():
    """Get list of available voice commands"""
    from services.voice_wake_word import VoiceCommand
    
    commands = {
        "wake_word": "Hi Ora",
        "commands": [
            {
                "command": VoiceCommand.REVENUE_TODAY.value,
                "examples": [
                    "what's the revenue today?",
                    "show me today's sales",
                    "how much money did we make?"
                ]
            },
            {
                "command": VoiceCommand.SYSTEM_STATUS.value,
                "examples": [
                    "what's the system status?",
                    "are all systems healthy?",
                    "check the health"
                ]
            },
            {
                "command": VoiceCommand.LATEST_LEADS.value,
                "examples": [
                    "show me the leads",
                    "what are the latest leads?",
                    "find me prospects"
                ]
            },
            {
                "command": VoiceCommand.RECOVER_CARTS.value,
                "examples": [
                    "recover those carts",
                    "send cart recovery messages",
                    "follow up on abandoned carts"
                ]
            },
            {
                "command": VoiceCommand.BUG_REPORT.value,
                "examples": [
                    "are there any bugs?",
                    "show me the errors",
                    "what issues do we have?"
                ]
            },
            {
                "command": VoiceCommand.CIRCUIT_BREAKERS.value,
                "examples": [
                    "check the circuit breakers",
                    "show me the breakers",
                    "are services running?"
                ]
            },
            {
                "command": VoiceCommand.PENDING_WORK.value,
                "examples": [
                    "what's pending?",
                    "show me the tasks",
                    "what do I need to do?"
                ]
            },
            {
                "command": VoiceCommand.SYNC_SYSTEM.value,
                "examples": [
                    "sync the system",
                    "refresh everything",
                    "update the system"
                ]
            }
        ]
    }
    
    return commands


print("[STARTUP] Voice Command Routes loaded (Hi Ora)")
