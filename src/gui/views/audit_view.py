"""
audit_view.py — Read-only audit log.

No edit, no delete, no clear. Append-only is the guarantee.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.gui.theme import Colors
from src.gui.viewmodels.audit_vm import TIMESTAMP_WARNING, audit_rows, timestamps_reliable

COLUMNS = ("timestamp", "action", "actor", "resource", "outcome")


class AuditView(ttk.Frame):
    def __init__(self, parent, gateway, bridge) -> None:
        super().__init__(parent, padding=12)
        self._gateway = gateway

        header = ttk.Frame(self)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Audit log (read-only)", font=("", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)

        if not timestamps_reliable():
            ttk.Label(
                self, text=TIMESTAMP_WARNING, foreground=Colors.WARNING, wraplength=760
            ).pack(fill=tk.X, pady=(6, 0))

        self._tree = ttk.Treeview(self, columns=COLUMNS, show="headings", height=18)
        widths = {"timestamp": 150, "action": 170, "actor": 160, "resource": 190, "outcome": 90}
        for column in COLUMNS:
            self._tree.heading(column, text=column.title())
            self._tree.column(column, width=widths[column])
        self._tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self._tree.tag_configure("ok", foreground=Colors.SUCCESS)
        self._tree.tag_configure("bad", foreground=Colors.ERROR)

        self._empty = ttk.Label(self, text="", foreground=Colors.TEXT_DIM)
        self._empty.pack(anchor=tk.W, pady=(4, 0))

        self.refresh()

    def refresh(self) -> None:
        rows = audit_rows(self._gateway.recent_audit(limit=100))
        self._tree.delete(*self._tree.get_children())

        for row in rows:
            self._tree.insert(
                "",
                tk.END,
                values=(
                    f"{row['timestamp']:%Y-%m-%d %H:%M:%S}",
                    row["action"],
                    row["actor"],
                    row["resource"],
                    row["outcome"],
                ),
                tags=("ok" if row["ok"] else "bad",),
            )

        self._empty.configure(text="" if rows else "Audit log is empty — no workflow has completed.")
