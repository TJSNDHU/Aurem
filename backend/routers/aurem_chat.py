"""
AUREM AI Chat API
Handles conversational AI for the dashboard
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
import os
import uuid

# Import OpenAI from emergentintegrations if available
try:
    from emergentintegrations.openai_integration import OpenAI
    EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
    client = OpenAI(api_key=EMERGENT_LLM_KEY) if EMERGENT_LLM_KEY else None
except ImportError:
    client = None

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: str | None = None
    timestamp: str

# Simple in-memory chat history (replace with DB in production)
chat_sessions = {}

@router.post("/api/aurem/chat", response_model=ChatResponse)
async def aurem_chat(request: ChatRequest):
    """
    AI-powered chat endpoint for AUREM Intelligence
    """
    try:
        # Generate or use existing session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get or create session history
        if session_id not in chat_sessions:
            chat_sessions[session_id] = []
        
        # Add user message to history
        chat_sessions[session_id].append({
            "role": "user",
            "content": request.message
        })
        
        # Generate AI response
        if client:
            # Use GPT-5.2 via Emergent LLM key
            try:
                messages = [
                    {
                        "role": "system",
                        "content": """You are AUREM, an AI business intelligence assistant for the AUREM platform.
                        
You help users with:
- Business automation strategies
- AI agent deployment and management
- Lead generation and customer engagement
- Integration setup (Gmail, WhatsApp, CRM, etc.)
- Analytics and reporting
- Circuit breaker monitoring

Be concise, helpful, and business-focused. Use data-driven insights when possible."""
                    }
                ] + chat_sessions[session_id][-10:]  # Last 10 messages for context
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7
                )
                
                ai_response = response.choices[0].message.content
                
            except Exception as llm_error:
                print(f"[AUREM Chat] LLM error: {llm_error}")
                ai_response = f"I'm having trouble connecting to my AI service right now. However, I can help you navigate the AUREM platform. What would you like to know about? You can explore:\n\n• AI Conversation features\n• Automation Engine\n• Agent Swarm deployment\n• Integrations (Gmail, WhatsApp, CRM)\n• Analytics & Reporting"
        else:
            # Fallback response when no LLM is available
            ai_response = f"Hello! I'm AUREM AI. I can help you with:\n\n• Understanding your business metrics\n• Setting up AI agents\n• Configuring integrations\n• Analyzing data\n• Automation strategies\n\nWhat would you like to explore?"
        
        # Add AI response to history
        chat_sessions[session_id].append({
            "role": "assistant",
            "content": ai_response
        })
        
        # Detect intent (simple keyword matching)
        intent = detect_intent(request.message.lower())
        
        return ChatResponse(
            response=ai_response,
            session_id=session_id,
            intent=intent,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        print(f"[AUREM Chat] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


def detect_intent(message: str) -> str:
    """Simple intent detection based on keywords"""
    if any(word in message for word in ['integrate', 'integration', 'connect', 'setup']):
        return 'integration'
    elif any(word in message for word in ['agent', 'swarm', 'deploy', 'automation']):
        return 'agent_management'
    elif any(word in message for word in ['metric', 'analytics', 'report', 'data']):
        return 'analytics'
    elif any(word in message for word in ['help', 'how', 'what', 'guide']):
        return 'help'
    else:
        return 'general'
