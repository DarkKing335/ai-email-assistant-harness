"""
app.py — The window.

The asyncio loop is pumped from Tk's timer (see bridge.py), so the orchestrator
coroutine, the approval gate's Futures, and the Approve button all live on one
thread. That is what makes the human-in-the-loop actually close: the CLI cannot
do it, because `email process` and `email approve` are separate processes with
separate in-memory gates.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from src.gui.bridge import AsyncBridge
from src.gui.gateway import bootstrap_logging, bootstrap_session, get_gateway
from src.gui.theme import Colors
from src.gui.views.audit_view import AuditView
from src.gui.views.config_view import ConfigView
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.queue_view import QueueView

logger = logging.getLogger("email_assistant.gui.app")

TITLE = "AI Email Assistant — Human-in-the-Loop"
QUEUE_POLL_MS = 750


class EmailAssistantApp:
    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title(TITLE)
        self._root.geometry("980x640")
        self._apply_style()

        # The bridge must be constructed on the thread that will run mainloop.
        self._bridge = AsyncBridge(self._root)
        self._gateway = get_gateway()

        notebook = ttk.Notebook(self._root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._dashboard = DashboardView(notebook, self._gateway, self._bridge)
        self._queue = QueueView(notebook, self._gateway, self._bridge)
        self._audit = AuditView(notebook, self._gateway, self._bridge)
        self._config = ConfigView(notebook, self._gateway, self._bridge)

        notebook.add(self._dashboard, text="Dashboard")
        notebook.add(self._queue, text="Approvals")
        notebook.add(self._audit, text="Audit")
        notebook.add(self._config, text="Config")

        self._status = ttk.Label(
            self._root,
            text=f"Reviewer: {self._gateway.session.reviewer}",
            foreground=Colors.TEXT_DIM,
        )
        self._status.pack(anchor=tk.W, padx=12, pady=(0, 6))

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_style(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

    def _poll_queue(self) -> None:
        try:
            self._queue.refresh()
        except Exception:
            logger.exception("Failed to refresh the approval queue")
        self._root.after(QUEUE_POLL_MS, self._poll_queue)

    def _on_close(self) -> None:
        self._bridge.stop()
        self._root.destroy()

    def run(self) -> None:
        self._bridge.start()
        self._root.after(QUEUE_POLL_MS, self._poll_queue)
        self._root.mainloop()


def run() -> None:
    bootstrap_logging()
    bootstrap_session()
    EmailAssistantApp().run()
