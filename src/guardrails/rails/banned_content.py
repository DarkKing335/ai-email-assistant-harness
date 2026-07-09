"""
banned_content.py — OUTPUT rail. Blocks drafts that leak secrets or slip
credentials into an outbound email.

Validator, fail-closed. These patterns are deterministic and cheap — exactly
the kind of check that should never depend on an LLM.
"""
from __future__ import annotations

from src.guardrails.base import Guardrail
from src.guardrails.policy import get_policy
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult, GuardrailStage


class BannedContentRail(Guardrail):
    """Hard-blocks a draft that contains secrets or credentials."""

    name = "banned_content"
    stage = GuardrailStage.OUTPUT
    fail_mode = FailMode.CLOSED

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        draft = ctx.draft
        if draft is None:
            return self.allow("no draft to scan")

        haystack = f"{draft.subject}\n{draft.body}"
        for label, pattern in get_policy().banned_patterns():
            if pattern.search(haystack):
                draft.content_flagged = True
                return self.block(f"draft appears to contain a {label}", pattern=label)

        return self.allow("no banned content detected")
