"""
logger.py — Append-only audit logger.

Writes structured audit events as JSONL (one JSON object per line).
JSONL is ideal for audit logs: each line is self-contained, parseable,
and appendable without rewriting the entire file.

Inspired by deliberate's LedgerEntry pattern (tamper-evident chain),
simplified to a flat JSONL file suitable for local + cloud deployment.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.config.constants import AuditAction
from src.config.settings import settings
from src.models.audit_event import AuditEvent

logger = logging.getLogger("email_assistant.audit")


class AuditLogger:
    """Writes audit events to an append-only JSONL file."""

    def __init__(self, log_path: Optional[str] = None) -> None:
        self._path = Path(log_path or settings.audit_log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def log(
        self,
        action: AuditAction,
        actor: str = "system",
        resource_type: str = "",
        resource_id: str = "",
        workflow_id: str = "",
        outcome: str = "SUCCESS",
        detail: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Create and persist an audit event. Thread-safe via asyncio.Lock."""
        event = AuditEvent(
            action=action,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            workflow_id=workflow_id,
            outcome=outcome,
            detail=detail,
            metadata=metadata or {},
            timestamp=datetime.utcnow(),
        )

        async with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")

        logger.debug("Audit: %s | %s | %s", action.value, actor, outcome)
        return event

    def read_recent(self, limit: int = 50) -> list[AuditEvent]:
        """Read the most recent N audit events from the log file."""
        if not self._path.exists():
            return []

        events = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines[-limit:]):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                events.append(
                    AuditEvent(
                        event_id=data.get("event_id", ""),
                        action=AuditAction(data.get("action", AuditAction.WORKFLOW_ERROR.value)),
                        actor=data.get("actor", ""),
                        resource_type=data.get("resource_type", ""),
                        resource_id=data.get("resource_id", ""),
                        workflow_id=data.get("workflow_id", ""),
                        outcome=data.get("outcome", ""),
                        detail=data.get("detail"),
                        metadata=data.get("metadata", {}),
                    )
                )
        except Exception as e:
            logger.error("Failed to read audit log: %s", e)

        return events


# Singleton
audit_logger = AuditLogger()
