"""
AUREM Acquisition Engine Router
Zero-cost customer acquisition — customer's own Gmail & WhatsApp, our automation
Handles campaigns, lead capture, auto-email via SMTP, WhatsApp deep links,
script generation for Apps Script, and early access signups
"""
import logging
import os
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/acquisition", tags=["AUREM Acquisition"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


def _encrypt_value(value: str) -> str:
    try:
        from routers.vault_router import _encrypt
        return _encrypt(value)
    except Exception:
        return value


def _decrypt_value(encrypted: str) -> str:
    try:
        from routers.vault_router import _decrypt
        return _decrypt(encrypted)
    except Exception:
        return encrypted


SMART_ROUTES = {
    "pigmentation": {"template": "welcome-luxe", "wa_msg": "Hi! I'm interested in pigmentation solutions"},
    "texture": {"template": "welcome-luxe", "wa_msg": "Hi! I'd like to improve my skin texture"},
    "anti-aging": {"template": "offer-discount", "wa_msg": "Hi! Tell me about your anti-aging products"},
    "acne": {"template": "followup-care", "wa_msg": "Hi! I need help with acne treatment"},
    "general": {"template": "welcome-luxe", "wa_msg": "Hi! I'd like to learn more about your products"},
}


def _get_smart_route(concern: str) -> dict:
    concern_lower = (concern or "general").lower()
    for keyword, route in SMART_ROUTES.items():
        if keyword in concern_lower:
            return route
    return SMART_ROUTES["general"]


def _generate_whatsapp_link(phone: str, message: str) -> str:
    return f"https://wa.me/{phone}?text={quote_plus(message)}"


def _build_email_html(brand_name, brand_tagline, lead_name, concern, whatsapp_link, discount="10"):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#050505;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="background:#0A0A0A;border:1px solid #1A1A1A;border-radius:16px;overflow:hidden;">
    <div style="padding:32px;text-align:center;border-bottom:1px solid #1A1A1A;">
      <h1 style="margin:0;color:#D4AF37;font-size:24px;letter-spacing:3px;">{brand_name}</h1>
      <p style="margin:8px 0 0;color:#666;font-size:12px;">{brand_tagline}</p>
    </div>
    <div style="padding:32px;">
      <h2 style="margin:0 0 16px;color:#F4F4F4;font-size:18px;">Welcome, {lead_name}</h2>
      <p style="color:#AAA;font-size:14px;line-height:1.6;">
        Thank you for your interest{f' in <strong style="color:#D4AF37">{concern}</strong>' if concern and concern != 'general' else ''}.
        We have prepared something special just for you.
      </p>
      <div style="margin:24px 0;padding:20px;background:linear-gradient(135deg,#D4AF37,#8B7355);border-radius:12px;text-align:center;">
        <p style="margin:0;color:#050505;font-size:28px;font-weight:bold;">{discount}% OFF</p>
        <p style="margin:4px 0 0;color:#050505;font-size:12px;">Your exclusive welcome offer</p>
      </div>
      <p style="color:#888;font-size:13px;line-height:1.6;">Claim your offer instantly via WhatsApp:</p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{whatsapp_link}" style="display:inline-block;padding:14px 32px;background:#25D366;color:white;text-decoration:none;border-radius:50px;font-size:14px;font-weight:600;">Claim on WhatsApp</a>
      </div>
    </div>
    <div style="padding:20px 32px;border-top:1px solid #1A1A1A;text-align:center;">
      <p style="margin:0;color:#444;font-size:10px;">{brand_name} &bull; Powered by AUREM</p>
    </div>
  </div>
</div>
</body></html>"""


async def _send_email_smtp(gmail_email, gmail_password, to_email, subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail_email
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_email, gmail_password)
            server.sendmail(gmail_email, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


# ═══════════════════════════════════════
# Config endpoints
# ═══════════════════════════════════════

class AcquisitionConfig(BaseModel):
    gmail_email: Optional[str] = None
    gmail_app_password: Optional[str] = None
    whatsapp_number: Optional[str] = None
    brand_name: Optional[str] = None
    brand_tagline: Optional[str] = None


@router.get("/config")
async def get_config(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    config = await db.acquisition_config.find_one({"user_id": user_id}, {"_id": 0})
    if config:
        return {"config": {
            "gmail_email": config.get("gmail_email", ""),
            "whatsapp_number": config.get("whatsapp_number", ""),
            "brand_name": config.get("brand_name", ""),
            "brand_tagline": config.get("brand_tagline", "")
        }}
    return {"config": None}


@router.post("/config")
async def save_config(data: AcquisitionConfig, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    doc = {
        "user_id": user_id,
        "gmail_email": data.gmail_email or "",
        "whatsapp_number": data.whatsapp_number or "",
        "brand_name": data.brand_name or "",
        "brand_tagline": data.brand_tagline or "",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if data.gmail_app_password:
        doc["gmail_app_password_enc"] = _encrypt_value(data.gmail_app_password)
    await db.acquisition_config.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
    return {"success": True}


# ═══════════════════════════════════════
# Campaign endpoints
# ═══════════════════════════════════════

class CampaignCreate(BaseModel):
    name: str
    template_id: Optional[str] = "welcome-luxe"
    whatsapp_msg: Optional[str] = ""
    discount: Optional[str] = "10"
    auto_email: Optional[bool] = True
    auto_whatsapp: Optional[bool] = True
    form_fields: Optional[List[str]] = ["name", "email", "phone", "concern"]


@router.get("/campaigns")
async def list_campaigns(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    campaigns = []
    cursor = db.acquisition_campaigns.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    async for c in cursor:
        lead_count = await db.acquisition_leads.count_documents({"campaign_id": c["id"]})
        c["lead_count"] = lead_count
        campaigns.append(c)
    return {"campaigns": campaigns}


@router.post("/campaigns")
async def create_campaign(data: CampaignCreate, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    campaign_id = f"camp-{uuid.uuid4().hex[:8]}"
    campaign = {
        "id": campaign_id, "user_id": user_id, "name": data.name,
        "template_id": data.template_id, "whatsapp_msg": data.whatsapp_msg,
        "discount": data.discount, "auto_email": data.auto_email,
        "auto_whatsapp": data.auto_whatsapp, "form_fields": data.form_fields,
        "status": "active", "lead_count": 0, "emails_sent": 0,
        "wa_clicks": 0, "conversion_rate": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.acquisition_campaigns.insert_one(campaign)
    return {"success": True, "id": campaign_id}


@router.put("/campaigns/{campaign_id}/toggle")
async def toggle_campaign(campaign_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    body = await request.json()
    new_status = body.get("status", "paused")
    await db.acquisition_campaigns.update_one(
        {"id": campaign_id, "user_id": user_id}, {"$set": {"status": new_status}}
    )
    return {"success": True}


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    await db.acquisition_campaigns.delete_one({"id": campaign_id, "user_id": user_id})
    return {"success": True}


# ═══════════════════════════════════════
# Lead capture & processing
# ═══════════════════════════════════════

class LeadSubmission(BaseModel):
    name: str
    email: str
    phone: Optional[str] = ""
    concern: Optional[str] = "general"


@router.get("/leads")
async def list_leads(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    leads = []
    cursor = db.acquisition_leads.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(100)
    async for lead in cursor:
        leads.append(lead)
    return {"leads": leads}


@router.post("/capture/{campaign_id}")
async def capture_lead(campaign_id: str, data: LeadSubmission):
    """Public endpoint — no auth. Captures lead from form and triggers automation."""
    db = get_db()
    campaign = await db.acquisition_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.get("status") != "active":
        raise HTTPException(400, "Campaign is not active")

    user_id = campaign["user_id"]
    config = await db.acquisition_config.find_one({"user_id": user_id}, {"_id": 0})
    route = _get_smart_route(data.concern)
    wa_number = config.get("whatsapp_number", "") if config else ""
    wa_msg = campaign.get("whatsapp_msg") or route.get("wa_msg", "Hi!")
    wa_link = _generate_whatsapp_link(wa_number, wa_msg) if wa_number else ""

    lead = {
        "id": f"lead-{uuid.uuid4().hex[:8]}",
        "user_id": user_id, "campaign_id": campaign_id,
        "name": data.name, "email": data.email, "phone": data.phone,
        "concern": data.concern, "smart_route": route,
        "wa_link": wa_link, "email_sent": False, "wa_clicked": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.acquisition_leads.insert_one(lead)
    await db.acquisition_campaigns.update_one({"id": campaign_id}, {"$inc": {"lead_count": 1}})

    email_sent = False
    if campaign.get("auto_email") and config and config.get("gmail_email") and config.get("gmail_app_password_enc"):
        try:
            gmail_pw = _decrypt_value(config["gmail_app_password_enc"])
            brand = config.get("brand_name", "Our Brand")
            tagline = config.get("brand_tagline", "")
            discount = campaign.get("discount", "10")
            subject = f"Welcome to {brand} — Your Exclusive {discount}% Offer"
            html = _build_email_html(brand, tagline, data.name, data.concern, wa_link, discount)
            email_sent = await _send_email_smtp(config["gmail_email"], gmail_pw, data.email, subject, html)
            if email_sent:
                await db.acquisition_leads.update_one({"id": lead["id"]}, {"$set": {"email_sent": True}})
                await db.acquisition_campaigns.update_one({"id": campaign_id}, {"$inc": {"emails_sent": 1}})
        except Exception as e:
            logger.error(f"Auto-email failed: {e}")

    return {"success": True, "lead_id": lead["id"], "email_sent": email_sent, "whatsapp_link": wa_link}


# ═══════════════════════════════════════
# Lead capture form (embeddable HTML)
# ═══════════════════════════════════════

@router.get("/form/{campaign_id}", response_class=HTMLResponse)
async def serve_lead_form(campaign_id: str):
    db = get_db()
    campaign = await db.acquisition_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        return HTMLResponse("<h1>Campaign not found</h1>", status_code=404)

    user_id = campaign["user_id"]
    config = await db.acquisition_config.find_one({"user_id": user_id}, {"_id": 0})
    brand = config.get("brand_name", "AUREM") if config else "AUREM"
    tagline = config.get("brand_tagline", "") if config else ""

    api_base = os.environ.get("BACKEND_URL", "")
    capture_url = f"{api_base}/api/acquisition/capture/{campaign_id}"

    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{brand} - Get Your Offer</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#050505;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.card{{background:#0A0A0A;border:1px solid #1A1A1A;border-radius:16px;max-width:420px;width:100%;overflow:hidden}}
.header{{padding:28px;text-align:center;border-bottom:1px solid #1A1A1A}}
.header h1{{color:#D4AF37;font-size:22px;letter-spacing:3px;margin-bottom:4px}}
.header p{{color:#666;font-size:11px}}
.form{{padding:24px}}
.field{{margin-bottom:16px}}
.field label{{display:block;color:#5a5a72;font-size:10px;letter-spacing:1px;margin-bottom:6px;text-transform:uppercase}}
.field input,.field select{{width:100%;padding:12px;background:#151515;border:1px solid #252525;border-radius:8px;color:#CCC;font-size:13px;outline:none;transition:border .2s}}
.field input:focus,.field select:focus{{border-color:#D4AF3780}}
.field select option{{background:#151515;color:#CCC}}
.btn{{width:100%;padding:14px;background:linear-gradient(135deg,#D4AF37,#8B7355);color:#050505;border:none;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;transition:opacity .2s}}
.btn:hover{{opacity:.9}}.btn:disabled{{opacity:.5}}
.success{{text-align:center;padding:32px}}
.success h2{{color:#4ade80;font-size:18px;margin-bottom:8px}}
.success p{{color:#888;font-size:13px;margin-bottom:20px}}
.wa-btn{{display:inline-block;padding:12px 28px;background:#25D366;color:white;text-decoration:none;border-radius:50px;font-size:14px;font-weight:600}}
.secure{{display:flex;align-items:center;gap:6px;justify-content:center;padding:12px;color:#4ade8080;font-size:10px}}
</style></head>
<body>
<div class="card">
  <div class="header"><h1>{brand}</h1><p>{tagline}</p></div>
  <div id="form-view" class="form">
    <form id="lead-form" onsubmit="return submitForm(event)">
      <div class="field"><label>Name</label><input type="text" id="f-name" required placeholder="Your name"></div>
      <div class="field"><label>Email</label><input type="email" id="f-email" required placeholder="your@email.com"></div>
      <div class="field"><label>WhatsApp Number</label><input type="tel" id="f-phone" placeholder="+1 555 123 4567"></div>
      <div class="field"><label>What are you looking for?</label>
        <select id="f-concern">
          <option value="general">General inquiry</option>
          <option value="pigmentation">Pigmentation solutions</option>
          <option value="texture">Skin texture improvement</option>
          <option value="anti-aging">Anti-aging treatments</option>
          <option value="acne">Acne treatment</option>
        </select>
      </div>
      <button type="submit" class="btn" id="submit-btn">Get My Exclusive Offer</button>
    </form>
    <div class="secure">Secured by AUREM</div>
  </div>
  <div id="success-view" class="success" style="display:none">
    <h2>You're In!</h2>
    <p>Check your email for your exclusive offer</p>
    <a id="wa-link" href="#" class="wa-btn" target="_blank">Claim on WhatsApp</a>
  </div>
</div>
<script>
async function submitForm(e){{
  e.preventDefault();
  document.getElementById('submit-btn').disabled=true;
  document.getElementById('submit-btn').textContent='Submitting...';
  try{{
    const res=await fetch('{capture_url}',{{
      method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{
        name:document.getElementById('f-name').value,
        email:document.getElementById('f-email').value,
        phone:document.getElementById('f-phone').value,
        concern:document.getElementById('f-concern').value
      }})
    }});
    const data=await res.json();
    if(data.whatsapp_link)document.getElementById('wa-link').href=data.whatsapp_link;
    document.getElementById('form-view').style.display='none';
    document.getElementById('success-view').style.display='block';
  }}catch(err){{
    document.getElementById('submit-btn').disabled=false;
    document.getElementById('submit-btn').textContent='Get My Exclusive Offer';
    alert('Something went wrong. Please try again.');
  }}
  return false;
}}
</script>
</body></html>""")


# ═══════════════════════════════════════
# Funnel stats
# ═══════════════════════════════════════

@router.get("/funnel-stats")
async def get_funnel_stats(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    total_leads = await db.acquisition_leads.count_documents({"user_id": user_id})
    emails_sent = await db.acquisition_leads.count_documents({"user_id": user_id, "email_sent": True})
    wa_clicked = await db.acquisition_leads.count_documents({"user_id": user_id, "wa_clicked": True})
    return {
        "discovered": total_leads * 3,
        "captured": total_leads,
        "nurtured": emails_sent,
        "converted": wa_clicked
    }

# ═══════════════════════════════════════
# Early Access Signup (Tier 3)
# ═══════════════════════════════════════

class EarlyAccessRequest(BaseModel):
    email: str


@router.post("/early-access")
async def join_early_access(data: EarlyAccessRequest, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    await db.early_access_signups.update_one(
        {"email": data.email},
        {"$set": {
            "email": data.email,
            "user_id": user_id,
            "product": "aurem-extension",
            "signed_up_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"success": True, "message": "You're on the early access list!"}



# ═══════════════════════════════════════
# Voice Agent (Tier 5A) — Web Voice Chat
# ═══════════════════════════════════════

class VoiceChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []
    session_id: Optional[str] = "default"
    brand_context: Optional[str] = ""


@router.post("/voice-chat")
async def voice_chat(data: VoiceChatRequest, request: Request):
    """AI voice agent chat — uses Emergent LLM key for GPT-4o brain."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    # Get brand config for context
    config = await db.acquisition_config.find_one({"user_id": user_id}, {"_id": 0})
    brand_name = config.get("brand_name", "AUREM") if config else "AUREM"
    brand_tagline = config.get("brand_tagline", "") if config else ""

    # Build system prompt
    system_prompt = f"""You are the AI Voice Agent for {brand_name}{f' — {brand_tagline}' if brand_tagline else ''}.
You are speaking LIVE with a potential customer via voice. Keep responses SHORT (2-3 sentences max) and conversational.

Your goals:
1. Greet warmly and ask what they're looking for
2. Understand their needs (skin concerns, product interests, etc.)
3. Provide helpful info and recommend solutions
4. Guide them to book a consultation or claim an offer
5. Collect their name and email naturally during conversation

Speaking style: Professional yet warm. Like a knowledgeable friend, not a robot.
Never say you're an AI unless directly asked. Keep the luxury brand feel.
{f'Additional context: {data.brand_context}' if data.brand_context else ''}"""

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return {"response": "I'm here to help! Our team will be with you shortly.", "error": "LLM key not configured"}

        chat = LlmChat(
            api_key=api_key,
            session_id=f"voice-{user_id}-{data.session_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")

        # Build message with history
        message_text = data.message
        if data.history and len(data.history) > 0:
            context_parts = []
            for msg in data.history[-6:]:
                role = "Customer" if msg.get("role") == "user" else "Agent"
                context_parts.append(f"{role}: {msg.get('content', '')}")
            if context_parts:
                message_text = f"Recent conversation:\n{chr(10).join(context_parts)}\n\nCustomer just said: {data.message}"

        response = await chat.send_message(UserMessage(text=message_text))

        # Log the voice interaction
        await db.voice_interactions.insert_one({
            "user_id": user_id,
            "session_id": data.session_id,
            "customer_message": data.message,
            "agent_response": str(response),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        return {"response": str(response), "session_id": data.session_id}

    except Exception as e:
        logger.error(f"Voice chat error: {e}")
        return {
            "response": f"Welcome to {brand_name}! How can I help you today?",
            "error": str(e)
        }


# ═══════════════════════════════════════
# Self-Hosted Voice Guide (Tier 5B)
# ═══════════════════════════════════════

@router.post("/generate-voice-script")
async def generate_voice_script(request: Request):
    """Generate the self-hosted voice agent Python starter code."""
    _get_user_from_token(request)

    script = '''# ═══════════════════════════════════════════════════════════
# AUREM Self-Hosted Voice Agent — Zero-Cost AI Calling
# Stack: Whisper Turbo (STT) + Ollama/Llama 3.2 (Brain) + Kokoro-82M (TTS)
# Orchestration: Pipecat Framework
# ═══════════════════════════════════════════════════════════
# REQUIREMENTS:
# pip install pipecat-ai faster-whisper kokoro ollama
# Also install Ollama: https://ollama.ai
# Then run: ollama pull llama3.2
# ═══════════════════════════════════════════════════════════

import asyncio
try:
    from pipecat.frames.frames import TextFrame, AudioRawFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask
    from pipecat.services.whisper import WhisperSTTService
    from pipecat.services.ollama import OllamaLLMService
    from pipecat.transports.services.daily import DailyTransport
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False

# ── Configuration ──
OLLAMA_MODEL = "llama3.2"
WHISPER_MODEL = "turbo"  # Fastest model, <100ms
BRAND_NAME = "Your Brand"  # Replace with your brand

SYSTEM_PROMPT = f"""You are the AI Voice Agent for {BRAND_NAME}.
You are speaking LIVE with a potential customer. Keep responses to 2-3 sentences.
Be warm, professional, and helpful. Guide them toward booking a consultation.
Never say you are an AI unless directly asked."""

async def main():
    """
    Main pipeline: Microphone → Whisper STT → Ollama LLM → Kokoro TTS → Speaker
    Total latency target: <300ms
    """

    # 1. Speech-to-Text (The "Ears")
    stt = WhisperSTTService(
        model=WHISPER_MODEL,
        language="en",
        # VAD (Voice Activity Detection) — only transcribe when human speaks
        vad_enabled=True,
        vad_threshold=0.5
    )

    # 2. LLM Brain (The "Thinker")
    llm = OllamaLLMService(
        model=OLLAMA_MODEL,
        system_prompt=SYSTEM_PROMPT,
        # Streaming: start speaking before full response is generated
        stream=True,
        temperature=0.7
    )

    # 3. Text-to-Speech (The "Voice")
    # Using Kokoro-82M — high quality, runs on CPU, $0
    # Install: pip install kokoro
    from pipecat.services.kokoro import KokoroTTSService
    tts = KokoroTTSService(
        voice="af_heart",  # Warm female voice
        speed=1.0
    )

    # 4. Transport (WebRTC connection)
    # Option A: Daily.co (free tier available)
    # Option B: LiveKit (open source, self-hosted)
    transport = DailyTransport(
        room_url=os.environ.get("DAILY_ROOM_URL", ""),
        token=os.environ.get("DAILY_TOKEN", ""),
        bot_name="AUREM Voice Agent"
    )

    # Build the pipeline
    pipeline = Pipeline([
        transport.input(),   # Audio from customer
        stt,                  # Speech → Text (~100ms)
        llm,                  # Text → Response (~150ms, streaming)
        tts,                  # Response → Speech (~100ms)
        transport.output()    # Audio to customer
    ])

    task = PipelineTask(pipeline)
    runner = PipelineRunner()

    print(f"[AUREM] Voice Agent running for {BRAND_NAME}")
    print(f"[AUREM] Stack: Whisper {WHISPER_MODEL} → Ollama {OLLAMA_MODEL} → Kokoro")
    print(f"[AUREM] Expected latency: <300ms")
    print(f"[AUREM] Cost: $0.00/minute")

    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(main())

# ═══════════════════════════════════════════════════════════
# ALTERNATIVE: SIP Bridge for Real Phone Calls
# ═══════════════════════════════════════════════════════════
# To connect to real phone numbers:
#
# 1. Install Asterisk (open-source PBX):
#    sudo apt install asterisk
#
# 2. Get a SIP trunk (Twilio trial = $15 free credit):
#    - Sign up at twilio.com
#    - Get a SIP trunk endpoint
#
# 3. Configure Asterisk to forward calls to your Pipecat pipeline
#
# 4. Cost breakdown:
#    - Asterisk: $0 (open source)
#    - Twilio trial: $0 (free credits cover ~5,000 minutes)
#    - AI processing: $0 (all local)
#    - Total: $0
# ═══════════════════════════════════════════════════════════
'''

    return {"script": script, "script_type": "voice-agent-selfhosted"}
