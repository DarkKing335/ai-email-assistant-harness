"""
runner.py — Agent runner với Rich live output.

Wrap LangGraph workflow, capture log events từ từng node,
và hiển thị tiến trình real-time bằng Rich Progress + Live.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
from langchain_core.messages import BaseMessage
from rich.live import Live
from rich.markup import escape as rich_escape
from rich.progress import Progress, TaskID
from rich.text import Text

from .display import (
    console,
    make_node_progress,
    print_node_done,
    print_node_error,
    print_rule,
    show_code_panel,
    show_final_result,
    show_retry_banner,
    show_task_panel,
    show_test_results,
    print_info,
)
from .themes import Colors

# ──────────────────────────────────────────────────────────────────────────────
# Custom log handler — intercept prints từ nodes
# ──────────────────────────────────────────────────────────────────────────────

class _ProgressCapture(logging.Handler):
    """Capture log records và cập nhật progress description."""

    def __init__(self, progress: Progress, task_id: TaskID):
        super().__init__()
        self._progress = progress
        self._task_id  = task_id

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        # Chỉ show message ngắn
        short = msg[:80]
        self._progress.update(self._task_id, description=short)


# ──────────────────────────────────────────────────────────────────────────────
# NodeTimer — đo thời gian từng node
# ──────────────────────────────────────────────────────────────────────────────

class _NodeTimer:
    def __init__(self) -> None:
        self._start: float = 0.0

    def start(self) -> None:
        self._start = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self._start


# ──────────────────────────────────────────────────────────────────────────────
# Main run function
# ──────────────────────────────────────────────────────────────────────────────

def run_agent(
    requirement: str,
    model: str = "gemini-2.5-flash",
    max_retries: int = 3,
    save_json: bool = True,
    json_path: str = "debug_last_run.json",
) -> Dict[str, Any]:
    """
    Chạy OpenCode Agent với UI đẹp.

    Returns:
        final_state dict từ LangGraph.
    """

    # Import workflow ở đây để tránh circular import
    from src.core.workflow import app as workflow_app

    task_id   = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # ── FR-04.3: Workspace Awareness ──────────────────────────────────────────────
    try:
        from .workspace import detect_workspace, format_workspace_summary
        from rich.panel import Panel as RichPanel
        from rich import box as rbox
        ws = detect_workspace()
        ws_summary = format_workspace_summary(ws)
        console.print(RichPanel(
            ws_summary,
            title=f"[bold {Colors.TEXT_DIM}]💻  Workspace Context (FR-04.3)[/]",
            border_style=Colors.TEXT_DIM,
            box=rbox.SIMPLE,
            padding=(0, 2),
        ))
    except Exception:
        pass  # Workspace detection không ảnh hưởng luồng chính

    # ── Show task panel ───────────────────────────────────────────────────────
    show_task_panel(requirement, task_id=task_id, model=model)

    # ── Build initial state ───────────────────────────────────────────────────
    initial_state = {
        "metadata": {
            "task_id":   task_id,
            "timestamp": timestamp,
            "version":   "1.0",
            "llm_model": model,
        },
        "state": {
            "requirement":      requirement,
            "code":             None,
            "execution_result": {
                "status":           "pending",
                "stdout":           "",
                "stderr":           "",
                "exit_code":        -1,
                "execution_time_ms": 0,
                "test_cases":       [],
            },
            "is_success":  False,
            "retry_count": 0,
            "max_retries": max_retries,
            "history":     [],
        },
        "action": None,
    }

    # ── Pipeline execution with live progress ────────────────────────────────
    run_start    = time.perf_counter()
    final_state  = None
    current_retry = 0

    import contextlib
    import io
    import sys

    # ─ Run with progress spinner ──────────────────────────────────────────────
    timer1 = _NodeTimer()
    all_retry_results: list = []  # collect (attempt, test_cases) per retry
    with make_node_progress() as progress:
        tid1 = progress.add_task(
            description=f"  [{Colors.NODE_1}]>>  Node 1 - Generator[/]  [dim]Starting...[/dim]",
            total=None,  # indeterminate
        )

        timer1.start()
        try:
            # Suppress noisy prints from workflow nodes (redirect to devnull)
            # Rich Progress writes to its own console file handle, NOT sys.stdout,
            # so redirecting sys.stdout here is safe.
            with open(os.devnull, "w", encoding="utf-8") as devnull:
                with contextlib.redirect_stdout(devnull):
                    final_state, all_retry_results = _run_with_live_updates(
                        workflow_app, initial_state, progress, tid1
                    )
        except Exception as e:
            # If devnull redirect fails, run without redirection
            final_state, all_retry_results = _run_with_live_updates(
                workflow_app, initial_state, progress, tid1
            )

    # ── Post-run display ──────────────────────────────────────────────────────
    _render_results(final_state, run_start, all_retry_results)

    # ── Save JSON ─────────────────────────────────────────────────────────────
    if save_json and final_state:
        def sanitize_for_json(obj: Any) -> Any:
            """Đệ quy làm sạch toàn bộ object trước khi đưa cho json.dump"""
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            if isinstance(obj, dict):
                return {str(k): sanitize_for_json(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [sanitize_for_json(v) for v in obj]
            
            # Xử lý các Object đặc biệt của LangChain / Pydantic
            if hasattr(obj, "to_json"):
                try:
                    return obj.to_json()
                except Exception:
                    pass
            if hasattr(obj, "model_dump"): # Pydantic V2 / Langchain BaseMessage
                try:
                    return sanitize_for_json(obj.model_dump())
                except Exception:
                    pass
            if hasattr(obj, "dict"): # Pydantic V1
                try:
                    return sanitize_for_json(obj.dict())
                except Exception:
                    pass
            
            # Bước đường cùng: Biến nó thành chuỗi Text
            return str(obj)

        try:
            # Bước 1: Tẩy rửa dữ liệu an toàn trên RAM
            safe_state = sanitize_for_json(final_state)
            
            # Bước 2: Ghi xuống đĩa (Lúc này json.dump chắc chắn không bao giờ crash)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(safe_state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            print_info(f"State đã lưu an toàn tuyệt đối → [dim]{json_path}[/dim]")
        except Exception as e:
            print_node_error(f"Lỗi ghi file debug: {e}")

    # ── AC-02: Tự động hiển thị lịch sử sửa lỗi nếu có retry ────────────────────────
    if final_state and save_json:
        retry_count = final_state.get("state", {}).get("retry_count", 0)
        if retry_count > 0:
            try:
                from .flow_viewer import view_execution_flow
                console.print()
                print_rule("Lịch Sử Sửa Lỗi (AC-02)")
                view_execution_flow(json_path)
            except Exception:
                pass

    return final_state or {}


# ──────────────────────────────────────────────────────────────────────────────
# _run_with_live_updates — invoke workflow với per-node progress
# ──────────────────────────────────────────────────────────────────────────────

def _run_with_live_updates(
    workflow_app: Any,
    initial_state: Dict[str, Any],
    progress: Progress,
    spinner_task: TaskID,
) -> tuple:
    """
    Chạy LangGraph workflow và cập nhật spinner theo từng node.
    Returns (final_output, all_retry_results) where all_retry_results is a
    list of {attempt, test_cases, code, is_success} per executor run.
    """

    import sys

    node_labels = {
        "node_1_generator": (1, "Node 1 · Generator", Colors.NODE_1),
        "node_2_executor":  (2, "Node 2 · Executor",  Colors.NODE_2),
        "node_3_router":    (3, "Node 3 · Router",    Colors.NODE_3),
    }

    node_timers: Dict[str, float] = {}
    node_done_order: list = []
    all_retry_results: list = []   # NEW: collect per-attempt results
    current_attempt: int = 1

    try:
        # LangGraph stream() yields (node_name, output) tuples
        final_output = None
        last_retry = 0

        for chunk in workflow_app.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                num, label, color = node_labels.get(
                    node_name, (0, node_name, Colors.TEXT_DIM)
                )

                # ── Start timing for this node ──
                if node_name not in node_timers:
                    node_timers[node_name] = time.perf_counter()

                elapsed = time.perf_counter() - node_timers[node_name]

                # ── Detect retry ──
                inner = node_output.get("state", {}) if isinstance(node_output, dict) else {}
                retry_count = inner.get("retry_count", 0)
                if retry_count > last_retry and node_name == "node_1_generator":
                    last_retry = retry_count
                    current_attempt = retry_count + 1
                    # Stop current spinner, print retry banner, restart
                    progress.stop_task(spinner_task)
                    console.print()
                    show_retry_banner(
                        retry_count=retry_count,
                        max_retries=inner.get("max_retries", 3),
                        reason=inner.get("execution_result", {}).get("stderr", "")[:120],
                    )
                    # Re-add spinner task
                    progress.reset(spinner_task)

                # ── Capture executor results per attempt ──
                if node_name == "node_2_executor":
                    exec_res = inner.get("execution_result", {})
                    tc = exec_res.get("test_cases", [])
                    if tc:
                        all_retry_results.append({
                            "attempt": current_attempt,
                            "test_cases": tc,
                            "code": inner.get("code", ""),
                            "is_success": inner.get("is_success", False),
                        })

                # ── Update spinner description ──
                is_success = inner.get("is_success", False)
                if node_name == "node_1_generator":
                    detail = "Code generated OK" if inner.get("code") else "Generating code..."
                elif node_name == "node_2_executor":
                    test_cases = inner.get("execution_result", {}).get("test_cases", [])
                    if test_cases:
                        passed = sum(1 for tc in test_cases if tc.get("passed"))
                        detail = f"{passed}/{len(test_cases)} tests passed"
                    else:
                        detail = "Running code..."
                else:
                    detail = "Done!" if is_success else "Evaluating..."

                # Escape detail to avoid MarkupError if it contains brackets
                safe_detail = rich_escape(detail)
                progress.update(
                    spinner_task,
                    description=(
                        f"  [bold {color}]>>  {label}[/]"
                        f"  [dim]{safe_detail}[/]"
                    ),
                )

                final_output = node_output

        return final_output or {}, all_retry_results

    except (NotImplementedError, AttributeError):
        # Fallback: stream() not supported by this workflow version
        console.print(f"  [dim]Running in batch mode...[/]")
        result = workflow_app.invoke(initial_state)
        return result, []


# ──────────────────────────────────────────────────────────────────────────────
# _render_results — hiển thị sau khi agent hoàn thành
# ──────────────────────────────────────────────────────────────────────────────

def _render_results(
    final_state: Dict[str, Any],
    run_start: float,
    retry_results: list = None,
) -> None:
    """Render code panel, test results từng lần thử và final summary."""
    if not final_state:
        return

    total_elapsed = time.perf_counter() - run_start

    inner      = final_state.get("state", {})
    metadata   = final_state.get("metadata", {})
    action     = final_state.get("action", {}) or {}

    code           = inner.get("code", "")
    is_success     = inner.get("is_success", False)
    retry_count    = inner.get("retry_count", 0)
    execution_res  = inner.get("execution_result", {})
    test_cases     = execution_res.get("test_cases", [])
    task_id        = metadata.get("task_id", "")
    message        = action.get("message", "")

    console.print()
    print_rule("Output")
    console.print()

    # ── Code panel (final code) ──
    if code:
        show_code_panel(code)

    # ── Show ALL retry attempts' test results ──
    if retry_results and len(retry_results) > 1:
        # Multiple attempts: show each one labeled
        for attempt_data in retry_results:
            attempt_num  = attempt_data["attempt"]
            attempt_tcs  = attempt_data["test_cases"]
            attempt_ok   = attempt_data["is_success"]
            is_last      = (attempt_data is retry_results[-1])

            passed = sum(1 for tc in attempt_tcs if tc.get("passed", False))
            total  = len(attempt_tcs)

            if attempt_ok:
                label_color = Colors.SUCCESS
                label_icon  = "✅"
                label_text  = f"Lần thử {attempt_num}: PASS ({passed}/{total})"
            else:
                label_color = Colors.ERROR
                label_icon  = "❌"
                label_text  = f"Lần thử {attempt_num}: FAIL ({passed}/{total} passed)"

            console.print(f"  [bold {label_color}]{label_icon}  {label_text}[/]")
            show_test_results(attempt_tcs)
            console.print()
    else:
        # Single attempt or no retry data
        if test_cases:
            show_test_results(test_cases)

    # ── Final summary ──
    show_final_result(
        is_success=is_success,
        retry_count=retry_count,
        message=message,
        total_duration=total_elapsed,
        task_id=task_id,
    )