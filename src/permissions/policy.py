"""
policy.py — Declarative role → permission grants.

Roles come from src.config.constants.UserRole. The grant table is the single
source of truth for "which role may do what". Keeping it declarative (data,
not code) means an audit of capabilities is a glance at one table.

  OPERATOR — runs the assistant: read threads, draft, look up contacts.
             Notably CANNOT send — that is the whole point of the HITL gate.
  REVIEWER — everything an operator can do, plus SEND (a send only happens
             after a reviewer approves).
  ADMIN    — everything, plus CONFIGURE.
  SYSTEM   — the harness itself; full trust (it is already gated by the
             workflow + approval + guardrail layers).
"""
from __future__ import annotations

from typing import Dict, Set

from src.config.constants import UserRole
from src.permissions.types import Action, Permission, ResourceType

P = Permission  # local alias for a compact table

_READ_THREAD = P(Action.READ, ResourceType.THREAD)
_DRAFT_DRAFT = P(Action.DRAFT, ResourceType.DRAFT)
_LOOKUP_CONTACT = P(Action.LOOKUP, ResourceType.CONTACT)
_SUMMARIZE_THREAD = P(Action.SUMMARIZE, ResourceType.THREAD)
_SEND_EMAIL = P(Action.SEND, ResourceType.EMAIL)
_CONFIGURE = P(Action.CONFIGURE, ResourceType.CONFIG)

_OPERATOR_PERMS: Set[Permission] = {
    _READ_THREAD,
    _DRAFT_DRAFT,
    _LOOKUP_CONTACT,
    _SUMMARIZE_THREAD,
}

_REVIEWER_PERMS: Set[Permission] = _OPERATOR_PERMS | {_SEND_EMAIL}

_ADMIN_PERMS: Set[Permission] = _REVIEWER_PERMS | {_CONFIGURE}

# SYSTEM gets the union of everything defined anywhere.
_ALL_PERMS: Set[Permission] = _ADMIN_PERMS


ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.OPERATOR: _OPERATOR_PERMS,
    UserRole.REVIEWER: _REVIEWER_PERMS,
    UserRole.ADMIN: _ADMIN_PERMS,
    UserRole.SYSTEM: _ALL_PERMS,
}


def permissions_for(role: UserRole) -> Set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())
