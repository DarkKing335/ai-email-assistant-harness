"""
send_step.py — Send the approved email via Gmail.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.workflow.engine.orchestrator import WorkflowContext

from src.tools.registry import tool_registry

logger = logging.getLogger("email_assistant.workflow.steps.send")


class SendStep:
    """Sends the approved Gmail draft."""

    async def run(self, ctx: "WorkflowContext") -> "WorkflowContext":
        draft = ctx.draft
        approval = ctx.approval

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
