"""
sender.py — Send an approved Gmail draft.

The Sender is intentionally kept separate from DraftManager.
Only the workflow orchestrator (post-approval) should instantiate Sender,
enforcing the HITL gate at the architectural level.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.integrations.gmail.client import GmailClient

logger = logging.getLogger("email_assistant.gmail.sender")


class GmailSender:
    """Sends approved draft emails via the Gmail API."""

    def __init__(self, client: Optional[GmailClient] = None) -> None:
        self._client = client or GmailClient()

    def send(self, gmail_draft_id: str) -> bool:
        """Send a Gmail draft by its ID.

        Args:
            gmail_draft_id: The Gmail API draft ID (not internal draft_id).

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        result = self._client.send_draft(gmail_draft_id)
        if result:
            logger.info("Email sent: gmail_draft_id=%s message_id=%s", gmail_draft_id, result.get("id"))
            return True
        logger.error("Failed to send draft: gmail_draft_id=%s", gmail_draft_id)
        return False
