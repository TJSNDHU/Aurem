"""
Hermes × DeepSleep Bridge
=========================
Integrates DeepSleep-beta's 3-layer memory (project / session / ephemeral)
into AUREM's Hermes memory stack as a CODEBASE SELF-AWARENESS layer.

Credit: github.com/Keshavsharma-code/DeepSleep-beta
Adapted for MongoDB persistence (per-tenant) instead of filesystem.

Three layers:
  - project    → stable repo facts / goals / summary (rarely changes)
  - session    → current session tasks, recent files, last dream
  - ephemeral  → last user msg, open questions, recent changes

Usage:
    from services.hermes_deepsleep_bridge import DeepSleepMemory
    dsm = DeepSleepMemory(tenant_id="polaris-built-001")
    await dsm.record_chat_turn(user_msg, assistant_msg, files=["server.py"])
    ctx = await dsm.build_context()   # string ready to inject into prompts
"""
from __future__ import annotations

import copy
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


MAX_MEMORY_BYTES = 4096  # 4KB per tenant (AUREM has more budget than DeepSleep local)
COLLECTION = "hermes_deepsleep_memory"


def _default_memory(tenant_id: str) -> Dict[str, Any]:
    ts = _utc_now()
    return {
        "tenant_id": tenant_id,
        "version": 1,
        "project": {
            "summary": "AUREM multi-agent business automation platform.",
            "goals": [],
            "facts": [],
        },
        "session": {
            "summary": "No session summary yet.",
            "recent_files": [],
            "recent_tasks": [],
            "last_dream_at": None,
        },
        "ephemeral": {
            "last_user_message": "",
            "last_assistant_message": "",
            "open_questions": [],
            "recent_changes": [],
        },
        "meta": {
            "created_at": ts,
            "updated_at": ts,
            "last_model": "claude-sonnet-4.5",
        },
    }


class DeepSleepMemory:
    """DeepSleep-style 3-layer memory persisted in MongoDB per tenant."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.max_bytes = MAX_MEMORY_BYTES

    async def _load(self) -> Dict[str, Any]:
        db = _get_db()
        if db is None:
            return _default_memory(self.tenant_id)
        doc = await db[COLLECTION].find_one(
            {"tenant_id": self.tenant_id}, {"_id": 0}
        )
        return doc or _default_memory(self.tenant_id)

    async def _save(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        db = _get_db()
        memory = self._compact(copy.deepcopy(memory))
        memory["meta"]["updated_at"] = _utc_now()
        if db is None:
            return memory
        await db[COLLECTION].update_one(
            {"tenant_id": self.tenant_id},
            {"$set": memory},
            upsert=True,
        )
        return memory

    async def initialize(self) -> Dict[str, Any]:
        db = _get_db()
        if db is None:
            return _default_memory(self.tenant_id)
        existing = await db[COLLECTION].find_one({"tenant_id": self.tenant_id})
        if existing:
            return existing
        default = _default_memory(self.tenant_id)
        await db[COLLECTION].insert_one(default)
        return default

    async def build_context(self) -> str:
        m = await self._load()
        recent_files = ", ".join(m["session"]["recent_files"]) or "none"
        recent_tasks = ", ".join(m["session"]["recent_tasks"]) or "none"
        open_q = ", ".join(m["ephemeral"]["open_questions"]) or "none"
        changes = ", ".join(m["ephemeral"]["recent_changes"]) or "none"
        return (
            "Project layer:\n"
            f"- Summary: {m['project']['summary']}\n"
            f"- Goals: {', '.join(m['project']['goals']) or 'none'}\n"
            f"- Facts: {', '.join(m['project']['facts']) or 'none'}\n\n"
            "Session layer:\n"
            f"- Summary: {m['session']['summary']}\n"
            f"- Recent files: {recent_files}\n"
            f"- Recent tasks: {recent_tasks}\n"
            f"- Last dream at: {m['session']['last_dream_at'] or 'never'}\n\n"
            "Ephemeral layer:\n"
            f"- Recent changes: {changes}\n"
            f"- Open questions: {open_q}\n"
            f"- Last user msg: {m['ephemeral']['last_user_message']}\n"
            f"- Last assistant msg: {m['ephemeral']['last_assistant_message']}\n"
        )

    async def record_chat_turn(
        self,
        user_message: str,
        assistant_message: str,
        files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        m = await self._load()
        m["ephemeral"]["last_user_message"] = _clip(user_message, 220)
        m["ephemeral"]["last_assistant_message"] = _clip(assistant_message, 260)
        m["session"]["recent_files"] = _merge_unique(
            m["session"]["recent_files"], files or [], 8
        )
        m["session"]["recent_tasks"] = _append_unique(
            m["session"]["recent_tasks"], _clip(user_message, 140), 5
        )
        return await self._save(m)

    async def record_dream(
        self,
        summary: str,
        changed_files: Optional[List[str]] = None,
        model_name: str = "claude-sonnet-4.5",
    ) -> Dict[str, Any]:
        m = await self._load()
        m["session"]["summary"] = _clip(summary, 480)
        m["session"]["recent_files"] = _merge_unique(
            m["session"]["recent_files"], changed_files or [], 8
        )
        m["session"]["last_dream_at"] = _utc_now()
        m["ephemeral"]["recent_changes"] = [
            _clip(c, 140) for c in (changed_files or [])[-8:]
        ]
        m["meta"]["last_model"] = model_name
        return await self._save(m)

    async def add_project_fact(self, fact: str) -> Dict[str, Any]:
        m = await self._load()
        m["project"]["facts"] = _append_unique(
            m["project"]["facts"], _clip(fact, 180), 6
        )
        return await self._save(m)

    async def add_goal(self, goal: str) -> Dict[str, Any]:
        m = await self._load()
        m["project"]["goals"] = _append_unique(
            m["project"]["goals"], _clip(goal, 140), 5
        )
        return await self._save(m)

    async def add_open_question(self, question: str) -> Dict[str, Any]:
        m = await self._load()
        m["ephemeral"]["open_questions"] = _append_unique(
            m["ephemeral"]["open_questions"], _clip(question, 140), 4
        )
        return await self._save(m)

    def _compact(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Apply DeepSleep-style clipping so memory stays under max_bytes."""
        memory["project"]["summary"] = _clip(memory["project"]["summary"], 280)
        memory["session"]["summary"] = _clip(memory["session"]["summary"], 480)
        memory["project"]["goals"] = _normalize_list(memory["project"]["goals"], 5, 120)
        memory["project"]["facts"] = _normalize_list(memory["project"]["facts"], 6, 160)
        memory["session"]["recent_files"] = _normalize_list(
            memory["session"]["recent_files"], 8, 100
        )
        memory["session"]["recent_tasks"] = _normalize_list(
            memory["session"]["recent_tasks"], 5, 140
        )
        memory["ephemeral"]["open_questions"] = _normalize_list(
            memory["ephemeral"]["open_questions"], 4, 140
        )
        memory["ephemeral"]["recent_changes"] = _normalize_list(
            memory["ephemeral"]["recent_changes"], 8, 140
        )
        return memory


# ──────────── helpers ────────────
def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def _append_unique(values: List[str], item: str, limit: int) -> List[str]:
    filtered = [v for v in values if v != item]
    filtered.append(item)
    return filtered[-limit:]


def _merge_unique(existing: List[str], incoming: List[str], limit: int) -> List[str]:
    merged = list(existing)
    for value in incoming:
        if not value:
            continue
        if value in merged:
            merged.remove(value)
        merged.append(value)
    return merged[-limit:]


def _normalize_list(values: List[str], limit: int, char_limit: int) -> List[str]:
    normalized = []
    for v in values:
        if not v:
            continue
        c = _clip(v, char_limit)
        if c not in normalized:
            normalized.append(c)
    return normalized[-limit:]
