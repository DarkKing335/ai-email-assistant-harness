"""
workspace.py — FR-04.3 Workspace Awareness
Tự động detect CWD, git status, danh sách file và truyền context vào Agent.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


# Extensions được coi là "source files" cần liệt kê
_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".cpp", ".c", ".h", ".cs", ".rb", ".php",
    ".html", ".css", ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".sql", ".sh", ".bat",
}
# Thư mục bỏ qua
_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv",
    "env", ".env", "dist", "build", ".mypy_cache", ".pytest_cache",
    "target", ".idea", ".vscode",
}
_MAX_FILES = 200  # Giới hạn số file trả về


def _run_git(*args: str, cwd: str) -> Optional[str]:
    """Chạy lệnh git, trả về stdout hoặc None nếu lỗi."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _is_git_repo(cwd: str) -> bool:
    return _run_git("rev-parse", "--is-inside-work-tree", cwd=cwd) == "true"


def _get_git_branch(cwd: str) -> Optional[str]:
    return _run_git("branch", "--show-current", cwd=cwd)


def _get_git_status_summary(cwd: str) -> Dict[str, Any]:
    """Trả về tổng hợp trạng thái git (staged, modified, untracked)."""
    raw = _run_git("status", "--porcelain", cwd=cwd)
    if raw is None:
        return {}

    staged, modified, untracked = [], [], []
    for line in raw.splitlines():
        if not line:
            continue
        xy = line[:2]
        fname = line[3:].strip()
        if xy[0] in ("A", "M", "D", "R", "C"):
            staged.append(fname)
        if xy[1] in ("M", "D"):
            modified.append(fname)
        if xy == "??":
            untracked.append(fname)

    return {
        "staged": staged[:20],
        "modified": modified[:20],
        "untracked": untracked[:20],
    }


def _get_recent_commits(cwd: str, n: int = 3) -> List[str]:
    raw = _run_git(
        "log", f"-{n}", "--oneline", "--no-decorate", cwd=cwd
    )
    if not raw:
        return []
    return raw.splitlines()


def _collect_files(root: str) -> List[str]:
    """Duyệt đệ quy, thu thập các file source (bỏ qua dir rác)."""
    collected: List[str] = []
    root_path = Path(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in _IGNORE_DIRS and not d.startswith(".")
        ]

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in _SOURCE_EXTS:
                full = Path(dirpath) / fname
                try:
                    rel = str(full.relative_to(root_path))
                    collected.append(rel)
                except ValueError:
                    collected.append(str(full))

            if len(collected) >= _MAX_FILES:
                return collected

    return collected


def detect_workspace(cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    FR-04.3: Phân tích workspace hiện tại và trả về dict context.

    Returns:
        {
            "workspace": "./",          # CWD path
            "git_repo": True,           # Có phải git repo không
            "git_branch": "main",       # Nhánh hiện tại
            "git_status": {...},        # Modified/staged/untracked
            "recent_commits": [...],    # 3 commit gần nhất
            "files": [...],             # Danh sách source files
            "file_count": 42,
            "project_name": "myapp",    # Tên thư mục gốc
        }
    """
    workspace = cwd or os.getcwd()
    workspace_path = Path(workspace).resolve()

    is_git = _is_git_repo(str(workspace_path))

    result: Dict[str, Any] = {
        "workspace": str(workspace_path),
        "git_repo": is_git,
        "git_branch": None,
        "git_status": {},
        "recent_commits": [],
        "files": [],
        "file_count": 0,
        "project_name": workspace_path.name,
    }

    if is_git:
        result["git_branch"] = _get_git_branch(str(workspace_path))
        result["git_status"] = _get_git_status_summary(str(workspace_path))
        result["recent_commits"] = _get_recent_commits(str(workspace_path))

    files = _collect_files(str(workspace_path))
    result["files"] = files
    result["file_count"] = len(files)

    return result


def format_workspace_summary(ws: Dict[str, Any]) -> str:
    """Tạo chuỗi summary ngắn gọn để hiển thị trên terminal."""
    lines = [
        f"📁  {ws['workspace']}",
    ]
    if ws["git_repo"]:
        branch = ws.get("git_branch") or "detached HEAD"
        lines.append(f"🔀  Git branch: {branch}")
        status = ws.get("git_status", {})
        staged = len(status.get("staged", []))
        modified = len(status.get("modified", []))
        untracked = len(status.get("untracked", []))
        if staged or modified or untracked:
            lines.append(
                f"    {staged} staged · {modified} modified · {untracked} untracked"
            )
    else:
        lines.append("    (not a git repository)")

    lines.append(f"📄  {ws['file_count']} source files detected")
    return "\n".join(lines)
