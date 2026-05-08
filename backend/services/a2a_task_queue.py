"""
AUREM Agent-to-Agent Task Queue (iter 296)
==========================================
Durable task chain on top of the existing pub/sub A2ABus.

Collection: a2a_tasks
  task_id, chain_id, parent_task_id,
  created_by, assigned_to, action, payload,
  status: queued|in_progress|complete|failed|escalated|vetoed,
  outcome, council_decision_id,
  created_at, claimed_at, completed_at,
  retries, max_retries, error

Public API:
  await tq.submit(from_agent, to_agent, action, payload, parent=None, council=None) -> task_id
  await tq.claim(agent) -> task | None
  await tq.complete(task_id, result, outcome="success")
  await tq.fail(task_id, error, retry=True)
  await tq.veto(task_id, reason)
  await tq.chain(chain_id) -> [tasks...]
  await tq.recent(limit=50, status=None) -> [...]
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self):
        self._db = None

    def set_db(self, db):
        self._db = db

    async def submit(
        self,
        from_agent: str,
        to_agent: str,
        action: str,
        payload: Dict[str, Any],
        parent_task_id: Optional[str] = None,
        council_decision_id: Optional[str] = None,
        priority: int = 5,
        max_retries: int = 3,
    ) -> str:
        if self._db is None:
            raise RuntimeError("TaskQueue.set_db not called")
        task_id = uuid.uuid4().hex[:14]
        chain_id = parent_task_id and (await self._chain_id_of(parent_task_id)) or task_id
        doc = {
            "task_id": task_id,
            "chain_id": chain_id,
            "parent_task_id": parent_task_id,
            "created_by": from_agent,
            "assigned_to": to_agent,
            "action": action,
            "payload": payload,
            "priority": int(priority),
            "status": "queued",
            "council_decision_id": council_decision_id,
            "max_retries": int(max_retries),
            "retries": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._db.a2a_tasks.insert_one(doc)
        logger.info(f"[a2a-task] submit {from_agent} -> {to_agent} action={action} id={task_id}")
        # Mirror to existing pub/sub bus so live subscribers see it
        try:
            from services.a2a_bus import bus
            await bus.emit(from_agent, f"task:{action}", {"task_id": task_id, "to": to_agent})
        except Exception:
            pass
        return task_id

    async def _chain_id_of(self, parent_task_id: str) -> Optional[str]:
        if self._db is None:
            return None
        doc = await self._db.a2a_tasks.find_one({"task_id": parent_task_id}, {"_id": 0, "chain_id": 1})
        return doc and doc.get("chain_id")

    async def claim(self, agent: str) -> Optional[Dict[str, Any]]:
        """Atomically claim the next queued task for this agent."""
        if self._db is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        doc = await self._db.a2a_tasks.find_one_and_update(
            {"assigned_to": agent, "status": "queued"},
            {"$set": {"status": "in_progress", "claimed_at": now}},
            sort=[("priority", -1), ("created_at", 1)],
            projection={"_id": 0},
            return_document=True,  # type: ignore
        ) if hasattr(self._db.a2a_tasks, "find_one_and_update") else None
        # Motor returns updated doc only if return_document=AFTER; emulate cleanly:
        if doc is None:
            # Fallback: emulate atomic claim
            cand = await self._db.a2a_tasks.find_one(
                {"assigned_to": agent, "status": "queued"},
                {"_id": 0},
                sort=[("priority", -1), ("created_at", 1)],
            )
            if not cand:
                return None
            r = await self._db.a2a_tasks.update_one(
                {"task_id": cand["task_id"], "status": "queued"},
                {"$set": {"status": "in_progress", "claimed_at": now}},
            )
            if r.modified_count == 0:
                return None
            cand["status"] = "in_progress"
            cand["claimed_at"] = now
            return cand
        return doc

    async def complete(self, task_id: str, result: Any, outcome: str = "success") -> None:
        if self._db is None:
            return
        await self._db.a2a_tasks.update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "complete",
                "result": result,
                "outcome": outcome,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        logger.info(f"[a2a-task] complete id={task_id} outcome={outcome}")

    async def fail(self, task_id: str, error: str, retry: bool = True) -> None:
        if self._db is None:
            return
        doc = await self._db.a2a_tasks.find_one({"task_id": task_id}, {"_id": 0, "retries": 1, "max_retries": 1})
        if not doc:
            return
        retries = (doc.get("retries") or 0) + 1
        if retry and retries < (doc.get("max_retries") or 3):
            await self._db.a2a_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "queued", "claimed_at": None, "retries": retries, "error": error[:500]}},
            )
            logger.warning(f"[a2a-task] fail+retry id={task_id} retries={retries}")
        else:
            await self._db.a2a_tasks.update_one(
                {"task_id": task_id},
                {"$set": {
                    "status": "failed",
                    "retries": retries,
                    "error": error[:500],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            logger.error(f"[a2a-task] failed id={task_id} retries={retries}")

    async def veto(self, task_id: str, reason: str) -> None:
        if self._db is None:
            return
        await self._db.a2a_tasks.update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "vetoed",
                "error": f"council_veto: {reason}"[:500],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    async def chain(self, chain_id: str) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        return await self._db.a2a_tasks.find(
            {"chain_id": chain_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(200)

    async def recent(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        q: Dict[str, Any] = {}
        if status:
            q["status"] = status
        return await self._db.a2a_tasks.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(int(limit))

    async def stats(self) -> Dict[str, Any]:
        if self._db is None:
            return {}
        agg = await self._db.a2a_tasks.aggregate([
            {"$group": {"_id": "$status", "n": {"$sum": 1}}},
        ]).to_list(20)
        return {row["_id"]: row["n"] for row in agg}


tq = TaskQueue()


def set_db(db):
    tq.set_db(db)
    # ensure indexes
    try:
        import asyncio
        async def _ix():
            try:
                await db.a2a_tasks.create_index([("assigned_to", 1), ("status", 1), ("priority", -1), ("created_at", 1)], background=True)
                await db.a2a_tasks.create_index([("chain_id", 1)], background=True)
                await db.a2a_tasks.create_index([("status", 1), ("created_at", -1)], background=True)
            except Exception as e:
                logger.debug(f"[a2a-task] index skip: {e}")
        asyncio.create_task(_ix())
    except Exception:
        pass
