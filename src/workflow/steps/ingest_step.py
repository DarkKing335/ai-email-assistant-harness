"""
Workflow Steps — all five pipeline steps in one file for clarity.

Each step is a thin class with a single async run() method.
Steps delegate to services/integrations — they contain NO business logic themselves.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.workflow.engine.orchestrator import WorkflowContext

logger = logging.getLogger("email_assistant.workflow.steps")


# ── Step 1: Ingest ────────────────────────────────────────────────────────────

class IngestStep:
    """Fetch and parse the Gmail thread into the workflow context."""

    def __init__(self) -> None:
        from src.integrations.gmail.thread_fetcher import ThreadFetcher
        self._fetcher = ThreadFetcher()

    async def run(self, thread_id: str) -> "WorkflowContext":
        from src.workflow.engine.orchestrator import WorkflowContext
        ctx = WorkflowContext()
        logger.info("IngestStep: fetching thread %s", thread_id)
        thread = self._fetcher.fetch_thread(thread_id)
        if thread is None or not thread.messages:
            raise ValueError(f"Could not fetch thread: {thread_id}")
        ctx.thread = thread
        logger.info(
            "IngestStep: ingested thread %s (%d messages)",
            thread_id, len(thread.messages),
        )
        return ctx
