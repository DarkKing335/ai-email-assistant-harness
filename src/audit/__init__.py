"""
audit — Append-only structured audit logging.

Every action in the system (tool invocations, approvals, sends, guardrail
events) produces an AuditEvent that is written to the JSONL audit log.

Public API:
    from src.audit import audit_logger
    from src.audit.logger import AuditLogger
    from src.audit.event import AuditEvent
"""
from src.audit.logger import AuditLogger, audit_logger
from src.models.audit_event import AuditEvent

__all__ = [
    "AuditLogger",
    "audit_logger",
    "AuditEvent",
]
