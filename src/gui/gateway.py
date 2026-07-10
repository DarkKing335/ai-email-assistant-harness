"""
gateway.py — The single seam between the GUI and the rest of the system.

This is the only module inside ``src/gui/`` permitted to import
``src.workflow``, ``src.approval``, ``src.audit``, or ``src.config.settings``.
Views and viewmodels talk only to this.

Two reasons, in order of importance:

1. **Enforcement.** "The GUI can never send an email" is only true if it is
   mechanically true. There is no ``send()`` here, and no module under
   ``src/gui/`` imports ``src.tools``. That invariant is greppable and is
   checked by tests/unit/gui/test_layering.py.

2. **Containment.** Every blocker listed in the contract changes the shape of
   the data we receive. When ``src/services/`` lands, ``approval_gate.approve()``
   becomes ``approval_service.approve()`` — a one-file edit here, rather than
   four call sites the way ``src/cli/app.py`` has it today (lines 101, 151,
   176, 318).

See docs/architecture/gui-gateway-contract.md for the full contract and the
numbered blockers referenced below.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional

from src.config.constants import WorkflowStatus
from src.gui.session import DEFAULT_REVIEWER, Session, get_session, reset_session
from src.gui.types import (
    ConfigSummary,
    GmailMode,
    PendingItem,
    ProgressEvent,
    WorkflowResult,
)
from src.models.audit_event import AuditEvent
from src.models.draft import Draft

logger = logging.getLogger("email_assistant.gui.gateway")

#: The logger the orchestrator and its steps write to. Our only progress source.
PROGRESS_LOGGER = "email_assistant"


# ── Live progress ─────────────────────────────────────────────────────────────

class _ProgressHandler(logging.Handler):
    """Forward log records to a GUI callback as ProgressEvent objects.

    Same technique as cli/runner.py::_ProgressCapture. Required because the
    orchestrator never writes ``ctx.status`` (BLOCKER-1), so log lines are the
    only observable evidence that a workflow is progressing.

    ``emit`` runs on whichever thread called ``logger.info``. The callback is
    responsible for marshalling onto the UI thread.
    """

    def __init__(self, callback: Callable[[ProgressEvent], None]) -> None:
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(
                ProgressEvent(
                    timestamp=datetime.fromtimestamp(record.created),
                    logger_name=record.name,
                    message=record.getMessage(),
                    level=record.levelname,
                )
            )
        except Exception:  # never let a UI callback break logging
            self.handleError(record)


# ── Gateway ───────────────────────────────────────────────────────────────────

class Gateway:
    """Everything the GUI is allowed to ask of the system.

    Dependencies are injected so the whole surface can be exercised against
    fakes without a Gmail account, an LLM key, or a working orchestrator.
    """

    def __init__(
        self,
        *,
        gate: Any = None,
        audit: Any = None,
        session: Optional[Session] = None,
        orchestrator_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        if gate is None:
            from src.approval.gate import approval_gate

            gate = approval_gate
        if audit is None:
            from src.audit.logger import audit_logger

            audit = audit_logger

        self._gate = gate
        self._audit = audit
        self._session = session
        self._orchestrator_factory = orchestrator_factory or _default_orchestrator

    @property
    def session(self) -> Session:
        return self._session if self._session is not None else get_session()

    # ── Commands ──────────────────────────────────────────────────────────────

    async def start_workflow(self, thread_id: str) -> WorkflowResult:
        """Run the full pipeline for one Gmail thread.

        This does NOT return when the draft is ready. ``ApprovalStep`` awaits an
        ``asyncio.Future`` inside the gate, so this coroutine stays suspended
        until ``approve()`` or ``reject()`` is called for the draft.

        Callers must run it as a background task and discover the draft through
        ``list_pending()`` — never through this return value.
        """
        orchestrator = self._orchestrator_factory()
        ctx = await orchestrator.run(thread_id)
        return self._to_result(ctx)

    def approve(self, draft_id: str, comments: str = "") -> bool:
        """Resolve a pending approval as APPROVED.

        Returns False if the draft is not in the pending queue. Reviewer
        identity comes from the session — deliberately not a parameter, so no
        view can forge the audit trail.

        THREAD AFFINITY — must be called on the thread running the workflow's
        event loop. ``ApprovalGate.approve()`` calls ``future.set_result()``
        directly, and ``asyncio.Future`` is not thread-safe: from a foreign
        thread it schedules via ``loop.call_soon()``, which neither raises (in
        non-debug mode) nor wakes the loop's selector. The observed result is
        that this returns True, the UI reports success, and the workflow never
        resumes. Verified empirically.

        bridge.py is responsible for honouring this. Either drive the loop on
        the UI thread with a pump, or marshal via
        ``asyncio.run_coroutine_threadsafe`` / ``loop.call_soon_threadsafe``.
        """
        if not self.session.can_approve():
            raise PermissionError(
                f"Reviewer {self.session.reviewer!r} is not permitted to approve drafts"
            )
        return bool(
            self._gate.approve(
                draft_id=draft_id,
                reviewer=self.session.reviewer,
                comments=comments,
            )
        )

    def reject(self, draft_id: str, reason: str = "") -> bool:
        """Resolve a pending approval as REJECTED. False if not pending.

        Same thread affinity requirement as ``approve()``.
        """
        if not self.session.can_reject():
            raise PermissionError(
                f"Reviewer {self.session.reviewer!r} is not permitted to reject drafts"
            )
        return bool(
            self._gate.reject(
                draft_id=draft_id,
                reviewer=self.session.reviewer,
                reason=reason,
            )
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_pending(self) -> list[PendingItem]:
        """The approval queue.

        Safe to poll — the gate holds this in memory. Today ``PendingItem.draft``
        and ``.thread`` are always None (BLOCKER-2, BLOCKER-3), so the reviewer
        sees only a 200-character preview.
        """
        return [self._to_pending_item(raw) for raw in self._gate.list_pending()]

    def pending_count(self) -> int:
        return int(self._gate.pending_count)

    def recent_audit(self, limit: int = 50) -> list[AuditEvent]:
        """Most recent audit events, newest first.

        Note: ``AuditLogger.read_recent`` does not restore ``timestamp`` from the
        JSONL line, so every event carries its *read* time (BLOCKER-6).
        """
        return list(self._audit.read_recent(limit=limit))

    def config_summary(self) -> ConfigSummary:
        from src.config.settings import settings

        key = settings.active_llm_api_key
        return ConfigSummary(
            app_env=settings.app_env,
            app_version=settings.app_version,
            llm_provider=settings.llm_provider,
            llm_model_draft=settings.llm_model_draft,
            llm_api_key_last4=key[-4:] if len(key) >= 4 else "",
            gmail_user_email=settings.gmail_user_email,
            gmail_mode=detect_gmail_mode(),
            audit_log_path=settings.audit_log_path,
            approval_timeout_seconds=settings.approval_timeout_seconds,
            reviewer=self.session.reviewer,
            permissions_enforced=self.session.permissions_enforced,
        )

    @staticmethod
    def workflow_states() -> list[WorkflowStatus]:
        """Every member of WorkflowStatus, in declaration order.

        Views must render the timeline from this, never from a hardcoded list.
        ``GUARDRAILS_FAILED`` is already a legal edge in ``VALID_TRANSITIONS``
        and becomes reachable the moment ``src/guardrails/`` ships.
        """
        return list(WorkflowStatus)

    def workflow_history(self) -> Optional[list[WorkflowStatus]]:
        """The state transitions of the running workflow, or None.

        Always None today. ``orchestrator.run()`` keeps its ``WorkflowStateMachine``
        as a local variable and never writes ``ctx.status`` (BLOCKER-1), so the
        history dies with the stack frame.
        """
        return None

    # ── Observation ───────────────────────────────────────────────────────────

    def subscribe_progress(
        self, callback: Callable[[ProgressEvent], None]
    ) -> Callable[[], None]:
        """Stream live progress. Returns an idempotent unsubscribe callable."""
        handler = _ProgressHandler(callback)
        handler.setLevel(logging.INFO)
        root = logging.getLogger(PROGRESS_LOGGER)
        root.addHandler(handler)

        unsubscribed = False

        def unsubscribe() -> None:
            nonlocal unsubscribed
            if not unsubscribed:
                root.removeHandler(handler)
                unsubscribed = True

        return unsubscribe

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_result(ctx: Any) -> WorkflowResult:
        """Project a WorkflowContext onto the fields that actually exist.

        Reads ``metadata["error"]`` and ``metadata["approval_record"]``.
        Does NOT read ``ctx.error``, ``ctx.approval`` (neither attribute exists)
        or ``ctx.status`` (never written).
        """
        return WorkflowResult(
            workflow_id=ctx.workflow_id,
            draft=ctx.draft,
            thread=ctx.email_thread,
            approval=ctx.metadata.get("approval_record"),
            error=ctx.metadata.get("error"),
            is_approved=bool(ctx.is_approved),
        )

    def _to_pending_item(self, raw: dict) -> PendingItem:
        draft, thread = self._full_draft_and_thread(raw["draft_id"])
        return PendingItem(
            draft_id=raw["draft_id"],
            to=raw.get("to", ""),
            subject=raw.get("subject", ""),
            preview=raw.get("preview", ""),
            requested_at=_parse_iso(raw.get("requested_at")),
            timeout_at=_parse_iso(raw.get("timeout_at")),
            draft=draft,
            thread=thread,
        )

    def _full_draft_and_thread(self, draft_id: str) -> tuple[Optional[Draft], Optional[Any]]:
        """Fetch the full Draft and EmailThread if the gate exposes them."""
        getter = getattr(self._gate, "get_pending", None)
        if getter is None:
            return None, None
        try:
            entry = getter(draft_id)
            if not entry:
                return None, None
            if len(entry) == 3:
                _, draft, thread = entry
                return draft, thread
            elif len(entry) == 2:
                _, draft = entry
                return draft, None
        except Exception as exc:
            logger.warning("gate.get_pending(%s) failed: %s", draft_id, exc)
        return None, None


# ── Module helpers ────────────────────────────────────────────────────────────

def _default_orchestrator() -> Any:
    """Imported lazily: the orchestrator pulls in agents and the LLM client."""
    from src.workflow.engine.orchestrator import EmailWorkflowOrchestrator

    return EmailWorkflowOrchestrator()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """ApprovalGate.list_pending() hands back ISO strings, not datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def detect_gmail_mode() -> GmailMode:
    """Predict Gmail connection mode without constructing a GmailClient.

    ``GmailClient.__init__`` calls ``get_credentials()``, which falls through to
    ``flow.run_local_server(port=8080)`` (auth.py:116) when no token exists —
    opening a browser and blocking. A config panel must never trigger that, so
    this mirrors the same decision tree by inspection.
    """
    from src.config.settings import settings

    if importlib.util.find_spec("googleapiclient") is None:
        return GmailMode.MOCK
    if importlib.util.find_spec("google_auth_oauthlib") is None:
        return GmailMode.MOCK
    if os.getenv("GMAIL_TOKEN_JSON"):
        return GmailMode.READY
    if settings.gmail_token_file.exists():
        return GmailMode.READY
    return GmailMode.NEEDS_AUTH


def bootstrap_logging() -> None:
    """Configure logging so INFO records reach subscribe_progress().

    Without this the ``email_assistant`` logger inherits root's WARNING level
    and every progress record is dropped at the source.
    """
    from src.config.logging_config import configure_logging
    from src.config.settings import settings

    configure_logging(level=settings.log_level, fmt=settings.log_format)


def bootstrap_session() -> Session:
    """Seed the process-wide session from settings. Called once at startup.

    Lives here rather than in session.py so that gateway.py remains the single
    importer of ``src.config.settings``.
    """
    from src.config.settings import settings

    session = Session(reviewer=settings.reviewer_email or DEFAULT_REVIEWER)
    reset_session(session)
    return session


_default_gateway: Optional[Gateway] = None


def get_gateway() -> Gateway:
    """The process-wide gateway. Built lazily to avoid import-time filesystem I/O
    (``AuditLogger.__init__`` creates its log directory)."""
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = Gateway()
    return _default_gateway


def reset_gateway(gateway: Optional[Gateway] = None) -> None:
    """Replace the process-wide gateway. For tests."""
    global _default_gateway
    _default_gateway = gateway
