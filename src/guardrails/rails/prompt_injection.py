"""
prompt_injection.py — INPUT rail. The headline guardrail for an email
assistant: the inbound email is attacker-controlled text, and the LLM will
read it. This is classic indirect (second-order) prompt injection.

Strategy (deterministic-first, no LLM in the hot path):
  1. Scan every inbound message body for known injection markers.
  2. NEUTRALISE them in place (wrap the suspicious span) so the drafting LLM
     sees them as quoted, inert text rather than instructions.  → TRANSFORM
  3. Raise a flag in ctx.metadata so the OUTPUT stage forces human approval —
     we never silently trust a draft derived from injected content.

We neutralise rather than block: legitimate emails sometimes contain phrases
like "ignore the previous email". Escalation + neutralisation is safer than a
hard block (which would create a trivial denial-of-service: anyone could stop
the assistant replying just by including a trigger phrase).
"""
from __future__ import annotations

import re
from typing import List

from src.guardrails.base import Guardrail
from src.guardrails.policy import get_policy
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult, GuardrailStage

# Key used by the OUTPUT stage to know an inbound injection attempt was seen.
INJECTION_FLAG = "input_injection_detected"


class PromptInjectionRail(Guardrail):
    """Neutralises inbound prompt-injection attempts and flags the workflow."""

    name = "prompt_injection"
    stage = GuardrailStage.INPUT
    fail_mode = FailMode.CLOSED

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        thread = ctx.thread
        if thread is None or not thread.messages:
            return self.allow("no inbound content to scan")

        patterns = get_policy().injection_patterns()
        hits: List[str] = []
        for msg in thread.messages:
            neutralised, matched = self._neutralise(msg.body_plain, patterns)
            if matched:
                msg.body_plain = neutralised
                hits.extend(matched)

        if not hits:
            return self.allow("no injection markers found")

        # Signal the output stage to force human review of any resulting draft.
        ctx.metadata[INJECTION_FLAG] = True
        return self.transform(
            f"neutralised {len(hits)} inbound injection marker(s); output will require approval",
            markers=hits,
        )

    @staticmethod
    def _neutralise(text: str, patterns: List["re.Pattern[str]"]) -> tuple[str, List[str]]:
        matched: List[str] = []

        def _wrap(m: "re.Match[str]") -> str:
            matched.append(m.group(0))
            return f"[untrusted-content-neutralised: {m.group(0)}]"

        out = text
        for pattern in patterns:
            out = pattern.sub(_wrap, out)
        return out, matched


class InjectionEscalationRail(Guardrail):
    """OUTPUT counterpart: forces approval if the INPUT stage saw an injection.

    The two rails communicate through ctx.metadata (the INPUT rail runs on the
    thread, this one runs on the draft) — this is why the pipeline threads a
    single mutable GuardrailContext through every stage of a workflow.
    """

    name = "injection_escalation"
    stage = GuardrailStage.OUTPUT
    fail_mode = FailMode.OPEN

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        if ctx.metadata.get(INJECTION_FLAG):
            return self.require_approval(
                "draft derived from an email containing neutralised injection markers"
            )
        return self.allow("no inbound injection flag set")
