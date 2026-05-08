"""
AUREM Agent RBAC — SOC 2 Least Privilege Access Control
=========================================================
Defines role-based permissions for each pipeline agent.
SCOUT = read-only, CLOSER = write (scoped to tenant_id).
No single agent gets blanket DB access.
"""
import logging
from typing import Dict, Set, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    SCOUT = "scout"
    ARCHITECT = "architect"
    ENVOY = "envoy"
    CLOSER = "closer"
    VERIFIER = "verifier"
    SYSTEM = "system"


class Permission(str, Enum):
    DB_READ = "db_read"
    DB_WRITE = "db_write"
    API_CALL_EXTERNAL = "api_call_external"
    DEPLOY_PATCH = "deploy_patch"
    ACCESS_CREDENTIALS = "access_credentials"
    MODIFY_SETTINGS = "modify_settings"
    TRIGGER_SCAN = "trigger_scan"
    SEND_NOTIFICATION = "send_notification"


# SOC 2 Least Privilege Matrix
AGENT_PERMISSIONS: Dict[AgentRole, Set[Permission]] = {
    AgentRole.SCOUT: {
        Permission.DB_READ,
        Permission.TRIGGER_SCAN,
    },
    AgentRole.ARCHITECT: {
        Permission.DB_READ,
    },
    AgentRole.ENVOY: {
        Permission.DB_READ,
        Permission.API_CALL_EXTERNAL,
    },
    AgentRole.CLOSER: {
        Permission.DB_READ,
        Permission.DB_WRITE,
        Permission.API_CALL_EXTERNAL,
        Permission.DEPLOY_PATCH,
        Permission.SEND_NOTIFICATION,
    },
    AgentRole.VERIFIER: {
        Permission.DB_READ,
        Permission.TRIGGER_SCAN,
    },
    AgentRole.SYSTEM: {
        Permission.DB_READ,
        Permission.DB_WRITE,
        Permission.API_CALL_EXTERNAL,
        Permission.DEPLOY_PATCH,
        Permission.ACCESS_CREDENTIALS,
        Permission.MODIFY_SETTINGS,
        Permission.TRIGGER_SCAN,
        Permission.SEND_NOTIFICATION,
    },
}

# Track which tenant each agent is currently scoped to
_agent_tenant_scope: Dict[str, Optional[str]] = {}


def check_permission(agent_role: str, permission: Permission, tenant_id: Optional[str] = None) -> bool:
    """Check if an agent has a specific permission. SOC 2 enforced."""
    try:
        role = AgentRole(agent_role.lower())
    except ValueError:
        logger.warning(f"[RBAC] Unknown agent role: {agent_role}")
        return False

    allowed = permission in AGENT_PERMISSIONS.get(role, set())
    if not allowed:
        logger.warning(f"[RBAC] DENIED: {agent_role} attempted {permission.value} (tenant={tenant_id})")
    return allowed


def scope_agent_to_tenant(agent_id: str, tenant_id: str):
    """Bind an agent instance to a specific tenant for the duration of a pipeline run."""
    _agent_tenant_scope[agent_id] = tenant_id
    logger.debug(f"[RBAC] Agent {agent_id} scoped to tenant {tenant_id}")


def clear_agent_scope(agent_id: str):
    """Clear tenant scope after pipeline completion."""
    _agent_tenant_scope.pop(agent_id, None)


def get_agent_tenant_scope(agent_id: str) -> Optional[str]:
    """Get the tenant an agent is currently scoped to."""
    return _agent_tenant_scope.get(agent_id)


def verify_tenant_access(agent_id: str, target_tenant_id: str) -> bool:
    """Verify that an agent is authorized to access a specific tenant's data."""
    scoped_tenant = _agent_tenant_scope.get(agent_id)
    if scoped_tenant is None:
        logger.warning(f"[RBAC] Agent {agent_id} has no tenant scope, denying access to {target_tenant_id}")
        return False
    if scoped_tenant != target_tenant_id:
        logger.warning(f"[RBAC] CROSS-TENANT VIOLATION: Agent {agent_id} (scoped={scoped_tenant}) tried to access {target_tenant_id}")
        return False
    return True


def get_permissions_for_role(agent_role: str) -> list:
    """Return list of permissions for a given role."""
    try:
        role = AgentRole(agent_role.lower())
        return [p.value for p in AGENT_PERMISSIONS.get(role, set())]
    except ValueError:
        return []


def get_rbac_matrix() -> Dict:
    """Return the full RBAC matrix for compliance reporting."""
    return {
        role.value: [p.value for p in perms]
        for role, perms in AGENT_PERMISSIONS.items()
    }


print("[STARTUP] Agent RBAC loaded — SOC 2 Least Privilege enforced", flush=True)
