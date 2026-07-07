"""
display.py — Tất cả Rich TUI components cho OpenCode Agent CLI.

Mỗi hàm là một "widget" độc lập, in ra console.
Tất cả dùng màu sắc từ themes.py.
"""

from __future__ import annotations

import io
import os
import sys
import time
from typing import Any, Dict, List, Optional

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .themes import Colors, THEME, PanelStyle

def _make_console() -> Console:
    """Tạo Console với UTF-8 encoding trên Windows."""
    if sys.platform == "win32":
        # Bật UTF-8 mode cho Windows terminal
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # CP_UTF8
        except Exception:
            pass
        # Dùng sys.stdout với UTF-8 wrapping
        try:
            utf8_stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            return Console(theme=THEME, highlight=False, file=utf8_stdout, force_terminal=True)
        except AttributeError:
            # sys.stdout không có .buffer (ví dụ khi bị redirect)
            return Console(theme=THEME, highlight=False)
    return Console(theme=THEME, highlight=False)


console = _make_console()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Banner
# ──────────────────────────────────────────────────────────────────────────────

ASCII_LOGO = "\n".join(
    [
        " ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗",
        "██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝",
        "██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║   ██║██║  ██║█████╗  ",
        "██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║   ██║██║  ██║██╔══╝  ",
        "╚██████╔╝██║     ███████╗██║ ╚████║╚██████╗╚██████╔╝██████╔╝███████╗",
        " ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
    ]
)

OPENCODE_MASCOT = "\n".join(
    [
        " __         __",
        "/  \\.-\"\"\"-./  \\",
        "\\    -   -    /",
        " |   o   o   |",
        " \\  .-'''-.  /",
        " '-\\__Y__/-'",
        " `---`",
    ]
)


def show_banner(version: str = "1.0.0") -> None:
    """Hiển thị banner đẹp khi khởi động CLI."""

    logo_lines = ASCII_LOGO.split("\n")
    logo_width = max(len(line) for line in logo_lines)

    mascot_lines = OPENCODE_MASCOT.split("\n")

    # Logo Text
    logo_text = Text(no_wrap=True)
    for i, line in enumerate(logo_lines):
        color = [
            Colors.PRIMARY_DARK,
            Colors.PRIMARY,
            Colors.PRIMARY_LIGHT,
            Colors.PRIMARY_LIGHT,
            Colors.PRIMARY,
            Colors.PRIMARY_DARK,
        ][i % 6]
        logo_text.append(line + "\n", style=f"bold {color}")

    badge = "[ AGENT ]"
    logo_text.append(" " * (logo_width - len(badge)) + badge, style=f"bold {Colors.ACCENT_LIGHT}")

    # Mascot Text
    mascot_text = Text(no_wrap=True)
    for line in mascot_lines:
        mascot_text.append(line + "\n", style=f"bold {Colors.ACCENT}")

    # Header Layout
    header = Table.grid(padding=(0, 4))
    header.add_column(justify="center", vertical="middle", no_wrap=True)
    header.add_column(justify="left", vertical="middle", no_wrap=True)
    header.add_row(mascot_text, logo_text)

    # Sub-title
    subtitle = Text(justify="center")
    subtitle.append("✨ AI-powered Code Generation & Testing Agent ✨\n\n", style=f"bold {Colors.TEXT}")
    
    for j, tech in enumerate(["Python", "LangGraph", "Gemini"]):
        if j:
            subtitle.append("  •  ", style=f"dim {Colors.TEXT_MUTED}")
        subtitle.append(tech, style=f"bold {Colors.PRIMARY_LIGHT}")
    
    subtitle.append(f"\n\nVersion {version}", style=f"dim {Colors.TEXT_DIM}")

    # Overall Content Layout
    content = Table.grid(padding=(1, 0))
    content.add_column(justify="center")
    content.add_row(header)
    content.add_row(Rule(style=f"dim {Colors.PRIMARY_DARK}"))
    content.add_row(subtitle)

    panel = Panel(
        Align.center(content),
        border_style=Colors.PRIMARY,
        box=box.ROUNDED,
        padding=(1, 4),
    )

    console.print()
    console.print(panel)
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Task Panel
# ──────────────────────────────────────────────────────────────────────────────

def show_task_panel(requirement: str, task_id: str = "", model: str = "gemini-2.5-flash") -> None:
    """Hiển thị panel thông tin task đang được xử lý."""

    content = Text()
    content.append("  >>  ", style=f"bold {Colors.PRIMARY}")
    content.append(requirement, style=f"bold {Colors.TEXT}")
    content.append("\n\n")

    meta = Text()
    if task_id:
        meta.append("  Task ID  ", style=f"dim {Colors.TEXT_DIM}")
        meta.append(task_id[:16] + "...", style=Colors.ACCENT_LIGHT)
        meta.append("   ", style="")

    meta.append("  Model  ", style=f"dim {Colors.TEXT_DIM}")
    meta.append(model, style=f"{Colors.PRIMARY}")

    content.append_text(meta)

    console.print(
        Panel(
            content,
            title=f"[bold {Colors.PRIMARY}]◆ Task[/]",
            border_style=Colors.PRIMARY,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Node Step Indicator (static — dùng sau khi node hoàn thành)
# ──────────────────────────────────────────────────────────────────────────────

NODE_INFO = {
    1: ("Node 1", "Generator", Colors.NODE_1),
    2: ("Node 2", "Executor",  Colors.NODE_2),
    3: ("Node 3", "Router",    Colors.NODE_3),
}

def _node_label(node_num: int, status: str, detail: str = "", elapsed: float = 0.0) -> Text:
    """
    status: 'pending' | 'running' | 'done' | 'error'
    """
    label, role, color = NODE_INFO[node_num]

    t = Text()

    if status == "pending":
        t.append("  [ ]  ", style=f"dim {Colors.TEXT_MUTED}")
        t.append(f"{label} - {role}", style=f"dim {Colors.TEXT_DIM}")
    elif status == "running":
        t.append("  [~]  ", style=f"bold {color}")
        t.append(f"{label} - {role}  ", style=f"bold {color}")
        if detail:
            t.append(detail, style=f"italic {Colors.TEXT_DIM}")
    elif status == "done":
        t.append("  [+]  ", style=f"bold {Colors.SUCCESS}")
        t.append(f"{label} - {role}  ", style=f"bold {Colors.TEXT}")
        if detail:
            t.append(detail, style=Colors.SUCCESS)
        if elapsed:
            t.append(f"  ({elapsed:.1f}s)", style=f"dim {Colors.TEXT_DIM}")
    elif status == "error":
        t.append("  [x]  ", style=f"bold {Colors.ERROR}")
        t.append(f"{label} - {role}  ", style=f"bold {Colors.TEXT}")
        if detail:
            t.append(detail, style=Colors.ERROR)
        if elapsed:
            t.append(f"  ({elapsed:.1f}s)", style=f"dim {Colors.TEXT_DIM}")

    return t


def print_node_done(node_num: int, detail: str = "", elapsed: float = 0.0) -> None:
    """In dòng trạng thái DONE cho một node."""
    console.print(_node_label(node_num, "done", detail, elapsed))


def print_node_error(node_num: int, detail: str = "", elapsed: float = 0.0) -> None:
    """In dòng trạng thái ERROR cho một node."""
    console.print(_node_label(node_num, "error", detail, elapsed))


# ──────────────────────────────────────────────────────────────────────────────
# 4. Retry Indicator
# ──────────────────────────────────────────────────────────────────────────────

def show_retry_banner(retry_count: int, max_retries: int, reason: str = "") -> None:
    """Hiển thị thông báo khi agent retry."""
    dots_done = "*" * retry_count
    dots_left = "." * (max_retries - retry_count)
    bar = f"  [{dots_done}{dots_left}]"

    t = Text()
    t.append("\n  [~]  ", style=f"bold {Colors.WARNING}")
    t.append(f"Retry {retry_count}/{max_retries}  ", style=f"bold {Colors.WARNING}")
    t.append(bar, style=Colors.WARNING)
    if reason:
        t.append(f"\n       {reason[:120]}", style=f"dim {Colors.TEXT_DIM}")
    t.append("\n")

    console.print(t)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Code Panel
# ──────────────────────────────────────────────────────────────────────────────

def show_code_panel(code: str, title: str = "Generated Code") -> None:
    """Hiển thị code với syntax highlighting đẹp."""
    if not code or not code.strip():
        console.print(f"  [dim]No code to display.[/dim]")
        return

    syntax = Syntax(
        code,
        "python",
        theme="one-dark",        # dark theme đẹp
        line_numbers=True,
        word_wrap=True,
        background_color="#1E1E2E",
    )

    console.print(
        Panel(
            syntax,
            title=f"[bold {Colors.ACCENT}]</> {title}[/]",
            border_style=Colors.ACCENT,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Test Results Table
# ──────────────────────────────────────────────────────────────────────────────

def show_test_results(test_cases: List[Dict[str, Any]]) -> None:
    """Hiển thị test cases dạng bảng với pass/fail rõ ràng."""
    if not test_cases:
        console.print(f"  [dim {Colors.TEXT_DIM}]  ─ No test cases generated.[/]")
        return

    passed = sum(1 for tc in test_cases if tc.get("passed", False))
    total = len(test_cases)
    all_pass = passed == total

    status_color = Colors.SUCCESS if all_pass else Colors.ERROR
    status_icon  = "[OK]" if all_pass else "[!!]"
    title_str    = f"[bold {status_color}]{status_icon}  Test Results ({passed}/{total} passed)[/]"

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=status_color,
        header_style=f"bold {status_color}",
        show_header=True,
        show_lines=False,
        pad_edge=True,
        padding=(0, 1),
    )

    table.add_column("#",        style=f"dim {Colors.TEXT_DIM}", width=4,  justify="center")
    table.add_column("Input",    style=Colors.TEXT,              min_width=20)
    table.add_column("Expected", style=f"dim {Colors.TEXT}",     min_width=14)
    table.add_column("Actual",   style=Colors.TEXT,              min_width=14)
    table.add_column("Status",   width=8,                        justify="center")

    for i, tc in enumerate(test_cases, start=1):
        inp      = tc.get("input", {})
        expected = tc.get("expected_output", "")
        actual   = tc.get("actual_output", "")
        ok       = tc.get("passed", False)

        # Format input nicely
        if isinstance(inp, dict):
            inp_str = ", ".join(f"{k}={repr(v)}" for k, v in inp.items())
        else:
            inp_str = str(inp)

        # Truncate long values
        def trunc(s: Any, n: int = 30) -> str:
            s = str(s)
            return s if len(s) <= n else s[:n - 1] + "..."

        row_style = ""  # default
        status_cell = Text("PASS", style=f"bold {Colors.SUCCESS}") if ok \
                 else Text("FAIL", style=f"bold {Colors.ERROR}")

        table.add_row(
            str(i),
            trunc(inp_str, 35),
            trunc(expected, 20),
            trunc(actual, 20),
            status_cell,
            style=f"on #1a1a2e" if not ok else "",
        )

    console.print(
        Panel(
            table,
            title=title_str,
            border_style=status_color,
            box=box.ROUNDED,
            padding=(0, 0),
        )
    )
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# 7. Final Result Summary
# ──────────────────────────────────────────────────────────────────────────────

def show_final_result(
    is_success: bool,
    retry_count: int,
    message: str = "",
    total_duration: float = 0.0,
    task_id: str = "",
) -> None:
    """Hiển thị summary cuối cùng của toàn bộ run."""

    if is_success:
        icon   = "[+]"
        color  = Colors.SUCCESS
        status = "THANH CONG"
        rule_style = Colors.SUCCESS
    else:
        icon   = "[-]"
        color  = Colors.ERROR
        status = "THAT BAI"
        rule_style = Colors.ERROR

    content = Text()
    content.append(f"  {icon}  ", style=f"bold {color}")
    content.append(f"{status}", style=f"bold {color}")


    if message:
        content.append(f"\n  {message}", style=f"dim {Colors.TEXT}")

    content.append(f"\n\n  Số lần thử:   ", style=f"dim {Colors.TEXT_DIM}")
    content.append(f"{retry_count + 1}", style=f"bold {Colors.TEXT}")

    if total_duration:
        content.append(f"\n  Thời gian:    ", style=f"dim {Colors.TEXT_DIM}")
        content.append(f"{total_duration:.2f}s", style=f"bold {Colors.TEXT}")

    if task_id:
        content.append(f"\n  Task ID:      ", style=f"dim {Colors.TEXT_DIM}")
        content.append(task_id[:16] + "...", style=f"{Colors.ACCENT_LIGHT}")

    # AC-03: Thong bao hoc tap than thien khi that bai
    if not is_success:
        content.append(f"\n\n  ", style="")
        content.append(
            "Agent chua tim ra giai phap toi uu sau nhieu lan thu. "
            "Day la code hien tai va log loi de ban cung nghien cuu nhe!",
            style=f"italic {Colors.WARNING}",
        )
        content.append(f"\n\n  Goi y cho hoc sinh:", style=f"bold {Colors.INFO}")
        content.append(
            f"\n    - Xem code trong panel phia tren"
            f"\n    - Xem log loi trong bang Test Results"
            f"\n    - Go /flow  de xem lich su tung retry"
            f"\n    - Go /patch de xem chi tiet thay doi cuoi",
            style=f"dim {Colors.TEXT}",
        )

    # AC-02: Thong bao tu sua thanh cong
    if is_success and retry_count > 0:
        content.append(f"\n\n  Agent da tu sua ", style=f"bold {Colors.SUCCESS}")
        content.append(f"{retry_count} lan", style=f"bold {Colors.WARNING}")
        content.append(f" de dat duoc ket qua dung!", style=f"bold {Colors.SUCCESS}")
        content.append(
            f"\n     Go /flow de xem lich su debug chi tiet.",
            style=f"dim {Colors.TEXT_DIM}",
        )

    console.print()
    console.print(
        Panel(
            content,
            title=f"[bold {color}]Ket Qua[/]",
            border_style=color,
            box=box.DOUBLE_EDGE,
            padding=(0, 1),
        )
    )
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# 8. Divider / Rule
# ──────────────────────────────────────────────────────────────────────────────

def print_rule(title: str = "") -> None:
    console.print(Rule(title, style=f"dim {Colors.TEXT_MUTED}"))


# ──────────────────────────────────────────────────────────────────────────────
# 9. Quick message helpers
# ──────────────────────────────────────────────────────────────────────────────

def print_success(msg: str) -> None:
    console.print(f"\n  [bold {Colors.SUCCESS}][+][/]  {msg}\n")


def print_error(msg: str) -> None:
    console.print(f"\n  [bold {Colors.ERROR}][x][/]  [bold]{msg}[/bold]\n")


def print_warning(msg: str) -> None:
    console.print(f"\n  [bold {Colors.WARNING}][!][/]  {msg}\n")


def print_info(msg: str) -> None:
    console.print(f"  [bold {Colors.INFO}][i][/]  [dim]{msg}[/dim]")


# ──────────────────────────────────────────────────────────────────────────────
# 10. Live Progress builder (dùng trong runner.py)
# ──────────────────────────────────────────────────────────────────────────────

def make_node_progress() -> Progress:
    """Tao Progress object de dung trong context manager."""
    return Progress(
        SpinnerColumn(spinner_name="dots", style=f"bold {Colors.PRIMARY}"),
        TextColumn("{task.description}", markup=True),
        TimeElapsedColumn(),
        console=console,
        transient=False,
        expand=False,
    )
