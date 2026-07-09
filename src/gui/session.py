"""
session.py — Who the reviewer is, and what they are allowed to do.

This module exists for one reason that matters more than refactoring
convenience: ``ApprovalRecord.reviewer`` and ``AuditEvent.actor`` are the
accountability record — the answer to "who authorised this email".

``gateway.approve()`` deliberately takes no ``reviewer`` parameter. It asks this
module. If any view could pass an arbitrary reviewer string, the audit trail
would be forgeable from the UI, and the compliance story the project is built on
would be worthless.

``can_approve()`` returns True unconditionally today because ``src/permissions/``
is empty. That is an honest pre-wired socket, not a fake: when RBAC lands, set
``role`` and the check activates. This is different from a role dropdown, which
would tell the user access control exists when it does not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.config.constants import UserRole

logger = logging.getLogger("email_assistant.gui.session")

DEFAULT_REVIEWER = "gui-user"

#: Roles permitted to resolve an approval, once src/permissions/ enforces them.
_APPROVER_ROLES = frozenset({UserRole.REVIEWER, UserRole.ADMIN})


class IdentityError(ValueError):
    """Raised when the reviewer identity is missing or invalid."""


@dataclass
class Session:
    """The identity acting in this GUI process."""

    reviewer: str = DEFAULT_REVIEWER
    #: None means src/permissions/ is not yet implemented — no RBAC to enforce.
    role: Optional[UserRole] = None

    def __post_init__(self) -> None:
        self.reviewer = self._validated(self.reviewer)

    @property
    def permissions_enforced(self) -> bool:
        """True once a role is attached, i.e. once RBAC actually exists."""
        return self.role is not None

    def set_reviewer(self, reviewer: str) -> None:
        """Set the reviewer identity. Raises IdentityError on blank input."""
        self.reviewer = self._validated(reviewer)
        logger.info("GUI reviewer identity set to %s", self.reviewer)

    def can_approve(self) -> bool:
        if self.role is None:
            return True
        return self.role in _APPROVER_ROLES

    def can_reject(self) -> bool:
        if self.role is None:
            return True
        return self.role in _APPROVER_ROLES

    @staticmethod
    def _validated(reviewer: str) -> str:
        cleaned = (reviewer or "").strip()
        if not cleaned:
            raise IdentityError("Reviewer identity must not be blank")
        return cleaned


_session: Optional[Session] = None


def get_session() -> Session:
    """Return the process-wide session, creating a default one on first call.

    This module never reads ``src.config.settings`` — that would make it the
    second importer of settings and weaken the layering rule enforced by
    tests/unit/gui/test_layering.py. The gateway seeds the real reviewer
    identity at startup via ``gateway.bootstrap_session()``.
    """
    global _session
    if _session is None:
        _session = Session()
    return _session


def reset_session(session: Optional[Session] = None) -> None:
    """Replace the process-wide session. For tests and for re-login."""
    global _session
    _session = session
