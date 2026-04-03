"""
CoinGecko API for RSI and Volume Data
"""
import httpx
import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"

# Symbol to CoinGecko ID mapping (common coins)
SYMBOL_TO_ID = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "BNBUSDT": "binancecoin",
    "SOLUSDT": "solana",
    "XRPUSDT": "ripple",
    "ADAUSDT": "cardano",
    "DOGEUSDT": "dogecoin",
    "DOTUSDT": "polkadot",
    "MATICUSDT": "matic-network",
    "AVAXUSDT": "avalanche-2",
    "LINKUSDT": "chainlink",
    "UNIUSDT": "uniswap",
    "ATOMUSDT": "cosmos",
    "LTCUSDT": "litecoin",
    "NEARUSDT": "near",
    "APTUSDT": "aptos",
    "ARBUSDT": "arbitrum",
    "OPUSDT": "optimism",
    "INJUSDT": "injective-protocol",
    "SUIUSDT": "sui",
    "SEIUSDT": "sei-network",
    "TIAUSDT": "celestia",
    "JUPUSDT": "jupiter-exchange-solana",
    "WIFUSDT": "dogwifcoin",
    "PEPEUSDT": "pepe",
    "SHIBUSDT": "shiba-inu",
    "HYPEUSDT": "hyperliquid",
}


class CoinGeckoAPI:
    def __init__(self):
        self.cache: Dict[str, dict] = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        self.cad_rate = 1.36  # Default USD to CAD rate
        self._last_rate_fetch = None
        
    async def get_usd_to_cad_rate(self) -> float:
        """Get current USD to CAD exchange rate"""
        now = datetime.now()
        if self._last_rate_fetch and (now - self._last_rate_fetch).seconds < 3600:
            return self.cad_rate
            
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{COINGECKO_API}/simple/price",
                    params={"ids": "usd", "vs_currencies": "cad"}
                )
                if response.status_code == 200:
                    data = response.json()
                    # Actually get CAD value of 1 USD
                    response2 = await client.get(
                        f"{COINGECKO_API}/exchange_rates"
                    )
                    if response2.status_code == 200:
                        rates = response2.json().get("rates", {})
                        cad = rates.get("cad", {}).get("value", 1.36)
                        usd = rates.get("usd", {}).get("value", 1)
                        self.cad_rate = cad / usd
                        self._last_rate_fetch = now
                        logger.info(f"[CoinGecko] USD/CAD rate: {self.cad_rate}")
        except Exception as e:
            logger.error(f"[CoinGecko] Rate fetch error: {e}")
            
        return self.cad_rate
        
    def get_coingecko_id(self, symbol: str) -> Optional[str]:
        """Convert Binance symbol to CoinGecko ID"""
        return SYMBOL_TO_ID.get(symbol.upper())
        
    async def add_symbol_mapping(self, symbol: str, coingecko_id: str):
        """Add a new symbol mapping"""
        SYMBOL_TO_ID[symbol.upper()] = coingecko_id
        
    async def get_coin_data(self, symbol: str) -> Optional[dict]:
        """Get comprehensive coin data including RSI calculation"""
        coin_id = self.get_coingecko_id(symbol)
        if not coin_id:
            logger.warning(f"[CoinGecko] No mapping for {symbol}")
            return None
            
        # Check cache
        cache_key = f"{coin_id}_data"
        cached = self.cache.get(cache_key)
        if cached and (datetime.now() - cached["timestamp"]).seconds < self.cache_ttl:
            return cached["data"]
            
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Get market data
                response = await client.get(
                    f"{COINGECKO_API}/coins/{coin_id}",
                    params={
                        "localization": "false",
                        "tickers": "false",
                        "community_data": "false",
                        "developer_data": "false"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"[CoinGecko] API error: {response.status_code}")
                    return None
                    
                data = response.json()
                market_data = data.get("market_data", {})
                
                cad_rate = await self.get_usd_to_cad_rate()
                price_usd = market_data.get("current_price", {}).get("usd", 0)
                
                result = {
                    "symbol": symbol,
                    "name": data.get("name", symbol),
                    "price_usd": price_usd,
                    "price_cad": price_usd * cad_rate,
                    "volume_24h": market_data.get("total_volume", {}).get("usd", 0),
                    "market_cap": market_data.get("market_cap", {}).get("usd", 0),
                    "change_24h": market_data.get("price_change_percentage_24h", 0),
                    "change_7d": market_data.get("price_change_percentage_7d", 0),
                    "high_24h": market_data.get("high_24h", {}).get("usd", 0),
                    "low_24h": market_data.get("low_24h", {}).get("usd", 0),
                    "timestamp": datetime.now()
                }
                
                # Get RSI from price history
                rsi = await self._calculate_rsi(coin_id, client)
                result["rsi"] = rsi
                
                # Cache the result
                self.cache[cache_key] = {"data": result, "timestamp": datetime.now()}
                
                return result
                
        except Exception as e:
            logger.error(f"[CoinGecko] Error fetching {symbol}: {e}")
            return None
            
    async def _calculate_rsi(self, coin_id: str, client: httpx.AsyncClient, period: int = 14) -> Optional[float]:
        """Calculate RSI from price history"""
        try:
            response = await client.get(
                f"{COINGECKO_API}/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": "14", "interval": "daily"}
            )
            
            if response.status_code != 200:
                return None
                
            data = response.json()
            prices = [p[1] for p in data.get("prices", [])]
            
            if len(prices) < period + 1:
                return None
                
            # Calculate price changes
            changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            
            # Separate gains and losses
            gains = [c if c > 0 else 0 for c in changes]
            losses = [-c if c < 0 else 0 for c in changes]
            
            # Calculate average gain/loss
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            
            if avg_loss == 0:
                return 100.0
                
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception as e:
            logger.error(f"[CoinGecko] RSI calculation error: {e}")
            return None
            
    async def search_coin(self, query: str) -> List[dict]:
        """Search for coins by name or symbol"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{COINGECKO_API}/search",
                    params={"query": query}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    coins = data.get("coins", [])[:10]  # Limit to 10 results
                    return [
                        {
                            "id": c["id"],
                            "symbol": c["symbol"].upper(),
                            "name": c["name"],
                            "thumb": c.get("thumb")
                        }
                        for c in coins
                    ]
        except Exception as e:
            logger.error(f"[CoinGecko] Search error: {e}")
            
        return []


# Global instance
coingecko = CoinGeckoAPI()
