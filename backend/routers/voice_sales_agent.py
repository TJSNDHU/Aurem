"""
AUREM AI Voice Sales Co-Pilot
Full custom DIY voice solution for production calls
"""

from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import asyncio
import json
import os
import jwt as pyjwt
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE — uses set_db pattern (no circular import from server)
# ═══════════════════════════════════════════════════════════════════════════════
_db = None

def set_db(database):
    global _db
    _db = database

def _get_db():
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _db

# ═══════════════════════════════════════════════════════════════════════════════
# VOICE TRAINING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceTrainingRequest(BaseModel):
    team_member_name: str
    team_member_id: str
    audio_samples: List[str]  # Base64 encoded audio samples

class VoiceProfile(BaseModel):
    profile_id: str
    team_member_name: str
    team_member_id: str
    voice_embedding: List[float]
    trained_at: str
    sample_count: int

@router.post("/api/voice/train")
async def train_team_voice(request: VoiceTrainingRequest, authorization: str = Header(None)):
    """
    Train AI to recognize team member's voice
    Records 5-10 voice samples and creates voice profile
    """
    try:
        import secrets
        
        db = _get_db()
        user = _get_current_user(authorization)
        
        profile_id = f"voice_{secrets.token_urlsafe(16)}"
        
        voice_profile = {
            "profile_id": profile_id,
            "team_member_name": request.team_member_name,
            "team_member_id": request.team_member_id,
            "tenant_id": user.get("tenant_id"),
            "audio_samples": request.audio_samples,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "sample_count": len(request.audio_samples),
            "active": True
        }
        
        await db.voice_profiles.insert_one(voice_profile)
        
        return {
            "success": True,
            "profile_id": profile_id,
            "message": f"Voice profile created for {request.team_member_name}",
            "samples_processed": len(request.audio_samples)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Voice Training] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/voice/profiles")
async def list_voice_profiles(authorization: str = Header(None)):
    """List all trained voice profiles for tenant"""
    try:
        db = _get_db()
        user = _get_current_user(authorization)
        tenant_id = user.get("tenant_id")
        
        profiles = await db.voice_profiles.find(
            {"tenant_id": tenant_id, "active": True},
            {"_id": 0, "audio_samples": 0}
        ).to_list(100)
        
        return {"profiles": profiles}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# AI SALES AGENT - Context-Aware
# ═══════════════════════════════════════════════════════════════════════════════

class SalesCallRequest(BaseModel):
    scan_id: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    call_type: str = "auto"  # auto, assisted, manual

class SalesCallContext:
    """AI agent context for sales calls"""
    
    def __init__(self, scan_data: dict, pricing_data: dict):
        self.scan_data = scan_data
        self.pricing_data = pricing_data
        self.conversation_history = []
        
    def get_opening_pitch(self) -> str:
        """Generate opening pitch based on scan results"""
        issues = self.scan_data.get('issues_found', 0)
        critical = self.scan_data.get('critical_issues', 0)
        savings = self.scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$1,500')
        
        return f"""Hello! I'm AUREM, an AI business automation assistant. 

I just completed a comprehensive scan of your website and found {issues} issues, 
including {critical} critical problems that are currently costing you approximately 
{savings} per month in lost productivity and inefficiencies.

I'd love to walk you through the findings and show you how we can fix these 
automatically. Do you have 5 minutes?"""
    
    def get_issue_presentation(self) -> str:
        """Present top issues"""
        recommendations = self.scan_data.get('recommendations', [])[:3]
        
        presentation = "Here are the top 3 critical issues:\n\n"
        for i, rec in enumerate(recommendations, 1):
            presentation += f"{i}. {rec['title']}\n"
            presentation += f"   Impact: {rec['description']}\n"
            presentation += f"   AUREM Solution: {rec['solution']}\n\n"
        
        return presentation
    
    def get_pricing_pitch(self) -> str:
        """Present pricing based on scan"""
        tier = self.pricing_data.get('recommended_tier', 'professional')
        monthly = self.pricing_data.get('pricing', {}).get('monthly_fee', 599)
        savings = self.pricing_data.get('comparison', {}).get('customer_saves', '$10,000')
        
        return f"""Based on your scan results, I recommend our {tier.title()} plan at 
${monthly} per month. 

Here's the value: You'll save {savings} in the first year, with break-even in 
Month {self.pricing_data.get('value_proposition', {}).get('break_even_month', 2)}.

We'll automate all {self.scan_data.get('issues_found', 0)} issues and save you 
{self.scan_data.get('aurem_impact', {}).get('estimated_time_saved_monthly', '60 hours')} 
every month.

Would you like me to send you a detailed proposal?"""
    
    def answer_question(self, question: str) -> str:
        """Answer customer questions intelligently"""
        q_lower = question.lower()
        
        # Pricing questions
        if any(word in q_lower for word in ['cost', 'price', 'how much', 'expensive']):
            return self.get_pricing_pitch()
        
        # Technical questions
        if any(word in q_lower for word in ['how does', 'technical', 'integrate', 'setup']):
            return """AUREM integrates seamlessly with your existing tech stack. 
We detected that you're using [list from deep scan], and we have native integrations 
for all of them. Setup takes 15 minutes - no coding required."""
        
        # ROI questions
        if any(word in q_lower for word in ['roi', 'return', 'savings', 'worth']):
            return f"""Great question! Based on your scan, you're currently losing 
{self.scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2,000')} 
per month. AUREM costs ${self.pricing_data.get('pricing', {}).get('monthly_fee', 599)}/month.

That's a {self.pricing_data.get('comparison', {}).get('value_multiple', '3.5x')} return 
on investment."""
        
        # Default intelligent response
        return "That's a great question! Let me connect you with our team member who can provide specific details on that."


@router.post("/api/voice/start-sales-call")
async def start_sales_call(request: SalesCallRequest, authorization: str = Header(None)):
    """
    Start AI-assisted sales call
    AI automatically presents scan results and handles conversation
    """
    try:
        import secrets
        
        db = _get_db()
        user = _get_current_user(authorization)
        
        # Get scan data
        scan = await db.system_scans.find_one({"scan_id": request.scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get pricing recommendation
        pricing_response = await _calculate_pricing_internal(request.scan_id)
        
        # Create AI context
        call_context = SalesCallContext(scan, pricing_response)
        
        # Generate call script
        call_script = {
            "opening": call_context.get_opening_pitch(),
            "issue_presentation": call_context.get_issue_presentation(),
            "pricing_pitch": call_context.get_pricing_pitch(),
            "objection_handlers": {
                "too_expensive": "I understand. But consider this: you're already spending [amount] on inefficiencies. AUREM actually saves you money.",
                "need_time": "Absolutely! I'll send you a detailed PDF report. When would be a good time to follow up?",
                "not_interested": "I appreciate your honesty. Can I ask - which of the [X] issues we found is NOT a concern for you?",
                "already_have_solution": "That's great! What we found is that most solutions handle pieces of the puzzle. AUREM consolidates [list integrations] into one platform."
            }
        }
        
        # Create call session
        call_id = f"call_{secrets.token_urlsafe(16)}"
        call_session = {
            "call_id": call_id,
            "scan_id": request.scan_id,
            "tenant_id": user.get("tenant_id"),
            "created_by": user.get("user_id"),
            "customer_email": request.customer_email,
            "customer_phone": request.customer_phone,
            "call_type": request.call_type,
            "call_script": call_script,
            "status": "active",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "conversation_log": []
        }
        
        await db.sales_calls.insert_one(call_session)
        
        return {
            "success": True,
            "call_id": call_id,
            "call_script": call_script,
            "scan_summary": {
                "issues": scan.get('issues_found'),
                "critical": scan.get('critical_issues'),
                "savings": scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Sales Call] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE CALL INTERFACE - WebSocket for Real-Time Communication
# ═══════════════════════════════════════════════════════════════════════════════

class CallSession:
    def __init__(self, call_id: str, context: SalesCallContext):
        self.call_id = call_id
        self.context = context
        self.active_speaker = None
        self.team_members = set()
        self.customer_speaking = False
        
    async def handle_speech(self, speaker_type: str, text: str):
        """Handle speech from different speakers"""
        self.context.conversation_history.append({
            "speaker": speaker_type,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # If customer asks question, AI should respond
        if speaker_type == "customer" and "?" in text:
            response = self.context.answer_question(text)
            return {
                "type": "ai_response",
                "text": response,
                "speaker": "ai"
            }
        
        return None

active_calls = {}

@router.websocket("/ws/voice/call/{call_id}")
async def websocket_call_handler(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint for live call handling
    Receives audio/text from team member and customer
    AI responds in real-time
    """
    await websocket.accept()
    
    try:
        db = _get_db()
        
        # Get call session
        call = await db.sales_calls.find_one({"call_id": call_id})
        if not call:
            await websocket.send_json({"error": "Call not found"})
            await websocket.close()
            return
        
        # Get scan and pricing data
        scan = await db.system_scans.find_one({"scan_id": call['scan_id']}, {"_id": 0})
        pricing = await _calculate_pricing_internal(call['scan_id'])
        
        # Create session
        context = SalesCallContext(scan, pricing)
        session = CallSession(call_id, context)
        active_calls[call_id] = session
        
        # Send initial AI greeting
        opening = context.get_opening_pitch()
        await websocket.send_json({
            "type": "ai_speech",
            "text": opening,
            "speaker": "ai"
        })
        
        # Listen for incoming messages
        while True:
            data = await websocket.receive_json()
            
            message_type = data.get('type')
            
            if message_type == 'speech':
                speaker = data.get('speaker')  # 'team', 'customer', 'ai'
                text = data.get('text')
                
                # Process speech
                response = await session.handle_speech(speaker, text)
                
                if response:
                    await websocket.send_json(response)
            
            elif message_type == 'end_call':
                # Save conversation log
                await db.sales_calls.update_one(
                    {"call_id": call_id},
                    {
                        "$set": {
                            "status": "completed",
                            "ended_at": datetime.now(timezone.utc).isoformat(),
                            "conversation_log": context.conversation_history
                        }
                    }
                )
                break
                
    except WebSocketDisconnect:
        if call_id in active_calls:
            del active_calls[call_id]
    except Exception as e:
        print(f"[WebSocket Call] Error: {e}")
        await websocket.send_json({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# AUREM DIY VOICE INTEGRATION (Self-Hosted Voice AI)
# ═══════════════════════════════════════════════════════════════════════════════

class DIYCallRequest(BaseModel):
    scan_id: str
    customer_phone: str
    assistant_voice: str = "Google UK English Female"  # Browser SpeechSynthesis voice

@router.post("/api/voice/diy/create-call")
async def create_diy_call(request: DIYCallRequest, authorization: str = Header(None)):
    """
    Create AI sales call using AUREM DIY voice engine.
    Uses browser Web Speech API + AUREM backend for AI responses.
    """
    try:
        import secrets as sec
        
        db = _get_db()
        user = _get_current_user(authorization)
        
        # Get scan data
        scan = await db.system_scans.find_one({"scan_id": request.scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get pricing
        pricing = await _calculate_pricing_internal(request.scan_id)
        
        # Create context
        context = SalesCallContext(scan, pricing)
        
        call_id = f"call_{sec.token_urlsafe(16)}"
        
        # DIY voice config — processed client-side via Web Speech API
        assistant_config = {
            "name": "AUREM Sales Agent",
            "firstMessage": context.get_opening_pitch(),
            "systemPrompt": f"""You are AUREM, an AI sales assistant. You just scanned the customer's website and found:

- {scan.get('issues_found')} total issues
- {scan.get('critical_issues')} critical issues  
- Estimated cost: {scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly')} per month

Your goal:
1. Present these findings professionally
2. Show them how AUREM can help
3. Recommend the {pricing.get('recommended_tier')} plan at ${pricing.get('pricing', {}).get('monthly_fee')}/month
4. Handle objections confidently
5. Book a demo or close the deal

Be consultative, not pushy. Focus on their pain points.""",
            "voice": {
                "provider": "browser",
                "name": request.assistant_voice,
            },
        }

        # Save call record
        await db.sales_calls.insert_one({
            "call_id": call_id,
            "scan_id": request.scan_id,
            "tenant_id": user.get("tenant_id"),
            "customer_phone": request.customer_phone,
            "provider": "aurem_diy",
            "assistant_config": assistant_config,
            "status": "ready",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "success": True,
            "call_id": call_id,
            "assistant_config": assistant_config,
            "engine": "aurem_diy",
            "status": "ready",
            "message": "AUREM DIY Voice call session created — connect via WebSocket to start",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DIY Call] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-OUTREACH SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/voice/auto-outreach")
async def auto_outreach_after_scan(scan_id: str, customer_contact: dict, authorization: str = Header(None)):
    """
    Automatically reach out to customer after scan
    AI calls/emails them with findings
    """
    try:
        db = _get_db()
        user = _get_current_user(authorization)
        
        # Get scan
        scan = await db.system_scans.find_one({"scan_id": scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        outreach_methods = []
        
        # Option 1: If phone provided, schedule DIY voice call
        if customer_contact.get('phone'):
            outreach_methods.append("voice_call")
        
        # Option 2: If email provided, send scan report
        if customer_contact.get('email'):
            # Send email with PDF report
            outreach_methods.append("email")
        
        # Create outreach record
        await db.outreach_attempts.insert_one({
            "scan_id": scan_id,
            "tenant_id": user.get("tenant_id"),
            "customer_contact": customer_contact,
            "methods": outreach_methods,
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "outreach_methods": outreach_methods,
            "message": f"Auto-outreach scheduled via {', '.join(outreach_methods)}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# CALL HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/voice/call-history")
async def get_call_history(authorization: str = Header(None)):
    """Get sales call history for the authenticated user's tenant"""
    try:
        db = _get_db()
        user = _get_current_user(authorization)
        tenant_id = user.get("tenant_id")

        calls = await db.sales_calls.find(
            {"tenant_id": tenant_id},
            {"_id": 0, "call_script": 0, "conversation_log": 0}
        ).sort("started_at", -1).to_list(50)

        return {"calls": calls}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_JWT_SECRET = os.environ.get("JWT_SECRET", "")

def _get_current_user(authorization: str):
    """Extract user from JWT — proper implementation"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = pyjwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def _calculate_pricing_internal(scan_id: str):
    """Internal pricing calculation"""
    db = _get_db()
    
    scan = await db.system_scans.find_one({"scan_id": scan_id}, {"_id": 0})
    if not scan:
        return {}
    
    issues_count = scan.get('issues_found', 0)
    critical_count = scan.get('critical_issues', 0)
    
    if critical_count <= 2 and issues_count < 25:
        tier = "professional"
        monthly = 599
    elif critical_count <= 5 and issues_count < 50:
        tier = "business"
        monthly = 999
    else:
        tier = "enterprise"
        monthly = 1999
    
    return {
        "recommended_tier": tier,
        "pricing": {"monthly_fee": monthly},
        "value_proposition": {"break_even_month": 2},
        "comparison": {"customer_saves": "$10,000", "value_multiple": "3.5x"}
    }
