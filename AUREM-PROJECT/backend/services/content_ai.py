"""
Content AI Service for Reroots
AI-powered content creation engine for marketing

6 Content Types:
1. Instagram caption
2. Instagram story script
3. Product description
4. WhatsApp broadcast
5. Blog post outline
6. Email subject line variants
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

# MongoDB reference
_db = None

# LLM configuration
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
LLM_MODEL = "anthropic/claude-sonnet-4"

# Brand voice rules
BRAND_VOICE_RULES = """
REROOTS BRAND VOICE RULES - STRICTLY FOLLOW:
- Say "age recovery" NOT "anti-aging"
- Say "AURA-GEN System" NOT "products" or "items"
- Say "skin renewal" NOT "anti-wrinkle"
- Say "clinical-grade skincare" NOT "beauty products"
- Tone: warm, knowledgeable, clinical-meets-luxe
- Never mention competitors by name (La Mer, Tatcha, etc.)
- Focus on skin health journey, not quick fixes
- Use "medical aesthetics" terminology
- Target audience: 35-55 professionals who value science-backed skincare
- Emphasize: PDRN, TXA, Argireline ingredients
- Never use clickbait or overly promotional language
"""

CONTENT_TYPES = {
    "instagram_caption": {
        "name": "Instagram Caption",
        "description": "Caption with hashtags and CTA for Instagram posts",
        "inputs": ["product_name", "skin_concern", "tone"],
        "output_format": "caption + 5 hashtags + CTA"
    },
    "instagram_story": {
        "name": "Instagram Story Script",
        "description": "5-slide story structure with hooks and CTAs",
        "inputs": ["topic", "product_focus"],
        "output_format": "5 slides, each under 15 words"
    },
    "product_description": {
        "name": "Product Description",
        "description": "SEO-optimized product description",
        "inputs": ["product_name", "ingredients", "target_concern"],
        "output_format": "SEO-friendly description with key benefits"
    },
    "whatsapp_broadcast": {
        "name": "WhatsApp Broadcast",
        "description": "Conversational WhatsApp message under 160 chars",
        "inputs": ["campaign_goal", "offer_details"],
        "output_format": "Under 160 characters with emoji"
    },
    "blog_outline": {
        "name": "Blog Post Outline",
        "description": "800-word SEO blog outline with keywords",
        "inputs": ["topic", "target_keywords"],
        "output_format": "H1, H2s, keywords, meta description"
    },
    "email_subjects": {
        "name": "Email Subject Lines",
        "description": "5 subject line variants with reasoning",
        "inputs": ["email_goal", "target_audience"],
        "output_format": "5 options with predicted open rate reasoning"
    }
}


def set_db(database):
    """Set database reference"""
    global _db
    _db = database


def apply_brand_guard(text: str) -> str:
    """Apply brand guard to strip competitor mentions"""
    competitors = [
        "La Mer", "Tatcha", "Drunk Elephant", "SK-II", "Estee Lauder",
        "Clinique", "Lancome", "Olay", "Neutrogena", "CeraVe", "The Ordinary",
        "Sunday Riley", "Charlotte Tilbury", "Glossier", "Fenty"
    ]
    
    result = text
    for competitor in competitors:
        result = result.replace(competitor, "other brands")
        result = result.replace(competitor.lower(), "other brands")
    
    # Also fix common anti-aging mentions
    result = result.replace("anti-aging", "age recovery")
    result = result.replace("Anti-aging", "Age recovery")
    result = result.replace("anti-wrinkle", "skin renewal")
    result = result.replace("Anti-wrinkle", "Skin renewal")
    
    return result


async def generate_content(
    content_type: str,
    inputs: Dict[str, str]
) -> Dict[str, Any]:
    """Generate content using Claude"""
    
    if not LLM_API_KEY:
        return {
            "success": False,
            "error": "LLM API key not configured"
        }
    
    config = CONTENT_TYPES.get(content_type)
    if not config:
        return {
            "success": False,
            "error": f"Unknown content type: {content_type}"
        }
    
    # Build prompts based on content type
    prompts = {
        "instagram_caption": f"""Create an Instagram caption for ReRoots Skincare.

Product: {inputs.get('product_name', 'AURA-GEN System')}
Skin concern: {inputs.get('skin_concern', 'general skin health')}
Tone: {inputs.get('tone', 'educational')}

Output format:
1. Caption (2-3 sentences, engaging but not salesy)
2. 5 relevant hashtags
3. Clear call to action

Keep it authentic and avoid generic influencer language.""",

        "instagram_story": f"""Create a 5-slide Instagram Story script for ReRoots.

Topic: {inputs.get('topic', 'skin renewal journey')}
Product focus: {inputs.get('product_focus', 'AURA-GEN System')}

Format EXACTLY as:
SLIDE 1 (Hook): [under 15 words - attention grabber]
SLIDE 2 (Problem): [under 15 words - pain point]
SLIDE 3 (Solution): [under 15 words - how AURA-GEN helps]
SLIDE 4 (Ingredient): [under 15 words - key ingredient highlight]
SLIDE 5 (CTA): [under 15 words - action to take]

Each slide must be under 15 words. No hashtags in story.""",

        "product_description": f"""Write an SEO-optimized product description for ReRoots.

Product: {inputs.get('product_name', 'AURA-GEN TXA + PDRN Serum')}
Key ingredients: {inputs.get('ingredients', 'PDRN, Tranexamic Acid, Argireline')}
Target concern: {inputs.get('target_concern', 'uneven skin tone and texture')}

Requirements:
- 150-200 words
- Include 3-5 natural keyword placements
- Lead with the benefit, then explain the science
- End with usage instructions
- Clinical but warm tone
- SEO-friendly structure with clear sections""",

        "whatsapp_broadcast": f"""Write a WhatsApp broadcast message for ReRoots.

Campaign goal: {inputs.get('campaign_goal', 'new product launch')}
Offer details: {inputs.get('offer_details', 'no specific offer')}

Requirements:
- UNDER 160 characters (critical!)
- Conversational, warm tone
- Include 1-2 relevant emojis
- Clear but subtle CTA
- Not pushy or salesy
- Feel like a message from a friend who happens to work in skincare""",

        "blog_outline": f"""Create an 800-word blog post outline for ReRoots.

Topic: {inputs.get('topic', 'understanding skin aging')}
Target keywords: {inputs.get('target_keywords', 'skin health, PDRN benefits')}

Output format:
META DESCRIPTION: [under 155 characters]

H1: [main title with primary keyword]

INTRO: [2-3 sentences summarizing the post]

H2: [first main section]
- Key points to cover
- How to naturally mention AURA-GEN

H2: [second main section]
- Key points to cover

H2: [third main section]
- Key points to cover

H2: [conclusion/CTA section]

KEYWORD SUGGESTIONS: [5 related keywords to include]

SEO NOTES: [brief optimization tips]""",

        "email_subjects": f"""Generate 5 email subject line options for ReRoots.

Email goal: {inputs.get('email_goal', 'drive engagement')}
Target audience: {inputs.get('target_audience', 'existing customers')}

For each subject line, provide:
1. The subject line (under 50 characters)
2. Predicted open rate reasoning (why it works)
3. Best time to send

Format:
OPTION 1: "[subject line]"
- Reasoning: [why this works]
- Best send time: [day/time]

[repeat for all 5 options]

Make each option distinctly different in approach (curiosity, urgency, personal, benefit-focused, question)."""
    }
    
    prompt = prompts.get(content_type, prompts["instagram_caption"])
    
    system_prompt = f"""You are the content strategist for ReRoots Aesthetics Inc., a clinical skincare brand.

{BRAND_VOICE_RULES}

Create content that feels authentic and valuable, not like typical marketing copy.
Focus on education and genuine connection with the audience.
"""
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.8
                }
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"LLM API error: {response.status_code}"
                }
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Apply brand guard
            content = apply_brand_guard(content)
            
            return {
                "success": True,
                "content_type": content_type,
                "config": config,
                "inputs": inputs,
                "output": content,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"[CONTENT_AI] Failed to generate content: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def save_content(
    content_type: str,
    inputs: Dict[str, str],
    output: str,
    admin_email: str
) -> Dict[str, Any]:
    """Save approved content to MongoDB"""
    
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        doc = {
            "content_type": content_type,
            "inputs": inputs,
            "output": output,
            "approved_by": admin_email,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "approved",
            "watermark": f"ReRoots Content | {content_type} | {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        }
        
        result = await _db.reroots_content.insert_one(doc)
        
        return {
            "success": True,
            "id": str(result.inserted_id),
            "message": "Content saved successfully"
        }
        
    except Exception as e:
        logger.error(f"[CONTENT_AI] Failed to save content: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_content_history(
    limit: int = 50,
    content_type: Optional[str] = None
) -> List[Dict]:
    """Get content generation history"""
    
    if _db is None:
        return []
    
    try:
        query = {"status": "approved"}
        if content_type:
            query["content_type"] = content_type
        
        contents = await _db.reroots_content.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return contents
        
    except Exception as e:
        logger.error(f"[CONTENT_AI] Failed to get history: {e}")
        return []


async def search_content(
    query: str,
    content_type: Optional[str] = None,
    limit: int = 20
) -> List[Dict]:
    """Search saved content"""
    
    if _db is None:
        return []
    
    try:
        search_query = {
            "status": "approved",
            "$or": [
                {"output": {"$regex": query, "$options": "i"}},
                {"inputs.topic": {"$regex": query, "$options": "i"}},
                {"inputs.product_name": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if content_type:
            search_query["content_type"] = content_type
        
        contents = await _db.reroots_content.find(
            search_query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return contents
        
    except Exception as e:
        logger.error(f"[CONTENT_AI] Failed to search content: {e}")
        return []
