"""
AgenticPay 5-Round Negotiation Loop
====================================
Multi-round buyer/seller negotiation with floor price logic.
Each round: buyer proposes → seller evaluates → accept/counter/reject.
Max 5 rounds per session. Floor price never breached.
"""

import os
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


MAX_ROUNDS = 5

# Floor prices by order value bracket
FLOOR_RULES = [
    # (min_value, max_value, floor_discount_pct, start_max_discount_pct)
    (0, 200, 3.0, 2.0),
    (200, 500, 5.0, 3.0),
    (500, 2000, 10.0, 5.0),
    (2000, 10000, 15.0, 8.0),
    (10000, float('inf'), 20.0, 12.0),
]


def _get_floor_and_start(order_value: float, bulk_qty: int = 0) -> tuple:
    """Get floor discount and starting max discount for order value."""
    floor = 3.0
    start = 2.0
    for min_v, max_v, f, s in FLOOR_RULES:
        if min_v <= order_value < max_v:
            floor = f
            start = s
            break
    # Bulk bonus
    if bulk_qty > 10:
        floor += 2.0
        start += 1.0
    if bulk_qty > 50:
        floor += 3.0
        start += 2.0
    return floor, start


def _concession_for_round(round_num: int, floor: float, start: float) -> float:
    """Calculate max discount the seller offers in this round.
    Each round concedes 1-2% more but never exceeds floor."""
    # Linear concession: round 1 = start, round 5 = floor
    if round_num <= 1:
        return start
    progress = min((round_num - 1) / (MAX_ROUNDS - 1), 1.0)
    current = start + (floor - start) * progress
    return round(min(current, floor), 1)


async def start_negotiation(
    tenant_id: str,
    buyer_agent_id: str,
    product_ids: list,
    quantities: list,
    initial_discount_pct: float,
    justification: str = "",
) -> dict:
    """Start a new 5-round negotiation session."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    # Calculate order value
    total_value = 0.0
    products = []
    for pid, qty in zip(product_ids, quantities):
        product = await db.products.find_one(
            {"id": pid, "tenant_id": tenant_id}, {"_id": 0}
        )
        if product:
            price = product.get("price", 0)
            total_value += price * qty
            products.append({"id": pid, "name": product.get("name", pid), "price": price, "qty": qty})

    if total_value == 0:
        total_value = sum(quantities) * 100  # fallback estimate

    bulk_qty = sum(quantities) if quantities else 0
    floor, start = _get_floor_and_start(total_value, bulk_qty)

    session_id = str(uuid.uuid4())[:12]

    # Evaluate round 1
    round_result = _evaluate_round(1, initial_discount_pct, floor, start, total_value)

    session = {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "buyer_agent_id": buyer_agent_id,
        "product_ids": product_ids,
        "quantities": quantities,
        "order_value": total_value,
        "floor_discount_pct": floor,
        "current_round": 1,
        "status": round_result["session_status"],
        "rounds": [{
            "round": 1,
            "buyer_proposed": initial_discount_pct,
            "seller_max": round_result["seller_max"],
            "decision": round_result["decision"],
            "final_discount": round_result["final_discount"],
            "message": round_result["message"],
            "justification": justification,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
        "final_discount_pct": round_result["final_discount"] if round_result["session_status"] == "accepted" else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.negotiation_sessions.insert_one({**session})

    return {
        "session_id": session_id,
        "round": 1,
        "max_rounds": MAX_ROUNDS,
        "decision": round_result["decision"],
        "seller_offer_pct": round_result["seller_max"],
        "final_discount_pct": round_result["final_discount"],
        "message": round_result["message"],
        "order_value": total_value,
        "discounted_total": round(total_value * (1 - round_result["final_discount"] / 100), 2),
        "status": round_result["session_status"],
        "can_counter": round_result["session_status"] == "negotiating",
    }


async def counter_offer(
    session_id: str,
    proposed_discount_pct: float,
    justification: str = "",
) -> dict:
    """Buyer counters with a new discount proposal."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    session = await db.negotiation_sessions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not session:
        return {"error": "Negotiation session not found"}

    if session["status"] != "negotiating":
        return {"error": f"Session is {session['status']}, cannot counter"}

    current_round = session["current_round"] + 1
    if current_round > MAX_ROUNDS:
        # Final round exceeded — reject
        await db.negotiation_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {
            "session_id": session_id,
            "round": current_round,
            "decision": "expired",
            "message": f"Negotiation expired after {MAX_ROUNDS} rounds. Best we offered: {session['floor_discount_pct']}%.",
            "status": "expired",
            "can_counter": False,
        }

    floor = session["floor_discount_pct"]
    start = session["rounds"][0]["seller_max"]  # round 1 seller max
    order_value = session["order_value"]

    round_result = _evaluate_round(current_round, proposed_discount_pct, floor, start, order_value)

    round_record = {
        "round": current_round,
        "buyer_proposed": proposed_discount_pct,
        "seller_max": round_result["seller_max"],
        "decision": round_result["decision"],
        "final_discount": round_result["final_discount"],
        "message": round_result["message"],
        "justification": justification,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    update = {
        "$push": {"rounds": round_record},
        "$set": {
            "current_round": current_round,
            "status": round_result["session_status"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    if round_result["session_status"] == "accepted":
        update["$set"]["final_discount_pct"] = round_result["final_discount"]

    await db.negotiation_sessions.update_one(
        {"session_id": session_id}, update
    )

    return {
        "session_id": session_id,
        "round": current_round,
        "max_rounds": MAX_ROUNDS,
        "decision": round_result["decision"],
        "seller_offer_pct": round_result["seller_max"],
        "final_discount_pct": round_result["final_discount"],
        "message": round_result["message"],
        "order_value": order_value,
        "discounted_total": round(order_value * (1 - round_result["final_discount"] / 100), 2),
        "status": round_result["session_status"],
        "can_counter": round_result["session_status"] == "negotiating",
        "rounds_remaining": MAX_ROUNDS - current_round,
    }


def _evaluate_round(round_num: int, proposed: float, floor: float, start: float, order_value: float) -> dict:
    """Evaluate a single round of negotiation."""
    seller_max = _concession_for_round(round_num, floor, start)

    if proposed <= seller_max:
        return {
            "decision": "accepted",
            "seller_max": seller_max,
            "final_discount": proposed,
            "message": f"Deal! {proposed}% discount accepted on ${order_value:.2f} order. Round {round_num}/{MAX_ROUNDS}.",
            "session_status": "accepted",
        }

    if round_num >= MAX_ROUNDS:
        return {
            "decision": "final_offer",
            "seller_max": seller_max,
            "final_discount": seller_max,
            "message": f"Final offer: {seller_max}% is our maximum on ${order_value:.2f}. Take it or leave it.",
            "session_status": "final_offer",
        }

    if proposed <= floor + 5:
        return {
            "decision": "counter",
            "seller_max": seller_max,
            "final_discount": 0,
            "message": f"We can do {seller_max}% this round (you asked {proposed}%). Counter or accept? {MAX_ROUNDS - round_num} rounds left.",
            "session_status": "negotiating",
        }

    return {
        "decision": "counter",
        "seller_max": seller_max,
        "final_discount": 0,
        "message": f"{proposed}% is too high. Our current offer: {seller_max}%. We can go up to {floor}% max. {MAX_ROUNDS - round_num} rounds left.",
        "session_status": "negotiating",
    }


async def get_session(session_id: str) -> dict:
    """Get full negotiation session with all rounds."""
    db = _get_db()
    if db is None:
        return {}
    session = await db.negotiation_sessions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    return session or {}


async def get_tenant_sessions(tenant_id: str, limit: int = 20) -> list:
    """Get recent negotiation sessions for a tenant."""
    db = _get_db()
    if db is None:
        return []
    cursor = db.negotiation_sessions.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def accept_final_offer(session_id: str) -> dict:
    """Buyer accepts the seller's current offer."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    session = await db.negotiation_sessions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not session:
        return {"error": "Session not found"}

    if session["status"] not in ("negotiating", "final_offer"):
        return {"error": f"Session is {session['status']}"}

    last_round = session["rounds"][-1] if session["rounds"] else {}
    seller_offer = last_round.get("seller_max", 0)

    await db.negotiation_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": "accepted",
            "final_discount_pct": seller_offer,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    return {
        "session_id": session_id,
        "status": "accepted",
        "final_discount_pct": seller_offer,
        "order_value": session["order_value"],
        "discounted_total": round(session["order_value"] * (1 - seller_offer / 100), 2),
        "message": f"Deal closed! {seller_offer}% discount applied. Total rounds: {session['current_round']}.",
    }
