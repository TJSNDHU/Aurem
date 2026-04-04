"""
Multi-Tenancy Service
Ensures data isolation between tenants/companies
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from functools import wraps
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class TenantContext:
    """
    Thread-local tenant context
    Stores current tenant_id for request scope
    """
    
    _tenant_id: Optional[str] = None
    
    @classmethod
    def set_tenant(cls, tenant_id: str):
        """Set current tenant ID"""
        cls._tenant_id = tenant_id
    
    @classmethod
    def get_tenant(cls) -> Optional[str]:
        """Get current tenant ID"""
        return cls._tenant_id
    
    @classmethod
    def clear_tenant(cls):
        """Clear tenant context"""
        cls._tenant_id = None
    
    @classmethod
    def require_tenant(cls) -> str:
        """
        Get tenant ID or raise error
        Use this in services that MUST have tenant context
        """
        if not cls._tenant_id:
            raise ValueError("No tenant context set. Multi-tenancy violation!")
        return cls._tenant_id


class MultiTenancyService:
    """
    Multi-tenancy management service
    
    Responsibilities:
    - Tenant creation & management
    - Data isolation enforcement
    - Tenant metadata
    """
    
    def __init__(self, db):
        self.db = db
        logger.info("[MultiTenancy] Service initialized")
    
    async def create_tenant(
        self,
        tenant_id: str,
        company_name: str,
        plan_tier: str = "free",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a new tenant (company)
        
        Args:
            tenant_id: Unique tenant identifier (e.g., "company_acme")
            company_name: Company name
            plan_tier: Subscription tier (free, starter, pro, enterprise)
            metadata: Additional tenant info
        
        Returns:
            Tenant record
        """
        try:
            # Check if tenant exists
            existing = await self.db.tenants.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            
            if existing:
                raise ValueError(f"Tenant already exists: {tenant_id}")
            
            tenant = {
                "tenant_id": tenant_id,
                "company_name": company_name,
                "plan_tier": plan_tier,
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "metadata": metadata or {},
                "settings": {
                    "data_isolation_enabled": True,
                    "encryption_enabled": True
                }
            }
            
            await self.db.tenants.insert_one(tenant)
            
            logger.info(f"[MultiTenancy] Created tenant: {tenant_id} ({company_name})")
            
            return tenant
        
        except Exception as e:
            logger.error(f"[MultiTenancy] Error creating tenant: {e}")
            raise
    
    async def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        try:
            tenant = await self.db.tenants.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            
            return tenant
        
        except Exception as e:
            logger.error(f"[MultiTenancy] Error getting tenant: {e}")
            return None
    
    async def list_tenants(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all tenants"""
        try:
            tenants = await self.db.tenants.find(
                {},
                {"_id": 0}
            ).limit(limit).to_list(limit)
            
            return tenants
        
        except Exception as e:
            logger.error(f"[MultiTenancy] Error listing tenants: {e}")
            return []
    
    def add_tenant_filter(self, query: Dict, tenant_id: Optional[str] = None) -> Dict:
        """
        Add tenant_id filter to database query
        
        CRITICAL: Call this for EVERY multi-tenant collection query
        
        Args:
            query: Original MongoDB query
            tenant_id: Tenant ID (uses TenantContext if not provided)
        
        Returns:
            Query with tenant_id filter added
        """
        tenant = tenant_id or TenantContext.get_tenant()
        
        if not tenant:
            raise ValueError(
                "MULTI-TENANCY VIOLATION: No tenant_id in query. "
                "This would expose data across tenants!"
            )
        
        # Add tenant_id to query
        query["tenant_id"] = tenant
        
        return query
    
    def add_tenant_id(self, document: Dict, tenant_id: Optional[str] = None) -> Dict:
        """
        Add tenant_id to document before insert
        
        CRITICAL: Call this for EVERY document insert into multi-tenant collections
        
        Args:
            document: Document to insert
            tenant_id: Tenant ID (uses TenantContext if not provided)
        
        Returns:
            Document with tenant_id added
        """
        tenant = tenant_id or TenantContext.get_tenant()
        
        if not tenant:
            raise ValueError(
                "MULTI-TENANCY VIOLATION: No tenant_id for document insert. "
                "This would create orphaned data!"
            )
        
        document["tenant_id"] = tenant
        
        return document


def require_tenant(func):
    """
    Decorator to enforce tenant context
    
    Usage:
        @require_tenant
        async def my_endpoint():
            # This will only execute if tenant_id is set
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        tenant_id = TenantContext.get_tenant()
        
        if not tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Multi-tenancy violation: No tenant context"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper


# Singleton instance
_multi_tenancy_service = None


def get_multi_tenancy_service(db):
    """Get singleton MultiTenancyService instance"""
    global _multi_tenancy_service
    
    if _multi_tenancy_service is None:
        _multi_tenancy_service = MultiTenancyService(db)
    
    return _multi_tenancy_service
