"""
audit_vm.py — AuditEvent → audit-log row.

The audit view is strictly read-only. There is no edit, no delete, no clear.
Append-only is the guarantee the compliance story rests on.

Caveat (BLOCKER-6): ``AuditLogger.read_recent`` reconstructs each AuditEvent
without passing ``timestamp=``, so the dataclass default fires and every event
carries the time it was *read*, not the time it occurred. The persisted JSONL
line has the correct value. Until that is fixed, timestamps shown here are
wrong, and ``timestamps_reliable()`` says so.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.models.audit_event import AuditEvent

TIMESTAMP_WARNING = (
    "Audit timestamps show when the log was read, not when the event occurred: "
    "AuditLogger.read_recent() drops the persisted timestamp (BLOCKER-6)."
)


def timestamps_reliable() -> bool:
    """False while BLOCKER-6 stands. Views should surface TIMESTAMP_WARNING."""
    return False


def audit_to_dict(event: AuditEvent) -> dict[str, Any]:
    resource = (
        f"{event.resource_type}/{event.resource_id}"
        if event.resource_type
        else event.resource_id
    )
    return {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "action": event.action.value,
        "actor": event.actor,
        "resource": resource,
        "workflow_id": event.workflow_id,
        "outcome": event.outcome,
        "ok": event.outcome == "SUCCESS",
        "detail": event.detail or "",
    }


def audit_rows(events: Sequence[AuditEvent]) -> list[dict[str, Any]]:
    """Newest first — ``read_recent`` already reverses."""
    return [audit_to_dict(event) for event in events]
