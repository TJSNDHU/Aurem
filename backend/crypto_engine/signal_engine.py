"""
Signal Detection Engine
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

from .models import CoinSettings, Signal, SignalType, Timeframe
from .coingecko import coingecko

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalEngine:
    def __init__(self):
        self.price_history: Dict[str, List[dict]] = defaultdict(list)
        self.last_signals: Dict[str, datetime] = {}  # Prevent spam
        self.signal_cooldown = 300  # 5 minutes between same signal type
        self.signal_callbacks: List[callable] = []
        
    def add_callback(self, callback: callable):
        """Add callback for new signals"""
        self.signal_callbacks.append(callback)
        
    async def update_price(self, symbol: str, price_usd: float):
        """Update price history and check for signals"""
        now = datetime.now()
        
        # Store price history
        self.price_history[symbol].append({
            "price": price_usd,
            "timestamp": now
        })
        
        # Keep only last 24 hours
        cutoff = now - timedelta(hours=24)
        self.price_history[symbol] = [
            p for p in self.price_history[symbol]
            if p["timestamp"] > cutoff
        ]
        
    async def check_signals(self, coin: CoinSettings, current_data: dict) -> List[Signal]:
        """Check all signal conditions for a coin"""
        if not coin.enabled:
            return []
            
        signals = []
        symbol = coin.symbol
        price_usd = current_data.get("price_usd", 0)
        price_cad = current_data.get("price_cad", 0)
        rsi = current_data.get("rsi")
        volume_24h = current_data.get("volume_24h", 0)
        
        # 1. Price Change Alert
        price_signal = await self._check_price_change(coin, price_usd, price_cad, rsi)
        if price_signal:
            signals.append(price_signal)
            
        # 2. Volume Spike Alert
        volume_signal = await self._check_volume_spike(coin, volume_24h, price_usd, price_cad, rsi)
        if volume_signal:
            signals.append(volume_signal)
            
        # 3. RSI Alerts
        rsi_signal = await self._check_rsi(coin, rsi, price_usd, price_cad)
        if rsi_signal:
            signals.append(rsi_signal)
            
        # 4. Price Target Alerts
        target_signal = await self._check_price_targets(coin, price_usd, price_cad, rsi)
        if target_signal:
            signals.append(target_signal)
            
        # Notify callbacks
        for signal in signals:
            for callback in self.signal_callbacks:
                try:
                    await callback(signal, coin)
                except Exception as e:
                    logger.error(f"[Signal] Callback error: {e}")
                    
        return signals
        
    async def _check_price_change(self, coin: CoinSettings, price_usd: float, price_cad: float, rsi: Optional[float]) -> Optional[Signal]:
        """Check for significant price changes"""
        symbol = coin.symbol
        history = self.price_history.get(symbol, [])
        
        if len(history) < 2:
            return None
            
        # Check cooldown
        signal_key = f"{symbol}_price_change"
        if not self._check_cooldown(signal_key):
            return None
            
        # Get price from X minutes ago
        minutes_ago = datetime.now() - timedelta(minutes=coin.price_change_minutes)
        old_prices = [p for p in history if p["timestamp"] <= minutes_ago]
        
        if not old_prices:
            return None
            
        old_price = old_prices[-1]["price"]
        change_percent = ((price_usd - old_price) / old_price) * 100
        
        if abs(change_percent) >= coin.price_change_percent:
            self.last_signals[signal_key] = datetime.now()
            
            direction = "SURGE" if change_percent > 0 else "SHARP DROP"
            emoji = "🟢" if change_percent > 0 else "🔴"
            rsi_text = f" | RSI: {rsi:.0f}" if rsi else ""
            rsi_status = ""
            if rsi:
                if rsi > 70:
                    rsi_status = " (Overbought)"
                elif rsi < 30:
                    rsi_status = " (Oversold)"
                    
            message = f"{emoji} {coin.name} {direction} — {'+' if change_percent > 0 else ''}{change_percent:.1f}% in {coin.price_change_minutes} min{rsi_text}{rsi_status} | Current: ${price_cad:.2f} CAD"
            
            return Signal(
                id=str(uuid.uuid4()),
                symbol=symbol,
                signal_type=SignalType.PRICE_CHANGE,
                message=message,
                price_cad=price_cad,
                price_usd=price_usd,
                rsi=rsi,
                price_change=change_percent,
                timeframe=coin.timeframe.value
            )
            
        return None
        
    async def _check_volume_spike(self, coin: CoinSettings, volume_24h: float, price_usd: float, price_cad: float, rsi: Optional[float]) -> Optional[Signal]:
        """Check for volume spikes"""
        # This would need historical volume data
        # For now, we'll use 24h volume change from CoinGecko
        return None  # Simplified - CoinGecko doesn't provide real-time volume comparison
        
    async def _check_rsi(self, coin: CoinSettings, rsi: Optional[float], price_usd: float, price_cad: float) -> Optional[Signal]:
        """Check RSI conditions"""
        if rsi is None:
            return None
            
        symbol = coin.symbol
        
        # Check overbought
        if rsi >= coin.rsi_overbought:
            signal_key = f"{symbol}_rsi_overbought"
            if self._check_cooldown(signal_key):
                self.last_signals[signal_key] = datetime.now()
                message = f"🔴 {coin.name} OVERBOUGHT — RSI: {rsi:.0f} (>{coin.rsi_overbought:.0f}) | Current: ${price_cad:.2f} CAD"
                return Signal(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    signal_type=SignalType.RSI_OVERBOUGHT,
                    message=message,
                    price_cad=price_cad,
                    price_usd=price_usd,
                    rsi=rsi,
                    timeframe=coin.timeframe.value
                )
                
        # Check oversold
        if rsi <= coin.rsi_oversold:
            signal_key = f"{symbol}_rsi_oversold"
            if self._check_cooldown(signal_key):
                self.last_signals[signal_key] = datetime.now()
                message = f"🟢 {coin.name} OVERSOLD — RSI: {rsi:.0f} (<{coin.rsi_oversold:.0f}) | Current: ${price_cad:.2f} CAD"
                return Signal(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    signal_type=SignalType.RSI_OVERSOLD,
                    message=message,
                    price_cad=price_cad,
                    price_usd=price_usd,
                    rsi=rsi,
                    timeframe=coin.timeframe.value
                )
                
        return None
        
    async def _check_price_targets(self, coin: CoinSettings, price_usd: float, price_cad: float, rsi: Optional[float]) -> Optional[Signal]:
        """Check if price targets are hit"""
        symbol = coin.symbol
        rsi_text = f" | RSI: {rsi:.0f}" if rsi else ""
        
        # High target
        if coin.target_price_high and price_cad >= coin.target_price_high:
            signal_key = f"{symbol}_target_high"
            if self._check_cooldown(signal_key):
                self.last_signals[signal_key] = datetime.now()
                message = f"🎯 {coin.name} TARGET HIGH HIT — ${price_cad:.2f} CAD reached ${coin.target_price_high:.2f} target{rsi_text}"
                return Signal(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    signal_type=SignalType.TARGET_HIGH,
                    message=message,
                    price_cad=price_cad,
                    price_usd=price_usd,
                    rsi=rsi,
                    timeframe=coin.timeframe.value
                )
                
        # Low target
        if coin.target_price_low and price_cad <= coin.target_price_low:
            signal_key = f"{symbol}_target_low"
            if self._check_cooldown(signal_key):
                self.last_signals[signal_key] = datetime.now()
                message = f"⚠️ {coin.name} TARGET LOW HIT — ${price_cad:.2f} CAD dropped to ${coin.target_price_low:.2f} target{rsi_text}"
                return Signal(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    signal_type=SignalType.TARGET_LOW,
                    message=message,
                    price_cad=price_cad,
                    price_usd=price_usd,
                    rsi=rsi,
                    timeframe=coin.timeframe.value
                )
                
        return None
        
    def _check_cooldown(self, signal_key: str) -> bool:
        """Check if we're past the cooldown period"""
        last_signal = self.last_signals.get(signal_key)
        if not last_signal:
            return True
        return (datetime.now() - last_signal).seconds >= self.signal_cooldown


# Global instance
signal_engine = SignalEngine()
