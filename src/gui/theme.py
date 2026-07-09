"""
theme.py — Colour palette, ported from src/cli/themes.py.

Values are copied rather than imported so that the GUI does not depend on
`rich`. Keep them in sync by hand; there are eleven of them.
"""

from __future__ import annotations


class Colors:
    PRIMARY = "#00D4AA"
    PRIMARY_DARK = "#00A882"
    ACCENT = "#7B5EA7"

    SUCCESS = "#00C851"
    ERROR = "#FF4444"
    WARNING = "#FFBB33"
    INFO = "#33B5E5"

    BG = "#1E1E1E"
    BG_PANEL = "#252526"
    TEXT = "#E8E8E8"
    TEXT_DIM = "#888888"


#: Guardrail badge colours, keyed by GuardrailState.value.
GUARDRAIL_COLORS = {
    "PASSED": Colors.SUCCESS,
    "FAILED": Colors.ERROR,
    "NOT_EVALUATED": Colors.TEXT_DIM,
}
