"""
types.py — Data types that cross the GUI boundary.

These live outside gateway.py so that viewmodels can import them without
pulling in ``src.config.settings`` (which requires pydantic-settings) or the
approval/audit singletons (which touch the filesystem at import time).

Consequence: the entire ``viewmodels/`` package is importable and testable
with nothing installed but pytest.

The gateway returns Ring 1 domain models (Draft, EmailThread, ApprovalRecord,
AuditEvent) unmodified — Ring 3 depending on Ring 1 is legal. The dataclasses
here only wrap them with GUI-specific framing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from src.models.approval_record import ApprovalRecord
from src.models.draft import Draft
from src.models.email import EmailThread


class GuardrailState(str, Enum):
    """Tri-state guardrail verdict.

    ``Draft.guardrails_passed`` is a bool, so it cannot distinguish
    "guardrails ran and the draft failed" from "guardrails never ran because
    src/guardrails/ is empty". Rendering a red FAILED badge for the second case
    would be a lie. See viewmodels/draft_vm.py::guardrail_state.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"


class GmailMode(str, Enum):
    """Predicted Gmail connection mode.

    Derived without constructing a GmailClient, because GmailClient.__init__
    calls get_credentials(), which can fall through to
    ``flow.run_local_server(port=8080)`` (auth.py:116) and open a browser.
    A config panel must never do that.
    """

    MOCK = "MOCK"              # Google libraries not installed — mock data only
    READY = "READY"            # Libraries present and a token is available
    NEEDS_AUTH = "NEEDS_AUTH"  # Libraries present, no token: would prompt OAuth


@dataclass(frozen=True)
class WorkflowResult:
    """Outcome of a completed workflow run.

    Built only from fields that actually exist on WorkflowContext.
    Note there is no ``ctx.error`` and no ``ctx.approval`` — cli/runner.py:92
    and :111 read those and raise AttributeError.
    """

    workflow_id: str
    draft: Optional[Draft]
    thread: Optional[EmailThread]
    approval: Optional[ApprovalRecord]
    error: Optional[str]
    is_approved: bool


@dataclass(frozen=True)
class PendingItem:
    """One draft sitting in the approval queue.

    ``draft`` and ``thread`` are None until the ApprovalGate exposes them
    (BLOCKER-2 / BLOCKER-3). The gate already holds the Draft in ``_pending``;
    it simply is not reachable. Views must render the None case rather than
    assume a body is present.
    """

    draft_id: str
    to: str
    subject: str
    preview: str
    requested_at: Optional[datetime]
    timeout_at: Optional[datetime]
    draft: Optional[Draft] = None
    thread: Optional[EmailThread] = None


@dataclass(frozen=True)
class ProgressEvent:
    """A live progress signal emitted while a workflow runs.

    Sourced from the ``email_assistant`` logger, because the orchestrator never
    writes ``ctx.status`` (BLOCKER-1). These are human-readable strings, not
    structured state.
    """

    timestamp: datetime
    logger_name: str
    message: str
    level: str


@dataclass(frozen=True)
class ConfigSummary:
    """Configuration shown to the user.

    Carries no secret. ``llm_api_key_last4`` is the standard last-four
    fingerprint; the key itself never crosses this boundary, masked or not.
    """

    app_env: str
    app_version: str
    llm_provider: str
    llm_model_draft: str
    llm_api_key_last4: str          # "" when no key is configured
    gmail_user_email: str
    gmail_mode: GmailMode
    audit_log_path: str
    approval_timeout_seconds: int
    reviewer: str
    permissions_enforced: bool
