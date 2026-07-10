"""
queue_vm.py — PendingItem → approval-queue row.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Optional

from src.gui.types import PendingItem
from src.gui.viewmodels.draft_vm import draft_to_dict

BODY_UNAVAILABLE_REASON = (
    "Full draft body is not exposed by ApprovalGate.list_pending() — "
    "only a 200-character preview (BLOCKER-2)."
)
THREAD_UNAVAILABLE_REASON = (
    "The original email thread is not stored by the approval gate (BLOCKER-3)."
)


def pending_to_dict(item: PendingItem) -> dict[str, Any]:
    """Project one queued draft for display.

    ``body`` is None until BLOCKER-2 lands. Views must render the reason rather
    than an empty panel: a reviewer approving on a 200-character preview should
    know that is all they were shown.
    """
    draft = draft_to_dict(item.draft)
    return {
        "draft_id": item.draft_id,
        "to": item.to,
        "subject": item.subject,
        "preview": item.preview,
        "requested_at": item.requested_at,
        "timeout_at": item.timeout_at,
        "body": draft["body"] if draft else None,
        "body_unavailable_reason": None if draft else BODY_UNAVAILABLE_REASON,
        "guardrail_state": draft["guardrail_state"] if draft else None,
        "guardrail_label": draft["guardrail_label"] if draft else None,
        "thread_available": item.thread is not None,
        "thread_text": getattr(item.thread, "full_text", "") if item.thread else None,
        "thread_unavailable_reason": None if item.thread else THREAD_UNAVAILABLE_REASON,
    }


def queue_rows(items: Sequence[PendingItem]) -> list[dict[str, Any]]:
    return [pending_to_dict(item) for item in items]


def is_expired(item: PendingItem, now: Optional[datetime] = None) -> bool:
    """Whether the approval window has elapsed.

    Display only. ``ApprovalGate.wait_for_decision()`` awaits its future with no
    timeout, so an expired draft stays pending forever. Never gate a button on
    this — an expired-looking draft is still approvable, and pretending
    otherwise would strand it.

    ``now`` is injected so this is testable without freezing the clock.
    """
    if item.timeout_at is None:
        return False
    return (now or datetime.utcnow()) > item.timeout_at


def queue_summary(items: Sequence[PendingItem]) -> dict[str, Any]:
    return {
        "count": len(items),
        "has_items": bool(items),
        "empty_message": (
            "No drafts awaiting approval.\n"
            "Pending drafts are in-memory futures — they do not survive a restart."
        ),
    }
