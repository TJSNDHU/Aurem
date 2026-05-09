"""
bin_repo.py — BIN-scoped repository wrapper. Eliminates cross-BIN leaks.
═══════════════════════════════════════════════════════════════════════════
Usage:
    repo = BinScopedRepo(db, "campaign_leads", ctx.business_id)
    await repo.find_one({"lead_id": x})        # auto-injects business_id
    await repo.insert_one({"lead_id": ..., "email": ...})  # auto business_id
    async for d in repo.find({}, sort=[("ts", -1)]).limit(50):
        ...
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BinScopedRepo:
    def __init__(self, db, collection_name: str, business_id: str):
        if not business_id:
            raise ValueError("BinScopedRepo requires business_id")
        self.db = db
        self.coll = db[collection_name]
        self.bin = business_id
        self._cn = collection_name

    def _scope(self, q: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged = dict(q or {})
        merged["business_id"] = self.bin
        return merged

    async def find_one(self, q: Optional[Dict[str, Any]] = None,
                       projection: Optional[Dict[str, Any]] = None):
        proj = projection if projection is not None else {"_id": 0}
        return await self.coll.find_one(self._scope(q), proj)

    def find(self, q: Optional[Dict[str, Any]] = None,
             projection: Optional[Dict[str, Any]] = None):
        proj = projection if projection is not None else {"_id": 0}
        return self.coll.find(self._scope(q), proj)

    async def count(self, q: Optional[Dict[str, Any]] = None) -> int:
        return await self.coll.count_documents(self._scope(q))

    async def insert_one(self, doc: Dict[str, Any]):
        scoped = dict(doc)
        scoped["business_id"] = self.bin
        return await self.coll.insert_one(scoped)

    async def update_one(self, q: Dict[str, Any], update: Dict[str, Any], **kwargs):
        return await self.coll.update_one(self._scope(q), update, **kwargs)

    async def update_many(self, q: Dict[str, Any], update: Dict[str, Any], **kwargs):
        return await self.coll.update_many(self._scope(q), update, **kwargs)

    async def delete_one(self, q: Dict[str, Any]):
        return await self.coll.delete_one(self._scope(q))

    async def delete_many(self, q: Dict[str, Any]):
        return await self.coll.delete_many(self._scope(q))
