"""
ReRoots AI Product Description Generator
Auto-generate SEO-optimized product descriptions and marketing copy
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json

router = APIRouter(prefix="/api/product-ai", tags=["product-ai"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class GenerateDescriptionRequest(BaseModel):
    product_name: str
    category: str
    key_ingredients: List[str]
    benefits: Optional[List[str]] = None
    target_audience: Optional[str] = None
    skin_concerns: Optional[List[str]] = None
    tone: str = "luxury"  # luxury, scientific, friendly, minimal
    length: str = "medium"  # short, medium, long

class GenerateMarketingCopyRequest(BaseModel):
    product_name: str
    description: str
    platform: str  # instagram, email, website, ad
    tone: str = "engaging"
    include_cta: bool = True

class BulkGenerateRequest(BaseModel):
    products: List[Dict[str, Any]]
    output_type: str = "description"  # description, tagline, benefits


# ═══════════════════════════════════════════════════════════════════════════════
# AI GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

DESCRIPTION_SYSTEM_PROMPT = """You are an expert skincare copywriter for a luxury biotech skincare brand called ReRoots.
Create compelling, SEO-optimized product descriptions that:
1. Highlight scientific innovation and natural ingredients
2. Use sensory language that evokes luxury
3. Address specific skin concerns
4. Include key benefits
5. Are suitable for e-commerce product pages

Brand voice: Scientific yet accessible, luxurious but approachable, confident and authoritative.

Respond in JSON format:
{
  "short_description": "50-word summary",
  "full_description": "detailed 150-250 word description",
  "tagline": "catchy one-liner",
  "key_benefits": ["benefit1", "benefit2", "benefit3"],
  "how_to_use": "usage instructions",
  "seo_keywords": ["keyword1", "keyword2"],
  "meta_description": "SEO meta description under 160 chars"
}"""

MARKETING_SYSTEM_PROMPT = """You are a social media and marketing copywriter for ReRoots, a luxury biotech skincare brand.
Create engaging marketing copy that drives conversions while maintaining the brand's sophisticated voice.

For Instagram: Use emojis sparingly, include relevant hashtags, keep it concise yet impactful.
For Email: Create compelling subject lines and body copy with clear CTAs.
For Website: Write conversion-focused hero text and feature descriptions.
For Ads: Create punchy, benefit-driven copy with strong CTAs.

Respond in JSON format:
{
  "primary_copy": "main marketing text",
  "headline": "attention-grabbing headline",
  "subheadline": "supporting text",
  "cta_text": "call to action button text",
  "hashtags": ["hashtag1", "hashtag2"],
  "variations": ["variation1", "variation2"]
}"""


async def generate_with_ai(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """Generate content using AI"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")
        
        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"product_ai_{secrets.token_hex(6)}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        # Parse JSON response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
        except:
            return {"error": "Failed to parse response", "raw": response[:500]}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/generate/description")
async def generate_product_description(data: GenerateDescriptionRequest):
    """Generate AI-powered product description"""
    
    # Build prompt
    prompt = f"""Create a product description for:

Product: {data.product_name}
Category: {data.category}
Key Ingredients: {', '.join(data.key_ingredients)}
"""
    
    if data.benefits:
        prompt += f"Benefits: {', '.join(data.benefits)}\n"
    if data.target_audience:
        prompt += f"Target Audience: {data.target_audience}\n"
    if data.skin_concerns:
        prompt += f"Addresses: {', '.join(data.skin_concerns)}\n"
    
    prompt += f"\nTone: {data.tone}\nLength: {data.length}"
    
    result = await generate_with_ai(DESCRIPTION_SYSTEM_PROMPT, prompt)
    
    # Store generation
    await db.ai_generations.insert_one({
        "type": "product_description",
        "input": data.dict(),
        "output": result,
        "created_at": datetime.now(timezone.utc)
    })
    
    return result


@router.post("/generate/marketing")
async def generate_marketing_copy(data: GenerateMarketingCopyRequest):
    """Generate marketing copy for various platforms"""
    
    prompt = f"""Create {data.platform} marketing copy for:

Product: {data.product_name}
Description: {data.description}
Tone: {data.tone}
Include CTA: {data.include_cta}
"""
    
    result = await generate_with_ai(MARKETING_SYSTEM_PROMPT, prompt)
    
    # Store generation
    await db.ai_generations.insert_one({
        "type": "marketing_copy",
        "platform": data.platform,
        "input": data.dict(),
        "output": result,
        "created_at": datetime.now(timezone.utc)
    })
    
    return result


@router.post("/generate/tagline")
async def generate_tagline(
    product_name: str,
    key_benefit: str,
    style: str = "luxury"
):
    """Generate product tagline"""
    
    prompt = f"""Generate 5 tagline options for:
Product: {product_name}
Key Benefit: {key_benefit}
Style: {style}

Respond in JSON: {{"taglines": ["tagline1", "tagline2", ...]}}"""
    
    result = await generate_with_ai(
        "You are a luxury skincare brand copywriter. Create catchy, memorable taglines.",
        prompt
    )
    
    return result


@router.post("/generate/benefits")
async def generate_product_benefits(
    product_name: str,
    ingredients: List[str],
    category: str
):
    """Generate product benefits from ingredients"""
    
    prompt = f"""Based on these ingredients, generate compelling benefit statements for:
Product: {product_name}
Category: {category}
Ingredients: {', '.join(ingredients)}

Respond in JSON:
{{
  "primary_benefits": ["benefit1", "benefit2", "benefit3"],
  "ingredient_benefits": {{"ingredient": "specific benefit"}},
  "claims": ["clinically-inspired claim1"],
  "differentiators": ["what makes this unique"]
}}"""
    
    result = await generate_with_ai(DESCRIPTION_SYSTEM_PROMPT, prompt)
    
    return result


@router.post("/generate/bulk")
async def bulk_generate(data: BulkGenerateRequest):
    """Generate content for multiple products"""
    results = []
    
    for product in data.products[:10]:  # Limit to 10 products
        try:
            if data.output_type == "description":
                request = GenerateDescriptionRequest(
                    product_name=product.get("name", "Unknown"),
                    category=product.get("category", "Skincare"),
                    key_ingredients=product.get("ingredients", []),
                    benefits=product.get("benefits"),
                    tone=product.get("tone", "luxury"),
                    length=product.get("length", "medium")
                )
                result = await generate_product_description(request)
            elif data.output_type == "tagline":
                result = await generate_tagline(
                    product.get("name", "Unknown"),
                    product.get("key_benefit", "skincare"),
                    product.get("style", "luxury")
                )
            else:
                result = await generate_product_benefits(
                    product.get("name", "Unknown"),
                    product.get("ingredients", []),
                    product.get("category", "Skincare")
                )
            
            results.append({
                "product": product.get("name"),
                "success": True,
                "output": result
            })
        except Exception as e:
            results.append({
                "product": product.get("name"),
                "success": False,
                "error": str(e)
            })
    
    return {
        "total": len(data.products),
        "processed": len(results),
        "results": results
    }


@router.get("/history")
async def get_generation_history(
    type: Optional[str] = None,
    limit: int = 20
):
    """Get AI generation history"""
    query = {}
    if type:
        query["type"] = type
    
    generations = await db.ai_generations.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"generations": generations}


@router.post("/improve")
async def improve_description(
    current_description: str,
    feedback: str,
    focus: Optional[str] = None
):
    """Improve existing product description based on feedback"""
    
    prompt = f"""Improve this product description based on the feedback:

Current Description:
{current_description}

Feedback: {feedback}
{f'Focus on: {focus}' if focus else ''}

Provide the improved version in JSON:
{{
  "improved_description": "the improved description",
  "changes_made": ["change1", "change2"],
  "seo_score_improvement": "estimate"
}}"""
    
    result = await generate_with_ai(DESCRIPTION_SYSTEM_PROMPT, prompt)
    
    return result
