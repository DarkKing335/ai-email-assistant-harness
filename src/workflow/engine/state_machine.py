"""
state_machine.py — Enum-driven workflow state machine.

Enforces valid transitions for the email processing pipeline.
No transition is possible unless it is declared in VALID_TRANSITIONS.
Invalid transitions raise WorkflowTransitionError immediately.

Design inspired by:
  - deliberate: explicit Approval state enum
  - Email-AI-Agent: LangGraph conditional edges reimplemented as a pure Python
    state machine (no LangGraph dependency required)
"""
from __future__ import annotations

import logging
from typing import Set

from src.config.constants import WorkflowStatus

logger = logging.getLogger("email_assistant.workflow.state_machine")


class WorkflowTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


# ── Valid state transition table ──────────────────────────────────────────────
# Each key is a (from, to) pair. Any pair not in this set is forbidden.

VALID_TRANSITIONS: Set[tuple[WorkflowStatus, WorkflowStatus]] = {
    # Happy path
    (WorkflowStatus.RECEIVED,           WorkflowStatus.INGESTED),
    (WorkflowStatus.INGESTED,           WorkflowStatus.DRAFTED),
    # Input guardrails may fail before a draft is ever produced.
    (WorkflowStatus.INGESTED,           WorkflowStatus.GUARDRAILS_FAILED),
    (WorkflowStatus.DRAFTED,            WorkflowStatus.GUARDRAILS_PASSED),
    (WorkflowStatus.DRAFTED,            WorkflowStatus.GUARDRAILS_FAILED),
    (WorkflowStatus.GUARDRAILS_PASSED,  WorkflowStatus.AWAITING_APPROVAL),
    (WorkflowStatus.AWAITING_APPROVAL,  WorkflowStatus.APPROVED),
    (WorkflowStatus.AWAITING_APPROVAL,  WorkflowStatus.REJECTED),
    (WorkflowStatus.APPROVED,           WorkflowStatus.SENDING),
    (WorkflowStatus.SENDING,            WorkflowStatus.SENT),
    (WorkflowStatus.SENT,               WorkflowStatus.AUDITED),

    # Error / termination paths (any non-terminal state can go to ERROR or TERMINATED)
    (WorkflowStatus.RECEIVED,           WorkflowStatus.ERROR),
    (WorkflowStatus.INGESTED,           WorkflowStatus.ERROR),
    (WorkflowStatus.DRAFTED,            WorkflowStatus.ERROR),
    (WorkflowStatus.GUARDRAILS_PASSED,  WorkflowStatus.ERROR),
    (WorkflowStatus.AWAITING_APPROVAL,  WorkflowStatus.TERMINATED),
    (WorkflowStatus.GUARDRAILS_FAILED,  WorkflowStatus.TERMINATED),
    (WorkflowStatus.REJECTED,           WorkflowStatus.TERMINATED),
    (WorkflowStatus.SENDING,            WorkflowStatus.ERROR),
}

# Terminal states — no further transitions allowed
TERMINAL_STATES: Set[WorkflowStatus] = {
    WorkflowStatus.AUDITED,
    WorkflowStatus.TERMINATED,
    WorkflowStatus.ERROR,
    WorkflowStatus.GUARDRAILS_FAILED,
}


class WorkflowStateMachine:
    """Manages state for a single email workflow run."""

    def __init__(self, workflow_id: str) -> None:
        self.workflow_id = workflow_id
        self._state = WorkflowStatus.RECEIVED
        self._history: list[WorkflowStatus] = [WorkflowStatus.RECEIVED]

    @property
    def state(self) -> WorkflowStatus:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    def transition(self, new_state: WorkflowStatus) -> None:
        """Attempt a state transition. Raises WorkflowTransitionError if invalid."""
        if self.is_terminal:
            raise WorkflowTransitionError(
                f"Workflow {self.workflow_id} is in terminal state "
                f"{self._state.value} — no further transitions allowed"
            )

        pair = (self._state, new_state)
        if pair not in VALID_TRANSITIONS:
            raise WorkflowTransitionError(
                f"Invalid transition: {self._state.value} → {new_state.value} "
                f"for workflow {self.workflow_id}"
            )

        logger.info(
            "Workflow %s: %s → %s",
            self.workflow_id,
            self._state.value,
            new_state.value,
        )
        self._state = new_state
        self._history.append(new_state)

    def history(self) -> list[WorkflowStatus]:
        return list(self._history)

    def __repr__(self) -> str:
        return f"<WorkflowStateMachine id={self.workflow_id!r} state={self._state.value}>"
