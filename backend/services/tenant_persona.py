"""
Tenant Persona Profiles — SOUL.md concept per tenant.
Each tenant gets a custom ORA personality loaded at session start.
"""

import os
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


DEFAULT_PERSONA = {
    "business_name": "AUREM Client",
    "industry": "general",
    "ora_name": "ORA",
    "tone": "professional, helpful, concise",
    "greeting": "Welcome",
    "sign_off": "Best regards",
    "avoid_words": [],
    "preferred_words": [],
    "language_style": "professional",
    "custom_knowledge": "",
}


async def get_persona(tenant_id: str) -> dict:
    """Get tenant persona. Returns default if none configured."""
    db = _get_db()
    if db is not None:
        persona = await db.tenant_personas.find_one(
            {"tenant_id": tenant_id}, {"_id": 0}
        )
        if persona:
            return {**DEFAULT_PERSONA, **persona}
    return {**DEFAULT_PERSONA, "tenant_id": tenant_id}


async def set_persona(tenant_id: str, data: dict) -> dict:
    """Create or update tenant persona."""
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}

    allowed_fields = [
        "business_name", "industry", "ora_name", "tone", "greeting",
        "sign_off", "avoid_words", "preferred_words", "language_style",
        "custom_knowledge",
    ]
    update = {k: v for k, v in data.items() if k in allowed_fields}
    update["tenant_id"] = tenant_id
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.tenant_personas.update_one(
        {"tenant_id": tenant_id},
        {"$set": update},
        upsert=True,
    )
    return await get_persona(tenant_id)


async def delete_persona(tenant_id: str) -> dict:
    """Delete tenant persona (revert to default)."""
    db = _get_db()
    if db is not None:
        await db.tenant_personas.delete_one({"tenant_id": tenant_id})
    return {"status": "deleted", "tenant_id": tenant_id}


def build_system_prompt(persona: dict) -> str:
    """Build ORA system prompt from persona profile."""
    name = persona.get("ora_name", "ORA")
    biz = persona.get("business_name", "")
    tone = persona.get("tone", "professional")
    preferred = persona.get("preferred_words", [])
    avoid = persona.get("avoid_words", [])
    greeting = persona.get("greeting", "")
    sign_off = persona.get("sign_off", "")
    knowledge = persona.get("custom_knowledge", "")

    prompt = f"You are {name}"
    if biz:
        prompt += f" for {biz}"
    prompt += f".\nTone: {tone}."
    if preferred:
        prompt += f"\nAlways use: {', '.join(preferred)}."
    if avoid:
        prompt += f"\nNever use: {', '.join(avoid)}."
    if greeting:
        prompt += f"\nGreeting style: {greeting}."
    if sign_off:
        prompt += f"\nSign-off: {sign_off}."
    if knowledge:
        prompt += f"\nBusiness context: {knowledge}"

    return prompt


async def list_personas(limit: int = 50) -> list:
    """List all configured tenant personas."""
    db = _get_db()
    if db is None:
        return []
    cursor = db.tenant_personas.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
