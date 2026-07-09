"""
length_rail.py — OUTPUT rail. Bounds the draft body length.

Fail-open: a length-check error should never block a send. A body that is
too short is suspicious (LLM produced junk) → escalate to a human. A body
that is too long is truncated is NOT done here (that would be a silent
transform); instead we escalate so a human decides.
"""
from __future__ import annotations

from src.guardrails.base import Guardrail
from src.guardrails.policy import get_policy
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult, GuardrailStage


class LengthRail(Guardrail):
    """Flags drafts that are implausibly short or excessively long."""

    name = "length_rail"
    stage = GuardrailStage.OUTPUT
    fail_mode = FailMode.OPEN

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        draft = ctx.draft
        if draft is None:
            return self.allow("no draft to measure")

        length = get_policy().length
        n = len(draft.body.strip())
        if n < length.min_chars:
            return self.require_approval(
                f"draft body is only {n} chars (min {length.min_chars}) — likely low quality",
                char_count=n,
            )
        if n > length.max_chars:
            return self.require_approval(
                f"draft body is {n} chars (max {length.max_chars}) — unusually long",
                char_count=n,
            )
        return self.allow(f"draft length ok ({n} chars)")
