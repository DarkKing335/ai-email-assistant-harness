"""
bridge.py — Runs the asyncio event loop on the UI thread.

Why single-threaded, rather than a worker thread plus ``call_soon_threadsafe``:

``ApprovalGate.approve()`` calls ``future.set_result()`` synchronously, and
``asyncio.Future`` is not thread-safe. Called from a thread other than the loop's,
``set_result()`` schedules its callbacks through ``loop.call_soon()``, which in
non-debug mode neither raises nor wakes the loop's selector. Verified: the call
returns True, the UI reports "Approved!", and the workflow coroutine never
resumes. A silent hang, in the one component whose job is to be trustworthy.

So this bridge pumps the loop from the toolkit's own timer. Tk's mainloop and
asyncio share one thread, and ``gate.approve()`` from a button callback is
therefore always on the loop thread. There is no marshalling to get wrong.

``call()`` enforces that at runtime, and the bridge takes an abstract
``scheduler`` (anything with ``.after(ms, callback)`` — Tk's root satisfies it)
so that tests can drive ``tick()`` by hand with no display.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from typing import Any, Optional, Protocol

logger = logging.getLogger("email_assistant.gui.bridge")

DEFAULT_INTERVAL_MS = 20


class Scheduler(Protocol):
    """Anything that can run a callback later. ``tkinter.Tk`` satisfies this."""

    def after(self, ms: int, func: Callable[[], None]) -> Any: ...


class WrongThreadError(RuntimeError):
    """Raised when the gate would be touched from off the loop thread."""


class AsyncBridge:
    """Drives an asyncio loop from the UI toolkit's timer, on one thread."""

    def __init__(
        self,
        scheduler: Scheduler,
        interval_ms: int = DEFAULT_INTERVAL_MS,
    ) -> None:
        self._scheduler = scheduler
        self._interval = interval_ms
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._owner_thread = threading.get_ident()
        self._running = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Pump ──────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin pumping. Call once, before the toolkit's mainloop."""
        if self._running:
            return
        self._running = True
        self._reschedule()

    def tick(self) -> None:
        """Run exactly one iteration of the loop on the calling thread.

        ``call_soon(stop)`` makes ``run_forever()`` drain the ready queue once
        and return, rather than blocking. Tasks awaiting a Future simply stay
        pending until a later tick.
        """
        if self._loop.is_closed():
            return
        self._loop.call_soon(self._loop.stop)
        self._loop.run_forever()

    def _reschedule(self) -> None:
        self._scheduler.after(self._interval, self._on_tick)

    def _on_tick(self) -> None:
        if not self._running:
            return
        try:
            self.tick()
        except Exception:
            logger.exception("Unhandled error while pumping the event loop")
        self._reschedule()

    # ── Work submission ───────────────────────────────────────────────────────

    def submit(
        self,
        coro: Coroutine[Any, Any, Any],
        on_done: Optional[Callable[[asyncio.Task], None]] = None,
    ) -> asyncio.Task:
        """Schedule a coroutine. ``on_done`` receives the finished Task.

        The callback must inspect ``task.exception()`` — a workflow that raises
        (every workflow today, at orchestrator.py:48) resolves the task with the
        exception rather than crashing the UI.
        """
        self.assert_loop_thread()
        task = self._loop.create_task(coro)
        if on_done is not None:
            task.add_done_callback(on_done)
        return task

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous loop-touching call, checking thread affinity first.

        Every ``gateway.approve()`` / ``gateway.reject()`` must go through here.
        """
        self.assert_loop_thread()
        return fn(*args, **kwargs)

    def assert_loop_thread(self) -> None:
        if threading.get_ident() != self._owner_thread:
            raise WrongThreadError(
                "Attempted to touch the event loop from a foreign thread. "
                "asyncio.Future is not thread-safe: gate.approve() would return "
                "True and the workflow would never resume."
            )

    # ── Teardown ──────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Stop pumping, cancel outstanding tasks, close the loop."""
        self._running = False
        if self._loop.is_closed():
            return

        pending = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            self.tick()  # let the cancellations propagate

        self._loop.close()
        logger.info("Event loop closed (%d task(s) cancelled)", len(pending))
