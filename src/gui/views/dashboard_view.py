"""
dashboard_view.py — Start a workflow, watch it progress.

Progress arrives through gateway.subscribe_progress(), which attaches a logging
handler. Because the asyncio loop is pumped on the Tk thread, that callback
already runs on the UI thread — no marshalling needed.
"""

from __future__ import annotations

import asyncio
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from src.gui.theme import Colors

DEFAULT_THREAD_ID = "thread_mock_001"


class DashboardView(ttk.Frame):
    def __init__(self, parent, gateway, bridge) -> None:
        super().__init__(parent, padding=12)
        self._gateway = gateway
        self._bridge = bridge
        self._unsubscribe = None

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Gmail thread ID:").pack(side=tk.LEFT)
        self._entry = ttk.Entry(controls, width=32)
        self._entry.insert(0, DEFAULT_THREAD_ID)
        self._entry.pack(side=tk.LEFT, padx=8)

        self._button = ttk.Button(controls, text="Start workflow", command=self._on_start)
        self._button.pack(side=tk.LEFT)

        self._status = ttk.Label(self, text="Idle.", foreground=Colors.TEXT_DIM)
        self._status.pack(fill=tk.X, pady=(10, 4))

        ttk.Label(self, text="Progress").pack(anchor=tk.W)
        self._log = ScrolledText(self, height=18, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 10))
        self._log.tag_config("ERROR", foreground=Colors.ERROR, font=("Consolas", 10, "bold"))
        self._log.tag_config("WARNING", foreground=Colors.WARNING, font=("Consolas", 10, "italic"))
        self._log.tag_config("INFO", foreground=Colors.TEXT)
        self._log.tag_config("TRANSITION", foreground=Colors.PRIMARY_DARK, font=("Consolas", 10, "bold"))
        self._log.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_start(self) -> None:
        thread_id = self._entry.get().strip()
        if not thread_id:
            self._set_status("Enter a thread ID first.", Colors.WARNING)
            return

        self._clear_log()
        self._button.state(["disabled"])
        self._set_status(f"Running workflow for {thread_id}…", Colors.INFO)

        self._unsubscribe = self._gateway.subscribe_progress(self._on_progress)
        self._bridge.submit(self._gateway.start_workflow(thread_id), on_done=self._on_done)

    def _on_progress(self, event) -> None:
        tag = event.level
        if "→" in event.message:
            tag = "TRANSITION"
        self._append(f"{event.timestamp:%H:%M:%S}  {event.message}", tag)
        
        if "AWAITING_APPROVAL" in event.message:
            self._append(f"{event.timestamp:%H:%M:%S}  👉 Bản nháp đã sẵn sàng! Vui lòng chuyển sang tab 'Approvals' để kiểm tra và duyệt.", "SUCCESS")

    def _on_done(self, task: asyncio.Task) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._button.state(["!disabled"])

        if task.cancelled():
            self._set_status("Workflow cancelled.", Colors.WARNING)
            return

        error = task.exception()
        if error is not None:
            # Every workflow lands here today: orchestrator.py:48 raises
            # AttributeError because the steps expose execute(), not run().
            self._set_status(f"Workflow failed: {type(error).__name__}: {error}", Colors.ERROR)
            self._append(f"\nERROR  {type(error).__name__}: {error}", "ERROR")
            return

        result = task.result()
        if result.error:
            self._set_status(f"Workflow error: {result.error}", Colors.ERROR)
        elif result.is_approved:
            self._set_status("Draft approved and sent.", Colors.SUCCESS)
        else:
            self._set_status("Draft rejected. Nothing was sent.", Colors.WARNING)

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str) -> None:
        self._status.configure(text=text, foreground=color)

    def _append(self, line: str, tag: str = "INFO") -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, line + "\n", tag)
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.configure(state=tk.DISABLED)

    def refresh(self) -> None:
        """Nothing to poll here."""
