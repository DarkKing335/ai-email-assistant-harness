"""
orchestrator.py — Email workflow orchestrator.

Drives the full pipeline from email receipt to send (or termination).
Calls steps in sequence, updates the state machine, and catches errors.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from src.config.constants import WorkflowStatus, AuditAction, UserRole
from src.config.settings import settings
from src.models.workflow_context import WorkflowContext
from src.guardrails.result import GuardrailContext, GuardrailStage, Verdict
from src.permissions.context import acting_as
from src.workflow.engine.state_machine import WorkflowStateMachine, WorkflowTransitionError

logger = logging.getLogger("email_assistant.workflow.orchestrator")


class EmailWorkflowOrchestrator:
    """Runs the email processing pipeline end-to-end."""

    def __init__(self) -> None:
        # Import steps here to avoid circular imports
        from src.workflow.steps.ingest_step import IngestStep
        from src.workflow.steps.draft_step import DraftStep
        from src.workflow.steps.approval_step import ApprovalStep
        from src.workflow.steps.send_step import SendStep
        from src.workflow.steps.audit_step import AuditStep

        from src.guardrails.registry import build_default_guardrails
        from src.guardrails.result import GuardrailStage

        self._ingest = IngestStep()
        self._draft = DraftStep()
        self._approval = ApprovalStep()
        self._send = SendStep()
        self._audit = AuditStep()

        registry = build_default_guardrails()
        self._input_guardrails = registry.pipeline(GuardrailStage.INPUT)
        self._output_guardrails = registry.pipeline(GuardrailStage.OUTPUT)
        
        # BLOCKER-7: Initialise tool registry so the orchestrator is self-contained
        from src.tools.registry import build_default_registry
        build_default_registry()

    async def run(self, thread_id: str) -> WorkflowContext:
        """Execute the full email workflow for a given Gmail thread ID."""
        # Khởi tạo Context chuẩn
        workflow_id = f"wf_{uuid.uuid4().hex[:16]}"
        ctx = WorkflowContext(workflow_id=workflow_id, thread_id=thread_id)
        sm = WorkflowStateMachine(ctx.workflow_id)

        logger.info("Workflow %s started for thread %s", ctx.workflow_id, thread_id)

        # ── Step 1: Ingest ──────────────────────────────────────────────────
        ctx = await self._run_step("ingest", sm, WorkflowStatus.INGESTED, ctx,
                                   self._ingest.execute, ctx)
        if sm.is_terminal:
            return ctx

        # A single guardrail context threads INPUT → OUTPUT so a rail on the
        # inbound email (e.g. injection detection) can flag the later draft stage.
        gctx = GuardrailContext(
            stage=GuardrailStage.INPUT,
            workflow_id=sm.workflow_id,
            thread=ctx.email_thread,
            metadata=ctx.metadata,
        )

        # ── Step 2: Input guardrails (on the untrusted inbound email) ────────
        if settings.guardrails_enable_input:
            in_outcome = await self._input_guardrails.run(gctx)
            if in_outcome.blocked:
                ctx.metadata["error"] = "; ".join(in_outcome.reasons(Verdict.BLOCK)) or "input guardrails blocked"
                sm.transition(WorkflowStatus.GUARDRAILS_FAILED)
                sm.transition(WorkflowStatus.TERMINATED)
                ctx.status = sm.state
                logger.warning("Workflow %s terminated by input guardrails", sm.workflow_id)
                return ctx

        # ── Step 3: Draft ───────────────────────────────────────────────────
        # The drafting agent acts as OPERATOR: it may read/draft/summarise/look
        # up, but the permission engine forbids it from ever sending.
        with acting_as(UserRole.OPERATOR, actor="drafting-agent"):
            ctx = await self._run_step("draft", sm, WorkflowStatus.DRAFTED, ctx,
                                       self._draft.execute, ctx)
        if sm.is_terminal:
            return ctx

        # ── Step 4: Output guardrails (on the generated draft) ──────────────
        gctx.stage = GuardrailStage.OUTPUT
        gctx.draft = ctx.draft
        if settings.guardrails_enable_output:
            out_outcome = await self._output_guardrails.run(gctx)
            if out_outcome.blocked:
                if ctx.draft:
                    ctx.draft.guardrails_passed = False
                ctx.metadata["error"] = "; ".join(out_outcome.reasons(Verdict.BLOCK))
                sm.transition(WorkflowStatus.GUARDRAILS_FAILED)
                sm.transition(WorkflowStatus.TERMINATED)
                ctx.status = sm.state
                logger.warning("Workflow %s terminated: output guardrails blocked the draft", sm.workflow_id)
                return ctx
            # Passed — surface any escalation reasons to the human reviewer.
            if out_outcome.requires_approval and ctx.draft:
                escalations = out_outcome.reasons(Verdict.REQUIRE_APPROVAL)
                ctx.metadata["guardrail_escalations"] = escalations
                ctx.draft.guardrail_notes = (
                    ctx.draft.guardrail_notes + " needs-approval: " + "; ".join(escalations)
                ).strip()
        if ctx.draft:
            ctx.draft.guardrails_passed = True
        sm.transition(WorkflowStatus.GUARDRAILS_PASSED)

        # ── Step 4: Approval Gate ───────────────────────────────────────────
        ctx = await self._run_step("approval", sm, WorkflowStatus.AWAITING_APPROVAL, ctx,
                                   self._approval.execute, ctx)
        if sm.is_terminal:
            return ctx

        # Check approval result trực tiếp từ thuộc tính is_approved của Context
        if ctx.is_approved:
            sm.transition(WorkflowStatus.APPROVED)
        else:
            sm.transition(WorkflowStatus.REJECTED)
            sm.transition(WorkflowStatus.TERMINATED)
            ctx.status = sm.state
            logger.info("Workflow %s terminated: draft rejected", ctx.workflow_id)
            return ctx

        # ── Step 5: Send ────────────────────────────────────────────────────
        sm.transition(WorkflowStatus.SENDING)
        ctx = await self._run_step("send", sm, WorkflowStatus.SENT, ctx,
                                   self._send.execute, ctx)
        if sm.is_terminal:
            return ctx

        # ── Step 6: Audit ───────────────────────────────────────────────────
        ctx.metadata["history"] = sm.history()
        await self._audit.execute(ctx)
        sm.transition(WorkflowStatus.AUDITED)
        ctx.status = sm.state

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
            # Lưu lỗi vào metadata vì Context chuẩn không có trường error
            ctx.metadata["error"] = str(e)
            try:
                sm.transition(WorkflowStatus.ERROR)
            except WorkflowTransitionError:
                pass
        
        # BLOCKER-1: Ensure context status reflects the state machine
        ctx.status = sm.state
        return ctx