"""
result.py — Verdict model shared by every guardrail.

A guardrail never mutates control flow directly. It inspects a
GuardrailContext and returns a GuardrailResult carrying a Verdict.
The GuardrailPipeline is the only component that interprets verdicts and
decides what happens to the workflow.

Design note: "checking" and "manipulating" are deliberately separated.
  - A *validator* returns ALLOW / BLOCK / REQUIRE_APPROVAL and never mutates.
  - A *transformer* mutates the payload in place and returns TRANSFORM.
Every TRANSFORM is audited — nothing is ever changed silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.draft import Draft
    from src.models.email import EmailThread


class Verdict(str, Enum):
    """The outcome a single guardrail can return.

    Precedence (most → least severe), used by the pipeline to fold many
    rail results into one final decision:
        BLOCK > REQUIRE_APPROVAL > TRANSFORM > ALLOW
    """
    ALLOW = "ALLOW"                        # Payload is fine as-is
    TRANSFORM = "TRANSFORM"                # Rail mutated the payload; continue
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"  # Force human sign-off before proceeding
    BLOCK = "BLOCK"                        # Hard stop; terminate the workflow


# Severity ranking for folding multiple verdicts into the strictest one.
_VERDICT_RANK: Dict[Verdict, int] = {
    Verdict.ALLOW: 0,
    Verdict.TRANSFORM: 1,
    Verdict.REQUIRE_APPROVAL: 2,
    Verdict.BLOCK: 3,
}


def strictest(a: Verdict, b: Verdict) -> Verdict:
    """Return the more severe of two verdicts."""
    return a if _VERDICT_RANK[a] >= _VERDICT_RANK[b] else b


class GuardrailStage(str, Enum):
    """When in the pipeline a rail runs."""
    INPUT = "INPUT"    # On the untrusted inbound email, before drafting
    OUTPUT = "OUTPUT"  # On the generated draft, before it reaches the reviewer


class FailMode(str, Enum):
    """What to do when a rail raises an unexpected exception.

    Safety rails (send, PII, banned content) should fail CLOSED — an error
    means block. Optimisation rails (normalisation, length) should fail OPEN
    — an error means let the payload through unchanged.
    """
    OPEN = "OPEN"      # On error → ALLOW (log and continue)
    CLOSED = "CLOSED"  # On error → BLOCK


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class GuardrailContext:
    """The payload under inspection, shared across all rails in a stage.

    Rails read and (for transformers) mutate `draft` / `thread` in place.
    `metadata` is a scratchpad rails use to pass signals to later stages —
    e.g. an INPUT injection rail sets a flag the OUTPUT stage reads to force
    human approval.
    """
    stage: GuardrailStage
    workflow_id: str = ""
    draft: Optional["Draft"] = None
    thread: Optional["EmailThread"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailResult:
    """The outcome of one guardrail's inspection."""
    rail_name: str
    verdict: Verdict
    reason: str = ""
    severity: Severity = Severity.INFO
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        return self.verdict == Verdict.BLOCK

    def __repr__(self) -> str:
        return f"<GuardrailResult {self.rail_name} {self.verdict.value}: {self.reason!r}>"
