"""
tests/unit/gui/test_gateway.py — The gateway against fakes.

No Gmail account, no LLM key, no working orchestrator. That is the point: the
orchestrator currently raises AttributeError on its first step (BLOCKER-5), and
the gateway still has to be provably correct.
"""

import logging
from datetime import datetime

import pytest

from src.config.constants import UserRole, WorkflowStatus
from src.gui.gateway import Gateway, _parse_iso
from src.gui.session import Session
from src.models.approval_record import ApprovalRecord
from src.models.draft import Draft


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeGate:
    """Mirrors ApprovalGate's real surface: no get_pending (BLOCKER-2)."""

    def __init__(self, pending=None):
        self._pending = pending or []
        self.calls = []

    def list_pending(self):
        return list(self._pending)

    def approve(self, draft_id, reviewer, comments=""):
        self.calls.append(("approve", draft_id, reviewer, comments))
        return True

    def reject(self, draft_id, reviewer, reason=""):
        self.calls.append(("reject", draft_id, reviewer, reason))
        return True

    @property
    def pending_count(self):
        return len(self._pending)


class FutureGate(FakeGate):
    """ApprovalGate once BLOCKER-2 is fixed: exposes (ApprovalRecord, Draft)."""

    def __init__(self, pending=None, draft=None):
        super().__init__(pending)
        self._draft = draft

    def get_pending(self, draft_id):
        if self._draft is None or draft_id != self._draft.draft_id:
            return None
        return (ApprovalRecord(draft_id=draft_id), self._draft)


class FakeAudit:
    def __init__(self, events=None):
        self.events = events or []

    def read_recent(self, limit=50):
        return self.events[:limit]


class FakeContext:
    """A WorkflowContext with only the fields that actually exist.

    Deliberately has no ``error``, ``approval`` or usable ``status`` attribute,
    so a gateway that reached for them would blow up here the way
    cli/runner.py:92 blows up at runtime.
    """

    __slots__ = ("workflow_id", "thread_id", "draft", "email_thread", "is_approved", "metadata")

    def __init__(self, **kwargs):
        self.workflow_id = kwargs.get("workflow_id", "wf_test")
        self.thread_id = kwargs.get("thread_id", "th_test")
        self.draft = kwargs.get("draft")
        self.email_thread = kwargs.get("email_thread")
        self.is_approved = kwargs.get("is_approved", False)
        self.metadata = kwargs.get("metadata", {})


class FakeOrchestrator:
    def __init__(self, ctx):
        self._ctx = ctx

    async def run(self, thread_id):
        return self._ctx


def _pending_raw(draft_id="dr_test", **overrides):
    raw = {
        "draft_id": draft_id,
        "to": "client@example.com",
        "subject": "Re: Timeline",
        "preview": "Dear Client, ...",
        "requested_at": "2026-07-10T09:00:00",
        "timeout_at": "2026-07-10T10:00:00",
    }
    raw.update(overrides)
    return raw


def _gateway(gate=None, audit=None, session=None, ctx=None):
    return Gateway(
        gate=gate or FakeGate(),
        audit=audit or FakeAudit(),
        session=session or Session(reviewer="alice@example.com"),
        orchestrator_factory=lambda: FakeOrchestrator(ctx or FakeContext()),
    )


@pytest.fixture(autouse=True)
def enable_progress_logging():
    """The "email_assistant" logger inherits root's WARNING level, so INFO
    records are dropped at the source unless something lowers it. In the app
    that is ``configure_logging()``; here it is this fixture."""
    log = logging.getLogger("email_assistant")
    previous = log.level
    log.setLevel(logging.INFO)
    yield
    log.setLevel(previous)


# ── Identity cannot be forged ─────────────────────────────────────────────────

def test_approve_uses_the_session_identity():
    gate = FakeGate()
    gw = _gateway(gate=gate, session=Session(reviewer="alice@example.com"))
    assert gw.approve("dr_test", comments="ok") is True
    assert gate.calls == [("approve", "dr_test", "alice@example.com", "ok")]


def test_reject_uses_the_session_identity():
    gate = FakeGate()
    gw = _gateway(gate=gate, session=Session(reviewer="bob@example.com"))
    gw.reject("dr_test", reason="wrong date")
    assert gate.calls == [("reject", "dr_test", "bob@example.com", "wrong date")]


def test_caller_cannot_pass_a_reviewer():
    gw = _gateway()
    with pytest.raises(TypeError):
        gw.approve("dr_test", reviewer="mallory@evil.com")  # type: ignore[call-arg]


# ── Permissions socket ────────────────────────────────────────────────────────

def test_approval_allowed_while_permissions_are_unimplemented():
    gw = _gateway(session=Session(reviewer="alice", role=None))
    assert gw.approve("dr_test") is True


def test_operator_cannot_approve_once_roles_exist():
    gw = _gateway(session=Session(reviewer="alice", role=UserRole.OPERATOR))
    with pytest.raises(PermissionError):
        gw.approve("dr_test")


def test_reviewer_can_approve_once_roles_exist():
    gw = _gateway(session=Session(reviewer="alice", role=UserRole.REVIEWER))
    assert gw.approve("dr_test") is True


# ── WorkflowContext projection ────────────────────────────────────────────────

def test_result_reads_error_from_metadata_not_ctx_error():
    ctx = FakeContext(metadata={"error": "IngestStep exploded"})
    result = Gateway._to_result(ctx)
    assert result.error == "IngestStep exploded"


def test_result_reads_approval_from_metadata_not_ctx_approval():
    record = ApprovalRecord(draft_id="dr_test")
    ctx = FakeContext(metadata={"approval_record": record})
    assert Gateway._to_result(ctx).approval is record


def test_result_uses_email_thread_not_thread():
    # DraftStep reads ctx.thread and crashes; the field is ctx.email_thread.
    ctx = FakeContext(email_thread="THREAD")
    assert Gateway._to_result(ctx).thread == "THREAD"


def test_result_of_a_clean_context_has_no_error():
    result = Gateway._to_result(FakeContext())
    assert result.error is None
    assert result.approval is None
    assert result.is_approved is False


async def test_start_workflow_projects_the_context():
    ctx = FakeContext(workflow_id="wf_42", is_approved=True)
    gw = _gateway(ctx=ctx)
    result = await gw.start_workflow("th_test")
    assert result.workflow_id == "wf_42"
    assert result.is_approved is True


# ── Pending queue ─────────────────────────────────────────────────────────────

def test_list_pending_parses_iso_timestamps():
    gw = _gateway(gate=FakeGate([_pending_raw()]))
    item = gw.list_pending()[0]
    assert item.requested_at == datetime(2026, 7, 10, 9, 0, 0)
    assert item.timeout_at == datetime(2026, 7, 10, 10, 0, 0)


def test_list_pending_tolerates_a_missing_timeout():
    gw = _gateway(gate=FakeGate([_pending_raw(timeout_at=None)]))
    assert gw.list_pending()[0].timeout_at is None


def test_pending_draft_is_none_while_the_gate_hides_it():
    # BLOCKER-2: today's ApprovalGate has no get_pending.
    gw = _gateway(gate=FakeGate([_pending_raw()]))
    item = gw.list_pending()[0]
    assert item.draft is None
    assert item.thread is None


def test_pending_draft_appears_when_the_gate_grows_get_pending():
    """Forward compatibility: the fix lands in Ring 2, not here."""
    draft = Draft(draft_id="dr_test", body="Full body")
    gw = _gateway(gate=FutureGate([_pending_raw()], draft=draft))
    assert gw.list_pending()[0].draft is draft


def test_pending_draft_is_none_when_get_pending_raises():
    class Broken(FakeGate):
        def get_pending(self, draft_id):
            raise RuntimeError("boom")

    gw = _gateway(gate=Broken([_pending_raw()]))
    assert gw.list_pending()[0].draft is None


def test_pending_count():
    gw = _gateway(gate=FakeGate([_pending_raw(), _pending_raw("dr_2")]))
    assert gw.pending_count() == 2


# ── Audit and state ───────────────────────────────────────────────────────────

def test_recent_audit_passes_the_limit_through():
    gw = _gateway(audit=FakeAudit(["a", "b", "c"]))
    assert gw.recent_audit(limit=2) == ["a", "b"]


def test_workflow_states_covers_the_whole_enum():
    assert Gateway.workflow_states() == list(WorkflowStatus)


def test_workflow_history_is_unavailable():
    # BLOCKER-1: the state machine is a local in orchestrator.run().
    assert _gateway().workflow_history() is None


# ── Progress ──────────────────────────────────────────────────────────────────

def test_subscribe_progress_receives_log_records():
    gw = _gateway()
    seen = []
    unsubscribe = gw.subscribe_progress(seen.append)
    try:
        logging.getLogger("email_assistant.workflow").info("IngestStep: fetched thread")
    finally:
        unsubscribe()

    assert len(seen) == 1
    assert seen[0].message == "IngestStep: fetched thread"
    assert seen[0].level == "INFO"


def test_unsubscribe_stops_delivery_and_is_idempotent():
    gw = _gateway()
    seen = []
    unsubscribe = gw.subscribe_progress(seen.append)
    unsubscribe()
    unsubscribe()  # must not raise
    logging.getLogger("email_assistant.workflow").info("ignored")
    assert seen == []


def test_a_failing_callback_never_breaks_logging():
    gw = _gateway()

    def explode(_event):
        raise ValueError("bad widget")

    unsubscribe = gw.subscribe_progress(explode)
    try:
        logging.getLogger("email_assistant.workflow").info("still fine")
    finally:
        unsubscribe()


# ── Helpers ───────────────────────────────────────────────────────────────────

def test_parse_iso_handles_none_and_garbage():
    assert _parse_iso(None) is None
    assert _parse_iso("") is None
    assert _parse_iso("not-a-date") is None
    assert _parse_iso("2026-07-10T09:00:00") == datetime(2026, 7, 10, 9, 0, 0)
