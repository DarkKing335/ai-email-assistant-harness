"""
queue_view.py — The approval queue. This is the product.

Approve/reject go through bridge.call(), which asserts we are on the event-loop
thread before touching the gate's asyncio.Future.

There is no Send button, and this module does not import src.tools.
The reviewer approves; the orchestrator sends.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from src.gui.theme import GUARDRAIL_COLORS, Colors
from src.gui.viewmodels.queue_vm import pending_to_dict, queue_summary


class QueueView(ttk.Frame):
    def __init__(self, parent, gateway, bridge) -> None:
        super().__init__(parent, padding=12)
        self._gateway = gateway
        self._bridge = bridge
        self._rows: dict[str, dict] = {}

        self._summary = ttk.Label(self, text="", foreground=Colors.TEXT_DIM)
        self._summary.pack(fill=tk.X, pady=(0, 6))

        panes = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        # ── Left: the queue ───────────────────────────────────────────────────
        left = ttk.Frame(panes)
        self._tree = ttk.Treeview(
            left, columns=("to", "subject"), show="headings", selectmode="browse", height=14
        )
        self._tree.heading("to", text="To")
        self._tree.heading("subject", text="Subject")
        self._tree.column("to", width=180)
        self._tree.column("subject", width=220)
        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", lambda _e: self._show_selected())
        panes.add(left, weight=1)

        # ── Right: the draft ──────────────────────────────────────────────────
        right = ttk.Frame(panes, padding=(10, 0, 0, 0))

        self._subject = ttk.Label(right, text="Select a draft", font=("", 11, "bold"))
        self._subject.pack(anchor=tk.W)
        self._to = ttk.Label(right, text="", foreground=Colors.TEXT_DIM)
        self._to.pack(anchor=tk.W, pady=(0, 4))

        self._badge = ttk.Label(right, text="")
        self._badge.pack(anchor=tk.W, pady=(0, 6))

        self._body = tk.Text(right, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self._body.pack(fill=tk.BOTH, expand=True)

        self._caveats = ttk.Label(right, text="", foreground=Colors.WARNING, wraplength=440)
        self._caveats.pack(anchor=tk.W, pady=(6, 0))

        controls = ttk.Frame(right)
        controls.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(controls, text="Comment / reason:").pack(anchor=tk.W)
        self._comment = ttk.Entry(controls)
        self._comment.pack(fill=tk.X, pady=(2, 6))

        buttons = ttk.Frame(controls)
        buttons.pack(anchor=tk.W)
        self._approve = ttk.Button(buttons, text="Approve", command=self._on_approve)
        self._approve.pack(side=tk.LEFT)
        self._reject = ttk.Button(buttons, text="Reject", command=self._on_reject)
        self._reject.pack(side=tk.LEFT, padx=6)

        panes.add(right, weight=2)
        self._set_buttons(enabled=False)

    # ── Polling ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        items = self._gateway.list_pending()
        rows = {item.draft_id: pending_to_dict(item) for item in items}

        if set(rows) != set(self._rows):
            selected = self._selected_id()
            self._tree.delete(*self._tree.get_children())
            for draft_id, row in rows.items():
                self._tree.insert("", tk.END, iid=draft_id, values=(row["to"], row["subject"]))
            if selected in rows:
                self._tree.selection_set(selected)

        self._rows = rows

        summary = queue_summary(items)
        if summary["has_items"]:
            self._summary.configure(text=f"{summary['count']} draft(s) awaiting approval.")
        else:
            self._summary.configure(text=summary["empty_message"].replace("\n", "  "))
            self._clear_detail()

    # ── Detail pane ───────────────────────────────────────────────────────────

    def _selected_id(self):
        selection = self._tree.selection()
        return selection[0] if selection else None

    def _show_selected(self) -> None:
        draft_id = self._selected_id()
        row = self._rows.get(draft_id) if draft_id else None
        if row is None:
            self._clear_detail()
            return

        self._subject.configure(text=row["subject"])
        self._to.configure(text=f"To: {row['to']}")

        state = row["guardrail_state"]
        if state:
            self._badge.configure(text=row["guardrail_label"], foreground=GUARDRAIL_COLORS[state])
        else:
            self._badge.configure(text="Guardrails: unknown", foreground=Colors.TEXT_DIM)

        # BLOCKER-2: the gate exposes only a 200-character preview.
        body = row["body"] if row["body"] is not None else row["preview"]
        self._set_body(body)

        caveats = [c for c in (row["body_unavailable_reason"], row["thread_unavailable_reason"]) if c]
        self._caveats.configure(text="\n".join(caveats))
        self._set_buttons(enabled=True)

    def _clear_detail(self) -> None:
        self._subject.configure(text="Select a draft")
        self._to.configure(text="")
        self._badge.configure(text="")
        self._set_body("")
        self._caveats.configure(text="")
        self._set_buttons(enabled=False)

    def _set_body(self, text: str) -> None:
        self._body.configure(state=tk.NORMAL)
        self._body.delete("1.0", tk.END)
        self._body.insert("1.0", text)
        self._body.configure(state=tk.DISABLED)

    def _set_buttons(self, *, enabled: bool) -> None:
        can_approve = enabled and self._gateway.session.can_approve()
        can_reject = enabled and self._gateway.session.can_reject()
        self._approve.state(["!disabled"] if can_approve else ["disabled"])
        self._reject.state(["!disabled"] if can_reject else ["disabled"])

    # ── Decisions ─────────────────────────────────────────────────────────────

    def _on_approve(self) -> None:
        self._decide(self._gateway.approve, "approved")

    def _on_reject(self) -> None:
        self._decide(self._gateway.reject, "rejected")

    def _decide(self, action, verb: str) -> None:
        draft_id = self._selected_id()
        if not draft_id:
            return
        text = self._comment.get().strip()

        # bridge.call asserts loop-thread affinity before the Future is touched.
        ok = self._bridge.call(action, draft_id, text)

        if not ok:
            messagebox.showwarning(
                "Not pending",
                f"Draft {draft_id} is no longer in the approval queue.",
            )
        self._comment.delete(0, tk.END)
        self.refresh()
