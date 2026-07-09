"""
draft_vm.py — Draft → display dict, including the guardrail badge.
"""

from __future__ import annotations

from typing import Any, Optional

from src.gui.types import GuardrailState
from src.models.draft import Draft

GUARDRAIL_LABELS: dict[GuardrailState, str] = {
    GuardrailState.PASSED: "Guardrails passed",
    GuardrailState.FAILED: "Guardrails blocked this draft",
    GuardrailState.NOT_EVALUATED: "Not evaluated — guardrails not implemented",
}


def guardrail_state(draft: Draft) -> GuardrailState:
    """Infer the tri-state guardrail verdict from Draft's boolean fields.

    ``Draft.guardrails_passed`` defaults to False, and ``src/guardrails/`` is an
    empty package, so *every* draft today reads False. Showing a red FAILED
    badge would tell the reviewer the system rejected a draft it never examined.

    The inference: a genuine failure leaves evidence — a note, a PII hit, or a
    content flag. False with no evidence means nothing ran.

    This heuristic should be deleted once the guardrails team makes the field
    ``Optional[bool]`` (None = not evaluated) or adds ``guardrails_evaluated``.
    """
    if draft.guardrails_passed:
        return GuardrailState.PASSED
    if draft.pii_detected or draft.content_flagged or (draft.guardrail_notes or "").strip():
        return GuardrailState.FAILED
    return GuardrailState.NOT_EVALUATED


def draft_to_dict(draft: Optional[Draft]) -> Optional[dict[str, Any]]:
    """Project a Draft for display. None in, None out."""
    if draft is None:
        return None

    state = guardrail_state(draft)
    return {
        "draft_id": draft.draft_id,
        "thread_id": draft.thread_id,
        "to": draft.to,
        "subject": draft.subject,
        "body": draft.body,
        "preview": draft.preview,
        "guardrail_state": state.value,
        "guardrail_label": GUARDRAIL_LABELS[state],
        "guardrail_notes": draft.guardrail_notes or "",
        "pii_detected": draft.pii_detected,
        "content_flagged": draft.content_flagged,
        # Exposed as a boolean, not an ID: no view has business acting on the
        # Gmail draft handle. Sending is the orchestrator's job.
        "is_in_gmail": bool(draft.gmail_draft_id),
        "created_at": draft.created_at,
    }
