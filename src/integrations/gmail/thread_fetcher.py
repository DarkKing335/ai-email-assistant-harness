"""
thread_fetcher.py — Fetch and parse full Gmail threads.
draft_manager.py — Create and manage Gmail drafts.
sender.py — Send approved Gmail drafts.
"""
# thread_fetcher.py
from __future__ import annotations
import logging
from typing import List, Optional
from src.integrations.gmail.client import GmailClient
from src.integrations.gmail.message_parser import parse_thread
from src.models.email import EmailThread

logger = logging.getLogger("email_assistant.gmail.thread_fetcher")


class ThreadFetcher:
    """Fetches and parses email threads from Gmail."""

    def __init__(self, client: Optional[GmailClient] = None) -> None:
        self._client = client or GmailClient()

    def fetch_unread(self, max_results: int = 10) -> List[EmailThread]:
        """Fetch unread threads."""
        raw_threads = self._client.list_threads(query="is:unread", max_results=max_results)
        threads = []
        for t in raw_threads:
            raw = self._client.get_thread(t["id"])
            if raw:
                thread = parse_thread(raw)
                threads.append(thread)
        return threads

    def fetch_thread(self, thread_id: str) -> Optional[EmailThread]:
        """Fetch a specific thread by ID."""
        raw = self._client.get_thread(thread_id)
        if raw is None:
            return None
        return parse_thread(raw)
