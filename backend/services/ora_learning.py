"""
AUREM ORA Learning Loop (iter 296)
==================================
Every agent action → log_action → outcome update → pattern indexer.

Collections:
  agent_outcomes — input/output/outcome rows
  agent_feed     — live feed (ORA Brain dashboard)
  ora_patterns   — clustered patterns from outcomes (rebuilt periodically)
  legion_finetune_jobs — every 100 outcomes triggers a batch

Public API:
  action_id = await ora.log_action(agent, action, input, output, cost_usd=0)
  await ora.update_outcome(action_id, "converted"|"no_reply"|"bounced"|"fixed"|"failed")
  similar = await ora.find_similar(agent, action, input_keys=[...], limit=5)
  await ora.maybe_trigger_legion_finetune()
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FINETUNE_BATCH_SIZE = 100


class ORALearning:
    def __init__(self):
        self._db = None
        self._counter_since_last_finetune = 0

    def set_db(self, db):
        self._db = db

    # ─── log_action ──────────────────────────────────────────────────────────
    async def log_action(
        self,
        agent: str,
        action: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]] = None,
        cost_usd: float = 0.0,
        chain_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        if self._db is None:
            return ""
        action_id = uuid.uuid4().hex[:14]
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "action_id": action_id,
            "agent": agent,
            "action": action,
            "input": _trim(input_data, 2000),
            "output": _trim(output_data or {}, 2000),
            "cost_usd": float(cost_usd),
            "chain_id": chain_id,
            "task_id": task_id,
            "outcome": "pending",
            "ts": now,
        }
        try:
            await self._db.agent_outcomes.insert_one(doc)
            # Mirror to live feed (drives ORA Brain dashboard)
            await self._db.agent_feed.insert_one({
                "agent_id": agent,
                "action": action,
                "action_id": action_id,
                "ts": now,
                "summary": _summarize(action, input_data, output_data, cost_usd),
                "cost_usd": float(cost_usd),
            })
        except Exception as e:
            logger.warning(f"[ora-learn] log_action persist failed: {e}")
        self._counter_since_last_finetune += 1
        if self._counter_since_last_finetune >= FINETUNE_BATCH_SIZE:
            asyncio.create_task(self.maybe_trigger_legion_finetune())
        return action_id

    # ─── update_outcome ──────────────────────────────────────────────────────
    async def update_outcome(
        self,
        action_id: str,
        outcome: str,
        signal: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._db is None or not action_id:
            return
        valid = {"converted", "no_reply", "bounced", "fixed", "failed", "success"}
        if outcome not in valid:
            outcome = "success"
        try:
            await self._db.agent_outcomes.update_one(
                {"action_id": action_id},
                {"$set": {
                    "outcome": outcome,
                    "outcome_signal": signal or {},
                    "outcome_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        except Exception as e:
            logger.warning(f"[ora-learn] update_outcome failed: {e}")

    # ─── find_similar ────────────────────────────────────────────────────────
    async def find_similar(
        self,
        agent: str,
        action: str,
        input_keys: Optional[Dict[str, Any]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        q: Dict[str, Any] = {"agent": agent, "action": action,
                             "outcome": {"$in": ["converted", "success", "fixed"]}}
        if input_keys:
            for k, v in input_keys.items():
                q[f"input.{k}"] = v
        return await self._db.agent_outcomes.find(q, {"_id": 0}).sort("outcome_at", -1).limit(int(limit)).to_list(int(limit))

    # ─── pattern + finetune ──────────────────────────────────────────────────
    async def maybe_trigger_legion_finetune(self) -> None:
        if self._db is None:
            return
        try:
            since = await self._db.legion_finetune_jobs.find_one(
                {}, {"_id": 0, "until_ts": 1}, sort=[("created_at", -1)],
            )
            since_ts = (since or {}).get("until_ts") or "1970-01-01T00:00:00Z"
            outcomes = await self._db.agent_outcomes.find(
                {"outcome": {"$ne": "pending"}, "outcome_at": {"$gte": since_ts}},
                {"_id": 0, "agent": 1, "action": 1, "input": 1, "output": 1, "outcome": 1, "outcome_at": 1},
            ).limit(FINETUNE_BATCH_SIZE * 2).to_list(FINETUNE_BATCH_SIZE * 2)
            if len(outcomes) < FINETUNE_BATCH_SIZE:
                self._counter_since_last_finetune = 0
                return
            until = max(o.get("outcome_at", "") for o in outcomes)
            job = {
                "job_id": uuid.uuid4().hex[:14],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "until_ts": until,
                "n_examples": len(outcomes),
                "status": "queued",
                "target_model": os.environ.get("LEGION_MODEL", "llama3.1"),
            }
            await self._db.legion_finetune_jobs.insert_one(job)
            logger.info(f"[ora-learn] finetune job queued — {len(outcomes)} examples → {job['target_model']}")
            # Update top-level patterns table (frequency map)
            await self._rebuild_patterns(outcomes)
        except Exception as e:
            logger.error(f"[ora-learn] finetune trigger failed: {e}")
        finally:
            self._counter_since_last_finetune = 0

    async def _rebuild_patterns(self, outcomes: List[Dict[str, Any]]) -> None:
        if self._db is None:
            return
        from collections import defaultdict
        agg: Dict[str, Dict[str, int]] = defaultdict(lambda: {"n": 0, "converted": 0, "bounced": 0, "no_reply": 0})
        for o in outcomes:
            key = f"{o.get('agent','?')}::{o.get('action','?')}"
            agg[key]["n"] += 1
            if o.get("outcome") in ("converted", "success", "fixed"):
                agg[key]["converted"] += 1
            elif o.get("outcome") == "bounced":
                agg[key]["bounced"] += 1
            elif o.get("outcome") == "no_reply":
                agg[key]["no_reply"] += 1
        now = datetime.now(timezone.utc).isoformat()
        for key, stats in agg.items():
            await self._db.ora_patterns.update_one(
                {"key": key},
                {"$set": {"key": key, "stats": stats, "updated_at": now}},
                upsert=True,
            )

    async def patterns(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        return await self._db.ora_patterns.find({}, {"_id": 0}).sort("stats.n", -1).limit(int(limit)).to_list(int(limit))

    async def feed(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        return await self._db.agent_feed.find({}, {"_id": 0}).sort("ts", -1).limit(int(limit)).to_list(int(limit))

    async def stats(self) -> Dict[str, Any]:
        if self._db is None:
            return {}
        agg = await self._db.agent_outcomes.aggregate([
            {"$group": {"_id": "$outcome", "n": {"$sum": 1}}},
        ]).to_list(20)
        outcomes = {row["_id"]: row["n"] for row in agg}
        return {"outcomes": outcomes, "until_finetune": max(0, FINETUNE_BATCH_SIZE - self._counter_since_last_finetune)}


# ─── helpers ─────────────────────────────────────────────────────────────────
def _trim(d: Any, max_len: int) -> Any:
    s = str(d)
    if len(s) <= max_len:
        return d
    if isinstance(d, dict):
        return {k: (str(v)[:200] if not isinstance(v, (int, float, bool)) else v) for k, v in list(d.items())[:30]}
    return s[:max_len]


def _summarize(action: str, input_data: Dict, output_data: Optional[Dict], cost_usd: float) -> str:
    parts = [action]
    if input_data:
        for k in ("lead_id", "domain", "to", "channel", "agent"):
            if k in input_data:
                parts.append(f"{k}={input_data[k]}")
                break
    if output_data and output_data.get("success") is not None:
        parts.append(f"ok={output_data['success']}")
    if cost_usd:
        parts.append(f"${cost_usd:.4f}")
    return " ".join(parts)[:200]


ora = ORALearning()


def set_db(db):
    ora.set_db(db)
    try:
        import asyncio as _a
        async def _ix():
            try:
                await db.agent_outcomes.create_index([("agent", 1), ("action", 1), ("outcome_at", -1)], background=True)
                await db.agent_outcomes.create_index([("action_id", 1)], background=True, unique=True)
                await db.agent_outcomes.create_index([("outcome", 1), ("outcome_at", -1)], background=True)
                await db.agent_feed.create_index([("ts", -1)], background=True)
                await db.ora_patterns.create_index([("stats.n", -1)], background=True)
            except Exception:
                pass
        _a.create_task(_ix())
    except Exception:
        pass
