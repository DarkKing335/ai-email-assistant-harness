"""
email.py — Domain model for an email message.

This is the innermost ring. No infrastructure imports allowed here.
All fields map 1:1 to what the Gmail API returns after parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class EmailMessage:
    """A fully parsed, normalised email message.

    Created by: src/integrations/gmail/message_parser.py
    Consumed by: workflow steps, agents, tools
    """

    # Gmail identifiers
    message_id: str                   # Gmail message ID
    thread_id: str                    # Gmail thread ID

    # Headers
    subject: str
    sender: str                       # "Name <email@domain.com>"
    sender_email: str                 # "email@domain.com" extracted
    recipients: List[str]             # To: header values
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)

    # Body
    body_plain: str = ""
    body_html: str = ""

    # Metadata
    received_at: Optional[datetime] = None
    snippet: str = ""
    labels: List[str] = field(default_factory=list)

    # Internal tracking
    internal_id: Optional[str] = None

    @property
    def display_sender(self) -> str:
        """Return the human-readable sender name or email."""
        name_part = self.sender.split("<")[0].strip().strip('"')
        return name_part if name_part else self.sender_email

    @property
    def short_preview(self) -> str:
        """Return a 120-char preview of the email body."""
        text = self.body_plain or self.snippet
        return text[:120].replace("\n", " ").strip()

    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "recipients": self.recipients,
            "body_plain": self.body_plain,
            "snippet": self.snippet,
            "received_at": self.received_at.isoformat() if self.received_at else None,
        }


@dataclass
class EmailThread:
    """A full thread containing multiple EmailMessage objects."""

    thread_id: str
    messages: List[EmailMessage] = field(default_factory=list)

    @property
    def latest_message(self) -> Optional[EmailMessage]:
        return self.messages[-1] if self.messages else None

    @property
    def full_text(self) -> str:
        """Concatenate all message bodies for LLM context."""
        parts = []
        for msg in self.messages:
            parts.append(
                f"From: {msg.sender}\n"
                f"Subject: {msg.subject}\n"
                f"{msg.body_plain}"
            )
        return "\n\n---\n\n".join(parts)
