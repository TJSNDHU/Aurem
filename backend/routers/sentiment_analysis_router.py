"""
ReRoots AI Sentiment Analysis Router
Analyzes customer reviews and feedback to identify trends and insights
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json

router = APIRouter(prefix="/api/sentiment", tags=["sentiment-analysis"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyzeTextRequest(BaseModel):
    text: str
    context: Optional[str] = None  # review, feedback, support, social

class BatchAnalyzeRequest(BaseModel):
    texts: List[str]
    context: Optional[str] = None

class ReviewAnalysisRequest(BaseModel):
    product_id: Optional[str] = None
    days: int = 30


# ═══════════════════════════════════════════════════════════════════════════════
# SENTIMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

SENTIMENT_SYSTEM_PROMPT = """You are an expert sentiment analysis AI for a skincare brand.
Analyze the provided text and extract:
1. Overall sentiment (positive, negative, neutral, mixed)
2. Sentiment score (-1.0 to 1.0)
3. Emotions detected (happy, frustrated, satisfied, disappointed, excited, etc.)
4. Key topics mentioned
5. Product feedback categories (effectiveness, texture, scent, packaging, price, shipping)
6. Improvement suggestions if any
7. Purchase intent signals

Respond in valid JSON format:
{
  "sentiment": "positive|negative|neutral|mixed",
  "score": 0.0,
  "confidence": 0.0,
  "emotions": ["emotion1", "emotion2"],
  "topics": ["topic1", "topic2"],
  "feedback_categories": {
    "effectiveness": "positive|negative|neutral|null",
    "texture": "positive|negative|neutral|null",
    "scent": "positive|negative|neutral|null",
    "packaging": "positive|negative|neutral|null",
    "price": "positive|negative|neutral|null",
    "shipping": "positive|negative|neutral|null"
  },
  "suggestions": ["suggestion1"],
  "purchase_intent": "high|medium|low|none",
  "key_phrases": ["phrase1", "phrase2"]
}"""


async def analyze_sentiment(text: str, context: str = "review") -> Dict[str, Any]:
    """Analyze sentiment of text using LLM"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            # Fallback to basic analysis
            return basic_sentiment_analysis(text)
        
        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"sentiment_{secrets.token_hex(6)}",
            system_message=SENTIMENT_SYSTEM_PROMPT
        ).with_model("openai", "gpt-5-mini")  # Use smaller model for speed
        
        response = await chat.send_message(UserMessage(
            text=f"Context: {context}\n\nText to analyze:\n{text}"
        ))
        
        # Parse JSON response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
        except:
            return basic_sentiment_analysis(text)
            
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return basic_sentiment_analysis(text)


def basic_sentiment_analysis(text: str) -> Dict[str, Any]:
    """Basic rule-based sentiment analysis fallback"""
    text_lower = text.lower()
    
    positive_words = ["love", "great", "amazing", "excellent", "best", "perfect", "wonderful", "fantastic", "happy", "satisfied", "recommend", "worth", "effective", "smooth", "glowing"]
    negative_words = ["hate", "terrible", "awful", "worst", "bad", "disappointed", "waste", "horrible", "poor", "useless", "broke", "irritated", "burning", "allergic"]
    
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        sentiment = "positive"
        score = min(0.5 + (pos_count * 0.1), 1.0)
    elif neg_count > pos_count:
        sentiment = "negative"
        score = max(-0.5 - (neg_count * 0.1), -1.0)
    else:
        sentiment = "neutral"
        score = 0.0
    
    return {
        "sentiment": sentiment,
        "score": round(score, 2),
        "confidence": 0.6,
        "emotions": [],
        "topics": [],
        "feedback_categories": {},
        "suggestions": [],
        "purchase_intent": "medium" if sentiment == "positive" else "low",
        "key_phrases": []
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze")
async def analyze_text_sentiment(data: AnalyzeTextRequest):
    """Analyze sentiment of provided text"""
    result = await analyze_sentiment(data.text, data.context or "general")
    
    # Store analysis
    await db.sentiment_analyses.insert_one({
        "text": data.text[:500],  # Truncate for storage
        "context": data.context,
        "result": result,
        "analyzed_at": datetime.now(timezone.utc)
    })
    
    return result


@router.post("/analyze/batch")
async def analyze_batch_sentiment(data: BatchAnalyzeRequest):
    """Analyze sentiment of multiple texts"""
    results = []
    
    for text in data.texts[:50]:  # Limit to 50 texts
        result = await analyze_sentiment(text, data.context or "general")
        results.append({
            "text": text[:100] + "..." if len(text) > 100 else text,
            "analysis": result
        })
    
    # Calculate aggregate stats
    scores = [r["analysis"]["score"] for r in results]
    sentiments = [r["analysis"]["sentiment"] for r in results]
    
    return {
        "results": results,
        "aggregate": {
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "sentiment_distribution": {
                "positive": sentiments.count("positive"),
                "negative": sentiments.count("negative"),
                "neutral": sentiments.count("neutral"),
                "mixed": sentiments.count("mixed")
            },
            "total_analyzed": len(results)
        }
    }


@router.get("/reviews/analysis")
async def analyze_product_reviews(product_id: Optional[str] = None, days: int = 30):
    """Analyze sentiment of product reviews"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = {"created_at": {"$gte": since}}
    if product_id:
        query["product_id"] = product_id
    
    # Get reviews
    reviews = await db.reviews.find(query).to_list(100)
    
    if not reviews:
        return {
            "message": "No reviews found for the specified criteria",
            "total_reviews": 0
        }
    
    # Analyze each review
    analyses = []
    for review in reviews:
        text = review.get("review_text") or review.get("text") or review.get("comment", "")
        if text:
            analysis = await analyze_sentiment(text, "review")
            analyses.append({
                "review_id": str(review.get("_id")),
                "rating": review.get("rating"),
                "analysis": analysis
            })
    
    # Calculate aggregate insights
    if analyses:
        scores = [a["analysis"]["score"] for a in analyses]
        sentiments = [a["analysis"]["sentiment"] for a in analyses]
        
        # Extract common topics
        all_topics = []
        for a in analyses:
            all_topics.extend(a["analysis"].get("topics", []))
        
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Extract common suggestions
        all_suggestions = []
        for a in analyses:
            all_suggestions.extend(a["analysis"].get("suggestions", []))
        
        return {
            "total_reviews": len(analyses),
            "period_days": days,
            "aggregate": {
                "average_sentiment_score": round(sum(scores) / len(scores), 2),
                "sentiment_distribution": {
                    "positive": sentiments.count("positive"),
                    "negative": sentiments.count("negative"),
                    "neutral": sentiments.count("neutral"),
                    "mixed": sentiments.count("mixed")
                },
                "top_topics": top_topics,
                "common_suggestions": list(set(all_suggestions))[:10]
            },
            "detailed_analyses": analyses[:20]  # Return first 20 detailed analyses
        }
    
    return {"total_reviews": 0, "message": "No analyzable reviews found"}


@router.get("/trends")
async def get_sentiment_trends(days: int = 30):
    """Get sentiment trends over time"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Daily sentiment averages
    daily_trends = await db.sentiment_analyses.aggregate([
        {"$match": {"analyzed_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$analyzed_at"}},
            "avg_score": {"$avg": "$result.score"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]).to_list(100)
    
    # Overall stats
    total = await db.sentiment_analyses.count_documents({"analyzed_at": {"$gte": since}})
    
    sentiment_dist = await db.sentiment_analyses.aggregate([
        {"$match": {"analyzed_at": {"$gte": since}}},
        {"$group": {
            "_id": "$result.sentiment",
            "count": {"$sum": 1}
        }}
    ]).to_list(10)
    
    return {
        "period_days": days,
        "total_analyses": total,
        "daily_trends": daily_trends,
        "sentiment_distribution": {s["_id"]: s["count"] for s in sentiment_dist if s["_id"]}
    }
