"""
grounding.py — OUTPUT LLM-judge rail. Detects hallucination: does the draft
assert facts/commitments/figures/dates NOT supported by the original thread?

If so, it escalates to a human (REQUIRE_APPROVAL) rather than blocking — the
model may be wrong, and a person should judge borderline claims. Opt-in,
cached, fail-open (see LLMJudgeRail).
"""
from __future__ import annotations

from typing import Any, Dict

from src.guardrails.llm_judge import LLMJudgeRail
from src.guardrails.result import GuardrailContext, GuardrailResult, GuardrailStage

_SYSTEM = (
    "You are a strict fact-checking guardrail for an email assistant. You are given "
    "the ORIGINAL email thread and a DRAFT reply written on the user's behalf. Decide "
    "whether the draft asserts specific facts, commitments, figures, dates, prices, or "
    "claims that are NOT supported by the thread. Ignore generic pleasantries, greetings, "
    "and offers to help. Respond with ONLY a JSON object: "
    '{"flag": <true if unsupported claims are present, else false>, '
    '"reason": "<short reason naming the unsupported claim, or \'grounded\'>"}'
)


class GroundingRail(LLMJudgeRail):
    """Escalates drafts that make claims unsupported by the thread."""

    name = "grounding_rail"
    stage = GuardrailStage.OUTPUT
    llm_task = "reflect"  # needs reasoning → primary model

    def _cache_text(self, ctx: GuardrailContext) -> str:
        thread_text = ctx.thread.full_text if ctx.thread else ""
        body = ctx.draft.body if ctx.draft else ""
        if not body:
            return ""
        return f"{thread_text}\n===DRAFT===\n{body}"

    def _system_prompt(self) -> str:
        return _SYSTEM

    def _user_prompt(self, ctx: GuardrailContext) -> str:
        thread_text = ctx.thread.full_text if ctx.thread else "(no thread context available)"
        body = ctx.draft.body if ctx.draft else ""
        return (
            f"ORIGINAL THREAD:\n{thread_text[:3000]}\n\n"
            f"DRAFT REPLY:\n{body[:2000]}\n\n"
            "JSON:"
        )

    def _interpret(self, judgment: Dict[str, Any], ctx: GuardrailContext) -> GuardrailResult:
        if judgment["flag"]:
            return self.require_approval(
                f"possible unsupported claim in draft — {judgment['reason']}",
                reason_detail=judgment["reason"],
            )
        return self.allow("draft appears grounded in the thread")
