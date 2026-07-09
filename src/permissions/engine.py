"""
engine.py — Evaluates access requests against the role→permission policy.

Deny-by-default: a request is allowed only if the actor's role has been granted
the exact (action, resource_type) capability. Value-level scope checks (e.g.
recipient-domain allowlisting) live in the guardrail layer, where the concrete
recipient is available — the permission engine answers the coarser "may this
role do this at all?" question.
"""
from __future__ import annotations

import logging

from src.permissions.policy import permissions_for
from src.permissions.types import AccessRequest, PolicyDecision

logger = logging.getLogger("email_assistant.permissions.engine")


class PermissionEngine:
    """Stateless evaluator of AccessRequests."""

    def evaluate(self, request: AccessRequest) -> PolicyDecision:
        granted = permissions_for(request.role)
        if request.permission in granted:
            return PolicyDecision(True, f"{request.role.value} may {request.permission}")

        reason = f"{request.role.value} is not permitted to {request.permission}"
        logger.warning(
            "Permission denied: actor=%s role=%s permission=%s scope=%s",
            request.actor or "?", request.role.value, request.permission, request.resource_scope,
        )
        return PolicyDecision(False, reason)


# Singleton
permission_engine = PermissionEngine()
