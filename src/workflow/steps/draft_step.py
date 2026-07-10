"""
draft_step.py - Workflow adapter for the email writing agent.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from src.workflow.steps.base_step import BaseWorkflowStep
from src.agents.email_writing_agent import EmailWritingAgent

if TYPE_CHECKING:
    from src.models.workflow_context import WorkflowContext

logger = logging.getLogger("email_assistant.workflow.steps.draft")


class DraftStep(BaseWorkflowStep):
    """Delegates draft generation to the email writing agent."""

    def __init__(self, agent: Optional[EmailWritingAgent] = None) -> None:
        self._agent = agent or EmailWritingAgent()

    @property
    def name(self) -> str:
        return "draft_step"

    async def execute(self, ctx: "WorkflowContext") -> "WorkflowContext":
        if ctx.email_thread is None:
            raise ValueError("DraftStep: no email thread in context")

        ctx.draft = await self._agent.run(ctx.email_thread)
        logger.info("DraftStep: draft generated (%d chars)", len(ctx.draft.body))
        return ctx
