"""
approval_step.py — Human-in-the-loop approval gate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.workflow.steps.base_step import BaseWorkflowStep
from src.approval.gate import approval_gate
from src.audit.logger import audit_logger
from src.models.approval_record import ApprovalRecord
from src.config.constants import ApprovalDecision, AuditAction
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
        escalations = list(ctx.metadata.get("guardrail_escalations", []))
        approval = ApprovalRecord(
            draft_id=draft.draft_id,
            workflow_id=ctx.workflow_id,
            escalations=escalations,
            timeout_at=datetime.utcnow() + timedelta(seconds=settings.approval_timeout_seconds),
        )

        logger.info(
            "ApprovalStep: draft %s is AWAITING_APPROVAL%s. "
            "Run: email approve %s  OR  email reject %s",
            draft.draft_id,
            f" ({len(escalations)} guardrail flag(s))" if escalations else "",
            draft.draft_id, draft.draft_id,
        )

        # Record why approval is being requested (surfaces the guardrail reasons
        # in the audit trail alongside the pipeline's GUARDRAIL_ESCALATED events).
        await audit_logger.log(
            action=AuditAction.APPROVAL_REQUESTED,
            actor="system",
            resource_type="draft",
            resource_id=draft.draft_id,
            workflow_id=ctx.workflow_id,
            detail="; ".join(escalations) if escalations else "no guardrail flags",
            metadata={"escalations": escalations},
        )

        # Chờ người duyệt
        decision_record = await approval_gate.wait_for_decision(approval, draft)
        
        # Cập nhật ID và đối tượng vào Context
        ctx.approval_record_id = decision_record.approval_id
        ctx.metadata["approval_record"] = decision_record
        
        return ctx