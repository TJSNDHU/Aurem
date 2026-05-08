"""SHIM — migrated to `shared.auth.rbac`. Explicit re-exports below."""
from shared.auth.rbac import (
    AgentRole,
    Permission,
    check_permission,
    scope_agent_to_tenant,
    clear_agent_scope,
    get_agent_tenant_scope,
    verify_tenant_access,
    get_permissions_for_role,
    get_rbac_matrix,
)

__all__ = [
    "AgentRole",
    "Permission",
    "check_permission",
    "scope_agent_to_tenant",
    "clear_agent_scope",
    "get_agent_tenant_scope",
    "verify_tenant_access",
    "get_permissions_for_role",
    "get_rbac_matrix",
]
