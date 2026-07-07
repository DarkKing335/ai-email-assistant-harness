"""
thread_summarizer_tool.py — Tool to summarise long email threads via LLM.

Prevents context window overflow when threads are very long.
The agent calls this first when the thread_text exceeds ~2000 chars.

Inspired by agents-from-scratch which uses LLM-based summarisation
before the triage/response step.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.infrastructure.llm.llm_router import llm_router

logger = logging.getLogger("email_assistant.tools.summarizer")


class SummarizerSchema(BaseModel):
    thread_text: str = Field(
        ...,
        description="The full concatenated text of the email thread to summarise.",
    )
    max_summary_words: int = Field(
        150,
        ge=50,
        le=500,
        description="Target word count for the summary.",
    )


class ThreadSummarizerTool(BaseTool):
    """Summarises a long email thread into key points and action items.

    Use this when the email thread is longer than 2000 characters to
    prevent exceeding the LLM context window.
    """
    name = "summarize_email_thread"
    description = (
        "Summarise a long email thread into key points and action items. "
        "Call this when the thread text exceeds 2000 characters to reduce context size. "
        "Returns a concise bullet-point summary."
    )
    args_schema = SummarizerSchema

    async def _run(self, thread_text: str, max_summary_words: int = 150) -> Dict[str, Any]:
        llm = llm_router.get_client("summarize")
        system_msg = (
            "You are an expert email summariser. "
            "Extract the key points, questions, and action items from the email thread. "
            f"Be concise — target {max_summary_words} words or fewer."
        )
        prompt = (
            f"Please summarise the following email thread:\n\n"
            f"---\n{thread_text}\n---\n\n"
            "Provide:\n"
            "• Key points discussed\n"
            "• Questions asked\n"
            "• Action items required"
        )
        response = await llm.generate(prompt=prompt, system_message=system_msg)
        logger.info("Thread summarised: %d chars → %d chars", len(thread_text), len(response.content))

        return {
            "summary": response.content,
            "original_length": len(thread_text),
            "summary_length": len(response.content),
            "model_used": response.model,
        }
