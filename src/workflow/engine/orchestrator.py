"""
orchestrator.py — Email workflow orchestrator.

Drives the full pipeline from email receipt to send (or termination).
Calls steps in sequence, updates the state machine, and catches errors.

Flow:
  RECEIVED → ingest → INGESTED → draft → DRAFTED → guardrails
  → GUARDRAILS_PASSED → approval gate → APPROVED → send → SENT → audit → AUDITED

This is a thin coordinator — all business logic lives in the steps.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.config.constants import WorkflowStatus, AuditAction
from src.models.email import EmailThread
from src.models.draft import Draft
from src.models.approval_record import ApprovalRecord
from src.workflow.engine.state_machine import WorkflowStateMachine, WorkflowTransitionError

logger = logging.getLogger("email_assistant.workflow.orchestrator")


@dataclass
class WorkflowContext:
    """Shared context passed between workflow steps."""
    workflow_id: str = field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:16]}")
    thread: Optional[EmailThread] = None
    draft: Optional[Draft] = None
    approval: Optional[ApprovalRecord] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmailWorkflowOrchestrator:
    """Runs the email processing pipeline end-to-end."""

    def __init__(self) -> None:
        # Import steps here to avoid circular imports
        from src.workflow.steps.ingest_step import IngestStep
        from src.workflow.steps.draft_step import DraftStep
        from src.workflow.steps.approval_step import ApprovalStep
        from src.workflow.steps.send_step import SendStep
        from src.workflow.steps.audit_step import AuditStep
        from src.audit.logger import audit_logger

        self._ingest = IngestStep()
        self._draft = DraftStep()
        self._approval = ApprovalStep()
        self._send = SendStep()
        self._audit = AuditStep()
        self._audit_logger = audit_logger

    async def run(self, thread_id: str) -> WorkflowContext:
        """Execute the full email workflow for a given Gmail thread ID."""
        ctx = WorkflowContext()
        sm = WorkflowStateMachine(ctx.workflow_id)

        logger.info("Workflow %s started for thread %s", ctx.workflow_id, thread_id)

        # ── Step 1: Ingest ──────────────────────────────────────────────────
        ctx = await self._run_step("ingest", sm, WorkflowStatus.INGESTED, ctx,
                                   self._ingest.run, thread_id)
        if sm.is_terminal:
            return ctx

        # ── Step 2: Draft ───────────────────────────────────────────────────
        ctx = await self._run_step("draft", sm, WorkflowStatus.DRAFTED, ctx,
                                   self._draft.run, ctx)
        if sm.is_terminal:
            return ctx

        # ── Step 3: Guardrails (basic — always pass in this version) ────────
        sm.transition(WorkflowStatus.GUARDRAILS_PASSED)

        # ── Step 4: Approval Gate ───────────────────────────────────────────
        ctx = await self._run_step("approval", sm, WorkflowStatus.AWAITING_APPROVAL, ctx,
                                   self._approval.run, ctx)
        if sm.is_terminal:
            return ctx

        # Check approval result
        if ctx.approval and ctx.approval.is_approved:
            sm.transition(WorkflowStatus.APPROVED)
        else:
            sm.transition(WorkflowStatus.REJECTED)
            sm.transition(WorkflowStatus.TERMINATED)
            logger.info("Workflow %s terminated: draft rejected", ctx.workflow_id)
            return ctx

        # ── Step 5: Send ────────────────────────────────────────────────────
        sm.transition(WorkflowStatus.SENDING)
        ctx = await self._run_step("send", sm, WorkflowStatus.SENT, ctx,
                                   self._send.run, ctx)
        if sm.is_terminal:
            return ctx

        # ── Step 6: Audit ───────────────────────────────────────────────────
        await self._audit.run(ctx, sm.history())
        sm.transition(WorkflowStatus.AUDITED)

        logger.info("Workflow %s completed successfully", ctx.workflow_id)
        return ctx

    async def _run_step(
        self,
        step_name: str,
        sm: WorkflowStateMachine,
        success_state: WorkflowStatus,
        ctx: WorkflowContext,
        step_fn,
        *args,
    ) -> WorkflowContext:
        """Run one step. On exception, transition to ERROR and return."""
        try:
            result = await step_fn(*args)
            if isinstance(result, WorkflowContext):
                ctx = result
            sm.transition(success_state)
        except WorkflowTransitionError:
            raise
        except Exception as e:
            logger.error("Step '%s' failed: %s", step_name, e, exc_info=True)
            ctx.error = str(e)
            try:
                sm.transition(WorkflowStatus.ERROR)
            except WorkflowTransitionError:
                pass
        return ctx
