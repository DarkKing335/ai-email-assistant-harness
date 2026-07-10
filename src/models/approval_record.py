"""
approval_record.py — Domain model for the full human approval lifecycle.

Inspired by deliberate's Approval model, simplified to remove DB coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from src.config.constants import ApprovalDecision


@dataclass
class ApprovalRecord:
    """Records a single approval lifecycle for one draft."""

    approval_id: str = field(default_factory=lambda: f"ap_{uuid.uuid4().hex[:16]}")
    draft_id: str = ""
    workflow_id: str = ""

    # Why the human is being asked: guardrail rails that returned REQUIRE_APPROVAL
    # (e.g. "recipient_allowlist: external recipient", "injection_escalation: ...").
    escalations: List[str] = field(default_factory=list)

    # Decision
    decision: Optional[ApprovalDecision] = None
    reviewer: Optional[str] = None       # email or user ID of the reviewer
    comments: Optional[str] = None

    # Timing
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None

    @property
    def is_decided(self) -> bool:
        return self.decision is not None

    @property
    def is_approved(self) -> bool:
        return self.decision == ApprovalDecision.APPROVED

    @property
    def is_pending(self) -> bool:
        return self.decision is None
