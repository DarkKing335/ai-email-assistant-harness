"""
constants.py — Application-wide enumerations and constants.

Centralizing all enums here prevents magic strings from being scattered
throughout the codebase and makes state transitions explicit and auditable.
"""

from __future__ import annotations

from enum import Enum


class WorkflowStatus(str, Enum):
    """All valid states in the email processing state machine.

    Transition rules (enforced by state_machine.py):
        RECEIVED → INGESTED → DRAFTED → GUARDRAILS_PASSED
        → AWAITING_APPROVAL → APPROVED → SENDING → SENT → AUDITED
        GUARDRAILS_FAILED, REJECTED, TERMINATED, ERROR are terminal states.
    """
    RECEIVED = "RECEIVED"
    INGESTED = "INGESTED"
    DRAFTED = "DRAFTED"
    GUARDRAILS_PASSED = "GUARDRAILS_PASSED"
    GUARDRAILS_FAILED = "GUARDRAILS_FAILED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENDING = "SENDING"
    SENT = "SENT"
    AUDITED = "AUDITED"
    TERMINATED = "TERMINATED"
    ERROR = "ERROR"


class ApprovalDecision(str, Enum):
    """Possible outcomes of a human approval review."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"


class EmailCategory(str, Enum):
    """Email triage categories.

    Inspired by the triage routing in agents-from-scratch.
    """
    RESPOND = "RESPOND"        # Draft a reply
    IGNORE = "IGNORE"          # Not worth responding to
    SPAM = "SPAM"              # Spam / unsolicited
    NOTIFY = "NOTIFY"          # Informational, no reply needed
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Ambiguous, route to HITL triage


class AuditAction(str, Enum):
    """Every recordable action in the audit log."""
    EMAIL_RECEIVED = "EMAIL_RECEIVED"
    EMAIL_INGESTED = "EMAIL_INGESTED"
    DRAFT_CREATED = "DRAFT_CREATED"
    GUARDRAILS_PASSED = "GUARDRAILS_PASSED"
    GUARDRAILS_FAILED = "GUARDRAILS_FAILED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    DRAFT_APPROVED = "DRAFT_APPROVED"
    DRAFT_REJECTED = "DRAFT_REJECTED"
    EMAIL_SENT = "EMAIL_SENT"
    WORKFLOW_TERMINATED = "WORKFLOW_TERMINATED"
    WORKFLOW_ERROR = "WORKFLOW_ERROR"
    TOOL_INVOKED = "TOOL_INVOKED"
    TOOL_FAILED = "TOOL_FAILED"


class UserRole(str, Enum):
    """RBAC roles in the system.

    Inspired by deliberate's role-based approval system.
    """
    OPERATOR = "OPERATOR"    # Can run the assistant, view drafts
    REVIEWER = "REVIEWER"    # Can approve or reject drafts
    ADMIN = "ADMIN"          # Full access including config changes


# ── Gmail API Scopes ──────────────────────────────────────────────────────────

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ── Tool Names (used as registry keys) ───────────────────────────────────────

TOOL_GMAIL_READ = "gmail_read_thread"
TOOL_GMAIL_DRAFT = "gmail_create_or_update_draft"
TOOL_GMAIL_SEND = "gmail_send_draft"
TOOL_SUMMARIZE = "summarize_email_thread"
TOOL_CONTACT_LOOKUP = "lookup_contact"

# ── Misc ─────────────────────────────────────────────────────────────────────

APP_NAME = "ai-email-assistant"
APP_VERSION = "1.0.0"
