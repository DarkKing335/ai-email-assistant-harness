"""
client.py — Authenticated Gmail API client with retry and error handling.

Wraps the Google API Python client. If credentials are unavailable,
all methods fall back to returning mock data so the rest of the system
can be developed and tested without real Gmail credentials.

Pattern: graceful mock fallback inspired by agents-from-scratch.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.integrations.gmail.auth import get_credentials

logger = logging.getLogger("email_assistant.gmail.client")

_API_AVAILABLE = False
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _API_AVAILABLE = True
except ImportError:
    logger.warning("google-api-python-client not installed — Gmail in mock mode")


class GmailClient:
    """Authenticated Gmail API client.

    Usage:
        client = GmailClient()
        threads = client.list_threads(query="is:unread", max_results=10)
    """

    def __init__(self) -> None:
        self._service = None
        self._mock_mode = False
        self._init_service()

    def _init_service(self) -> None:
        if not _API_AVAILABLE:
            logger.info("GmailClient running in mock mode (API library not installed)")
            self._mock_mode = True
            return

        creds = get_credentials()
        if creds is None:
            logger.info("GmailClient running in mock mode (no credentials)")
            self._mock_mode = True
            return

        try:
            self._service = build("gmail", "v1", credentials=creds)
            logger.info("GmailClient connected to Gmail API")
        except Exception as e:
            logger.error("Failed to build Gmail service: %s", e)
            self._mock_mode = True

    @property
    def is_mock(self) -> bool:
        return self._mock_mode

    def verify(self) -> Dict[str, Any]:
        """Verify the connection and return the authorised email address."""
        if self._mock_mode:
            return {"email": "mock@example.com", "status": "mock"}
        try:
            profile = self._service.users().getProfile(userId="me").execute()
            return {"email": profile.get("emailAddress"), "status": "ok"}
        except Exception as e:
            return {"email": None, "status": f"error: {e}"}

    def list_threads(self, query: str = "is:unread", max_results: int = 10) -> List[Dict]:
        """List Gmail thread summaries matching a query."""
        if self._mock_mode:
            return [
                {"id": "thread_mock_001", "snippet": "Hello, I wanted to follow up on..."},
                {"id": "thread_mock_002", "snippet": "Can you please confirm the timeline..."},
            ]
        try:
            result = self._service.users().threads().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            return result.get("threads", [])
        except Exception as e:
            logger.error("Failed to list threads: %s", e)
            return []

    def get_thread(self, thread_id: str) -> Optional[Dict]:
        """Fetch a complete thread by ID."""
        if self._mock_mode:
            return {
                "id": thread_id,
                "messages": [
                    {
                        "id": "msg_mock_001",
                        "threadId": thread_id,
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Project Timeline Question"},
                                {"name": "From", "value": "Client Name <client@example.com>"},
                                {"name": "To", "value": "me@company.com"},
                                {"name": "Date", "value": "Mon, 7 Jul 2026 08:00:00 +0000"},
                            ],
                            "body": {
                                "data": "SGVsbG8sIEkgd2FudGVkIHRvIGZvbGxvdyB1cCBvbiB0aGUgcHJvamVjdCB0aW1lbGluZS4gQ2FuIHlvdSBwbGVhc2UgY29uZmlybSB3aGVuIHdlIGNhbiBleHBlY3QgdGhlIGRlbGl2ZXJhYmxlcz8="
                            },
                        },
                        "snippet": "Hello, I wanted to follow up on the project timeline.",
                    }
                ],
            }
        try:
            return self._service.users().threads().get(
                userId="me", id=thread_id, format="full"
            ).execute()
        except Exception as e:
            logger.error("Failed to get thread %s: %s", thread_id, e)
            return None

    def create_draft(self, raw_message: str) -> Optional[Dict]:
        """Create a Gmail draft from a base64-encoded RFC 2822 message."""
        if self._mock_mode:
            return {"id": "draft_mock_001", "message": {"id": "msg_mock_draft_001"}}
        try:
            return self._service.users().drafts().create(
                userId="me", body={"message": {"raw": raw_message}}
            ).execute()
        except Exception as e:
            logger.error("Failed to create draft: %s", e)
            return None

    def send_draft(self, draft_id: str) -> Optional[Dict]:
        """Send an existing draft by ID."""
        if self._mock_mode:
            logger.info("[MOCK] Sending draft %s", draft_id)
            return {"id": "msg_sent_mock_001", "labelIds": ["SENT"]}
        try:
            return self._service.users().drafts().send(
                userId="me", body={"id": draft_id}
            ).execute()
        except Exception as e:
            logger.error("Failed to send draft %s: %s", draft_id, e)
            return None

    def mark_as_read(self, message_id: str) -> bool:
        """Remove UNREAD label from a message."""
        if self._mock_mode:
            return True
        try:
            self._service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
            return True
        except Exception as e:
            logger.error("Failed to mark message %s as read: %s", message_id, e)
            return False
