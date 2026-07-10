"""
gate.py — Human-in-the-loop approval gate.

Maintains an in-memory registry of pending approval requests.
The CLI `approve` and `reject` commands resolve these futures.

Architecture note: asyncio.Future is used so the workflow coroutine
can suspend (await) while the approval queue is visible to CLI commands
running in the same event loop.

Inspired by:
  - deliberate: Approval model with explicit state + escalation
  - agents-from-scratch: LangGraph interrupt() pattern (reimplemented without LangGraph)
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from src.models.draft import Draft

from src.models.approval_record import ApprovalRecord
from src.config.constants import ApprovalDecision

logger = logging.getLogger("email_assistant.approval.gate")


class ApprovalGate:
    """Manages pending approval futures for in-flight workflows."""

    def __init__(self) -> None:
        # Maps draft_id → (ApprovalRecord, Draft, asyncio.Future)
        self._pending: Dict[str, tuple[ApprovalRecord, "Draft", asyncio.Future]] = {}

    async def wait_for_decision(
        self, approval: ApprovalRecord, draft: "Draft"
    ) -> ApprovalRecord:
        """Register a pending approval and suspend until a decision is made.

        The coroutine resumes when approve() or reject() is called with
        the matching draft_id.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[draft.draft_id] = (approval, draft, future)

        logger.info(
            "Approval gate: draft %s registered. "
            "Run 'email approve %s' or 'email reject %s'",
            draft.draft_id, draft.draft_id, draft.draft_id,
        )

        try:
            # Suspend here — the CLI commands will resolve this future
            result: ApprovalRecord = await future
        finally:
            self._pending.pop(draft.draft_id, None)

        return result

    def approve(self, draft_id: str, reviewer: str, comments: str = "") -> bool:
        """Approve a pending draft. Called by CLI `email approve` command."""
        entry = self._pending.get(draft_id)
        if entry is None:
            return False
        approval, _, future = entry
        from datetime import datetime, timezone
        approval.decision = ApprovalDecision.APPROVED
        approval.reviewer = reviewer
        approval.comments = comments
        approval.decided_at = datetime.now(timezone.utc)
        if not future.done():
            future.set_result(approval)
        logger.info("Approval gate: draft %s APPROVED by %s", draft_id, reviewer)
        return True

    def reject(self, draft_id: str, reviewer: str, reason: str = "") -> bool:
        """Reject a pending draft. Called by CLI `email reject` command."""
        entry = self._pending.get(draft_id)
        if entry is None:
            return False
        approval, _, future = entry
        from datetime import datetime, timezone
        approval.decision = ApprovalDecision.REJECTED
        approval.reviewer = reviewer
        approval.comments = reason
        approval.decided_at = datetime.now(timezone.utc)
        if not future.done():
            future.set_result(approval)
        logger.info("Approval gate: draft %s REJECTED by %s", draft_id, reviewer)
        return True

    def list_pending(self) -> List[Dict]:
        """Return all pending approvals for the CLI `review` command."""
        result = []
        for draft_id, (approval, draft, _) in self._pending.items():
            result.append({
                "draft_id": draft_id,
                "to": draft.to,
                "subject": draft.subject,
                "preview": draft.preview,
                "requested_at": approval.requested_at.isoformat(),
                "timeout_at": approval.timeout_at.isoformat() if approval.timeout_at else None,
                # Why the reviewer is being asked (guardrail escalations + PII flag).
                "escalations": list(approval.escalations),
                "pii_detected": draft.pii_detected,
            })
        return result

    @property
    def pending_count(self) -> int:
        return len(self._pending)


# Singleton — shared between orchestrator and CLI commands
approval_gate = ApprovalGate()
