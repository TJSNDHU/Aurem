from motor.motor_asyncio import AsyncIOMotorClient
from datetime import timezone
from os import environ as env
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

MONGO_URI = env.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = env.get("MONGO_DB", "aurem")

class TenantScopedDatabase:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self._connected = False
    
    async def connect(self):
        """Ensure connection is established"""
        try:
            await self.client.admin.command('ping')
            self._connected = True
        except Exception as e:
            logger.error(f"MongoDB connection failed: {str(e)}")
            raise
    
    async def get_collection(self, tenant_id: str, name: str) -> AsyncIOMotorClient:
        """Get collection with tenant prefix and ensure TTL indexes"""
        if not self._connected:
            await self.connect()
        
        collection = self.db[f"{tenant_id}_{name}"]
        await registry.initialize_indexes(collection)
        return collection
    
    async def close(self):
        """Clean up connections"""
        if self.client:
            self.client.close()
            self._connected = False

# Singleton instance (import this)
database = TenantScopedDatabase()
