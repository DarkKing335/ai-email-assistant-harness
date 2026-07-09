"""
config_view.py — Configuration and health.

Renders no secret: ConfigSummary carries only the last four characters of the
API key. Warnings are prominent because a reviewer approving mock data while
believing it is real is a bad failure.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.gui.theme import Colors
from src.gui.viewmodels.config_vm import config_rows, config_warnings


class ConfigView(ttk.Frame):
    def __init__(self, parent, gateway, bridge) -> None:
        super().__init__(parent, padding=12)
        self._gateway = gateway

        header = ttk.Frame(self)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Configuration", font=("", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)

        self._warnings = ttk.Label(self, text="", foreground=Colors.WARNING, wraplength=760)
        self._warnings.pack(fill=tk.X, pady=(6, 0))

        self._tree = ttk.Treeview(self, columns=("value",), show="tree headings", height=14)
        self._tree.heading("#0", text="Setting")
        self._tree.heading("value", text="Value")
        self._tree.column("#0", width=200)
        self._tree.column("value", width=460)
        self._tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.refresh()

    def refresh(self) -> None:
        summary = self._gateway.config_summary()

        self._tree.delete(*self._tree.get_children())
        for label, value in config_rows(summary):
            self._tree.insert("", tk.END, text=label, values=(value,))

        warnings = config_warnings(summary)
        self._warnings.configure(text="\n".join(f"⚠  {w}" for w in warnings))
