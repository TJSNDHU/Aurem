"""
Crypto Treasury Management Service
Core service for managing treasury operations
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import uuid

from models.crypto_treasury_models import (
    TreasuryConfig,
    TreasuryTransaction,
    TransactionType,
    ConversionStatus,
    TreasuryStats
)
from services.crypto_treasury.coinbase_service import get_coinbase_service
from services.crypto_treasury.polygon_wallet_service import get_polygon_wallet_service

logger = logging.getLogger(__name__)


class CryptoTreasuryService:
    """
    Main treasury management service
    
    Responsibilities:
    - Track revenue from Stripe
    - Track expenses
    - Calculate profit
    - Auto-convert profit to USDT
    - Manage treasury wallets
    """
    
    def __init__(self, db):
        self.db = db
        self.coinbase = get_coinbase_service(db)
        self.polygon = get_polygon_wallet_service(db)
        
        logger.info("[Treasury] Service initialized")
    
    async def get_config(self) -> Dict[str, Any]:
        """
        Get current treasury configuration
        """
        try:
            config = await self.db.crypto_treasury_config.find_one(
                {"config_type": "main"},
                {"_id": 0}
            )
            
            if not config:
                # Return default config
                default_config = {
                    "config_type": "main",
                    "expense_reserve_usd": 5000.0,
                    "auto_conversion_enabled": True,
                    "conversion_threshold_usd": 1000.0,
                    "conversion_frequency": "daily",
                    "treasury_wallet_address": None,
                    "blockchain_network": "polygon",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                
                await self.db.crypto_treasury_config.insert_one(default_config)
                return default_config
            
            return config
        
        except Exception as e:
            logger.error(f"[Treasury] Error getting config: {e}")
            raise
    
    async def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update treasury configuration
        """
        try:
            updates["updated_at"] = datetime.now(timezone.utc)
            
            await self.db.crypto_treasury_config.update_one(
                {"config_type": "main"},
                {"$set": updates},
                upsert=True
            )
            
            logger.info(f"[Treasury] Config updated: {list(updates.keys())}")
            
            return await self.get_config()
        
        except Exception as e:
            logger.error(f"[Treasury] Error updating config: {e}")
            raise
    
    async def record_revenue(self, amount_usd: float, description: str, stripe_payment_id: Optional[str] = None) -> str:
        """
        Record revenue (from Stripe payments)
        """
        try:
            transaction_id = str(uuid.uuid4())
            
            transaction = {
                "transaction_id": transaction_id,
                "transaction_type": TransactionType.REVENUE.value,
                "amount_usd": amount_usd,
                "description": description,
                "stripe_payment_id": stripe_payment_id,
                "status": ConversionStatus.COMPLETED.value,
                "created_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc)
            }
            
            await self.db.crypto_treasury_transactions.insert_one(transaction)
            
            logger.info(f"[Treasury] Revenue recorded: ${amount_usd} USD")
            
            return transaction_id
        
        except Exception as e:
            logger.error(f"[Treasury] Error recording revenue: {e}")
            raise
    
    async def record_expense(self, amount_usd: float, description: str, category: str = "general") -> str:
        """
        Record expense (bills, costs)
        """
        try:
            transaction_id = str(uuid.uuid4())
            
            transaction = {
                "transaction_id": transaction_id,
                "transaction_type": TransactionType.EXPENSE.value,
                "amount_usd": amount_usd,
                "description": description,
                "category": category,
                "status": ConversionStatus.COMPLETED.value,
                "created_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc)
            }
            
            await self.db.crypto_treasury_transactions.insert_one(transaction)
            
            logger.info(f"[Treasury] Expense recorded: ${amount_usd} USD ({category})")
            
            return transaction_id
        
        except Exception as e:
            logger.error(f"[Treasury] Error recording expense: {e}")
            raise
    
    async def calculate_profit(self) -> Dict[str, float]:
        """
        Calculate current profit
        
        Returns:
            total_revenue, total_expenses, current_profit
        """
        try:
            # Get all revenue
            revenue_cursor = self.db.crypto_treasury_transactions.find({
                "transaction_type": TransactionType.REVENUE.value
            })
            
            total_revenue = 0.0
            async for record in revenue_cursor:
                total_revenue += record.get("amount_usd", 0.0)
            
            # Get all expenses
            expense_cursor = self.db.crypto_treasury_transactions.find({
                "transaction_type": TransactionType.EXPENSE.value
            })
            
            total_expenses = 0.0
            async for record in expense_cursor:
                total_expenses += record.get("amount_usd", 0.0)
            
            # Get total converted
            conversion_cursor = self.db.crypto_treasury_transactions.find({
                "transaction_type": TransactionType.CONVERSION.value,
                "status": ConversionStatus.COMPLETED.value
            })
            
            total_converted = 0.0
            async for record in conversion_cursor:
                total_converted += record.get("amount_usd", 0.0)
            
            # Calculate current profit (not yet converted)
            current_profit = total_revenue - total_expenses - total_converted
            
            return {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "total_converted": total_converted,
                "current_profit": max(0, current_profit)  # Can't be negative
            }
        
        except Exception as e:
            logger.error(f"[Treasury] Error calculating profit: {e}")
            raise
    
    async def check_conversion_eligibility(self) -> Dict[str, Any]:
        """
        Check if auto-conversion should trigger
        """
        try:
            config = await self.get_config()
            profit_data = await self.calculate_profit()
            
            current_profit = profit_data["current_profit"]
            expense_reserve = config.get("expense_reserve_usd", 5000.0)
            conversion_threshold = config.get("conversion_threshold_usd", 1000.0)
            auto_enabled = config.get("auto_conversion_enabled", True)
            
            # Available for conversion = profit - reserve
            available_for_conversion = max(0, current_profit - expense_reserve)
            
            eligible = (
                auto_enabled and
                available_for_conversion >= conversion_threshold
            )
            
            return {
                "eligible": eligible,
                "current_profit": current_profit,
                "expense_reserve": expense_reserve,
                "available_for_conversion": available_for_conversion,
                "conversion_threshold": conversion_threshold,
                "auto_enabled": auto_enabled
            }
        
        except Exception as e:
            logger.error(f"[Treasury] Error checking eligibility: {e}")
            raise
    
    async def convert_profit_to_usdt(
        self,
        amount_usd: Optional[float] = None,
        auto_send: bool = True
    ) -> Dict[str, Any]:
        """
        Convert profit USD to USDT
        
        Args:
            amount_usd: Specific amount to convert, or None to convert all available
            auto_send: Automatically send to treasury wallet
        
        Returns:
            Conversion result
        """
        try:
            # Determine amount to convert
            if amount_usd is None:
                eligibility = await self.check_conversion_eligibility()
                amount_usd = eligibility["available_for_conversion"]
            
            if amount_usd < 10:
                return {
                    "success": False,
                    "error": "Minimum conversion amount is $10 USD",
                    "amount_usd": amount_usd
                }
            
            transaction_id = str(uuid.uuid4())
            
            # Record conversion transaction
            conversion_record = {
                "transaction_id": transaction_id,
                "transaction_type": TransactionType.CONVERSION.value,
                "amount_usd": amount_usd,
                "description": f"Auto-conversion of ${amount_usd} USD to USDT",
                "status": ConversionStatus.PROCESSING.value,
                "created_at": datetime.now(timezone.utc)
            }
            
            await self.db.crypto_treasury_transactions.insert_one(conversion_record)
            
            # Execute conversion via Coinbase
            conversion_result = await self.coinbase.convert_usd_to_usdt(
                amount_usd=amount_usd,
                user_id="treasury_system"
            )
            
            if not conversion_result.get("success"):
                # Update status to failed
                await self.db.crypto_treasury_transactions.update_one(
                    {"transaction_id": transaction_id},
                    {"$set": {
                        "status": ConversionStatus.FAILED.value,
                        "error": conversion_result.get("error")
                    }}
                )
                
                return conversion_result
            
            # Update conversion record
            await self.db.crypto_treasury_transactions.update_one(
                {"transaction_id": transaction_id},
                {"$set": {
                    "status": ConversionStatus.COMPLETED.value,
                    "amount_usdt": conversion_result.get("amount_usdt"),
                    "completed_at": datetime.now(timezone.utc),
                    "coinbase_conversion_id": conversion_result.get("conversion_id"),
                    "conversion_rate": conversion_result.get("conversion_rate"),
                    "fee_usd": conversion_result.get("fee_usd")
                }}
            )
            
            logger.info(
                f"[Treasury] Conversion completed: ${amount_usd} USD → "
                f"{conversion_result.get('amount_usdt')} USDT"
            )
            
            # Auto-send to treasury wallet if enabled
            if auto_send:
                config = await self.get_config()
                treasury_wallet = config.get("treasury_wallet_address")
                
                if treasury_wallet:
                    # TODO: Implement actual transfer
                    logger.info(
                        f"[Treasury] USDT will be sent to treasury wallet: {treasury_wallet}"
                    )
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "amount_usd": amount_usd,
                "amount_usdt": conversion_result.get("amount_usdt"),
                "conversion_rate": conversion_result.get("conversion_rate"),
                "fee_usd": conversion_result.get("fee_usd"),
                "mock_mode": conversion_result.get("mock_mode", False),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"[Treasury] Error converting to USDT: {e}")
            raise
    
    async def get_treasury_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive treasury statistics
        """
        try:
            profit_data = await self.calculate_profit()
            config = await self.get_config()
            eligibility = await self.check_conversion_eligibility()
            
            # Get treasury wallet balance
            treasury_wallet_address = config.get("treasury_wallet_address")
            treasury_balance = 0.0
            
            if treasury_wallet_address:
                try:
                    balance_info = await self.polygon.get_wallet_balance(treasury_wallet_address)
                    treasury_balance = balance_info.get("balance_usdt", 0.0)
                except Exception:
                    pass
            
            # Count pending conversions
            pending_count = await self.db.crypto_treasury_transactions.count_documents({
                "transaction_type": TransactionType.CONVERSION.value,
                "status": {"$in": [ConversionStatus.PENDING.value, ConversionStatus.PROCESSING.value]}
            })
            
            # Get last conversion date
            last_conversion = await self.db.crypto_treasury_transactions.find_one(
                {
                    "transaction_type": TransactionType.CONVERSION.value,
                    "status": ConversionStatus.COMPLETED.value
                },
                {"_id": 0},
                sort=[("completed_at", -1)]
            )
            
            return {
                "total_revenue_usd": profit_data["total_revenue"],
                "total_expenses_usd": profit_data["total_expenses"],
                "current_profit_usd": profit_data["current_profit"],
                "total_converted_usdt": profit_data["total_converted"],
                "treasury_wallet_balance_usdt": treasury_balance,
                "pending_conversions": pending_count,
                "last_conversion_date": last_conversion.get("completed_at") if last_conversion else None,
                "auto_conversion_enabled": config.get("auto_conversion_enabled", False),
                "next_conversion_eligible": eligibility["eligible"],
                "available_for_conversion": eligibility["available_for_conversion"],
                "treasury_wallet_address": treasury_wallet_address
            }
        
        except Exception as e:
            logger.error(f"[Treasury] Error getting stats: {e}")
            raise


# Singleton instance
_treasury_service = None


def get_treasury_service(db):
    """Get singleton treasury service instance"""
    global _treasury_service
    
    if _treasury_service is None:
        _treasury_service = CryptoTreasuryService(db)
    
    return _treasury_service
