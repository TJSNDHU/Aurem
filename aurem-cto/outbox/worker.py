import asyncio
import json
import logging
import os
import signal
from datetime import datetime

import aiosqlite
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - worker.outbox - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'aurem_cto')
OUTBOX_DB_PATH = os.getenv('OUTBOX_DB_PATH', '/data/outbox.db')
POLL_INTERVAL_S = int(os.getenv('POLL_INTERVAL_S', '5'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
MAX_RETRIES = 5

shutdown_event = asyncio.Event()


def handle_shutdown(sig, frame):
    logger.info(f"Received signal {sig}, initiating graceful shutdown")
    shutdown_event.set()


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


async def connect_mongo_with_retry() -> AsyncIOMotorClient:
    backoff = 1
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            await client.admin.command('ping')
            logger.info(f"MongoDB connected on attempt {attempt}")
            return client
        except PyMongoError as e:
            logger.warning(f"MongoDB connection attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            else:
                raise


async def process_outbox():
    mongo_client = await connect_mongo_with_retry()
    db = mongo_client[DB_NAME]

    async with aiosqlite.connect(OUTBOX_DB_PATH) as sqlite_conn:
        logger.info("Outbox worker started")

        while not shutdown_event.is_set():
            try:
                cursor = await sqlite_conn.execute(
                    "SELECT id, payload, retry_count FROM outbox_pending WHERE status='pending' ORDER BY created_at LIMIT ?",
                    (BATCH_SIZE,)
                )
                rows = await cursor.fetchall()

                for row_id, payload_json, retry_count in rows:
                    try:
                        payload = json.loads(payload_json)
                        collection_name = payload.get('collection')
                        op = payload.get('op')
                        filter_doc = payload.get('filter', {})
                        document = payload.get('document', {})

                        if not collection_name or not op:
                            raise ValueError("Missing collection or op in payload")

                        collection = db[collection_name]

                        if op == 'insert':
                            await collection.insert_one(document)
                        elif op == 'update':
                            await collection.update_one(filter_doc, {'$set': document}, upsert=True)
                        elif op == 'delete':
                            await collection.delete_one(filter_doc)
                        else:
                            raise ValueError(f"Unknown op: {op}")

                        await sqlite_conn.execute(
                            "UPDATE outbox_pending SET status='processed', processed_at=? WHERE id=?",
                            (datetime.utcnow().isoformat(), row_id)
                        )
                        await sqlite_conn.commit()
                        logger.info(f"Processed outbox id={row_id} op={op} collection={collection_name}")

                    except Exception as e:
                        new_retry_count = retry_count + 1
                        new_status = 'failed' if new_retry_count >= MAX_RETRIES else 'pending'
                        await sqlite_conn.execute(
                            "UPDATE outbox_pending SET retry_count=?, status=? WHERE id=?",
                            (new_retry_count, new_status, row_id)
                        )
                        await sqlite_conn.commit()
                        logger.error(f"Failed outbox id={row_id} retry={new_retry_count}: {e}")

                await asyncio.sleep(POLL_INTERVAL_S)

            except Exception as e:
                logger.error(f"Outbox worker error: {e}")
                await asyncio.sleep(POLL_INTERVAL_S)

    mongo_client.close()
    logger.info("Outbox worker shutdown complete")


if __name__ == '__main__':
    asyncio.run(process_outbox())