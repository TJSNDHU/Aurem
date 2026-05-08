"""
AUREM Robotics Router — 6-DOF Digital Twin API + WebSocket
POST /api/robotics/trigger — trigger arm sequence
GET  /api/robotics/state — current arm joint state
GET  /api/robotics/sequences — available sequences
GET  /api/robotics/config — arm hardware config
GET  /api/robotics/history — task execution history
WS   /api/robotics/ws — real-time joint state stream
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, Dict

router = APIRouter(prefix="/api/robotics", tags=["Robotics Digital Twin"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _init_service():
    from services.robotics_service import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


class TriggerRequest(BaseModel):
    sequence_id: str
    trigger: str = "manual"
    metadata: Optional[Dict] = None


@router.post("/trigger")
async def trigger_sequence(req: TriggerRequest, authorization: str = Header(None)):
    """Trigger an arm animation sequence."""
    await _auth(authorization)
    _init_service()
    from services.robotics_service import trigger_sequence as _trigger
    result = await _trigger(req.sequence_id, req.trigger, req.metadata)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/state")
async def get_state(authorization: str = Header(None)):
    """Get current arm joint state (REST polling alternative to WebSocket)."""
    await _auth(authorization)
    from services.robotics_service import get_arm_state
    return get_arm_state()


@router.get("/sequences")
async def list_sequences(authorization: str = Header(None)):
    """List available animation sequences."""
    await _auth(authorization)
    from services.robotics_service import get_sequences
    return {"sequences": get_sequences()}


@router.get("/config")
async def arm_config(authorization: str = Header(None)):
    """Get arm hardware configuration (joint limits, link lengths)."""
    await _auth(authorization)
    from services.robotics_service import get_arm_config
    return get_arm_config()


@router.get("/history")
async def task_history(limit: int = 20, authorization: str = Header(None)):
    """Get recent task execution history."""
    await _auth(authorization)
    _init_service()
    from services.robotics_service import get_task_history
    tasks = await get_task_history(limit)
    return {"tasks": tasks, "count": len(tasks)}


@router.websocket("/ws")
async def robotics_ws(ws: WebSocket):
    """WebSocket: real-time joint state stream at 15 FPS."""
    await ws.accept()
    _init_service()
    from services.robotics_service import ws_joint_stream
    try:
        await ws_joint_stream(ws, fps=15)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[Robotics WS] Closed: {e}")
