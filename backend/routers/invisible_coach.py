"""
AUREM Invisible AI Sales Coach
AI listens in background during in-person meetings
Provides real-time suggestions without customer knowing
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
import json
import asyncio

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# INVISIBLE AI COACH - Silent Mode
# ═══════════════════════════════════════════════════════════════════════════════

class InvisibleCoachSession(BaseModel):
    scan_id: str
    meeting_type: str = "in_person"  # in_person, video_call, phone
    customer_name: Optional[str] = None
    silent_mode: bool = True  # AI never speaks to customer

class RealTimeSuggestion(BaseModel):
    type: str  # "talking_point", "objection_handler", "pricing", "technical_answer"
    suggestion: str
    confidence: float
    priority: str  # "urgent", "high", "medium", "low"

class ConversationIntelligence:
    """AI analyzes conversation and provides real-time coaching"""
    
    def __init__(self, scan_data: dict, pricing_data: dict):
        self.scan_data = scan_data
        self.pricing_data = pricing_data
        self.conversation_log = []
        self.detected_objections = []
        self.customer_questions = []
        self.sales_stage = "introduction"
        
    def analyze_speech(self, speaker: str, text: str) -> List[RealTimeSuggestion]:
        """
        Analyze what was just said and provide instant suggestions
        ONLY to your earpiece/screen - customer never knows
        """
        suggestions = []
        text_lower = text.lower()
        
        # Log conversation
        self.conversation_log.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # If CUSTOMER is speaking, analyze and prepare response
        if speaker == "customer":
            
            # Detect questions
            if "?" in text or any(word in text_lower for word in ["how", "what", "why", "when", "where", "can you"]):
                self.customer_questions.append(text)
                
                # Price question
                if any(word in text_lower for word in ["cost", "price", "expensive", "how much"]):
                    suggestions.append(RealTimeSuggestion(
                        type="pricing",
                        suggestion=f"💰 PRICING RESPONSE:\n\n'Based on the {self.scan_data.get('issues_found', 0)} issues we found, I recommend our {self.pricing_data.get('recommended_tier', 'Business').title()} plan at ${self.pricing_data.get('pricing', {}).get('monthly_fee', 999)}/month.\n\nHere's why it's worth it: You're currently losing {self.scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2,400')} per month. AUREM will save you {self.scan_data.get('aurem_impact', {}).get('customer_saves', '$16,000')} annually.\n\nBreak-even in Month {self.pricing_data.get('value_proposition', {}).get('break_even_month', 2)}.'",
                        confidence=0.95,
                        priority="urgent"
                    ))
                
                # ROI question
                elif any(word in text_lower for word in ["roi", "return", "worth", "value", "savings"]):
                    suggestions.append(RealTimeSuggestion(
                        type="technical_answer",
                        suggestion=f"📊 ROI ANSWER:\n\n'Great question! Let me show you the math:\n\n- You're losing: {self.scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2,400')}/month\n- AUREM costs: ${self.pricing_data.get('pricing', {}).get('monthly_fee', 999)}/month\n- Net savings: {self.scan_data.get('aurem_impact', {}).get('customer_saves', '$16,000')}/year\n- ROI multiple: {self.pricing_data.get('comparison', {}).get('value_multiple', '3.5x')}\n\nYou'll break even in {self.pricing_data.get('value_proposition', {}).get('break_even_month', 2)} months.'",
                        confidence=0.98,
                        priority="high"
                    ))
                
                # How does it work
                elif any(word in text_lower for word in ["how does", "how do you", "integrate", "setup", "implementation"]):
                    tech_stack = self.scan_data.get('deep_scan', {}).get('tech_stack', {})
                    services = self.scan_data.get('deep_scan', {}).get('third_party_services', [])
                    
                    suggestions.append(RealTimeSuggestion(
                        type="technical_answer",
                        suggestion=f"⚙️ TECHNICAL ANSWER:\n\n'We detected you're using:\n- {tech_stack.get('cms', 'your current CMS')}\n- {', '.join([s['name'] for s in services[:3]])}\n\nAUREM has native integrations for all of these. Setup is simple:\n\n1. One-click connect (15 minutes)\n2. We migrate your data automatically\n3. AI starts automating within 24 hours\n\nNo coding required. We handle everything.'",
                        confidence=0.92,
                        priority="high"
                    ))
            
            # Detect objections
            objection_detected = False
            
            if any(word in text_lower for word in ["too expensive", "too much", "can't afford", "budget"]):
                objection_detected = True
                self.detected_objections.append("price_objection")
                suggestions.append(RealTimeSuggestion(
                    type="objection_handler",
                    suggestion=f"🛡️ PRICE OBJECTION:\n\n'I understand budget is a concern. But consider this:\n\nYou're ALREADY spending {self.scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2,400')}/month on inefficiencies and manual work.\n\nAUREM doesn't cost you money - it SAVES you money. You'll actually be {self.scan_data.get('aurem_impact', {}).get('customer_saves', '$16,000')} richer next year.\n\nThink of it as converting wasted money into profit.'\n\n[THEN OFFER: Payment plan or smaller tier to start]",
                    confidence=0.90,
                    priority="urgent"
                ))
            
            elif any(word in text_lower for word in ["need to think", "need time", "get back to you", "talk to my team"]):
                objection_detected = True
                self.detected_objections.append("stalling")
                suggestions.append(RealTimeSuggestion(
                    type="objection_handler",
                    suggestion="⏰ STALLING OBJECTION:\n\n'Absolutely, I respect that. Before you go, can I ask - which of these {0} issues is NOT a concern for you?'\n\n[PAUSE - They'll realize ALL are concerns]\n\n'Here's what I suggest: Let me send you this PDF report. It has everything we discussed. Can we schedule 15 minutes next Tuesday to answer any questions?'\n\n[BOOK THE FOLLOW-UP NOW]".format(self.scan_data.get('issues_found', 18)),
                    confidence=0.88,
                    priority="urgent"
                ))
            
            elif any(word in text_lower for word in ["already have", "using something else", "current solution"]):
                objection_detected = True
                self.detected_objections.append("competitor")
                suggestions.append(RealTimeSuggestion(
                    type="objection_handler",
                    suggestion="🏆 COMPETITOR OBJECTION:\n\n'That's great! What I've found is most solutions handle pieces of the puzzle.\n\nFor example, you're using [list their tools]. That's 3-5 different logins, 3-5 different bills, and they don't talk to each other.\n\nAUREM consolidates everything into ONE platform with ONE login, ONE bill, and everything connected.\n\nPlus, we found {0} issues your current solution isn't catching. Can I show you those?'".format(self.scan_data.get('critical_issues', 5)),
                    confidence=0.85,
                    priority="high"
                ))
            
            elif any(word in text_lower for word in ["not sure", "don't know", "skeptical", "sounds too good"]):
                objection_detected = True
                self.detected_objections.append("skepticism")
                suggestions.append(RealTimeSuggestion(
                    type="objection_handler",
                    suggestion="✅ SKEPTICISM OBJECTION:\n\n'I appreciate your honesty! Here's what I suggest:\n\n1. I'll give you a FREE 14-day trial\n2. We'll fix 3 of your critical issues for free\n3. You see the results yourself\n4. If you're not blown away, no charge\n\nSound fair? I'm confident because I've ALREADY scanned your system. I know exactly what we can do for you.'\n\n[OFFER PROOF: Show them the scan results again]",
                    confidence=0.92,
                    priority="urgent"
                ))
            
            # Buying signals
            if any(word in text_lower for word in ["sounds good", "interested", "let's do it", "where do we start", "next steps"]):
                self.sales_stage = "closing"
                suggestions.append(RealTimeSuggestion(
                    type="talking_point",
                    suggestion="🎯 BUYING SIGNAL DETECTED!\n\n'Perfect! Here's what happens next:\n\n1. I'll send you the proposal (2 minutes)\n2. You review and sign (10 minutes)\n3. We schedule onboarding call (tomorrow)\n4. You're live within 48 hours\n\nI can have you set up by [DATE]. Sound good?'\n\n[PULL OUT CONTRACT NOW]",
                    confidence=0.95,
                    priority="urgent"
                ))
        
        # If YOU (sales rep) are speaking, provide backup info
        elif speaker == "sales_rep":
            # Just confirm you're doing well, provide supporting data
            if any(word in text_lower for word in ["scan", "found", "issues"]):
                suggestions.append(RealTimeSuggestion(
                    type="talking_point",
                    suggestion=f"📋 SCAN DETAILS (if they ask):\n- Total issues: {self.scan_data.get('issues_found', 0)}\n- Critical: {self.scan_data.get('critical_issues', 0)}\n- Performance score: {self.scan_data.get('performance', {}).get('score', 0)}/100\n- Security score: {self.scan_data.get('security', {}).get('score', 0)}/100",
                    confidence=0.80,
                    priority="low"
                ))
        
        return suggestions
    
    def get_next_move(self) -> RealTimeSuggestion:
        """Suggest what to say/do next based on conversation flow"""
        
        if self.sales_stage == "introduction":
            return RealTimeSuggestion(
                type="talking_point",
                suggestion="👋 OPENING:\n\n'Thanks for meeting with me! I ran a scan on your website and found some interesting things. Mind if I show you what I discovered?'\n\n[OPEN LAPTOP - SHOW SCAN RESULTS]",
                confidence=0.90,
                priority="high"
            )
        
        elif self.sales_stage == "presentation":
            return RealTimeSuggestion(
                type="talking_point",
                suggestion=f"📊 PRESENT FINDINGS:\n\n'I found {self.scan_data.get('issues_found', 0)} issues costing you about {self.scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2,400')} per month.\n\nLet me show you the top 3...'\n\n[SCROLL TO ISSUES LIST]",
                confidence=0.92,
                priority="high"
            )
        
        elif self.sales_stage == "closing":
            return RealTimeSuggestion(
                type="talking_point",
                suggestion="🤝 CLOSE THE DEAL:\n\n'Great! Let me get the paperwork started. I just need to confirm a few details...'\n\n[PULL UP CONTRACT/PROPOSAL]",
                confidence=0.95,
                priority="urgent"
            )
        
        return RealTimeSuggestion(
            type="talking_point",
            suggestion="Continue the conversation naturally. AI is listening and will suggest responses to customer questions.",
            confidence=0.70,
            priority="low"
        )


# Active invisible coach sessions
active_coaches = {}

@router.post("/api/coach/start-invisible")
async def start_invisible_coach(request: InvisibleCoachSession, authorization: str = Header(None)):
    """
    ONE-CLICK START: AI starts listening in background
    Customer has NO idea AI is helping you
    """
    try:
        from server import db
        import secrets
        
        # Auth
        user = get_current_user(authorization)
        
        # Get scan data
        scan = await db.system_scans.find_one({"_id": request.scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get pricing
        pricing = await calculate_pricing_internal(request.scan_id)
        
        # Create invisible coach
        coach_id = f"coach_{secrets.token_urlsafe(16)}"
        coach = ConversationIntelligence(scan, pricing)
        active_coaches[coach_id] = coach
        
        # Save session
        await db.coach_sessions.insert_one({
            "coach_id": coach_id,
            "scan_id": request.scan_id,
            "tenant_id": user.get("tenant_id"),
            "sales_rep": user.get("user_id"),
            "customer_name": request.customer_name,
            "meeting_type": request.meeting_type,
            "silent_mode": request.silent_mode,
            "status": "active",
            "started_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Return initial coaching
        initial_move = coach.get_next_move()
        
        return {
            "success": True,
            "coach_id": coach_id,
            "message": "🎯 Invisible AI Coach activated. Customer has no idea I'm here.",
            "initial_suggestion": initial_move.dict(),
            "scan_summary": {
                "issues": scan.get('issues_found'),
                "critical": scan.get('critical_issues'),
                "savings": scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly')
            }
        }
        
    except Exception as e:
        print(f"[Invisible Coach] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/coach/{coach_id}")
async def invisible_coach_websocket(websocket: WebSocket, coach_id: str):
    """
    Real-time invisible coaching
    You wear earpiece or look at screen
    AI whispers suggestions as conversation happens
    """
    await websocket.accept()
    
    try:
        # Get coach session
        if coach_id not in active_coaches:
            await websocket.send_json({"error": "Coach session not found"})
            await websocket.close()
            return
        
        coach = active_coaches[coach_id]
        
        # Send welcome message
        await websocket.send_json({
            "type": "coach_ready",
            "message": "🎯 AI Coach listening. Speak naturally - I'll help you close this deal.",
            "mode": "invisible"
        })
        
        # Listen for conversation
        while True:
            data = await websocket.receive_json()
            
            msg_type = data.get('type')
            
            if msg_type == 'speech':
                speaker = data.get('speaker')  # 'sales_rep' or 'customer'
                text = data.get('text')
                
                # Analyze what was said
                suggestions = coach.analyze_speech(speaker, text)
                
                # Send suggestions to YOUR earpiece/screen ONLY
                for suggestion in suggestions:
                    await websocket.send_json({
                        "type": "ai_suggestion",
                        "suggestion": suggestion.dict(),
                        "visible_to": "sales_rep_only",  # Customer CAN'T see this
                        "display_mode": "earpiece"  # Or "screen"
                    })
                
                # If customer is done speaking, suggest your response
                if speaker == "customer" and len(suggestions) > 0:
                    await websocket.send_json({
                        "type": "your_turn",
                        "message": "💬 Customer is waiting for your response",
                        "top_suggestion": suggestions[0].dict()
                    })
            
            elif msg_type == 'request_help':
                # You pressed panic button - need immediate help
                topic = data.get('topic', 'general')
                
                if topic == 'pricing':
                    help_text = coach.analyze_speech("sales_rep", "pricing help needed")
                    await websocket.send_json({
                        "type": "emergency_help",
                        "suggestion": help_text[0].dict() if help_text else None
                    })
            
            elif msg_type == 'end_session':
                # Meeting ended
                from server import db
                await db.coach_sessions.update_one(
                    {"coach_id": coach_id},
                    {
                        "$set": {
                            "status": "completed",
                            "ended_at": datetime.now(timezone.utc).isoformat(),
                            "conversation_log": coach.conversation_log,
                            "objections_handled": coach.detected_objections,
                            "questions_answered": len(coach.customer_questions)
                        }
                    }
                )
                
                # Send session summary
                await websocket.send_json({
                    "type": "session_complete",
                    "summary": {
                        "duration": "estimate",
                        "objections_handled": len(coach.detected_objections),
                        "questions_answered": len(coach.customer_questions),
                        "sales_stage_reached": coach.sales_stage
                    }
                })
                break
                
    except WebSocketDisconnect:
        if coach_id in active_coaches:
            del active_coaches[coach_id]
    except Exception as e:
        print(f"[Coach WebSocket] Error: {e}")
        await websocket.send_json({"error": str(e)})


@router.get("/api/coach/session/{coach_id}/transcript")
async def get_session_transcript(coach_id: str, authorization: str = Header(None)):
    """Get full transcript and AI suggestions from a coaching session"""
    try:
        from server import db
        
        session = await db.coach_sessions.find_one({"coach_id": coach_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions
def get_current_user(authorization: str):
    """Extract user from JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    token = authorization.replace("Bearer ", "")
    try:
        import jwt
        import os
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

async def calculate_pricing_internal(scan_id: str):
    """Get pricing for scan"""
    from server import db
    
    scan = await db.system_scans.find_one({"_id": scan_id}, {"_id": 0})
    if not scan:
        return {}
    
    issues = scan.get('issues_found', 0)
    critical = scan.get('critical_issues', 0)
    
    if critical <= 2 and issues < 25:
        tier, monthly = "professional", 599
    elif critical <= 5 and issues < 50:
        tier, monthly = "business", 999
    else:
        tier, monthly = "enterprise", 1999
    
    return {
        "recommended_tier": tier,
        "pricing": {"monthly_fee": monthly},
        "value_proposition": {"break_even_month": 2},
        "comparison": {"customer_saves": "$16,000", "value_multiple": "3.5x"}
    }
