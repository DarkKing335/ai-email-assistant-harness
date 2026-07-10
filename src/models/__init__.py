"""
models — Domain model layer (innermost ring).

Pure Python dataclasses with no infrastructure dependencies.
All layers above (tools, workflow, agent, GUI) use these models.
"""
from src.models.email import EmailMessage, EmailThread
from src.models.draft import Draft
from src.models.approval_record import ApprovalRecord
from src.models.audit_event import AuditEvent
from src.models.workflow_context import WorkflowContext

__all__ = [
    "EmailMessage",
    "EmailThread",
    "Draft",
    "ApprovalRecord",
    "AuditEvent",
    "WorkflowContext",
]
