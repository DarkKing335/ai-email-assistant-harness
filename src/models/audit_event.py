"""
audit_event.py — Domain model for an immutable audit log entry.

Inspired by deliberate's LedgerEntry model which uses content-hash chaining
to create a tamper-evident audit trail. Simplified here to a flat dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from src.config.constants import AuditAction


@dataclass
class AuditEvent:
    """A single, immutable audit log event.

    Every action in the system — tool calls, approvals, sends — must
    produce one AuditEvent. This provides a complete, queryable history.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: AuditAction = AuditAction.WORKFLOW_ERROR
    actor: str = "system"                    # user email, agent name, or "system"
    resource_type: str = ""                  # "draft", "email", "workflow"
    resource_id: str = ""
    workflow_id: str = ""
    outcome: str = "SUCCESS"                 # "SUCCESS" | "FAILURE"
    detail: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action": self.action.value,
            "actor": self.actor,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "workflow_id": self.workflow_id,
            "outcome": self.outcome,
            "detail": self.detail,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
