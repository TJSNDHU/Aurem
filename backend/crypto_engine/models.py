"""
Crypto Signal Engine - Data Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    PRICE_CHANGE = "price_change"
    VOLUME_SPIKE = "volume_spike"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    TARGET_HIGH = "target_high"
    TARGET_LOW = "target_low"


class Timeframe(str, Enum):
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1D"


class CoinSettings(BaseModel):
    """Per-coin alert settings"""
    symbol: str  # e.g., "BTCUSDT"
    name: str  # e.g., "Bitcoin"
    enabled: bool = True
    
    # Alert thresholds
    price_change_percent: float = 5.0  # Alert when price changes by X%
    price_change_minutes: int = 15  # Within X minutes
    volume_spike_percent: float = 100.0  # Alert when volume > 24h avg by X%
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    target_price_high: Optional[float] = None
    target_price_low: Optional[float] = None
    timeframe: Timeframe = Timeframe.M15
    
    # Notification toggles
    notify_push: bool = True
    
    # Portfolio tracking
    buy_price: Optional[float] = None  # Manual entry
    holdings: float = 0.0  # Quantity held
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Signal(BaseModel):
    """Generated signal"""
    id: str
    symbol: str
    signal_type: SignalType
    message: str
    price_cad: float
    price_usd: float
    rsi: Optional[float] = None
    volume_change: Optional[float] = None
    price_change: Optional[float] = None
    timeframe: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notified: bool = False


class PriceData(BaseModel):
    """Real-time price data"""
    symbol: str
    price_usd: float
    price_cad: float
    volume_24h: float
    change_24h: float
    rsi: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AddCoinRequest(BaseModel):
    symbol: str
    name: str


class UpdateCoinRequest(BaseModel):
    enabled: Optional[bool] = None
    price_change_percent: Optional[float] = None
    price_change_minutes: Optional[int] = None
    volume_spike_percent: Optional[float] = None
    rsi_overbought: Optional[float] = None
    rsi_oversold: Optional[float] = None
    target_price_high: Optional[float] = None
    target_price_low: Optional[float] = None
    timeframe: Optional[Timeframe] = None
    notify_push: Optional[bool] = None
    buy_price: Optional[float] = None
    holdings: Optional[float] = None
