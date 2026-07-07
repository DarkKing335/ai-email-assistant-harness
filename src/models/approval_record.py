"""
approval_record.py — Domain model for the full human approval lifecycle.

Inspired by deliberate's Approval model, simplified to remove DB coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.config.constants import ApprovalDecision


@dataclass
class ApprovalRecord:
    """Records a single approval lifecycle for one draft."""

    approval_id: str = field(default_factory=lambda: f"ap_{uuid.uuid4().hex[:16]}")
    draft_id: str = ""
    workflow_id: str = ""

    # Decision
    decision: Optional[ApprovalDecision] = None
    reviewer: Optional[str] = None       # email or user ID of the reviewer
    comments: Optional[str] = None

    # Timing
    requested_at: datetime = field(default_factory=datetime.utcnow)
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
