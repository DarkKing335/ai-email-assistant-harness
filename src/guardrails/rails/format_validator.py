"""
format_validator.py — OUTPUT rail. Structural validation of a draft.

A validator: inspects only, never mutates. Fail-closed — a malformed draft
must never reach the reviewer or the send step.
"""
from __future__ import annotations

import re

from src.guardrails.base import Guardrail
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult, GuardrailStage

# Deliberately permissive — we validate shape, not deliverability.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FormatValidatorRail(Guardrail):
    """Ensures a draft has a well-formed recipient, a subject, and a body."""

    name = "format_validator"
    stage = GuardrailStage.OUTPUT
    fail_mode = FailMode.CLOSED

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        draft = ctx.draft
        if draft is None:
            return self.block("no draft present in output stage")

        if not draft.to or not _EMAIL_RE.match(draft.to.strip()):
            return self.block(f"invalid recipient address: {draft.to!r}")
        if not draft.subject.strip():
            return self.block("draft has an empty subject")
        if not draft.body.strip():
            return self.block("draft has an empty body")

        return self.allow("draft is structurally valid")
