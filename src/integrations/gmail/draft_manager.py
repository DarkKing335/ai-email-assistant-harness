"""
draft_manager.py — Create, update, and delete Gmail drafts.
"""
from __future__ import annotations

import base64
import email as email_lib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.integrations.gmail.client import GmailClient

logger = logging.getLogger("email_assistant.gmail.draft_manager")


class DraftManager:
    """Creates and manages Gmail draft messages."""

    def __init__(self, client: Optional[GmailClient] = None) -> None:
        self._client = client or GmailClient()

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a new Gmail draft and return the Gmail draft ID.

        Args:
            to:        Recipient email address.
            subject:   Email subject line.
            body:      Plain text body.
            thread_id: If provided, the draft is added to this thread.

        Returns:
            The Gmail draft ID string, or None on failure.
        """
        raw = self._build_raw_message(to=to, subject=subject, body=body, thread_id=thread_id)
        result = self._client.create_draft(raw)
        if result:
            draft_id = result.get("id")
            logger.info("Draft created: gmail_draft_id=%s", draft_id)
            return draft_id
        return None

    def _build_raw_message(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        """Build a base64-encoded RFC 2822 message string."""
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["Subject"] = subject
        if thread_id:
            msg["References"] = thread_id
            msg["In-Reply-To"] = thread_id

        msg.attach(MIMEText(body, "plain", "utf-8"))
        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
