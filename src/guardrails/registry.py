"""
registry.py — Builds the guardrail pipelines for each stage.

Mirrors the tool registry pattern: rails register here, and the orchestrator
asks for a stage's pipeline at runtime. Adding a rail is a one-line change
with zero edits to the orchestrator.

Rail ORDER within a stage matters — cheap validators first, transformers next,
escalation rails last (so they can observe flags set by earlier rails).
"""
from __future__ import annotations

import logging
from typing import Dict, List

from src.guardrails.base import Guardrail
from src.guardrails.pipeline import GuardrailPipeline
from src.guardrails.result import GuardrailStage

logger = logging.getLogger("email_assistant.guardrails.registry")


class GuardrailRegistry:
    """Holds ordered rails per stage and hands out pipelines."""

    def __init__(self) -> None:
        self._by_stage: Dict[GuardrailStage, List[Guardrail]] = {
            GuardrailStage.INPUT: [],
            GuardrailStage.OUTPUT: [],
        }

    def register(self, rail: Guardrail) -> "GuardrailRegistry":
        self._by_stage[rail.stage].append(rail)
        logger.debug("Registered guardrail: %s (%s)", rail.name, rail.stage.value)
        return self

    def pipeline(self, stage: GuardrailStage) -> GuardrailPipeline:
        return GuardrailPipeline(self._by_stage[stage])

    def names(self, stage: GuardrailStage) -> List[str]:
        return [r.name for r in self._by_stage[stage]]


# ── Singleton registry ────────────────────────────────────────────────────────

guardrail_registry = GuardrailRegistry()


def build_default_guardrails() -> GuardrailRegistry:
    """Register the default rail set. Idempotent — safe to call more than once."""
    if guardrail_registry.names(GuardrailStage.OUTPUT):
        return guardrail_registry  # already built

    from src.guardrails.policy import get_policy
    from src.guardrails.rails.prompt_injection import (
        PromptInjectionRail,
        InjectionEscalationRail,
    )
    from src.guardrails.rails.format_validator import FormatValidatorRail
    from src.guardrails.rails.length_rail import LengthRail
    from src.guardrails.rails.banned_content import BannedContentRail
    from src.guardrails.rails.pii_redactor import PiiRedactorRail
    from src.guardrails.rails.recipient_allowlist import RecipientAllowlistRail
    from src.guardrails.rails.grounding import GroundingRail
    from src.guardrails.rails.injection_intent import InjectionIntentRail

    policy = get_policy()

    def _register(rail: Guardrail) -> None:
        """Register a rail unless the policy disables it; apply fail-mode override.

        opt_in rails (the LLM judges) are skipped unless the policy explicitly
        names them — a YAML `rails` section that omits them keeps them off.
        """
        toggle = policy.toggle(rail.name)
        enabled = toggle.enabled
        if rail.opt_in and rail.name not in policy.rails:
            enabled = False
        if not enabled:
            logger.info("Guardrail '%s' disabled (opt_in=%s) — skipped", rail.name, rail.opt_in)
            return
        if toggle.fail_mode is not None:
            rail.fail_mode = toggle.fail_mode  # instance override of the class default
        guardrail_registry.register(rail)

    # INPUT — run on the untrusted inbound email before drafting.
    #   deterministic first, then the (opt-in) LLM intent backstop.
    _register(PromptInjectionRail())
    _register(InjectionIntentRail())

    # OUTPUT — run on the generated draft, in deliberate order:
    #   validators (block bad drafts) → transformers (redact) →
    #   (opt-in) LLM grounding judge → escalation.
    _register(FormatValidatorRail())
    _register(BannedContentRail())
    _register(LengthRail())
    _register(PiiRedactorRail())
    _register(GroundingRail())
    _register(RecipientAllowlistRail())
    _register(InjectionEscalationRail())

    logger.info(
        "Default guardrails built: input=%s output=%s",
        guardrail_registry.names(GuardrailStage.INPUT),
        guardrail_registry.names(GuardrailStage.OUTPUT),
    )
    return guardrail_registry
