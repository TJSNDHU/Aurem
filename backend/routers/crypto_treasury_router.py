"""
Crypto Treasury Router
Admin APIs for crypto treasury management
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from services.crypto_treasury.treasury_service import get_treasury_service
from services.crypto_treasury.polygon_wallet_service import get_polygon_wallet_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/crypto-treasury",
    tags=["Crypto Treasury"]
)

# MongoDB reference
_db = None


def set_db(database):
    global _db
    _db = database
    logger.info("[CryptoTreasury] Database set")


# Request Models
class RevenueRecordRequest(BaseModel):
    amount_usd: float = Field(..., gt=0, description="Amount in USD")
    description: str
    stripe_payment_id: Optional[str] = None


class ExpenseRecordRequest(BaseModel):
    amount_usd: float = Field(..., gt=0, description="Amount in USD")
    description: str
    category: str = Field(default="general", description="Expense category")


class ConversionRequest(BaseModel):
    amount_usd: Optional[float] = Field(default=None, description="Amount to convert, or None for all available")
    auto_send: bool = Field(default=True, description="Auto-send to treasury wallet")


class ConfigUpdateRequest(BaseModel):
    expense_reserve_usd: Optional[float] = Field(default=None, gt=0)
    auto_conversion_enabled: Optional[bool] = None
    conversion_threshold_usd: Optional[float] = Field(default=None, gt=0)
    conversion_frequency: Optional[str] = None
    treasury_wallet_address: Optional[str] = None


class SetWalletRequest(BaseModel):
    wallet_address: str = Field(..., description="Polygon wallet address")


# Endpoints

@router.get("/stats")
async def get_treasury_stats():
    """
    Get comprehensive treasury statistics
    
    Returns:
    - Total revenue (USD)
    - Total expenses (USD)
    - Current profit (USD)
    - Total converted (USDT)
    - Treasury wallet balance (USDT)
    - Conversion eligibility
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        stats = await treasury_service.get_treasury_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Stats error: {e}")
        raise HTTPException(500, str(e))


@router.get("/config")
async def get_config():
    """
    Get current treasury configuration
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        config = await treasury_service.get_config()
        
        return {
            "success": True,
            "config": config
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Config retrieval error: {e}")
        raise HTTPException(500, str(e))


@router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update treasury configuration
    
    Example:
    {
        "expense_reserve_usd": 10000,
        "auto_conversion_enabled": true,
        "conversion_threshold_usd": 2000
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Build updates dict (only include provided fields)
        updates = {}
        if request.expense_reserve_usd is not None:
            updates["expense_reserve_usd"] = request.expense_reserve_usd
        if request.auto_conversion_enabled is not None:
            updates["auto_conversion_enabled"] = request.auto_conversion_enabled
        if request.conversion_threshold_usd is not None:
            updates["conversion_threshold_usd"] = request.conversion_threshold_usd
        if request.conversion_frequency is not None:
            updates["conversion_frequency"] = request.conversion_frequency
        if request.treasury_wallet_address is not None:
            updates["treasury_wallet_address"] = request.treasury_wallet_address
        
        if not updates:
            raise HTTPException(400, "No fields to update")
        
        treasury_service = get_treasury_service(_db)
        config = await treasury_service.update_config(updates)
        
        return {
            "success": True,
            "config": config,
            "message": f"Updated {len(updates)} config field(s)"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CryptoTreasury] Config update error: {e}")
        raise HTTPException(500, str(e))


@router.post("/revenue")
async def record_revenue(request: RevenueRecordRequest):
    """
    Record revenue from Stripe payments
    
    Example:
    {
        "amount_usd": 99.00,
        "description": "Starter plan subscription",
        "stripe_payment_id": "pi_xxxxx"
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        transaction_id = await treasury_service.record_revenue(
            amount_usd=request.amount_usd,
            description=request.description,
            stripe_payment_id=request.stripe_payment_id
        )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount_usd": request.amount_usd
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Revenue recording error: {e}")
        raise HTTPException(500, str(e))


@router.post("/expense")
async def record_expense(request: ExpenseRecordRequest):
    """
    Record business expense
    
    Example:
    {
        "amount_usd": 500.00,
        "description": "AWS hosting - January 2026",
        "category": "hosting"
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        transaction_id = await treasury_service.record_expense(
            amount_usd=request.amount_usd,
            description=request.description,
            category=request.category
        )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount_usd": request.amount_usd,
            "category": request.category
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Expense recording error: {e}")
        raise HTTPException(500, str(e))


@router.get("/profit")
async def calculate_profit():
    """
    Calculate current profit
    
    Returns:
    - Total revenue
    - Total expenses
    - Total converted
    - Current profit (not yet converted)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        profit_data = await treasury_service.calculate_profit()
        
        return {
            "success": True,
            "profit": profit_data
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Profit calculation error: {e}")
        raise HTTPException(500, str(e))


@router.get("/conversion-eligibility")
async def check_conversion_eligibility():
    """
    Check if auto-conversion should trigger
    
    Returns:
    - Whether eligible for conversion
    - Available amount
    - Threshold settings
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        eligibility = await treasury_service.check_conversion_eligibility()
        
        return {
            "success": True,
            "eligibility": eligibility
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Eligibility check error: {e}")
        raise HTTPException(500, str(e))


@router.post("/convert")
async def convert_to_usdt(request: ConversionRequest):
    """
    Manually trigger USD to USDT conversion
    
    Example:
    {
        "amount_usd": 1500.00,
        "auto_send": true
    }
    
    Or leave empty to convert all available profit:
    {
        "auto_send": true
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        treasury_service = get_treasury_service(_db)
        result = await treasury_service.convert_profit_to_usdt(
            amount_usd=request.amount_usd,
            auto_send=request.auto_send
        )
        
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "Conversion failed"))
        
        return {
            "success": True,
            "conversion": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CryptoTreasury] Conversion error: {e}")
        raise HTTPException(500, str(e))


# Wallet Management Endpoints

@router.post("/wallet/create")
async def create_treasury_wallet():
    """
    Create a new Polygon wallet for USDT treasury
    
    Returns wallet address (private key stored securely in DB)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        polygon_service = get_polygon_wallet_service(_db)
        wallet_info = await polygon_service.create_treasury_wallet()
        
        return {
            "success": True,
            "wallet": wallet_info,
            "message": "Treasury wallet created. Set as primary via /wallet/set-primary"
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Wallet creation error: {e}")
        raise HTTPException(500, str(e))


@router.get("/wallet/{wallet_address}/balance")
async def get_wallet_balance(wallet_address: str):
    """
    Get USDT and MATIC balance for a wallet
    
    Path params:
        wallet_address: Polygon wallet address (0x...)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        polygon_service = get_polygon_wallet_service(_db)
        balance_info = await polygon_service.get_wallet_balance(wallet_address)
        
        return {
            "success": True,
            "balance": balance_info
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Balance check error: {e}")
        raise HTTPException(500, str(e))


@router.post("/wallet/set-primary")
async def set_primary_wallet(request: SetWalletRequest):
    """
    Set a wallet as the primary treasury wallet
    
    All auto-conversions will send USDT to this wallet
    
    Example:
    {
        "wallet_address": "0x1234567890abcdef..."
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        polygon_service = get_polygon_wallet_service(_db)
        
        # Also update treasury config
        treasury_service = get_treasury_service(_db)
        await treasury_service.update_config({
            "treasury_wallet_address": request.wallet_address
        })
        
        success = await polygon_service.set_primary_wallet(request.wallet_address)
        
        if not success:
            raise HTTPException(404, "Wallet not found")
        
        return {
            "success": True,
            "primary_wallet": request.wallet_address,
            "message": "Primary treasury wallet updated"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CryptoTreasury] Set primary wallet error: {e}")
        raise HTTPException(500, str(e))


@router.get("/wallet/primary")
async def get_primary_wallet():
    """
    Get the primary treasury wallet
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        polygon_service = get_polygon_wallet_service(_db)
        wallet = await polygon_service.get_primary_treasury_wallet()
        
        if not wallet:
            return {
                "success": True,
                "wallet": None,
                "message": "No primary wallet set. Create one via /wallet/create"
            }
        
        # Don't expose private key
        wallet_info = {
            "wallet_id": wallet.get("wallet_id"),
            "address": wallet.get("address"),
            "network": wallet.get("network"),
            "is_primary": wallet.get("is_primary"),
            "created_at": wallet.get("created_at")
        }
        
        return {
            "success": True,
            "wallet": wallet_info
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Get primary wallet error: {e}")
        raise HTTPException(500, str(e))


@router.get("/transactions/history")
async def get_transaction_history(limit: int = 50):
    """
    Get treasury transaction history
    
    Query params:
        limit: Number of transactions to return (default: 50)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        transactions = await _db.crypto_treasury_transactions.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "count": len(transactions),
            "transactions": transactions
        }
    
    except Exception as e:
        logger.error(f"[CryptoTreasury] Transaction history error: {e}")
        raise HTTPException(500, str(e))
