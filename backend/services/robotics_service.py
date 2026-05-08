"""
AUREM Robotics Service — 6-DOF Digital Twin Simulation
=======================================================
Standalone simulation engine matching reBot-DevArm specs.
Forward/inverse kinematics for 6-DOF robotic arm.
Business trigger → animation sequence mapping.
WebSocket streaming of joint states.
"""
import os
import math
import time
import logging
import asyncio
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════
# 6-DOF ARM CONFIGURATION (matching reBot-DevArm physical specs)
# ═══════════════════════════════════════════════════════════════

ARM_CONFIG = {
    "name": "AUREM-Sovereign-Arm",
    "dof": 6,
    "reach_mm": 550,
    "joints": [
        {"name": "base_rotation", "min": -180, "max": 180, "home": 0, "speed_dps": 90},
        {"name": "shoulder", "min": -90, "max": 90, "home": 0, "speed_dps": 60},
        {"name": "elbow", "min": -135, "max": 135, "home": 0, "speed_dps": 75},
        {"name": "wrist_pitch", "min": -90, "max": 90, "home": 0, "speed_dps": 120},
        {"name": "wrist_roll", "min": -180, "max": 180, "home": 0, "speed_dps": 150},
        {"name": "gripper", "min": 0, "max": 45, "home": 0, "speed_dps": 200},
    ],
    "link_lengths_mm": [120, 180, 160, 60, 40, 30],
}


# ═══════════════════════════════════════════════════════════════
# ANIMATION SEQUENCES (business trigger → arm motion)
# ═══════════════════════════════════════════════════════════════

SEQUENCES = {
    "idle_breathe": {
        "name": "Idle Breathe",
        "description": "Gentle oscillation — arm is alive and ready",
        "duration_s": 4.0,
        "loop": True,
        "keyframes": [
            {"t": 0.0, "joints": [0, 0, 0, 0, 0, 0]},
            {"t": 0.5, "joints": [5, -3, 2, -2, 0, 0]},
            {"t": 1.0, "joints": [0, 0, 0, 0, 0, 0]},
        ],
    },
    "pick_and_pack": {
        "name": "Pick & Pack",
        "description": "Order fulfillment — pick item from shelf, place in box",
        "trigger": "shopify_order_paid",
        "duration_s": 6.0,
        "loop": False,
        "keyframes": [
            {"t": 0.0, "joints": [0, 0, 0, 0, 0, 0]},
            {"t": 0.15, "joints": [-45, 30, -20, 0, 0, 0]},
            {"t": 0.3, "joints": [-45, 45, -60, -15, 0, 0]},
            {"t": 0.4, "joints": [-45, 45, -60, -15, 0, 35]},
            {"t": 0.55, "joints": [-45, 20, -30, 10, 0, 35]},
            {"t": 0.7, "joints": [45, 30, -40, -10, 0, 35]},
            {"t": 0.8, "joints": [45, 50, -70, -20, 0, 35]},
            {"t": 0.9, "joints": [45, 50, -70, -20, 0, 0]},
            {"t": 1.0, "joints": [0, 0, 0, 0, 0, 0]},
        ],
    },
    "point_and_scan": {
        "name": "Point & Scan",
        "description": "Inventory scan — sweep across storage and identify items",
        "trigger": "inventory_low",
        "duration_s": 5.0,
        "loop": False,
        "keyframes": [
            {"t": 0.0, "joints": [0, 0, 0, 0, 0, 0]},
            {"t": 0.15, "joints": [-60, 20, -10, 5, 0, 0]},
            {"t": 0.35, "joints": [-30, 35, -25, 10, -30, 0]},
            {"t": 0.55, "joints": [30, 35, -25, 10, 30, 0]},
            {"t": 0.75, "joints": [60, 20, -10, 5, 0, 0]},
            {"t": 0.9, "joints": [0, 10, -5, 0, 0, 0]},
            {"t": 1.0, "joints": [0, 0, 0, 0, 0, 0]},
        ],
    },
    "quality_inspect": {
        "name": "Quality Inspect",
        "description": "Product QA — examine item from multiple angles",
        "trigger": "qa_request",
        "duration_s": 5.0,
        "loop": False,
        "keyframes": [
            {"t": 0.0, "joints": [0, 0, 0, 0, 0, 0]},
            {"t": 0.1, "joints": [0, 30, -45, 0, 0, 30]},
            {"t": 0.3, "joints": [0, 40, -60, 20, -45, 30]},
            {"t": 0.5, "joints": [0, 40, -60, -20, 45, 30]},
            {"t": 0.7, "joints": [0, 40, -60, 20, 90, 30]},
            {"t": 0.85, "joints": [0, 30, -45, 0, 0, 30]},
            {"t": 0.95, "joints": [0, 15, -20, 0, 0, 0]},
            {"t": 1.0, "joints": [0, 0, 0, 0, 0, 0]},
        ],
    },
    "wave_greeting": {
        "name": "Wave Greeting",
        "description": "Greeting gesture — friendly wave on user login",
        "trigger": "user_login",
        "duration_s": 3.0,
        "loop": False,
        "keyframes": [
            {"t": 0.0, "joints": [0, 0, 0, 0, 0, 0]},
            {"t": 0.2, "joints": [0, -45, 60, 30, 0, 0]},
            {"t": 0.4, "joints": [10, -45, 60, 30, 25, 15]},
            {"t": 0.55, "joints": [-10, -45, 60, 30, -25, 15]},
            {"t": 0.7, "joints": [10, -45, 60, 30, 25, 15]},
            {"t": 0.85, "joints": [0, -20, 30, 15, 0, 0]},
            {"t": 1.0, "joints": [0, 0, 0, 0, 0, 0]},
        ],
    },
}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smooth_step(t: float) -> float:
    return t * t * (3 - 2 * t)


def interpolate_keyframes(keyframes: list, progress: float) -> List[float]:
    """Interpolate joint angles at a given progress (0.0-1.0) using smooth step."""
    progress = max(0.0, min(1.0, progress))
    if not keyframes:
        return [0] * 6

    for i in range(len(keyframes) - 1):
        kf_a, kf_b = keyframes[i], keyframes[i + 1]
        if kf_a["t"] <= progress <= kf_b["t"]:
            segment_len = kf_b["t"] - kf_a["t"]
            local_t = (progress - kf_a["t"]) / segment_len if segment_len > 0 else 0
            smooth_t = _smooth_step(local_t)
            return [_lerp(a, b, smooth_t) for a, b in zip(kf_a["joints"], kf_b["joints"])]

    return keyframes[-1]["joints"]


# ═══════════════════════════════════════════════════════════════
# TASK QUEUE & STATE
# ═══════════════════════════════════════════════════════════════

_current_task = None
_task_queue = asyncio.Queue() if hasattr(asyncio, 'Queue') else None
_ws_clients = set()


def get_arm_state() -> Dict:
    """Current arm state for REST polling."""
    if _current_task:
        elapsed = time.time() - _current_task["started_at"]
        duration = _current_task["duration_s"]
        progress = min(1.0, elapsed / duration) if duration > 0 else 1.0
        seq = SEQUENCES.get(_current_task["sequence_id"], SEQUENCES["idle_breathe"])
        joints = interpolate_keyframes(seq["keyframes"], progress)
        return {
            "sequence": _current_task["sequence_id"],
            "sequence_name": seq["name"],
            "trigger": _current_task.get("trigger", "manual"),
            "progress": round(progress, 3),
            "joints": [round(j, 2) for j in joints],
            "status": "executing",
            "task_id": _current_task["task_id"],
            "metadata": _current_task.get("metadata", {}),
        }
    return {
        "sequence": "idle_breathe",
        "sequence_name": "Idle Breathe",
        "trigger": "none",
        "progress": 0,
        "joints": [0, 0, 0, 0, 0, 0],
        "status": "idle",
        "task_id": None,
        "metadata": {},
    }


async def trigger_sequence(
    sequence_id: str,
    trigger: str = "manual",
    metadata: Dict = None,
) -> Dict:
    """Trigger a new arm animation sequence."""
    global _current_task

    if sequence_id not in SEQUENCES:
        return {"error": f"Unknown sequence: {sequence_id}"}

    seq = SEQUENCES[sequence_id]
    task_id = f"task_{secrets.token_hex(6)}"

    _current_task = {
        "task_id": task_id,
        "sequence_id": sequence_id,
        "trigger": trigger,
        "duration_s": seq["duration_s"],
        "started_at": time.time(),
        "metadata": metadata or {},
    }

    # Log to DB
    if _db is not None:
        await _db.robotics_tasks.insert_one({
            "task_id": task_id,
            "sequence_id": sequence_id,
            "sequence_name": seq["name"],
            "trigger": trigger,
            "metadata": metadata or {},
            "status": "executing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Broadcast to WebSocket clients
    await _broadcast_ws({"type": "sequence_start", "task_id": task_id, "sequence": sequence_id, "name": seq["name"], "duration_s": seq["duration_s"], "trigger": trigger})

    # Schedule completion
    asyncio.ensure_future(_complete_after(task_id, seq["duration_s"]))

    logger.info(f"[Robotics] Triggered {sequence_id} (task={task_id}, trigger={trigger})")
    return {"task_id": task_id, "sequence": sequence_id, "name": seq["name"], "duration_s": seq["duration_s"]}


async def _complete_after(task_id: str, duration: float):
    """Mark task complete after duration."""
    global _current_task
    await asyncio.sleep(duration)

    if _current_task and _current_task["task_id"] == task_id:
        _current_task = None

        if _db is not None:
            await _db.robotics_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}},
            )

        await _broadcast_ws({"type": "sequence_complete", "task_id": task_id})


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET BROADCAST
# ═══════════════════════════════════════════════════════════════

async def register_ws(ws):
    _ws_clients.add(ws)

async def unregister_ws(ws):
    _ws_clients.discard(ws)

async def _broadcast_ws(msg: Dict):
    import json
    data = json.dumps(msg)
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def ws_joint_stream(ws, fps: int = 15):
    """Stream joint states at target FPS for real-time 3D rendering."""
    import json
    interval = 1.0 / fps
    try:
        await register_ws(ws)
        while True:
            state = get_arm_state()
            await ws.send_text(json.dumps({"type": "joint_state", **state}))
            await asyncio.sleep(interval)
    except Exception:
        pass
    finally:
        await unregister_ws(ws)


# ═══════════════════════════════════════════════════════════════
# BUSINESS TRIGGER HOOKS
# ═══════════════════════════════════════════════════════════════

async def on_shopify_order_paid(order_data: Dict):
    """Hook: Shopify order paid → pick_and_pack sequence."""
    return await trigger_sequence("pick_and_pack", "shopify_order_paid", {
        "order_id": order_data.get("order_id", ""),
        "items": order_data.get("line_items", [])[:3],
    })


async def on_inventory_low(product_data: Dict):
    """Hook: Inventory below threshold → point_and_scan sequence."""
    return await trigger_sequence("point_and_scan", "inventory_low", {
        "product": product_data.get("product_name", ""),
        "current_stock": product_data.get("stock", 0),
    })


async def get_task_history(limit: int = 20) -> List[Dict]:
    if _db is None:
        return []
    cursor = _db.robotics_tasks.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


def get_sequences() -> Dict:
    return {k: {"name": v["name"], "description": v["description"], "duration_s": v["duration_s"], "trigger": v.get("trigger", "manual")} for k, v in SEQUENCES.items()}


def get_arm_config() -> Dict:
    return ARM_CONFIG
