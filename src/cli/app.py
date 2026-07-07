"""
app.py — AI Email Assistant Harness CLI.

Refactored from OpenCode Agent CLI.
Reuses: Typer app structure, display.py, themes.py (unchanged).
Replaced: run_agent() → run_email_workflow(); domain commands.

The existing Rich TUI components (display.py, themes.py, flow_viewer.py)
are kept verbatim — only the domain-specific commands are replaced.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Confirm, Prompt
from rich.text import Text

from . import __version__, __app_name__
from .display import (
    console,
    print_error,
    print_info,
    print_rule,
    print_success,
    print_warning,
    show_banner,
)
from .themes import Colors

# ──────────────────────────────────────────────────────────────────────────────
# Typer app
# ──────────────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name=__app_name__,
    help="AI Email Assistant Harness — Draft, Approve, Send with Human-in-the-Loop",
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

# Sub-app for `email` commands
email_app = typer.Typer(
    name="email",
    help="Email processing commands.",
    rich_markup_mode="rich",
)
app.add_typer(email_app, name="email")

# ──────────────────────────────────────────────────────────────────────────────
# Shared options
# ──────────────────────────────────────────────────────────────────────────────

ModelOpt = typer.Option(
    "gpt-4o", "--model", "-m", help="LLM model override.", show_default=True
)

# ──────────────────────────────────────────────────────────────────────────────
# `email process` — run the full workflow for a thread
# ──────────────────────────────────────────────────────────────────────────────

@email_app.command("process")
def cmd_process(
    thread_id: str = typer.Argument(..., help="Gmail thread ID to process."),
) -> None:
    """Process a Gmail email thread: fetch → draft → approve → send."""
    from .runner import run_email_workflow
    show_banner(__version__)
    asyncio.run(run_email_workflow(thread_id=thread_id))


# ──────────────────────────────────────────────────────────────────────────────
# `email demo` — run with mock data
# ──────────────────────────────────────────────────────────────────────────────

@email_app.command("demo")
def cmd_demo() -> None:
    """Run the full workflow with mock Gmail data (no credentials needed)."""
    from .runner import run_email_workflow
    show_banner(__version__)
    print_info("Running demo workflow with mock data (thread_id=thread_mock_001)")
    asyncio.run(run_email_workflow(thread_id="thread_mock_001", demo=True))


# ──────────────────────────────────────────────────────────────────────────────
# `email review` — list pending drafts
# ──────────────────────────────────────────────────────────────────────────────

@email_app.command("review")
def cmd_review() -> None:
    """Show all drafts currently awaiting human approval."""
    from rich import box as rbox
    from rich.table import Table
    from src.approval.gate import approval_gate

    pending = approval_gate.list_pending()

    if not pending:
        print_info("No drafts are currently awaiting approval.")
        return

    table = Table(
        title=f"[bold {Colors.PRIMARY}]📬  Pending Approvals[/]",
        box=rbox.ROUNDED,
        border_style=Colors.PRIMARY,
        show_header=True,
        header_style=f"bold {Colors.PRIMARY}",
    )
    table.add_column("Draft ID", style="dim", width=20)
    table.add_column("To", width=25)
    table.add_column("Subject", width=30)
    table.add_column("Preview", width=40)
    table.add_column("Requested At", width=20)

    for item in pending:
        table.add_row(
            item["draft_id"],
            item["to"],
            item["subject"],
            item["preview"],
            item["requested_at"][:19],
        )

    console.print()
    console.print(table)
    console.print()
    print_info(
        f"To approve: [bold]email approve <draft_id>[/]  |  "
        f"To reject: [bold]email reject <draft_id>[/]"
    )


# ──────────────────────────────────────────────────────────────────────────────
# `email approve` — approve a draft
# ──────────────────────────────────────────────────────────────────────────────

@email_app.command("approve")
def cmd_approve(
    draft_id: str = typer.Argument(..., help="Draft ID to approve."),
    reviewer: str = typer.Option("cli-user", "--reviewer", "-r", help="Reviewer identifier."),
    comments: str = typer.Option("", "--comments", "-c", help="Optional approval comments."),
) -> None:
    """Approve a draft and allow the email to be sent."""
    from src.approval.gate import approval_gate

    success = approval_gate.approve(draft_id=draft_id, reviewer=reviewer, comments=comments)
    if success:
        print_success(f"Draft [bold]{draft_id}[/] approved by {reviewer}. Email will be sent.")
    else:
        print_error(
            f"Draft [bold]{draft_id}[/] not found in the pending queue. "
            "Run [bold]email review[/] to see pending drafts."
        )


# ──────────────────────────────────────────────────────────────────────────────
# `email reject` — reject a draft
# ──────────────────────────────────────────────────────────────────────────────

@email_app.command("reject")
def cmd_reject(
    draft_id: str = typer.Argument(..., help="Draft ID to reject."),
    reviewer: str = typer.Option("cli-user", "--reviewer", "-r", help="Reviewer identifier."),
    reason: str = typer.Option("", "--reason", help="Reason for rejection."),
) -> None:
    """Reject a draft. The email will NOT be sent."""
    from src.approval.gate import approval_gate

    success = approval_gate.reject(draft_id=draft_id, reviewer=reviewer, reason=reason)
    if success:
        print_warning(f"Draft [bold]{draft_id}[/] rejected by {reviewer}.")
    else:
        print_error(
            f"Draft [bold]{draft_id}[/] not found in pending queue. "
            "Run [bold]email review[/] to see pending drafts."
        )


# ──────────────────────────────────────────────────────────────────────────────
# `email audit` — show recent audit events
# ──────────────────────────────────────────────────────────────────────────────

@email_app.command("audit")
def cmd_audit(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of recent events to show."),
) -> None:
    """Show recent audit log entries."""
    from rich import box as rbox
    from rich.table import Table
    from src.audit.logger import audit_logger

    events = audit_logger.read_recent(limit=limit)

    if not events:
        print_info("Audit log is empty.")
        return

    table = Table(
        title=f"[bold {Colors.PRIMARY}]📋  Recent Audit Events[/]",
        box=rbox.ROUNDED,
        border_style=Colors.PRIMARY,
        show_header=True,
        header_style=f"bold {Colors.PRIMARY}",
    )
    table.add_column("Timestamp", width=20)
    table.add_column("Action", width=22)
    table.add_column("Actor", width=18)
    table.add_column("Resource", width=22)
    table.add_column("Outcome", width=10)

    for ev in events:
        outcome_style = "green" if ev.outcome == "SUCCESS" else "red"
        table.add_row(
            ev.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            ev.action.value,
            ev.actor,
            f"{ev.resource_type}/{ev.resource_id}"[:22],
            f"[{outcome_style}]{ev.outcome}[/]",
        )

    console.print()
    console.print(table)
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# `version` command
# ──────────────────────────────────────────────────────────────────────────────

@app.command("version")
def cmd_version() -> None:
    """Show CLI version."""
    console.print(
        f"\n  [bold {Colors.PRIMARY}]{__app_name__}[/]  "
        f"[dim]v{__version__}[/dim]\n"
    )


# ──────────────────────────────────────────────────────────────────────────────
# `config` command
# ──────────────────────────────────────────────────────────────────────────────

@app.command("config")
def cmd_config() -> None:
    """Show current configuration."""
    from rich import box as rbox
    from rich.table import Table
    from src.config.settings import settings

    def mask(val: str) -> str:
        if not val:
            return "[red]NOT SET[/red]"
        if len(val) <= 12:
            return "***"
        return f"{val[:6]}{'*' * (len(val) - 10)}{val[-4:]}"

    table = Table(
        title=f"[bold {Colors.PRIMARY}]⚙  Configuration[/]",
        box=rbox.ROUNDED,
        border_style=Colors.PRIMARY,
        show_header=False,
        padding=(0, 2),
    )
    table.add_column("Key", style=f"dim {Colors.TEXT_DIM}", width=28)
    table.add_column("Value", style=Colors.TEXT)

    table.add_row("App", f"{__app_name__} v{__version__}")
    table.add_row("Environment", settings.app_env)
    table.add_row("LLM Provider", settings.llm_provider)
    table.add_row("Draft Model", settings.llm_model_draft)
    table.add_row("Summarise Model", settings.llm_model_summarize)
    table.add_row("LLM API Key", mask(settings.active_llm_api_key))
    table.add_row("Gmail User", settings.gmail_user_email)
    table.add_row("Gmail Token", "✓ Found" if settings.gmail_token_file.exists() else "✗ Missing")
    table.add_row("Database URL", settings.database_url[:40] + "...")
    table.add_row("Audit Log", settings.audit_log_path)
    table.add_row("Approval Timeout", f"{settings.approval_timeout_seconds}s")

    console.print()
    console.print(table)
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# Default callback — Interactive mode
# ──────────────────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version and exit.", is_eager=True
    ),
) -> None:
    """AI Email Assistant Harness — Human-in-the-Loop Email Agent."""
    if version:
        cmd_version()
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    # Interactive mode — show status dashboard
    show_banner(__version__)
    _show_interactive_help()


def _show_interactive_help() -> None:
    from rich import box as rbox
    from rich.table import Table
    from src.approval.gate import approval_gate

    pending = approval_gate.pending_count
    pending_label = (
        f"[bold yellow]{pending} pending[/]" if pending > 0 else "[dim]none[/dim]"
    )

    table = Table(
        box=rbox.SIMPLE,
        show_header=False,
        padding=(0, 2),
        border_style=f"dim {Colors.TEXT_MUTED}",
    )
    table.add_column("Command", style=f"bold {Colors.PRIMARY}", width=32)
    table.add_column("Description", style=f"dim {Colors.TEXT}")

    table.add_row("email process <thread_id>", "Process a Gmail thread end-to-end")
    table.add_row("email demo",                "Run a full demo workflow")
    table.add_row(f"email review  [{pending_label}]", "Show drafts awaiting your approval")
    table.add_row("email approve <draft_id>",  "Approve and send a draft")
    table.add_row("email reject <draft_id>",   "Reject a draft")
    table.add_row("email audit",               "View recent audit log")
    table.add_row("config",                    "Show current configuration")
    table.add_row("version",                   "Show CLI version")

    console.print()
    console.print(table)
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    from src.config.logging_config import configure_logging
    from src.config.settings import settings
    from src.tools.registry import build_default_registry

    configure_logging(level=settings.log_level, fmt=settings.log_format)
    build_default_registry()
    app()


if __name__ == "__main__":
    main()
