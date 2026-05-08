"""
TOON API Router
Token-Oriented Object Notation for LLM optimization
Reduces JSON token usage by 30-60%
"""

import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from utils.toon_encoder import (
    json_to_toon,
    toon_to_json,
    estimate_token_savings,
    ToonMiddleware,
    ReRootsToonEncoder
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/toon", tags=["TOON Encoder"])

# MongoDB reference
_db = None
_middleware = ToonMiddleware()

def set_db(database):
    """Set database reference"""
    global _db, _middleware
    _db = database
    _middleware.set_db(database)


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ConvertRequest(BaseModel):
    data: Any = Field(..., description="JSON data to convert")
    data_type: Optional[str] = Field(None, description="Type hint: formula, products, inventory, customer, order")


class CompareRequest(BaseModel):
    data: Any = Field(..., description="JSON data to compare")
    data_type: Optional[str] = Field(None)


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/convert")
async def convert_to_toon(request: ConvertRequest):
    """
    Convert JSON data to TOON format
    """
    try:
        toon_output = json_to_toon(request.data, request.data_type)
        
        return {
            "toon": toon_output,
            "stats": estimate_token_savings(request.data, request.data_type)
        }
        
    except Exception as e:
        logger.error(f"[TOON] Convert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_json_toon(request: CompareRequest):
    """
    Compare JSON vs TOON - show before/after with token savings
    """
    try:
        json_str = json.dumps(request.data, indent=2)
        toon_str = json_to_toon(request.data, request.data_type)
        stats = estimate_token_savings(request.data, request.data_type)
        
        return {
            "before": {
                "format": "JSON",
                "content": json_str,
                "chars": stats['json_chars']
            },
            "after": {
                "format": "TOON",
                "content": toon_str,
                "chars": stats['toon_chars']
            },
            "savings": {
                "percent": stats['savings_percent'],
                "tokens_saved": stats['estimated_tokens_saved'],
                "description": f"Reduced by {stats['savings_percent']}% ({stats['estimated_tokens_saved']} tokens saved)"
            }
        }
        
    except Exception as e:
        logger.error(f"[TOON] Compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCH WITH TOON
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/products")
async def get_products_toon(limit: int = 20):
    """
    Fetch products and return as TOON
    """
    try:
        toon_output = await _middleware.get_products_toon(limit=limit)
        
        # Also get JSON for comparison
        if _db is not None:
            products = await _db.products.find(
                {},
                {'_id': 0, 'name': 1, 'price': 1, 'stock': 1, 'category': 1}
            ).limit(limit).to_list(limit)
            stats = estimate_token_savings(products, 'products')
        else:
            stats = {'savings_percent': 0}
        
        return {
            "format": "TOON",
            "data": toon_output,
            "savings_percent": stats.get('savings_percent', 0)
        }
        
    except Exception as e:
        logger.error(f"[TOON] Products error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory")
async def get_inventory_toon(low_stock_only: bool = False):
    """
    Fetch inventory and return as TOON
    """
    try:
        toon_output = await _middleware.get_inventory_toon(low_stock_only)
        
        return {
            "format": "TOON",
            "data": toon_output,
            "low_stock_only": low_stock_only
        }
        
    except Exception as e:
        logger.error(f"[TOON] Inventory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formula/{product_id}")
async def get_formula_toon(product_id: str):
    """
    Fetch product formula and return as TOON
    """
    try:
        toon_output = await _middleware.get_formula_toon(product_id)
        
        return {
            "format": "TOON",
            "data": toon_output
        }
        
    except Exception as e:
        logger.error(f"[TOON] Formula error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}")
async def get_customer_toon(customer_id: str):
    """
    Fetch customer data and return as TOON
    """
    try:
        toon_output = await _middleware.get_customer_toon(customer_id)
        
        return {
            "format": "TOON",
            "data": toon_output
        }
        
    except Exception as e:
        logger.error(f"[TOON] Customer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/demo")
async def demo_toon_savings():
    """
    Demo showing TOON savings with sample ReRoots data
    """
    # Sample Aura-Gen formula
    formula_json = {
        "name": "AURA-GEN PDRN + TXA + ARGIRELINE 17%",
        "ingredients": [
            {"ingredient": "Water", "percentage": 60, "function": "Base solvent"},
            {"ingredient": "PDRN", "percentage": 5, "function": "Cellular repair"},
            {"ingredient": "Tranexamic Acid", "percentage": 4, "function": "Brightening"},
            {"ingredient": "Argireline", "percentage": 3, "function": "Anti-wrinkle"},
            {"ingredient": "Niacinamide", "percentage": 2, "function": "Pore refinement"},
            {"ingredient": "Hyaluronic Acid", "percentage": 1.5, "function": "Hydration"},
            {"ingredient": "Peptide Complex", "percentage": 1, "function": "Firming"},
            {"ingredient": "Centella Asiatica", "percentage": 0.5, "function": "Soothing"},
            {"ingredient": "Allantoin", "percentage": 0.3, "function": "Healing"},
            {"ingredient": "Adenosine", "percentage": 0.2, "function": "Anti-aging"},
            {"ingredient": "Preservatives", "percentage": 0.1, "function": "Stability"},
            {"ingredient": "Fragrance", "percentage": 0.05, "function": "Scent"}
        ],
        "ph_level": "5.5-6.0",
        "texture": "Lightweight serum",
        "absorption_rate": "Fast"
    }
    
    # Sample product catalog
    products_json = [
        {"name": "AURA-GEN Serum", "price": 89.99, "stock": 45, "category": "Serum"},
        {"name": "Copper Peptide Complex", "price": 79.99, "stock": 32, "category": "Treatment"},
        {"name": "Biotech Cleanser", "price": 39.99, "stock": 67, "category": "Cleanser"},
        {"name": "Hydra-Barrier Moisturizer", "price": 59.99, "stock": 28, "category": "Moisturizer"},
        {"name": "Cell Renewal Mask", "price": 49.99, "stock": 51, "category": "Mask"}
    ]
    
    encoder = ReRootsToonEncoder()
    
    # Convert and calculate savings
    formula_toon = encoder.encode_formula(formula_json)
    products_toon = encoder.encode_products(products_json)
    
    formula_stats = estimate_token_savings(formula_json, 'formula')
    products_stats = estimate_token_savings(products_json, 'products')
    
    return {
        "formula_comparison": {
            "json": json.dumps(formula_json, indent=2),
            "toon": formula_toon,
            "savings": formula_stats
        },
        "products_comparison": {
            "json": json.dumps(products_json, indent=2),
            "toon": products_toon,
            "savings": products_stats
        },
        "summary": {
            "formula_savings": f"{formula_stats['savings_percent']}%",
            "products_savings": f"{products_stats['savings_percent']}%",
            "total_tokens_saved": formula_stats['estimated_tokens_saved'] + products_stats['estimated_tokens_saved']
        }
    }
