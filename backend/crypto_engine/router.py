"""
Crypto Signal Engine - FastAPI Router
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import asyncio
import json
import jwt
import os
import logging

from .models import (
    CoinSettings, Signal, SignalType, Timeframe,
    AddCoinRequest, UpdateCoinRequest
)
from .binance_ws import binance_ws
from .coingecko import coingecko, SYMBOL_TO_ID
from .signal_engine import signal_engine
from .notifications import push_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crypto", tags=["Crypto Signal Engine"])

# JWT Configuration
JWT_SECRET = os.environ.get("CRYPTO_JWT_SECRET", "crypto-signal-secret-2024")
JWT_ALGORITHM = "HS256"
LOGIN_PASSWORD = os.environ.get("CRYPTO_LOGIN_PASSWORD", "signal123")

# Security
security = HTTPBearer(auto_error=False)

# In-memory store (use MongoDB in production)
watchlist: Dict[str, CoinSettings] = {}
signal_history: List[Signal] = []
connected_clients: List[WebSocket] = []

# Price cache
price_cache: Dict[str, dict] = {}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub", "user")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ============ AUTH ============

@router.post("/auth/login")
async def login(password: str):
    """Login with password"""
    if password != LOGIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    token = jwt.encode(
        {
            "sub": "user",
            "exp": datetime.now(timezone.utc) + timedelta(days=30)
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )
    
    return {"token": token, "expires_in": 30 * 24 * 60 * 60}


# ============ WATCHLIST ============

@router.get("/watchlist")
async def get_watchlist(user: str = Depends(verify_token)):
    """Get all coins in watchlist with current prices"""
    result = []
    cad_rate = await coingecko.get_usd_to_cad_rate()
    
    for symbol, coin in watchlist.items():
        # Get current price
        price_usd = binance_ws.get_price(symbol) or price_cache.get(symbol, {}).get("price_usd", 0)
        price_cad = price_usd * cad_rate
        
        # Calculate P&L
        pnl = 0
        pnl_percent = 0
        if coin.buy_price and coin.holdings > 0:
            cost = coin.buy_price * coin.holdings
            value = price_cad * coin.holdings
            pnl = value - cost
            pnl_percent = ((price_cad - coin.buy_price) / coin.buy_price) * 100 if coin.buy_price else 0
        
        result.append({
            **coin.dict(),
            "price_usd": price_usd,
            "price_cad": price_cad,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "value_cad": price_cad * coin.holdings if coin.holdings else 0
        })
    
    return {"coins": result, "cad_rate": cad_rate}


@router.post("/watchlist")
async def add_coin(request: AddCoinRequest, user: str = Depends(verify_token)):
    """Add a coin to watchlist"""
    symbol = request.symbol.upper()
    if not symbol.endswith("USDT"):
        symbol = f"{symbol}USDT"
    
    if symbol in watchlist:
        raise HTTPException(status_code=400, detail="Coin already in watchlist")
    
    # Create coin settings
    coin = CoinSettings(
        symbol=symbol,
        name=request.name
    )
    watchlist[symbol] = coin
    
    # Subscribe to Binance WebSocket
    await binance_ws.subscribe(symbol)
    
    # Get initial data from CoinGecko
    data = await coingecko.get_coin_data(symbol)
    if data:
        price_cache[symbol] = data
    
    logger.info(f"[Crypto] Added {symbol} to watchlist")
    return {"message": f"Added {symbol}", "coin": coin.dict()}


@router.delete("/watchlist/{symbol}")
async def remove_coin(symbol: str, user: str = Depends(verify_token)):
    """Remove a coin from watchlist"""
    symbol = symbol.upper()
    if symbol not in watchlist:
        raise HTTPException(status_code=404, detail="Coin not in watchlist")
    
    del watchlist[symbol]
    await binance_ws.unsubscribe(symbol)
    
    logger.info(f"[Crypto] Removed {symbol} from watchlist")
    return {"message": f"Removed {symbol}"}


@router.put("/watchlist/{symbol}")
async def update_coin_settings(symbol: str, request: UpdateCoinRequest, user: str = Depends(verify_token)):
    """Update coin settings"""
    symbol = symbol.upper()
    if symbol not in watchlist:
        raise HTTPException(status_code=404, detail="Coin not in watchlist")
    
    coin = watchlist[symbol]
    update_data = request.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(coin, key, value)
    
    coin.updated_at = datetime.now(timezone.utc)
    watchlist[symbol] = coin
    
    return {"message": f"Updated {symbol}", "coin": coin.dict()}


# ============ SIGNALS ============

@router.get("/signals")
async def get_signals(limit: int = 50, user: str = Depends(verify_token)):
    """Get signal history"""
    return {"signals": signal_history[-limit:]}


@router.get("/signals/live")
async def get_live_signals(user: str = Depends(verify_token)):
    """Get recent signals (last hour)"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = [s for s in signal_history if s.timestamp > cutoff]
    return {"signals": recent}


# ============ SEARCH ============

@router.get("/search")
async def search_coins(q: str, user: str = Depends(verify_token)):
    """Search for coins"""
    results = await coingecko.search_coin(q)
    return {"results": results}


@router.get("/supported-coins")
async def get_supported_coins(user: str = Depends(verify_token)):
    """Get list of supported coins with Binance symbols"""
    return {"coins": list(SYMBOL_TO_ID.keys())}


# ============ PUSH NOTIFICATIONS ============

@router.post("/push/subscribe")
async def subscribe_push(subscription: dict, user: str = Depends(verify_token)):
    """Subscribe to push notifications"""
    push_service.save_subscription(user, subscription)
    return {"message": "Subscribed to push notifications"}


@router.post("/push/unsubscribe")
async def unsubscribe_push(user: str = Depends(verify_token)):
    """Unsubscribe from push notifications"""
    push_service.remove_subscription(user)
    return {"message": "Unsubscribed from push notifications"}


@router.get("/push/vapid-key")
async def get_vapid_key():
    """Get VAPID public key for push subscription"""
    vapid_key = os.environ.get("VAPID_PUBLIC_KEY", "")
    return {"vapid_key": vapid_key}


# ============ WEBSOCKET ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time price and signal updates"""
    await websocket.accept()
    connected_clients.append(websocket)
    
    try:
        # Send initial data
        await websocket.send_json({
            "type": "init",
            "watchlist": [c.dict() for c in watchlist.values()],
            "prices": price_cache
        })
        
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        logger.error(f"[Crypto WS] Error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# ============ BACKGROUND TASKS ============

async def broadcast_price_update(symbol: str, price_usd: float):
    """Broadcast price update to all connected clients"""
    cad_rate = await coingecko.get_usd_to_cad_rate()
    price_cad = price_usd * cad_rate
    
    message = {
        "type": "price",
        "symbol": symbol,
        "price_usd": price_usd,
        "price_cad": price_cad,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Update signal engine
    await signal_engine.update_price(symbol, price_usd)
    
    # Check signals
    if symbol in watchlist:
        coin = watchlist[symbol]
        data = price_cache.get(symbol, {})
        data["price_usd"] = price_usd
        data["price_cad"] = price_cad
        
        signals = await signal_engine.check_signals(coin, data)
        
        for signal in signals:
            signal_history.append(signal)
            # Keep only last 1000 signals
            if len(signal_history) > 1000:
                signal_history.pop(0)
            
            # Broadcast signal
            signal_message = {
                "type": "signal",
                "signal": signal.dict()
            }
            
            for client in connected_clients:
                try:
                    await client.send_json(signal_message)
                except:
                    pass
            
            # Send push notification if enabled
            if coin.notify_push:
                await push_service.broadcast_signal(
                    title="Crypto Signal",
                    body=signal.message,
                    data={"signal_id": signal.id, "symbol": symbol}
                )
    
    # Broadcast to clients
    for client in connected_clients:
        try:
            await client.send_json(message)
        except:
            pass


async def fetch_coingecko_data():
    """Periodically fetch data from CoinGecko"""
    while True:
        for symbol in list(watchlist.keys()):
            try:
                data = await coingecko.get_coin_data(symbol)
                if data:
                    price_cache[symbol] = data
                    
                    # Check signals with CoinGecko data (RSI, etc.)
                    coin = watchlist[symbol]
                    signals = await signal_engine.check_signals(coin, data)
                    
                    for signal in signals:
                        signal_history.append(signal)
                        
                        # Broadcast signal
                        for client in connected_clients:
                            try:
                                await client.send_json({
                                    "type": "signal",
                                    "signal": signal.dict()
                                })
                            except:
                                pass
                        
                        # Push notification
                        if coin.notify_push:
                            await push_service.broadcast_signal(
                                title="Crypto Signal",
                                body=signal.message,
                                data={"signal_id": signal.id, "symbol": symbol}
                            )
                            
            except Exception as e:
                logger.error(f"[CoinGecko] Error fetching {symbol}: {e}")
                
            # Rate limit: wait between requests
            await asyncio.sleep(2)
            
        # Wait before next cycle
        await asyncio.sleep(60)


# Register callbacks
binance_ws.add_callback(broadcast_price_update)


async def start_background_tasks():
    """Start background tasks"""
    asyncio.create_task(binance_ws.connect())
    asyncio.create_task(fetch_coingecko_data())
    logger.info("[Crypto] Background tasks started")
