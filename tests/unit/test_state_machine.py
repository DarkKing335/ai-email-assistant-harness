"""
tests/unit/test_state_machine.py — Unit tests for the workflow state machine.
"""
import pytest
from src.config.constants import WorkflowStatus
from src.workflow.engine.state_machine import WorkflowStateMachine, WorkflowTransitionError


def test_initial_state():
    sm = WorkflowStateMachine("wf_001")
    assert sm.state == WorkflowStatus.RECEIVED
    assert not sm.is_terminal


def test_happy_path_transitions():
    sm = WorkflowStateMachine("wf_002")
    transitions = [
        WorkflowStatus.INGESTED,
        WorkflowStatus.DRAFTED,
        WorkflowStatus.GUARDRAILS_PASSED,
        WorkflowStatus.AWAITING_APPROVAL,
        WorkflowStatus.APPROVED,
        WorkflowStatus.SENDING,
        WorkflowStatus.SENT,
        WorkflowStatus.AUDITED,
    ]
    for state in transitions:
        sm.transition(state)
        assert sm.state == state

    assert sm.is_terminal


def test_invalid_transition_raises():
    sm = WorkflowStateMachine("wf_003")
    with pytest.raises(WorkflowTransitionError):
        # Can't jump from RECEIVED to APPROVED
        sm.transition(WorkflowStatus.APPROVED)


def test_terminal_state_blocks_transition():
    sm = WorkflowStateMachine("wf_004")
    sm.transition(WorkflowStatus.ERROR)
    assert sm.is_terminal
    with pytest.raises(WorkflowTransitionError):
        sm.transition(WorkflowStatus.INGESTED)


def test_history_is_recorded():
    sm = WorkflowStateMachine("wf_005")
    sm.transition(WorkflowStatus.INGESTED)
    sm.transition(WorkflowStatus.DRAFTED)
    history = sm.history()
    assert history == [
        WorkflowStatus.RECEIVED,
        WorkflowStatus.INGESTED,
        WorkflowStatus.DRAFTED,
    ]


def test_guardrails_failed_is_terminal():
    sm = WorkflowStateMachine("wf_006")
    sm.transition(WorkflowStatus.INGESTED)
    sm.transition(WorkflowStatus.DRAFTED)
    sm.transition(WorkflowStatus.GUARDRAILS_FAILED)
    assert sm.is_terminal


def test_rejection_leads_to_terminated():
    sm = WorkflowStateMachine("wf_007")
    sm.transition(WorkflowStatus.INGESTED)
    sm.transition(WorkflowStatus.DRAFTED)
    sm.transition(WorkflowStatus.GUARDRAILS_PASSED)
    sm.transition(WorkflowStatus.AWAITING_APPROVAL)
    sm.transition(WorkflowStatus.REJECTED)
    sm.transition(WorkflowStatus.TERMINATED)
    assert sm.is_terminal
