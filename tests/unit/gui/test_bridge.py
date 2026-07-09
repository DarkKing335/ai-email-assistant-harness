"""
tests/unit/gui/test_bridge.py — The event-loop bridge, headless.

No Tk. AsyncBridge takes any object with ``.after(ms, cb)``, so these tests
drive ``tick()`` by hand.

The important test here is test_real_approval_gate_resolves_on_the_loop_thread:
it wires the *real* ApprovalGate to the *real* bridge and proves the workflow
coroutine actually resumes. That is the failure mode that would otherwise hang
the GUI silently.
"""

import asyncio
import threading

import pytest

from src.gui.bridge import AsyncBridge, WrongThreadError
from src.models.approval_record import ApprovalRecord
from src.models.draft import Draft


class FakeScheduler:
    """Records callbacks instead of running them, so tests control the clock."""

    def __init__(self):
        self.scheduled = []

    def after(self, ms, func):
        self.scheduled.append((ms, func))


@pytest.fixture
def bridge():
    b = AsyncBridge(FakeScheduler())
    yield b
    if not b.loop.is_closed():
        b.stop()


def _pump(bridge, times=5):
    for _ in range(times):
        bridge.tick()


# ── The failure mode this design exists to prevent ────────────────────────────

def test_real_approval_gate_resolves_on_the_loop_thread(bridge):
    from src.approval.gate import ApprovalGate

    gate = ApprovalGate()
    draft = Draft(draft_id="dr_probe", to="client@example.com", body="Hello")
    record = ApprovalRecord(draft_id="dr_probe")
    captured = {}

    async def workflow():
        captured["record"] = await gate.wait_for_decision(record, draft)

    bridge.submit(workflow())
    bridge.tick()

    # ApprovalStep has parked on the Future.
    assert gate.pending_count == 1

    # The Approve button, on the UI thread == the loop thread.
    assert bridge.call(gate.approve, "dr_probe", reviewer="alice@example.com") is True

    _pump(bridge)

    assert "record" in captured, "workflow never resumed — the gate silently hung"
    assert captured["record"].is_approved is True
    assert captured["record"].reviewer == "alice@example.com"
    assert gate.pending_count == 0


def test_real_approval_gate_reject_resolves(bridge):
    from src.approval.gate import ApprovalGate

    gate = ApprovalGate()
    draft = Draft(draft_id="dr_probe", body="Hello")
    captured = {}

    async def workflow():
        captured["record"] = await gate.wait_for_decision(ApprovalRecord(draft_id="dr_probe"), draft)

    bridge.submit(workflow())
    bridge.tick()
    bridge.call(gate.reject, "dr_probe", reviewer="bob", reason="wrong date")
    _pump(bridge)

    assert captured["record"].is_approved is False
    assert captured["record"].comments == "wrong date"


def test_touching_the_loop_from_another_thread_is_refused(bridge):
    errors = []

    def from_other_thread():
        try:
            bridge.call(lambda: None)
        except WrongThreadError as exc:
            errors.append(exc)

    t = threading.Thread(target=from_other_thread)
    t.start()
    t.join()

    assert len(errors) == 1, "a foreign thread was allowed to touch the loop"


# ── Pump mechanics ────────────────────────────────────────────────────────────

def test_tick_drains_ready_callbacks_without_blocking(bridge):
    done = []

    async def work():
        done.append("ran")

    bridge.submit(work())
    bridge.tick()
    assert done == ["ran"]


def test_tick_does_not_block_on_a_pending_future(bridge):
    """A parked coroutine must not stall the UI."""
    fut = bridge.loop.create_future()
    resumed = []

    async def waiter():
        await fut
        resumed.append(True)

    bridge.submit(waiter())
    _pump(bridge, 3)          # would hang here if tick() blocked
    assert resumed == []

    bridge.call(fut.set_result, None)
    _pump(bridge)
    assert resumed == [True]


def test_submit_surfaces_exceptions_through_the_task(bridge):
    """orchestrator.run() raises AttributeError today; the UI must not crash."""
    captured = {}

    async def boom():
        raise AttributeError("'IngestStep' object has no attribute 'run'")

    bridge.submit(boom(), on_done=lambda t: captured.update(exc=t.exception()))
    _pump(bridge)

    assert isinstance(captured["exc"], AttributeError)


def test_start_schedules_a_tick():
    scheduler = FakeScheduler()
    b = AsyncBridge(scheduler, interval_ms=7)
    b.start()
    assert b.is_running
    assert scheduler.scheduled and scheduler.scheduled[0][0] == 7
    b.stop()


def test_start_is_idempotent():
    scheduler = FakeScheduler()
    b = AsyncBridge(scheduler)
    b.start()
    b.start()
    assert len(scheduler.scheduled) == 1
    b.stop()


def test_stop_cancels_pending_tasks_and_closes_the_loop(bridge):
    async def forever():
        await asyncio.sleep(3600)

    bridge.submit(forever())
    bridge.tick()
    bridge.stop()

    assert bridge.loop.is_closed()
    assert bridge.is_running is False


def test_tick_after_close_is_a_no_op(bridge):
    bridge.stop()
    bridge.tick()  # must not raise


def test_stop_is_idempotent(bridge):
    bridge.stop()
    bridge.stop()
