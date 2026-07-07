"""
gmail_reader_tool.py — Tool to read email threads from Gmail.
gmail_draft_tool.py  — Tool to create/update Gmail drafts.
gmail_send_tool.py   — Tool to send an approved Gmail draft.
"""
# gmail_reader_tool.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.integrations.gmail.client import GmailClient
from src.integrations.gmail.message_parser import parse_thread

logger = logging.getLogger("email_assistant.tools.gmail_reader")


class GmailReaderSchema(BaseModel):
    thread_id: str = Field(..., description="Gmail thread ID to read.")
    max_messages: int = Field(10, ge=1, le=50, description="Max messages to return.")


class GmailReaderTool(BaseTool):
    """Fetches a full email thread from Gmail by thread ID.

    Returns a structured summary of all messages in the thread.
    Used by the agent to understand context before drafting a reply.
    """
    name = "gmail_read_thread"
    description = (
        "Fetch a full email thread from Gmail. "
        "Returns all messages with sender, date, subject, and body. "
        "Use this before drafting a reply to understand the conversation context."
    )
    args_schema = GmailReaderSchema

    def __init__(self, client: Optional[GmailClient] = None) -> None:
        self._client = client or GmailClient()

    async def _run(self, thread_id: str, max_messages: int = 10) -> Dict[str, Any]:
        raw = self._client.get_thread(thread_id)
        if raw is None:
            return {"error": f"Thread {thread_id} not found", "messages": []}

        thread = parse_thread(raw)
        messages = thread.messages[:max_messages]

        return {
            "thread_id": thread_id,
            "message_count": len(messages),
            "messages": [
                {
                    "message_id": m.message_id,
                    "from": m.sender,
                    "subject": m.subject,
                    "date": m.received_at.isoformat() if m.received_at else "",
                    "body": m.body_plain[:2000],  # cap to prevent context overflow
                }
                for m in messages
            ],
            "full_thread_text": thread.full_text[:4000],
        }
