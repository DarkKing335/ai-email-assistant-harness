"""
gmail_draft_tool.py — Tool to create or update a Gmail draft.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.permissions.types import Action, Permission, ResourceType
from src.integrations.gmail.draft_manager import DraftManager

logger = logging.getLogger("email_assistant.tools.gmail_draft")


class GmailDraftSchema(BaseModel):
    to: str = Field(..., description="Recipient email address.")
    subject: str = Field(..., description="Email subject line.")
    body: str = Field(..., description="Plain text body of the email.")
    thread_id: Optional[str] = Field(None, description="Thread ID to reply within.")


class GmailDraftTool(BaseTool):
    """Creates a new Gmail draft or updates an existing one.

    The agent calls this tool to materialise a draft in Gmail before it
    enters the approval queue. The draft stays in DRAFT status — it is
    never sent by this tool.
    """
    name = "gmail_create_or_update_draft"
    description = (
        "Create a new email draft in Gmail. "
        "The draft will NOT be sent — it must go through human approval first. "
        "Use this after you have composed the full reply body."
    )
    args_schema = GmailDraftSchema
    required_permission = Permission(Action.DRAFT, ResourceType.DRAFT)

    def __init__(self, manager: Optional[DraftManager] = None) -> None:
        self._manager = manager or DraftManager()

    async def _run(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        gmail_draft_id = self._manager.create_draft(
            to=to,
            subject=subject,
            body=body,
            thread_id=thread_id,
        )

        if gmail_draft_id:
            logger.info("Draft created in Gmail: %s", gmail_draft_id)
            return {
                "status": "created",
                "gmail_draft_id": gmail_draft_id,
                "to": to,
                "subject": subject,
                "preview": body[:200],
            }

        return {"status": "error", "message": "Failed to create draft in Gmail"}
