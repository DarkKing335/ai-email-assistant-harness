"""
audit_step.py — Record the workflow outcome in the audit log.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.workflow.steps.base_step import BaseWorkflowStep
from src.config.constants import AuditAction
from src.audit.logger import audit_logger

if TYPE_CHECKING:
    from src.models.workflow_context import WorkflowContext

logger = logging.getLogger("email_assistant.workflow.steps.audit")

class AuditStep(BaseWorkflowStep):
    """Ghi log quyết toán cuối cùng cho workflow."""

    @property
    def name(self) -> str:
        return "audit_step"

    async def execute(self, ctx: "WorkflowContext") -> "WorkflowContext":
        # Orchestrator sẽ báo lỗi bằng cách ném nội dung lỗi vào ctx.metadata["error"]
        error = ctx.metadata.get("error")
        outcome = "FAILURE" if error else "SUCCESS"

        approval = ctx.metadata.get("approval_record")
        approval_id = approval.approval_id if approval else None
        reviewer = approval.reviewer if approval else "system"
        draft_id = ctx.draft.draft_id if ctx.draft else None
        history = ctx.metadata.get("history", [])

        await audit_logger.log(
            action=AuditAction.EMAIL_SENT if outcome == "SUCCESS" else AuditAction.WORKFLOW_ERROR,
            actor=reviewer,
            resource_type="workflow",
            resource_id=ctx.workflow_id,
            workflow_id=ctx.workflow_id,
            outcome=outcome,
            detail=error,
            metadata={
                "draft_id": draft_id,
                "approval_id": approval_id,
                "state_history": [s.value for s in history if hasattr(s, 'value')],
            },
        )
        logger.info("AuditStep: workflow %s recorded. outcome=%s", ctx.workflow_id, outcome)
        return ctx