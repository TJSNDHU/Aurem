"""
ReRoots AI Skin Analysis Router
Uses GPT Vision to analyze skin photos and recommend products
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import base64
import json

router = APIRouter(prefix="/api/skin-analysis", tags=["skin-analysis"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SkinAnalysisRequest(BaseModel):
    image_base64: str
    user_concerns: Optional[List[str]] = None
    user_age: Optional[int] = None
    user_skin_type: Optional[str] = None  # oily, dry, combination, normal, sensitive

class SkinAnalysisResponse(BaseModel):
    analysis_id: str
    skin_conditions: List[Dict[str, Any]]
    overall_score: int
    recommended_products: List[Dict[str, Any]]
    personalized_routine: Dict[str, List[str]]
    tips: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# SKIN ANALYSIS PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

SKIN_ANALYSIS_SYSTEM_PROMPT = """You are an expert dermatological AI assistant specializing in skin analysis. 
Analyze the provided skin image and provide detailed, professional insights.

Your analysis should include:
1. Detected skin conditions (acne, wrinkles, dark spots, dryness, oiliness, enlarged pores, redness, uneven texture, etc.)
2. Severity rating for each condition (1-10 scale)
3. Overall skin health score (1-100)
4. Personalized skincare routine recommendations
5. Lifestyle tips for skin improvement

Be professional, empathetic, and avoid making medical diagnoses. 
Always recommend consulting a dermatologist for serious concerns.

Respond in valid JSON format with this structure:
{
  "skin_conditions": [
    {"condition": "string", "severity": number, "location": "string", "description": "string"}
  ],
  "overall_score": number,
  "skin_type_detected": "string",
  "age_estimate": "string",
  "concerns_identified": ["string"],
  "routine": {
    "morning": ["step1", "step2"],
    "evening": ["step1", "step2"],
    "weekly": ["treatment1"]
  },
  "product_categories_needed": ["category1", "category2"],
  "tips": ["tip1", "tip2"]
}"""


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze")
async def analyze_skin(data: SkinAnalysisRequest):
    """Analyze skin from uploaded image using GPT Vision"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="LLM API key not configured")
        
        # Create analysis ID
        import secrets
        analysis_id = f"skin_{secrets.token_hex(8)}"
        
        # Initialize chat with vision model
        chat = LlmChat(
            api_key=api_key,
            session_id=analysis_id,
            system_message=SKIN_ANALYSIS_SYSTEM_PROMPT
        ).with_model("openai", "gpt-5.2")
        
        # Build user context
        user_context = "Please analyze this skin image."
        if data.user_concerns:
            user_context += f" The user has concerns about: {', '.join(data.user_concerns)}."
        if data.user_age:
            user_context += f" User age: {data.user_age}."
        if data.user_skin_type:
            user_context += f" Self-reported skin type: {data.user_skin_type}."
        
        # Create image content
        image_content = ImageContent(image_base64=data.image_base64)
        
        # Send message with image
        user_message = UserMessage(
            text=user_context,
            image_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        
        # Parse JSON response
        try:
            # Clean response if needed
            response_text = response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            analysis_result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            analysis_result = {
                "skin_conditions": [],
                "overall_score": 70,
                "skin_type_detected": "unknown",
                "concerns_identified": [],
                "routine": {"morning": [], "evening": [], "weekly": []},
                "product_categories_needed": [],
                "tips": [response[:500]]
            }
        
        # Get product recommendations from database
        recommended_products = []
        if analysis_result.get("product_categories_needed"):
            for category in analysis_result["product_categories_needed"][:5]:
                products = await db.products.find({
                    "$or": [
                        {"category": {"$regex": category, "$options": "i"}},
                        {"concerns": {"$regex": category, "$options": "i"}},
                        {"tags": {"$regex": category, "$options": "i"}}
                    ],
                    "active": True
                }, {
                    "_id": 0,
                    "id": 1,
                    "name": 1,
                    "price": 1,
                    "images": 1,
                    "short_description": 1
                }).limit(2).to_list(2)
                recommended_products.extend(products)
        
        # Store analysis result
        analysis_record = {
            "analysis_id": analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "user_concerns": data.user_concerns,
            "user_age": data.user_age,
            "user_skin_type": data.user_skin_type,
            "result": analysis_result,
            "recommended_products": [p.get("id") for p in recommended_products]
        }
        await db.skin_analyses.insert_one(analysis_record)
        
        return {
            "analysis_id": analysis_id,
            "skin_conditions": analysis_result.get("skin_conditions", []),
            "overall_score": analysis_result.get("overall_score", 70),
            "skin_type_detected": analysis_result.get("skin_type_detected"),
            "concerns_identified": analysis_result.get("concerns_identified", []),
            "personalized_routine": analysis_result.get("routine", {}),
            "recommended_products": recommended_products,
            "tips": analysis_result.get("tips", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/upload")
async def analyze_skin_upload(
    file: UploadFile = File(...),
    concerns: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    skin_type: Optional[str] = Form(None)
):
    """Analyze skin from uploaded image file"""
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read and encode image
    image_bytes = await file.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # Parse concerns
    user_concerns = concerns.split(",") if concerns else None
    
    # Call main analysis function
    request = SkinAnalysisRequest(
        image_base64=image_base64,
        user_concerns=user_concerns,
        user_age=age,
        user_skin_type=skin_type
    )
    
    return await analyze_skin(request)


@router.get("/history")
async def get_analysis_history(user_id: Optional[str] = None, limit: int = 10):
    """Get skin analysis history"""
    query = {}
    if user_id:
        query["user_id"] = user_id
    
    analyses = await db.skin_analyses.find(
        query,
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return {"analyses": analyses}


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str):
    """Get a specific skin analysis result"""
    analysis = await db.skin_analyses.find_one(
        {"analysis_id": analysis_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return {"analysis": analysis}
