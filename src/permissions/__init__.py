"""
Permission engine — runtime tool authorization (RBAC).

The email-domain analog of a coding agent's per-tool permission checks. Each
tool declares a `required_permission`; BaseTool consults this engine (with the
ambient principal from src.permissions.context) before executing.

Public API:
    from src.permissions import (
        permission_engine, Permission, Action, ResourceType,
        AccessRequest, acting_as, current_role,
    )
"""
from src.permissions.context import acting_as, current_actor, current_role
from src.permissions.engine import PermissionEngine, permission_engine
from src.permissions.policy import ROLE_PERMISSIONS, permissions_for
from src.permissions.types import (
    AccessRequest,
    Action,
    Permission,
    PolicyDecision,
    ResourceType,
)

__all__ = [
    "acting_as",
    "current_actor",
    "current_role",
    "PermissionEngine",
    "permission_engine",
    "ROLE_PERMISSIONS",
    "permissions_for",
    "AccessRequest",
    "Action",
    "Permission",
    "PolicyDecision",
    "ResourceType",
]
