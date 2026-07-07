"""
audit_step.py — Record the workflow outcome in the audit log.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.workflow.engine.orchestrator import WorkflowContext

from src.config.constants import AuditAction, WorkflowStatus
from src.audit.logger import audit_logger

logger = logging.getLogger("email_assistant.workflow.steps.audit")


class AuditStep:
    """Writes a final audit record for the completed workflow."""

    async def run(self, ctx: "WorkflowContext", history: List[WorkflowStatus]) -> None:
        outcome = "SUCCESS"
        if ctx.error:
            outcome = "FAILURE"

        approval_id = ctx.approval.approval_id if ctx.approval else None
        draft_id = ctx.draft.draft_id if ctx.draft else None

        await audit_logger.log(
            action=AuditAction.EMAIL_SENT if outcome == "SUCCESS" else AuditAction.WORKFLOW_ERROR,
            actor=ctx.approval.reviewer if ctx.approval else "system",
            resource_type="workflow",
            resource_id=ctx.workflow_id,
            workflow_id=ctx.workflow_id,
            outcome=outcome,
            detail=ctx.error,
            metadata={
                "draft_id": draft_id,
                "approval_id": approval_id,
                "state_history": [s.value for s in history],
            },
        )
        logger.info("AuditStep: workflow %s recorded. outcome=%s", ctx.workflow_id, outcome)
