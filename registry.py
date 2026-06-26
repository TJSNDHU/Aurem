import asyncio
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import OperationFailure
import logging

logger = logging.getLogger(__name__)

INDEX_LOCK = asyncio.Lock()

async def initialize_indexes(collection: AsyncIOMotorCollection) -> None:
    """
    Idempotently create TTL indexes with race condition protection.
    
    Args:
        collection: MongoDB collection to initialize
    """
    try:
        async with INDEX_LOCK:
            existing_indexes = await collection.index_information()
            if "expires_at_1" not in existing_indexes:
                await collection.create_index(
                    [("expires_at", 1)],
                    name="expires_at_1",
                    expireAfterSeconds=0,
                    background=True
                )
                logger.info(f"Created TTL index for {collection.name}")
    except OperationFailure as e:
        if "already exists" not in str(e):
            logger.error(f"Failed to create index for {collection.name}: {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error creating indexes: {str(e)}")
        raise
