"""
approval_step.py — Human-in-the-loop approval gate.

This step is the core Harness Engineering concept: the workflow CANNOT
proceed to send without an explicit human decision.

For the CLI flow, the step writes the draft to an in-memory queue and
blocks until the user runs `email approve <draft_id>` or `email reject <draft_id>`.

In a production deployment, this would publish to a webhook/notification
channel (Slack, email) and poll for an async response.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.workflow.engine.orchestrator import WorkflowContext

from src.approval.gate import approval_gate
from src.models.approval_record import ApprovalRecord
from src.config.constants import ApprovalDecision
from src.config.settings import settings

logger = logging.getLogger("email_assistant.workflow.steps.approval")


class ApprovalStep:
    """Presents the draft for human review and waits for a decision."""

    async def run(self, ctx: "WorkflowContext") -> "WorkflowContext":
        if ctx.draft is None:
            raise ValueError("ApprovalStep: no draft in context")

        draft = ctx.draft
        approval = ApprovalRecord(
            draft_id=draft.draft_id,
            workflow_id=ctx.workflow_id,
            timeout_at=datetime.utcnow() + timedelta(seconds=settings.approval_timeout_seconds),
        )

        logger.info(
            "ApprovalStep: draft %s is AWAITING_APPROVAL. "
            "Run: email approve %s  OR  email reject %s",
            draft.draft_id, draft.draft_id, draft.draft_id,
        )

        # Register with the global gate and wait for a decision
        ctx.approval = await approval_gate.wait_for_decision(approval, draft)
        return ctx
