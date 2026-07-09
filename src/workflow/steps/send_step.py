"""
send_step.py — Send the approved email via Gmail.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.workflow.steps.base_step import BaseWorkflowStep
from src.tools.registry import tool_registry

if TYPE_CHECKING:
    from src.models.workflow_context import WorkflowContext

logger = logging.getLogger("email_assistant.workflow.steps.send")

class SendStep(BaseWorkflowStep):
    """Gửi email bản nháp nếu đã được Approve."""

    @property
    def name(self) -> str:
        return "send_step"

    async def execute(self, ctx: "WorkflowContext") -> "WorkflowContext":
        draft = ctx.draft
        approval = ctx.metadata.get("approval_record")

        if draft is None or approval is None:
            raise ValueError("SendStep: missing draft or approval in context")
        if not draft.gmail_draft_id:
            raise ValueError("SendStep: draft has no gmail_draft_id — was it created in Gmail?")
        if not approval.is_approved:
            raise ValueError("SendStep: draft was not approved")

        result = await tool_registry.call(
            "gmail_send_draft",
            gmail_draft_id=draft.gmail_draft_id,
            approval_id=approval.approval_id,
        )

        if result.get("status") != "sent":
            raise RuntimeError(f"SendStep: Gmail send failed: {result}")

        logger.info("SendStep: email sent. draft_id=%s", draft.draft_id)
        return ctx