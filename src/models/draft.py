"""
draft.py — Domain model for an agent-generated email draft.
approval_record.py — Domain model for the human approval lifecycle.
audit_event.py — Domain model for an immutable audit log entry.
user.py — Domain model for an authenticated system user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


# ── Draft ─────────────────────────────────────────────────────────────────────

@dataclass
class Draft:
    """An agent-generated reply draft awaiting human approval.

    Lifecycle: CREATED → APPROVED or REJECTED → (if APPROVED) SENT
    """
    draft_id: str = field(default_factory=lambda: f"dr_{uuid.uuid4().hex[:16]}")
    email_message_id: str = ""
    thread_id: str = ""

    # Content
    subject: str = ""
    to: str = ""
    body: str = ""

    # Guardrail results
    guardrails_passed: bool = False
    pii_detected: bool = False
    content_flagged: bool = False
    guardrail_notes: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Gmail draft ID (set after creating in Gmail)
    gmail_draft_id: Optional[str] = None

    @property
    def preview(self) -> str:
        return self.body[:200].replace("\n", " ").strip()
