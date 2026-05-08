"""
AUREM GEO Engine — Generative Engine Optimization
===================================================
Tracks how AI agents (GPT, Gemini, Perplexity) perceive and recommend
the merchant's brand. Provides both a calculated score (instant) and
a Live AI Check (on-demand via Emergent LLM Key).

GEO Score Components (0-100):
  - Schema.org / JSON-LD density (0-25)
  - UCP Protocol readiness (0-20)
  - Product data quality (0-20)
  - Brand citation signals (0-20)
  - Content freshness (0-15)
"""

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    return _db


async def calculate_geo_score(tenant_id: str) -> dict:
    """
    Calculate the GEO Index (0-100) based on structured data quality.
    This is the instant "Engine Specs" score.
    """
    db = get_db()
    if db is None:
        return {"score": 0, "breakdown": {}}

    now = datetime.now(timezone.utc)
    breakdown = {}

    # ═══ 1. PRODUCT DATA QUALITY (0-20) ═══
    products = await db.products.find(
        {"tenant_id": tenant_id, "status": "active"}, {"_id": 0}
    ).to_list(500)

    total_products = len(products)
    if total_products == 0:
        breakdown["product_quality"] = {"score": 0, "max": 20, "details": "No products in catalog"}
    else:
        with_desc = sum(1 for p in products if p.get("description", "").strip())
        with_price = sum(1 for p in products if p.get("price", 0) > 0)
        with_sku = sum(1 for p in products if p.get("sku", "").strip())
        with_category = sum(1 for p in products if p.get("category", "").strip())
        with_image = sum(1 for p in products if p.get("image_url", "").strip())
        with_tags = sum(1 for p in products if len(p.get("tags", [])) > 0)

        completeness = (
            (with_desc / total_products) * 4 +
            (with_price / total_products) * 4 +
            (with_sku / total_products) * 3 +
            (with_category / total_products) * 3 +
            (with_image / total_products) * 3 +
            (with_tags / total_products) * 3
        )
        score = min(20, round(completeness))
        breakdown["product_quality"] = {
            "score": score, "max": 20,
            "details": f"{total_products} products — {with_desc} have descriptions, {with_image} have images, {with_tags} have tags",
            "recommendations": []
        }
        if with_desc < total_products:
            breakdown["product_quality"]["recommendations"].append(f"Add descriptions to {total_products - with_desc} products")
        if with_image < total_products:
            breakdown["product_quality"]["recommendations"].append(f"Add images to {total_products - with_image} products")
        if with_tags < total_products:
            breakdown["product_quality"]["recommendations"].append(f"Add tags to {total_products - with_tags} products for better AI discovery")

    # ═══ 2. UCP READINESS (0-20) ═══
    connections = await db.platform_connections.count_documents({"tenant_id": tenant_id})
    has_products = total_products > 0
    has_ucp_orders = await db.universal_orders.count_documents({"tenant_id": tenant_id}) > 0
    has_negotiations = await db.ucp_negotiations.count_documents({"tenant_id": tenant_id}) > 0

    ucp_score = 0
    ucp_details = []
    if connections > 0:
        ucp_score += 5
        ucp_details.append(f"{connections} platform(s) connected")
    else:
        ucp_details.append("No platforms connected — connect at least one")
    if has_products:
        ucp_score += 5
        ucp_details.append("Product catalog populated")
    if has_ucp_orders:
        ucp_score += 5
        ucp_details.append("AI agent orders received")
    if has_negotiations:
        ucp_score += 5
        ucp_details.append("AI negotiations active")

    ucp_score = min(20, ucp_score)
    # UCP manifest is always available = +5 baseline
    ucp_score = min(20, ucp_score + 5)
    ucp_details.insert(0, "UCP manifest active at /.well-known/ucp")

    breakdown["ucp_readiness"] = {"score": ucp_score, "max": 20, "details": "; ".join(ucp_details)}

    # ═══ 3. SCHEMA / STRUCTURED DATA (0-25) ═══
    # Check knowledge base and training data quality
    kb_count = await db.knowledge_base.count_documents({"tenant_id": tenant_id})
    has_invoice_system = await db.invoices.count_documents({"tenant_id": tenant_id}) > 0

    schema_score = 5  # Base: AUREM provides structured JSON APIs
    schema_details = ["AUREM JSON APIs are machine-readable by default"]
    if kb_count > 0:
        schema_score += min(10, kb_count * 2)
        schema_details.append(f"{kb_count} knowledge base entries enrich AI context")
    if has_invoice_system:
        schema_score += 5
        schema_details.append("Invoice/payment data structured for agent verification")
    if total_products > 0:
        schema_score += 5
        schema_details.append("Product schema includes price, availability, category, tags")

    schema_score = min(25, schema_score)
    breakdown["schema_density"] = {"score": schema_score, "max": 25, "details": "; ".join(schema_details)}

    # ═══ 4. BRAND CITATION SIGNALS (0-20) ═══
    # Based on data that would generate citations
    customers = await db.tenant_customers.count_documents({"tenant_id": tenant_id})
    events = await db.universal_events.count_documents({"tenant_id": tenant_id})

    citation_score = 0
    citation_details = []
    if customers > 50:
        citation_score += 5
        citation_details.append(f"{customers} customers = strong market presence signal")
    elif customers > 0:
        citation_score += 2
        citation_details.append(f"{customers} customers — grow to 50+ for stronger AI signals")

    if total_products > 10:
        citation_score += 5
        citation_details.append("Diverse product catalog increases recommendation surface")
    elif total_products > 0:
        citation_score += 2
        citation_details.append(f"{total_products} products — expand to 10+ for better coverage")

    if events > 0:
        citation_score += 5
        citation_details.append(f"{events} tracking events provide behavioral signals")

    # Ghost Mode activity signals "active business"
    ghost_actions = await db.ghost_actions.count_documents({"tenant_id": tenant_id})
    if ghost_actions > 0:
        citation_score += 5
        citation_details.append("Ghost Mode active — consistent operational signals")

    citation_score = min(20, citation_score)
    breakdown["citation_signals"] = {"score": citation_score, "max": 20, "details": "; ".join(citation_details) if citation_details else "Build your customer base and product catalog"}

    # ═══ 5. CONTENT FRESHNESS (0-15) ═══
    recent_products = await db.products.count_documents({
        "tenant_id": tenant_id,
        "updated_at": {"$gte": (now - timedelta(days=7)).isoformat()},
    })
    recent_invoices = await db.invoices.count_documents({
        "tenant_id": tenant_id,
        "created_at": {"$gte": (now - timedelta(days=7)).isoformat()},
    })

    freshness_score = 0
    freshness_details = []
    if recent_products > 0:
        freshness_score += 7
        freshness_details.append(f"{recent_products} products updated in last 7 days")
    if recent_invoices > 0:
        freshness_score += 5
        freshness_details.append(f"{recent_invoices} invoices created in last 7 days")
    if ghost_actions > 0:
        freshness_score += 3
        freshness_details.append("Autonomous operations maintain freshness signals")

    freshness_score = min(15, freshness_score)
    breakdown["content_freshness"] = {"score": freshness_score, "max": 15, "details": "; ".join(freshness_details) if freshness_details else "Update products and create invoices to boost freshness"}

    # ═══ TOTAL SCORE ═══
    total = sum(b["score"] for b in breakdown.values())
    grade = "A+" if total >= 90 else "A" if total >= 80 else "B+" if total >= 70 else "B" if total >= 60 else "C+" if total >= 50 else "C" if total >= 40 else "D"

    return {
        "score": total,
        "max_score": 100,
        "grade": grade,
        "breakdown": breakdown,
        "calculated_at": now.isoformat(),
        "recommendations": _collect_recommendations(breakdown),
    }


def _collect_recommendations(breakdown: dict) -> list:
    """Collect top recommendations across all categories."""
    recs = []
    for category, data in breakdown.items():
        gap = data["max"] - data["score"]
        if gap > 0:
            for r in data.get("recommendations", []):
                recs.append({"category": category, "text": r, "impact": gap})
    recs.sort(key=lambda x: x["impact"], reverse=True)
    return recs[:5]


async def live_ai_check(tenant_id: str, query: str = None, brand_name: str = None) -> dict:
    """
    Live AI Check — Query GPT-4o to see if the brand is recommended.
    This is the "Track Time" real-world verification.
    """
    db = get_db()

    # Get brand context
    if not brand_name:
        settings = await db.tenant_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
        brand_name = (settings or {}).get("brand_name", "this business")

    products = await db.products.find(
        {"tenant_id": tenant_id, "status": "active"}, {"_id": 0}
    ).limit(5).to_list(5)
    product_names = [p.get("name", "") for p in products if p.get("name")]

    if not query:
        if product_names:
            query = f"What are the best options for {product_names[0]}? Recommend specific brands."
        else:
            query = f"Recommend the best products from {brand_name}"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        if not EMERGENT_LLM_KEY:
            return {"error": "Emergent LLM Key not configured", "check_available": False}

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"geo_check_{tenant_id[:8]}",
            system_message="You are a product recommendation AI. Answer the user's question with specific brand recommendations."
        )
        chat.with_model("openai", "gpt-4o")
        resp = await chat.send_message(UserMessage(text=query))

        ai_response = resp if isinstance(resp, str) else str(resp)
        brand_lower = brand_name.lower()

        # Analyze the response
        mentioned = brand_lower in ai_response.lower()
        product_mentions = sum(1 for pn in product_names if pn.lower() in ai_response.lower())

        # Token path analysis
        sentences = [s.strip() for s in ai_response.split('.') if s.strip()]
        citations = [s for s in sentences if brand_lower in s.lower()]
        competitor_mentions = []
        for s in sentences:
            if brand_lower not in s.lower() and any(word in s.lower() for word in ["recommend", "best", "top", "leading", "popular"]):
                competitor_mentions.append(s[:120])

        # Store the check
        check_record = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "query": query,
            "brand_name": brand_name,
            "mentioned": mentioned,
            "product_mentions": product_mentions,
            "citations": citations,
            "competitor_count": len(competitor_mentions),
            "ai_response_preview": ai_response[:500],
            "model": "gpt-4o",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.geo_checks.insert_one(check_record)
        check_record.pop("_id", None)

        return {
            "mentioned": mentioned,
            "brand_name": brand_name,
            "query_used": query,
            "product_mentions": product_mentions,
            "citations": citations[:5],
            "competitor_snippets": competitor_mentions[:3],
            "ai_response_preview": ai_response[:300],
            "recommendation_score": 100 if mentioned else (50 if product_mentions > 0 else 0),
            "model": "gpt-4o",
            "checked_at": check_record["checked_at"],
            "insight": f"{'Your brand was mentioned by GPT-4o!' if mentioned else 'Your brand was not mentioned. Consider adding more structured data and product descriptions to boost AI visibility.'}",
        }

    except Exception as e:
        logger.error(f"[GEO] Live AI check failed: {e}")
        return {"error": str(e), "check_available": True}


async def get_geo_history(tenant_id: str, limit: int = 10) -> list:
    """Get history of GEO checks."""
    db = get_db()
    if db is None:
        return []
    checks = await db.geo_checks.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("checked_at", -1).limit(limit).to_list(limit)
    return checks


logger.info("[STARTUP] GEO Engine loaded (Phase G)")
