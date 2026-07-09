"""
pipeline.py — Runs an ordered chain of guardrails and folds their verdicts.

The pipeline is the ONLY component that interprets verdicts. Rails just report.

Execution rules:
  - Rails run in registration order.
  - A BLOCK short-circuits the chain — no later rails run.
  - Every other verdict is recorded; the final verdict is the strictest seen.
  - If a rail raises, its FailMode decides: CLOSED → treated as BLOCK,
    OPEN → treated as ALLOW (logged).
  - Each result is emitted to the audit log so nothing changes silently.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from src.config.constants import AuditAction
from src.guardrails.base import Guardrail
from src.guardrails.result import (
    FailMode,
    GuardrailContext,
    GuardrailResult,
    Verdict,
    strictest,
)

logger = logging.getLogger("email_assistant.guardrails.pipeline")


@dataclass
class PipelineOutcome:
    """Aggregated result of running a full guardrail chain."""
    final_verdict: Verdict = Verdict.ALLOW
    results: List[GuardrailResult] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.final_verdict == Verdict.BLOCK

    @property
    def requires_approval(self) -> bool:
        return self.final_verdict == Verdict.REQUIRE_APPROVAL

    @property
    def transformed(self) -> bool:
        return any(r.verdict == Verdict.TRANSFORM for r in self.results)

    @property
    def escalations(self) -> List[GuardrailResult]:
        return [r for r in self.results if r.verdict == Verdict.REQUIRE_APPROVAL]

    def reasons(self, *verdicts: Verdict) -> List[str]:
        """Human-readable reasons, optionally filtered to specific verdicts."""
        wanted = set(verdicts)
        return [
            f"{r.rail_name}: {r.reason}"
            for r in self.results
            if r.reason and (not wanted or r.verdict in wanted)
        ]

    @property
    def summary(self) -> str:
        if not self.results:
            return "no guardrails ran"
        parts = [f"{r.rail_name}={r.verdict.value}" for r in self.results if r.verdict != Verdict.ALLOW]
        return f"{self.final_verdict.value} ({', '.join(parts)})" if parts else "ALLOW (all clear)"


class GuardrailPipeline:
    """An ordered chain of guardrails for a single stage."""

    def __init__(self, rails: Optional[Sequence[Guardrail]] = None) -> None:
        self._rails: List[Guardrail] = list(rails or [])

    def add(self, rail: Guardrail) -> "GuardrailPipeline":
        self._rails.append(rail)
        return self

    @property
    def rails(self) -> List[Guardrail]:
        return list(self._rails)

    async def run(self, ctx: GuardrailContext) -> PipelineOutcome:
        """Execute every rail against `ctx` and return the folded outcome."""
        outcome = PipelineOutcome()

        for rail in self._rails:
            try:
                result = await rail.check(ctx)
            except Exception as e:  # noqa: BLE001 — fail-mode policy handles this
                logger.error("Guardrail '%s' raised: %s", rail.name, e, exc_info=True)
                if rail.fail_mode == FailMode.CLOSED:
                    result = rail.block(f"rail error (fail-closed): {e}")
                else:
                    result = rail.allow(f"rail error (fail-open, ignored): {e}")

            outcome.results.append(result)
            outcome.final_verdict = strictest(outcome.final_verdict, result.verdict)

            await self._audit(ctx, result)

            if result.verdict == Verdict.BLOCK:
                logger.warning(
                    "Guardrail pipeline short-circuited by '%s': %s",
                    rail.name, result.reason,
                )
                break

        logger.info(
            "Guardrail pipeline [%s] → %s",
            ctx.stage.value, outcome.summary,
        )
        return outcome

    async def _audit(self, ctx: GuardrailContext, result: GuardrailResult) -> None:
        """Emit an audit event for any non-ALLOW verdict."""
        action = {
            Verdict.BLOCK: AuditAction.GUARDRAIL_BLOCKED,
            Verdict.TRANSFORM: AuditAction.GUARDRAIL_TRANSFORMED,
            Verdict.REQUIRE_APPROVAL: AuditAction.GUARDRAIL_ESCALATED,
        }.get(result.verdict)
        if action is None:
            return
        try:
            from src.audit.logger import audit_logger
            resource_id = ctx.draft.draft_id if ctx.draft else (ctx.thread.thread_id if ctx.thread else "")
            await audit_logger.log(
                action=action,
                actor="guardrails",
                resource_type="draft" if ctx.draft else "thread",
                resource_id=resource_id,
                workflow_id=ctx.workflow_id,
                outcome="BLOCKED" if result.is_blocking else "FLAGGED",
                detail=f"{result.rail_name}: {result.reason}",
                metadata={"stage": ctx.stage.value, "severity": result.severity.value, **result.metadata},
            )
        except Exception as e:  # noqa: BLE001 — audit must never break the pipeline
            logger.error("Failed to audit guardrail result: %s", e)
