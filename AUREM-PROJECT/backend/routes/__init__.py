"""
Routes package - modular API endpoints.
"""
from .auth import router as auth_router
from .orders import router as orders_router
from .websocket import router as websocket_router, websocket_endpoint, ws_manager, broadcast_admin_event, broadcast_inventory_update

__all__ = [
    "auth_router",
    "orders_router",
    "websocket_router", 
    "websocket_endpoint",
    "ws_manager",
    "broadcast_admin_event",
    "broadcast_inventory_update"
]
