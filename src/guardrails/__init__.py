"""
Guardrails layer — automated checks and transforms that intercept the
untrusted inbound email (INPUT) and the agent-generated draft (OUTPUT).

See docs/architecture/adr/0002-guardrails-layer.md for the design rationale.

Public API:
    from src.guardrails import (
        build_default_guardrails, guardrail_registry,
        GuardrailStage, GuardrailContext, Verdict,
    )
"""
from src.guardrails.base import Guardrail
from src.guardrails.pipeline import GuardrailPipeline, PipelineOutcome
from src.guardrails.policy import GuardrailPolicy, get_policy, load_policy, reload_policy
from src.guardrails.registry import build_default_guardrails, guardrail_registry
from src.guardrails.result import (
    FailMode,
    GuardrailContext,
    GuardrailResult,
    GuardrailStage,
    Severity,
    Verdict,
)

__all__ = [
    "Guardrail",
    "GuardrailPipeline",
    "PipelineOutcome",
    "GuardrailPolicy",
    "get_policy",
    "load_policy",
    "reload_policy",
    "build_default_guardrails",
    "guardrail_registry",
    "FailMode",
    "GuardrailContext",
    "GuardrailResult",
    "GuardrailStage",
    "Severity",
    "Verdict",
]
