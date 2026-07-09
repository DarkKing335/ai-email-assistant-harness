"""
ingest_step.py — Fetch and parse the Gmail thread into the workflow context.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.workflow.steps.base_step import BaseWorkflowStep

if TYPE_CHECKING:
    from src.models.workflow_context import WorkflowContext

logger = logging.getLogger("email_assistant.workflow.steps.ingest")

class IngestStep(BaseWorkflowStep):
    """Lấy và parse thread email từ Gmail vào workflow context."""

    def __init__(self) -> None:
        from src.integrations.gmail.thread_fetcher import ThreadFetcher
        self._fetcher = ThreadFetcher()

    @property
    def name(self) -> str:
        return "ingest_step"

    async def execute(self, ctx: "WorkflowContext") -> "WorkflowContext":
        logger.info("IngestStep: fetching thread %s", ctx.thread_id)
        
        thread = self._fetcher.fetch_thread(ctx.thread_id)
        if thread is None or not thread.messages:
            raise ValueError(f"Could not fetch thread: {ctx.thread_id}")
            
        ctx.email_thread = thread
        logger.info(
            "IngestStep: ingested thread %s (%d messages)",
            ctx.thread_id, len(thread.messages),
        )
        return ctx