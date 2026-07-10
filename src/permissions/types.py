"""
types.py — Value types for the permission (tool-authorization) engine.

This is the runtime, RUNTIME-stage guardrail: before a tool executes, the
engine answers "is this actor allowed to perform this action on this
resource?" — the email-domain analog of a coding agent's
`Tool GitHubPermissionRead` check.

Scope is intentionally email-only (per project decision): the resources are
threads, drafts, emails, contacts, and config — not repos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from src.config.constants import UserRole


class Action(str, Enum):
    """What an actor wants to do."""
    READ = "READ"          # Read a thread / message
    DRAFT = "DRAFT"        # Create or update a draft
    SEND = "SEND"          # Send an email
    LOOKUP = "LOOKUP"      # Look up a contact
    SUMMARIZE = "SUMMARIZE"
    CONFIGURE = "CONFIGURE"  # Change system policy/config


class ResourceType(str, Enum):
    """What the action targets."""
    THREAD = "THREAD"
    DRAFT = "DRAFT"
    EMAIL = "EMAIL"
    CONTACT = "CONTACT"
    CONFIG = "CONFIG"


@dataclass(frozen=True)
class Permission:
    """An (action, resource_type) capability. Hashable so it can live in a set."""
    action: Action
    resource_type: ResourceType

    def __str__(self) -> str:
        return f"{self.action.value}:{self.resource_type.value}"


@dataclass
class AccessRequest:
    """A single authorization question posed to the engine."""
    role: UserRole
    permission: Permission
    # Optional value-level context (e.g. {"recipient_domain": "acme.com"}).
    resource_scope: Dict[str, Any] = field(default_factory=dict)
    actor: str = ""  # for audit — the concrete principal, e.g. an email or agent name


@dataclass
class PolicyDecision:
    """The engine's answer."""
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed
