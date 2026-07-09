"""
base.py — Abstract base class for all guardrails.

A guardrail is a small, single-responsibility, independently testable unit.
It declares which stage it runs in and its fail mode, and implements one
async method: `check(ctx)`.

Subclasses use the helper constructors (`self.allow()`, `self.block()`,
`self.transform()`, `self.require_approval()`) so they never build a
GuardrailResult by hand.

Inspired by:
  - base_tool.py: same __init_subclass__ contract-enforcement pattern
  - opencode / guardrails-ai: chainable rail concept, reimplemented dependency-free
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from src.guardrails.result import (
    FailMode,
    GuardrailContext,
    GuardrailResult,
    GuardrailStage,
    Severity,
    Verdict,
)

logger = logging.getLogger("email_assistant.guardrails")


class Guardrail(ABC):
    """Abstract base class for a single guardrail rail.

    Subclass requirements:
        name (str):         Unique rail identifier.
        stage (GuardrailStage): INPUT or OUTPUT.
        fail_mode (FailMode):   OPEN or CLOSED (defaults to CLOSED — safe by default).
    """

    name: str
    stage: GuardrailStage
    fail_mode: FailMode = FailMode.CLOSED

    # opt_in rails are NOT registered unless the policy explicitly names them
    # (used by the LLM-judge rails, which cost money/latency and need an API key).
    opt_in: bool = False

    # Abstract intermediate bases (e.g. LLMJudgeRail) set this so the
    # name/stage contract is only enforced on concrete rails.
    _abstract_base: bool = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("_abstract_base"):
            return
        for attr in ("name", "stage"):
            if not hasattr(cls, attr):
                raise TypeError(f"Guardrail '{cls.__name__}' must define '{attr}'")

    @abstractmethod
    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        """Inspect (and for transformers, mutate) the context. Return a verdict."""

    # ── Result constructors ─────────────────────────────────────────────────

    def allow(self, reason: str = "") -> GuardrailResult:
        return GuardrailResult(self.name, Verdict.ALLOW, reason)

    def block(self, reason: str, **metadata: Any) -> GuardrailResult:
        return GuardrailResult(
            self.name, Verdict.BLOCK, reason, Severity.CRITICAL, dict(metadata)
        )

    def transform(self, reason: str, **metadata: Any) -> GuardrailResult:
        return GuardrailResult(
            self.name, Verdict.TRANSFORM, reason, Severity.INFO, dict(metadata)
        )

    def require_approval(self, reason: str, **metadata: Any) -> GuardrailResult:
        return GuardrailResult(
            self.name, Verdict.REQUIRE_APPROVAL, reason, Severity.WARNING, dict(metadata)
        )

    def __repr__(self) -> str:
        return f"<Guardrail {self.name} stage={self.stage.value} fail={self.fail_mode.value}>"
