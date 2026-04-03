"""
AUREM Security - Row-Level Security
Company: Polaris Built Inc.

Ensures users can only access their own data.
Super-admin can bypass for support.

Every AUREM collection query is filtered by platform_user_id.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Collections that require RLS
RLS_COLLECTIONS = [
    "aurem_missions",
    "aurem_prospects",
    "aurem_outreach",
    "aurem_analytics",
]

# Super-admin user IDs (can bypass RLS)
SUPER_ADMIN_IDS = set()

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database


def add_super_admin(user_id: str):
    """Add a user to super-admin list"""
    SUPER_ADMIN_IDS.add(user_id)
    logger.info(f"[AUREM RLS] Added super-admin: {user_id}")


def is_super_admin(user_id: str) -> bool:
    """Check if user is super-admin"""
    return user_id in SUPER_ADMIN_IDS


def add_user_filter(query: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Add platform_user_id filter to a MongoDB query.
    Super-admins bypass this filter.
    """
    if is_super_admin(user_id):
        logger.debug(f"[AUREM RLS] Super-admin {user_id} bypassing RLS")
        return query
    
    # Create new query with user filter
    filtered_query = query.copy()
    filtered_query["platform_user_id"] = user_id
    return filtered_query


def add_user_to_document(doc: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Add platform_user_id to a document before insert"""
    enhanced_doc = doc.copy()
    enhanced_doc["platform_user_id"] = user_id
    return enhanced_doc


async def find_with_rls(
    collection_name: str,
    query: Dict[str, Any],
    user_id: str,
    projection: Dict[str, Any] = None
) -> List[Dict]:
    """Find documents with RLS filter applied"""
    if _db is None:
        return []
    
    collection = _db[collection_name]
    filtered_query = add_user_filter(query, user_id)
    
    # Always exclude _id by default
    if projection is None:
        projection = {"_id": 0}
    elif "_id" not in projection:
        projection["_id"] = 0
    
    cursor = collection.find(filtered_query, projection)
    return await cursor.to_list(length=1000)


async def find_one_with_rls(
    collection_name: str,
    query: Dict[str, Any],
    user_id: str,
    projection: Dict[str, Any] = None
) -> Optional[Dict]:
    """Find one document with RLS filter applied"""
    if _db is None:
        return None
    
    collection = _db[collection_name]
    filtered_query = add_user_filter(query, user_id)
    
    if projection is None:
        projection = {"_id": 0}
    elif "_id" not in projection:
        projection["_id"] = 0
    
    return await collection.find_one(filtered_query, projection)


async def insert_with_rls(
    collection_name: str,
    document: Dict[str, Any],
    user_id: str
) -> str:
    """Insert document with platform_user_id"""
    if _db is None:
        return ""
    
    collection = _db[collection_name]
    enhanced_doc = add_user_to_document(document, user_id)
    enhanced_doc["created_at"] = datetime.now(timezone.utc)
    
    result = await collection.insert_one(enhanced_doc)
    return str(result.inserted_id)


async def update_with_rls(
    collection_name: str,
    query: Dict[str, Any],
    update: Dict[str, Any],
    user_id: str
) -> int:
    """Update documents with RLS filter applied"""
    if _db is None:
        return 0
    
    collection = _db[collection_name]
    filtered_query = add_user_filter(query, user_id)
    
    result = await collection.update_many(filtered_query, update)
    return result.modified_count


async def delete_with_rls(
    collection_name: str,
    query: Dict[str, Any],
    user_id: str
) -> int:
    """Delete documents with RLS filter applied"""
    if _db is None:
        return 0
    
    collection = _db[collection_name]
    filtered_query = add_user_filter(query, user_id)
    
    result = await collection.delete_many(filtered_query)
    return result.deleted_count


async def count_with_rls(
    collection_name: str,
    query: Dict[str, Any],
    user_id: str
) -> int:
    """Count documents with RLS filter applied"""
    if _db is None:
        return 0
    
    collection = _db[collection_name]
    filtered_query = add_user_filter(query, user_id)
    
    return await collection.count_documents(filtered_query)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA ISOLATION AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

async def audit_data_isolation():
    """
    Audit all RLS collections to find documents without platform_user_id.
    Returns list of collections with orphaned documents.
    """
    if _db is None:
        return {"error": "Database not available"}
    
    orphaned = {}
    
    for collection_name in RLS_COLLECTIONS:
        collection = _db[collection_name]
        count = await collection.count_documents({
            "platform_user_id": {"$exists": False}
        })
        if count > 0:
            orphaned[collection_name] = count
    
    return {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "orphaned_documents": orphaned,
        "collections_checked": RLS_COLLECTIONS,
        "is_clean": len(orphaned) == 0
    }
