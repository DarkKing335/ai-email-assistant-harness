"""
message_parser.py — Parse raw Gmail API payloads into domain models.

The Gmail API returns deeply nested JSON with base64-encoded MIME parts.
This module handles all that complexity and returns clean EmailMessage objects.

Parsing logic inspired by agents-from-scratch extract_message_part() function,
reimplemented cleanly with full MIME multipart support.
"""

from __future__ import annotations

import base64
import email.utils
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models.email import EmailMessage, EmailThread

logger = logging.getLogger("email_assistant.gmail.parser")


def parse_message(raw: Dict[str, Any]) -> Optional[EmailMessage]:
    """Parse a raw Gmail message dict into an EmailMessage domain object.

    Args:
        raw: The full Gmail message dict from the API (format="full").

    Returns:
        An EmailMessage, or None if parsing fails.
    """
    try:
        msg_id = raw.get("id", "")
        thread_id = raw.get("threadId", "")
        snippet = raw.get("snippet", "")

        payload = raw.get("payload", {})
        headers = _extract_headers(payload.get("headers", []))

        subject = headers.get("subject", "(No Subject)")
        sender_raw = headers.get("from", "")
        to_raw = headers.get("to", "")
        cc_raw = headers.get("cc", "")
        date_str = headers.get("date", "")

        sender_email = _extract_email_address(sender_raw)
        recipients = _parse_address_list(to_raw)
        cc = _parse_address_list(cc_raw)
        received_at = _parse_date(date_str)

        body_plain, body_html = _extract_body(payload)

        return EmailMessage(
            message_id=msg_id,
            thread_id=thread_id,
            subject=subject,
            sender=sender_raw,
            sender_email=sender_email,
            recipients=recipients,
            cc=cc,
            body_plain=body_plain,
            body_html=body_html,
            received_at=received_at,
            snippet=snippet,
            labels=raw.get("labelIds", []),
        )
    except Exception as e:
        logger.error("Failed to parse message %s: %s", raw.get("id", "?"), e)
        return None


def parse_thread(raw: Dict[str, Any]) -> EmailThread:
    """Parse a raw Gmail thread dict into an EmailThread domain object."""
    thread_id = raw.get("id", "")
    messages = []

    for raw_msg in raw.get("messages", []):
        msg = parse_message(raw_msg)
        if msg:
            messages.append(msg)

    return EmailThread(thread_id=thread_id, messages=messages)


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_headers(headers_list: List[Dict]) -> Dict[str, str]:
    """Convert list of {name, value} dicts to lowercase-keyed dict."""
    return {h["name"].lower(): h["value"] for h in headers_list if "name" in h}


def _extract_email_address(raw: str) -> str:
    """Extract the email address portion from 'Name <email@domain.com>'."""
    _, addr = email.utils.parseaddr(raw)
    return addr or raw


def _parse_address_list(raw: str) -> List[str]:
    """Parse a comma-separated list of email addresses."""
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse an RFC 2822 date string to a datetime object."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _decode_base64(data: str) -> str:
    """Decode a URL-safe base64-encoded string to UTF-8 text."""
    try:
        padded = data + "=" * (4 - len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Base64 decode failed: %s", e)
        return ""


def _extract_body(payload: Dict[str, Any]) -> tuple[str, str]:
    """Recursively extract plain text and HTML body parts from a MIME payload."""
    plain_parts: List[str] = []
    html_parts: List[str] = []
    _walk_parts(payload, plain_parts, html_parts)
    return "\n".join(plain_parts).strip(), "\n".join(html_parts).strip()


def _walk_parts(part: Dict[str, Any], plain: List[str], html: List[str]) -> None:
    """Walk MIME parts recursively, collecting text/plain and text/html content."""
    mime_type = part.get("mimeType", "")

    if mime_type == "text/plain":
        data = part.get("body", {}).get("data", "")
        if data:
            plain.append(_decode_base64(data))

    elif mime_type == "text/html":
        data = part.get("body", {}).get("data", "")
        if data:
            html.append(_decode_base64(data))

    elif mime_type.startswith("multipart/"):
        for sub_part in part.get("parts", []):
            _walk_parts(sub_part, plain, html)

    else:
        # Fallback: try to decode body directly
        data = part.get("body", {}).get("data", "")
        if data and not mime_type.startswith("image/"):
            decoded = _decode_base64(data)
            if decoded:
                plain.append(decoded)
