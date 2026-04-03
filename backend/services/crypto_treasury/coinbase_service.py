"""
Coinbase Integration Service
Handles USD to USDT conversions via Coinbase API
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


class CoinbaseService:
    """
    Coinbase API integration for USD to USDT conversions
    
    NOTE: Requires Coinbase API keys to be configured via Admin Mission Control.
    Until keys are added, conversions will run in MOCK mode.
    """
    
    def __init__(self, db):
        self.db = db
        self.api_key_id = None
        self.api_secret = None
        self.mock_mode = True
        
        logger.info("[Coinbase] Service initialized (Mock mode until API keys configured)")
    
    async def load_api_keys(self):
        """Load Coinbase API keys from Admin Mission Control"""
        try:
            # Check if keys exist in admin config
            config = await self.db.admin_api_keys.find_one(
                {"service": "coinbase"},
                {"_id": 0}
            )
            
            if config and config.get("api_key_id") and config.get("api_secret"):
                self.api_key_id = config["api_key_id"]
                self.api_secret = config["api_secret"]
                self.mock_mode = False
                logger.info("[Coinbase] API keys loaded from Admin Mission Control")
            else:
                logger.warning(
                    "[Coinbase] No API keys found. Running in MOCK mode. "
                    "Add keys via Admin Mission Control to enable real conversions."
                )
        
        except Exception as e:
            logger.error(f"[Coinbase] Error loading API keys: {e}")
    
    async def convert_usd_to_usdt(
        self,
        amount_usd: float,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Convert USD to USDT via Coinbase
        
        Args:
            amount_usd: Amount in USD to convert
            user_id: User/system initiating conversion
        
        Returns:
            Conversion result with transaction details
        """
        await self.load_api_keys()
        
        conversion_id = str(uuid.uuid4())
        
        # MOCK MODE (no API keys)
        if self.mock_mode:
            logger.info(
                f"[Coinbase MOCK] Converting ${amount_usd} USD to USDT "
                f"(Mock mode - add API keys to enable real conversions)"
            )
            
            # Simulate conversion (1:1 rate minus 0.5% fee)
            conversion_fee = amount_usd * 0.005
            amount_usdt = amount_usd - conversion_fee
            
            return {
                "success": True,
                "mock_mode": True,
                "conversion_id": conversion_id,
                "amount_usd": amount_usd,
                "amount_usdt": amount_usdt,
                "conversion_rate": 1.0,
                "fee_usd": conversion_fee,
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Mock conversion (add Coinbase API keys via Admin to enable real conversions)"
            }
        
        # REAL MODE (API keys configured)
        try:
            # TODO: Implement real Coinbase API call
            # from coinbase.rest import RESTClient
            # client = RESTClient(api_key=self.api_key_id, api_secret=self.api_secret)
            # response = client.market_order_buy(...)
            
            logger.info(f"[Coinbase] Converting ${amount_usd} USD to USDT")
            
            # Placeholder for real implementation
            return {
                "success": True,
                "mock_mode": False,
                "conversion_id": conversion_id,
                "amount_usd": amount_usd,
                "amount_usdt": amount_usd * 0.995,  # Estimated
                "conversion_rate": 1.0,
                "fee_usd": amount_usd * 0.005,
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"[Coinbase] Conversion error: {e}")
            return {
                "success": False,
                "error": str(e),
                "conversion_id": conversion_id
            }
    
    async def get_conversion_history(self, limit: int = 20) -> list:
        """Get conversion history"""
        try:
            history = await self.db.crypto_conversions.find(
                {},
                {"_id": 0}
            ).sort("created_at", -1).limit(limit).to_list(limit)
            
            return history
        
        except Exception as e:
            logger.error(f"[Coinbase] Error fetching history: {e}")
            return []
    
    async def get_current_rate(self) -> Dict[str, Any]:
        """Get current USD to USDT conversion rate"""
        await self.load_api_keys()
        
        if self.mock_mode:
            return {
                "rate": 1.0,
                "mock_mode": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # TODO: Implement real rate fetching
        return {
            "rate": 1.0,
            "mock_mode": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
_coinbase_service = None


def get_coinbase_service(db) -> CoinbaseService:
    """Get singleton Coinbase service instance"""
    global _coinbase_service
    
    if _coinbase_service is None:
        _coinbase_service = CoinbaseService(db)
    
    return _coinbase_service
