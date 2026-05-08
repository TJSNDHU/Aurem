"""
Binance WebSocket Connection for Real-time Prices
"""
import asyncio
import json
import logging
from typing import Dict, Callable, Set
import websockets
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"


class BinanceWebSocket:
    def __init__(self):
        self.ws = None
        self.subscriptions: Set[str] = set()
        self.price_callbacks: list[Callable] = []
        self.prices: Dict[str, dict] = {}
        self.running = False
        self._reconnect_delay = 5
        
    def add_callback(self, callback: Callable):
        """Add a callback for price updates"""
        self.price_callbacks.append(callback)
        
    async def subscribe(self, symbol: str):
        """Subscribe to a symbol's price stream"""
        symbol_lower = symbol.lower()
        if symbol_lower not in self.subscriptions:
            self.subscriptions.add(symbol_lower)
            if self.ws:
                await self._send_subscribe([symbol_lower])
                
    async def unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol"""
        symbol_lower = symbol.lower()
        if symbol_lower in self.subscriptions:
            self.subscriptions.remove(symbol_lower)
            if self.ws:
                await self._send_unsubscribe([symbol_lower])
                
    async def _send_subscribe(self, symbols: list):
        """Send subscribe message"""
        if not self.ws:
            return
        streams = [f"{s}@trade" for s in symbols]
        msg = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": int(datetime.now().timestamp())
        }
        await self.ws.send(json.dumps(msg))
        logger.info(f"[Binance] Subscribed to: {symbols}")
        
    async def _send_unsubscribe(self, symbols: list):
        """Send unsubscribe message"""
        if not self.ws:
            return
        streams = [f"{s}@trade" for s in symbols]
        msg = {
            "method": "UNSUBSCRIBE",
            "params": streams,
            "id": int(datetime.now().timestamp())
        }
        await self.ws.send(json.dumps(msg))
        logger.info(f"[Binance] Unsubscribed from: {symbols}")
        
    async def connect(self):
        """Connect to Binance WebSocket"""
        self.running = True
        
        while self.running:
            try:
                async with websockets.connect(BINANCE_WS_URL) as ws:
                    self.ws = ws
                    logger.info("[Binance] WebSocket connected")
                    
                    # Subscribe to all tracked symbols
                    if self.subscriptions:
                        await self._send_subscribe(list(self.subscriptions))
                    
                    # Listen for messages
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            await self._handle_message(data)
                        except json.JSONDecodeError:
                            pass
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("[Binance] Connection closed, reconnecting...")
            except Exception as e:
                logger.error(f"[Binance] Error: {e}")
                
            if self.running:
                await asyncio.sleep(self._reconnect_delay)
                
    async def _handle_message(self, data: dict):
        """Handle incoming WebSocket message"""
        # Trade event
        if data.get("e") == "trade":
            symbol = data.get("s", "").upper()
            price = float(data.get("p", 0))
            quantity = float(data.get("q", 0))
            
            self.prices[symbol] = {
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "timestamp": datetime.now()
            }
            
            # Notify callbacks
            for callback in self.price_callbacks:
                try:
                    await callback(symbol, price)
                except Exception as e:
                    logger.error(f"[Binance] Callback error: {e}")
                    
    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        data = self.prices.get(symbol.upper(), {})
        return data.get("price", 0)
        
    async def stop(self):
        """Stop the WebSocket connection"""
        self.running = False
        if self.ws:
            await self.ws.close()


# Global instance
binance_ws = BinanceWebSocket()
