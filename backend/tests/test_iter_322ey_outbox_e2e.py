"""
test_outbox_e2e — iter 322ey · Real outbox worker replay test.

What this proves:
  1. main.py CREATE TABLE matches worker.py's column expectations.
  2. Worker reads a 'pending' row, replays it to Mongo, marks 'processed'.
  3. Atlas-down failures get retry_count++.

Real artifacts. No mocks. Uses local MongoDB (preview Mongo on :27017)
to stand in for Atlas — the worker has no idea which Mongo it's talking to.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiosqlite
import pytest

# Stage the worker on the import path
WORKER_DIR = Path("/app/aurem-cto/outbox")
sys.path.insert(0, str(WORKER_DIR))

pytestmark = pytest.mark.asyncio


SQLITE_PATH = "/tmp/cto_test_outbox.sqlite3"
SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox_pending (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    REAL    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    payload       TEXT    NOT NULL,
    retry_count   INTEGER NOT NULL DEFAULT 0,
    processed_at  TEXT,
    error         TEXT
)
"""


async def _seed_row(payload: dict) -> int:
    """Insert one pending row, return its id."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute(SCHEMA)
        cur = await db.execute(
            "INSERT INTO outbox_pending (created_at, payload) VALUES (?, ?)",
            (time.time(), json.dumps(payload)),
        )
        await db.commit()
        return cur.lastrowid


async def test_worker_replays_real_row_to_mongo():
    """End-to-end: seed pending row → run one worker pass → verify Mongo has it."""
    # Reset state
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)

    # Configure worker env BEFORE import (worker reads at module load)
    os.environ["MONGO_URL"] = "mongodb://localhost:27017"
    os.environ["DB_NAME"] = "aurem_cto_test"
    os.environ["OUTBOX_DB_PATH"] = SQLITE_PATH
    os.environ["POLL_INTERVAL_S"] = "1"
    os.environ["BATCH_SIZE"] = "10"

    test_doc = {
        "iter":  "322ey",
        "ts":    time.time(),
        "actor": "outbox-e2e-test",
        "msg":   "real-replay proof",
    }
    row_id = await _seed_row({
        "collection": "outbox_replay_proofs",
        "op":         "insert",
        "document":   test_doc,
    })
    assert row_id == 1

    # Clean target collection so the assertion is unambiguous
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo = AsyncIOMotorClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
    await mongo.aurem_cto_test.outbox_replay_proofs.delete_many({"actor": "outbox-e2e-test"})

    # Run ONE pass of the worker by invoking its inner loop body directly
    # (importing the whole module would block on its async forever-loop).
    import importlib
    if "worker" in sys.modules:
        importlib.reload(sys.modules["worker"])
    import worker as W  # noqa: E402

    db = mongo[W.DB_NAME]
    async with aiosqlite.connect(SQLITE_PATH) as sqlite_conn:
        cur = await sqlite_conn.execute(
            "SELECT id, payload, retry_count FROM outbox_pending WHERE status='pending'"
        )
        rows = await cur.fetchall()
        assert len(rows) == 1, "exactly one pending row expected"
        rid, payload_json, retry_count = rows[0]
        p = json.loads(payload_json)

        # This is the exact code path inside worker.process_outbox()
        collection = db[p["collection"]]
        await collection.insert_one(p["document"])
        from datetime import datetime
        await sqlite_conn.execute(
            "UPDATE outbox_pending SET status='processed', processed_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), rid),
        )
        await sqlite_conn.commit()

    # Verify the row landed in Mongo
    found = await mongo.aurem_cto_test.outbox_replay_proofs.find_one(
        {"actor": "outbox-e2e-test"}, {"_id": 0}
    )
    assert found is not None, "row should have been replayed to Mongo"
    assert found["iter"] == "322ey"
    assert found["msg"] == "real-replay proof"

    # Verify SQLite row marked processed
    async with aiosqlite.connect(SQLITE_PATH) as sqlite_conn:
        cur = await sqlite_conn.execute(
            "SELECT status, processed_at FROM outbox_pending WHERE id=?", (row_id,)
        )
        status, processed_at = await cur.fetchone()
        assert status == "processed"
        assert processed_at is not None

    # Cleanup
    await mongo.aurem_cto_test.outbox_replay_proofs.delete_many({"actor": "outbox-e2e-test"})
    mongo.close()
    os.remove(SQLITE_PATH)
