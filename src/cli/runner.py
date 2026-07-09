"""
runner.py — Email workflow runner with Rich live output.

Refactored from OpenCode Agent runner.
Reuses: Rich Progress, Live display, _ProgressCapture log handler.
Replaced: run_agent() code-generation logic → run_email_workflow() email pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from rich.live import Live
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text

from .display import (
    console,
    print_error,
    print_info,
    print_rule,
    print_success,
    print_warning,
)
from .themes import Colors

# ──────────────────────────────────────────────────────────────────────────────
# Log capture for live display (reused from original runner)
# ──────────────────────────────────────────────────────────────────────────────

class _ProgressCapture(logging.Handler):
    """Intercept log records and update the Rich progress description."""

    def __init__(self, progress: Progress, task_id) -> None:
        super().__init__()
        self._progress = progress
        self._task_id = task_id

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._progress.update(self._task_id, description=msg[:90])


# ──────────────────────────────────────────────────────────────────────────────
# Main workflow runner
# ──────────────────────────────────────────────────────────────────────────────

async def run_email_workflow(thread_id: str, demo: bool = False) -> None:
    """Run the full email workflow for a thread and display Rich live progress."""
    from src.workflow.engine.orchestrator import EmailWorkflowOrchestrator
    from src.config.constants import WorkflowStatus

    orchestrator = EmailWorkflowOrchestrator()

    progress = Progress(
        SpinnerColumn(style=Colors.PRIMARY),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    )
    task_id = progress.add_task("Starting workflow...", total=None)

    log_handler = _ProgressCapture(progress, task_id)
    log_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger("email_assistant")
    root_logger.addHandler(log_handler)

    start = time.perf_counter()

    try:
        with Live(progress, console=console, refresh_per_second=10):
            progress.update(task_id, description=f"Processing thread [bold]{thread_id}[/]...")
            ctx = await orchestrator.run(thread_id)
    finally:
        root_logger.removeHandler(log_handler)

    elapsed = time.perf_counter() - start
    _display_result(ctx, elapsed)


def _display_result(ctx, elapsed: float) -> None:
    """Display the final result of a workflow run."""
    print_rule()
    console.print()

    error = ctx.metadata.get("error")
    if error:
        print_error(f"Workflow [bold]{ctx.workflow_id}[/] failed: {error}")
        return

    # Draft created
    if ctx.draft:
        draft = ctx.draft
        body = (
            f"[dim]To:[/]      {rich_escape(draft.to)}\n"
            f"[dim]Subject:[/] {rich_escape(draft.subject)}\n\n"
            f"{rich_escape(draft.preview)}..."
        )

        # Surface guardrail flags so the reviewer sees WHY approval is needed.
        flags = list(ctx.metadata.get("guardrail_escalations", []))
        if draft.pii_detected:
            flags.append("PII redacted in body")
        if flags:
            body += "\n\n[bold yellow]⚠ Guardrail flags:[/]\n" + "\n".join(
                f"  [yellow]•[/] {rich_escape(f)}" for f in flags
            )

        console.print(
            Panel(
                body,
                title=f"[bold {Colors.PRIMARY}]📝 Draft Generated[/]",
                border_style=Colors.WARNING if flags else Colors.PRIMARY,
                expand=False,
            )
        )

    # Approval result
    approval = ctx.metadata.get("approval_record")
    if approval:
        if approval.is_approved:
            print_success(
                f"Draft approved by [bold]{approval.reviewer}[/] → Email sent!"
            )
        else:
            print_warning(
                f"Draft rejected by [bold]{approval.reviewer}[/]. "
                f"Reason: {approval.comments or 'No reason given'}"
            )
    else:
        print_info(
            f"Draft [bold]{ctx.draft.draft_id}[/] is awaiting approval.\n"
            f"  Run: [bold {Colors.PRIMARY}]email approve {ctx.draft.draft_id}[/]  "
            f"or  [bold]email reject {ctx.draft.draft_id}[/]"
        )

    console.print(f"\n  [dim]Workflow completed in {elapsed:.1f}s[/dim]\n" if False else
                  f"\n  [dim]Workflow {ctx.workflow_id} finished[/dim]\n")
    print_rule()
    console.print()