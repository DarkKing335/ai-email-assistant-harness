"""
approval_step.py — Human-in-the-loop approval gate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.workflow.steps.base_step import BaseWorkflowStep
from src.approval.gate import approval_gate
from src.models.approval_record import ApprovalRecord
from src.config.settings import settings

if TYPE_CHECKING:
    from src.models.workflow_context import WorkflowContext

logger = logging.getLogger("email_assistant.workflow.steps.approval")

class ApprovalStep(BaseWorkflowStep):
    """Trình bản nháp cho con người duyệt và treo workflow đợi quyết định."""

    @property
    def name(self) -> str:
        return "approval_step"

    async def execute(self, ctx: "WorkflowContext") -> "WorkflowContext":
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

        # Chờ người duyệt
        decision_record = await approval_gate.wait_for_decision(approval, draft)
        
        # Cập nhật ID và đối tượng vào Context
        ctx.approval_record_id = decision_record.approval_id
        ctx.metadata["approval_record"] = decision_record
        
        return ctx