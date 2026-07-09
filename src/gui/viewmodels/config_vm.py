"""
config_vm.py — ConfigSummary → config-panel rows.

No secret reaches this module. ``ConfigSummary`` carries only the last four
characters of the API key; the key itself never crosses the gateway boundary.
"""

from __future__ import annotations

from typing import Any

from src.gui.types import ConfigSummary, GmailMode

NOT_SET = "NOT SET"

#: (label, is_warning) — a reviewer approving mock data believing it is real is
#: a bad failure, so MOCK and NEEDS_AUTH both warn.
GMAIL_MODE_LABELS: dict[GmailMode, tuple[str, bool]] = {
    GmailMode.READY: ("Connected", False),
    GmailMode.MOCK: ("MOCK DATA — Google libraries not installed", True),
    GmailMode.NEEDS_AUTH: ("Not authorised — no Gmail token found", True),
}


def fingerprint(last4: str) -> str:
    """Render an API key as ``••••abcd``, or NOT SET."""
    return f"••••{last4}" if last4 else NOT_SET


def gmail_mode_label(mode: GmailMode) -> tuple[str, bool]:
    return GMAIL_MODE_LABELS[mode]


def permissions_label(enforced: bool) -> tuple[str, bool]:
    if enforced:
        return ("Enforced", False)
    return ("Not enforced — src/permissions/ is empty", True)


def config_rows(summary: ConfigSummary) -> list[tuple[str, str]]:
    """Ordered (label, value) pairs for the config panel."""
    gmail_label, _ = gmail_mode_label(summary.gmail_mode)
    perms_label, _ = permissions_label(summary.permissions_enforced)
    return [
        ("Version", summary.app_version),
        ("Environment", summary.app_env),
        ("LLM provider", summary.llm_provider),
        ("Draft model", summary.llm_model_draft),
        ("LLM API key", fingerprint(summary.llm_api_key_last4)),
        ("Gmail account", summary.gmail_user_email),
        ("Gmail status", gmail_label),
        ("Reviewer", summary.reviewer),
        ("Permissions", perms_label),
        ("Audit log", summary.audit_log_path),
        ("Approval timeout", f"{summary.approval_timeout_seconds}s"),
    ]


def config_warnings(summary: ConfigSummary) -> list[str]:
    """Everything the user must know before trusting what they see."""
    warnings: list[str] = []

    gmail_label, gmail_warns = gmail_mode_label(summary.gmail_mode)
    if gmail_warns:
        warnings.append(f"Gmail: {gmail_label}")

    perms_label, perms_warn = permissions_label(summary.permissions_enforced)
    if perms_warn:
        warnings.append(f"Permissions: {perms_label}")

    if not summary.llm_api_key_last4:
        warnings.append(f"LLM API key: {NOT_SET} — drafting will fail")

    return warnings


def config_to_dict(summary: ConfigSummary) -> dict[str, Any]:
    return {
        "rows": config_rows(summary),
        "warnings": config_warnings(summary),
    }
