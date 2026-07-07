"""
tests/unit/test_approval_gate.py — Unit tests for the HITL approval gate.
"""
import asyncio
import pytest
from datetime import datetime, timedelta

from src.approval.gate import ApprovalGate
from src.models.approval_record import ApprovalRecord
from src.models.draft import Draft
from src.config.constants import ApprovalDecision


def _make_draft(draft_id: str = "dr_test_001") -> Draft:
    return Draft(
        draft_id=draft_id,
        email_message_id="msg_001",
        thread_id="thread_001",
        subject="Re: Test",
        to="client@example.com",
        body="Test reply body.",
    )


def _make_approval(draft_id: str = "dr_test_001") -> ApprovalRecord:
    return ApprovalRecord(
        draft_id=draft_id,
        workflow_id="wf_test_001",
        timeout_at=datetime.utcnow() + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_approve_resolves_future():
    gate = ApprovalGate()
    draft = _make_draft()
    approval = _make_approval()

    async def _approve_after_delay():
        await asyncio.sleep(0.05)
        gate.approve(draft_id=draft.draft_id, reviewer="test_user")

    asyncio.create_task(_approve_after_delay())
    result = await asyncio.wait_for(
        gate.wait_for_decision(approval, draft),
        timeout=2.0
    )

    assert result.decision == ApprovalDecision.APPROVED
    assert result.reviewer == "test_user"


@pytest.mark.asyncio
async def test_reject_resolves_future():
    gate = ApprovalGate()
    draft = _make_draft("dr_test_002")
    approval = _make_approval("dr_test_002")

    async def _reject_after_delay():
        await asyncio.sleep(0.05)
        gate.reject(draft_id=draft.draft_id, reviewer="reviewer_x", reason="Tone mismatch")

    asyncio.create_task(_reject_after_delay())
    result = await asyncio.wait_for(
        gate.wait_for_decision(approval, draft),
        timeout=2.0
    )

    assert result.decision == ApprovalDecision.REJECTED
    assert result.comments == "Tone mismatch"


def test_approve_nonexistent_returns_false():
    gate = ApprovalGate()
    result = gate.approve(draft_id="nonexistent", reviewer="user")
    assert result is False


def test_reject_nonexistent_returns_false():
    gate = ApprovalGate()
    result = gate.reject(draft_id="nonexistent", reviewer="user")
    assert result is False


def test_list_pending_empty():
    gate = ApprovalGate()
    assert gate.list_pending() == []
    assert gate.pending_count == 0
