"""
pii_redactor.py — OUTPUT rail. Redacts PII from the draft body.

This is a TRANSFORMER: it mutates the draft in place and returns TRANSFORM so
the pipeline audits the change. Redaction (not blocking) is chosen because a
reply legitimately may need to reference some data — the human reviewer sees
the redaction markers and can restore anything intentionally.

Deterministic patterns only. Covers the common, high-confidence cases; it is
a safety net, not a compliance-grade DLP engine.
"""
from __future__ import annotations

from typing import List

from src.guardrails.base import Guardrail
from src.guardrails.policy import get_policy
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult, GuardrailStage


class PiiRedactorRail(Guardrail):
    """Redacts high-confidence PII from the draft body before human review."""

    name = "pii_redactor"
    stage = GuardrailStage.OUTPUT
    fail_mode = FailMode.OPEN  # a redaction failure must not block the pipeline

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        draft = ctx.draft
        if draft is None:
            return self.allow("no draft to redact")

        body = draft.body
        found: List[str] = []
        for label, pattern, replacement in get_policy().pii_patterns():
            body, n = pattern.subn(replacement, body)
            if n:
                found.append(f"{label}×{n}")

        if not found:
            return self.allow("no PII detected")

        draft.body = body
        draft.pii_detected = True
        draft.guardrail_notes = (draft.guardrail_notes + f" redacted: {', '.join(found)};").strip()
        return self.transform(f"redacted PII: {', '.join(found)}", redactions=found)
