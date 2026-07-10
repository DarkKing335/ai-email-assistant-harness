"""
gmail_send_tool.py — Tool to send an approved Gmail draft.

This tool has requires_approval=True.
The ToolRegistry.get_agent_tools() method excludes it from the agent's
available tool list, so the LLM agent CANNOT call this directly.
It is only callable by the workflow orchestrator AFTER the approval gate
has recorded an APPROVED decision.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.permissions.types import Action, Permission, ResourceType
from src.integrations.gmail.sender import GmailSender

logger = logging.getLogger("email_assistant.tools.gmail_send")


class GmailSendSchema(BaseModel):
    gmail_draft_id: str = Field(..., description="Gmail API draft ID to send.")
    approval_id: str = Field(..., description="Approval record ID confirming human approval.")


class GmailSendTool(BaseTool):
    """Sends a Gmail draft that has been approved by a human.

    IMPORTANT: This tool is excluded from the agent's tool list.
    It can only be invoked by the orchestrator post-approval.
    requires_approval = True enforces this at the registry level.
    """
    name = "gmail_send_draft"
    description = (
        "Send an email draft that has already been approved by a human reviewer. "
        "Requires a valid approval_id. Never call this without explicit human approval."
    )
    args_schema = GmailSendSchema
    requires_approval = True  # Excluded from agent tool list
    # SEND is granted to REVIEWER/ADMIN/SYSTEM only — an OPERATOR (the role the
    # drafting agent runs under) is denied even if it somehow reaches this tool.
    required_permission = Permission(Action.SEND, ResourceType.EMAIL)

    def __init__(self, sender: Optional[GmailSender] = None) -> None:
        self._sender = sender or GmailSender()

    async def _run(self, gmail_draft_id: str, approval_id: str) -> Dict[str, Any]:
        logger.info(
            "Sending approved draft: gmail_draft_id=%s approval_id=%s",
            gmail_draft_id,
            approval_id,
        )
        success = self._sender.send(gmail_draft_id)
        if success:
            return {
                "status": "sent",
                "gmail_draft_id": gmail_draft_id,
                "approval_id": approval_id,
            }
        return {
            "status": "error",
            "message": f"Failed to send draft {gmail_draft_id}",
        }
