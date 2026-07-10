"""
context.py — The ambient actor principal for the current call.

Tools do not receive an actor argument (the agent calls them by name with only
domain kwargs). We thread the *acting role* through a contextvar instead, so a
tool call can be authorized without changing every call signature.

Default is SYSTEM: the harness itself is trusted, because it is already gated
by the workflow, approval, and guardrail layers. Code that runs *agent-authored*
logic should narrow the principal with `acting_as(UserRole.OPERATOR)` so that an
agent physically cannot invoke a capability (e.g. SEND) it was never granted —
defense in depth, even though the send tool is also excluded from the agent's
tool list.

Usage:
    with acting_as(UserRole.OPERATOR):
        await draft_step.run(ctx)   # anything here runs with operator rights
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

from src.config.constants import UserRole

_current_role: contextvars.ContextVar[UserRole] = contextvars.ContextVar(
    "current_role", default=UserRole.SYSTEM
)
_current_actor: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_actor", default="system"
)


def current_role() -> UserRole:
    return _current_role.get()


def current_actor() -> str:
    return _current_actor.get()


@contextmanager
def acting_as(role: UserRole, actor: str = "") -> Iterator[None]:
    """Temporarily narrow the acting principal for everything in the block."""
    role_token = _current_role.set(role)
    actor_token = _current_actor.set(actor or role.value.lower())
    try:
        yield
    finally:
        _current_role.reset(role_token)
        _current_actor.reset(actor_token)
