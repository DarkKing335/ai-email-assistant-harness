"""
themes.py — Bảng màu & styles thống nhất cho CLI.

Tất cả màu sắc và Rich styles được định nghĩa ở đây
để dễ dàng thay đổi giao diện từ một nơi duy nhất.
"""

from rich.theme import Theme
from rich.style import Style


# ──────────────────────────────────────────────────────────────────────────────
# Hex Color Palette
# ──────────────────────────────────────────────────────────────────────────────

class Colors:
    # Teal-green chủ đạo — gợi nhớ tone của Claude
    PRIMARY       = "#00D4AA"
    PRIMARY_DARK  = "#00A882"
    PRIMARY_LIGHT = "#4DFFDA"

    # Purple accent
    ACCENT        = "#7B5EA7"
    ACCENT_LIGHT  = "#A37FD4"

    # Status colors
    SUCCESS       = "#00C851"
    ERROR         = "#FF4444"
    WARNING       = "#FFBB33"
    INFO          = "#33B5E5"

    # Neutrals
    TEXT          = "#E8E8E8"
    TEXT_DIM      = "#888888"
    TEXT_MUTED    = "#555555"

    # Node-specific
    NODE_1        = "#00D4AA"   # Generator — teal
    NODE_2        = "#7B5EA7"   # Executor  — purple
    NODE_3        = "#FFBB33"   # Router    — amber

    # Background accents
    PANEL_BORDER  = "#00D4AA"
    CODE_BORDER   = "#7B5EA7"
    TEST_BORDER   = "#00C851"


# ──────────────────────────────────────────────────────────────────────────────
# Rich Theme
# ──────────────────────────────────────────────────────────────────────────────

THEME = Theme({
    # General
    "primary"       : f"bold {Colors.PRIMARY}",
    "accent"        : f"bold {Colors.ACCENT}",
    "dim_text"      : f"dim {Colors.TEXT_DIM}",
    "muted"         : Colors.TEXT_MUTED,

    # Status
    "success"       : f"bold {Colors.SUCCESS}",
    "error"         : f"bold {Colors.ERROR}",
    "warning"       : f"bold {Colors.WARNING}",
    "info"          : Colors.INFO,

    # Nodes
    "node1"         : f"bold {Colors.NODE_1}",
    "node2"         : f"bold {Colors.NODE_2}",
    "node3"         : f"bold {Colors.NODE_3}",

    # Structural
    "panel.border"  : Colors.PANEL_BORDER,
    "label"         : f"dim {Colors.TEXT_DIM}",
    "value"         : Colors.TEXT,

    # Progress
    "bar.complete"  : Colors.PRIMARY,
    "bar.finished"  : Colors.SUCCESS,
    "bar.pulse"     : Colors.ACCENT,

    # Repr overrides (make it look cleaner)
    "repr.str"      : Colors.PRIMARY_LIGHT,
    "repr.number"   : Colors.ACCENT_LIGHT,
    "repr.bool_true": Colors.SUCCESS,
    "repr.bool_false": Colors.ERROR,
})


# ──────────────────────────────────────────────────────────────────────────────
# Spinner Styles
# ──────────────────────────────────────────────────────────────────────────────

SPINNER_STYLE = Colors.PRIMARY     # spinner dots color
SPINNER_RUNNING = "dots"           # rich spinner name


# ──────────────────────────────────────────────────────────────────────────────
# Panel Style Presets
# ──────────────────────────────────────────────────────────────────────────────

class PanelStyle:
    TASK   = {"border_style": Colors.PRIMARY,  "title_align": "left"}
    CODE   = {"border_style": Colors.ACCENT,   "title_align": "left"}
    RESULT = {"border_style": Colors.SUCCESS,  "title_align": "left"}
    ERROR  = {"border_style": Colors.ERROR,    "title_align": "left"}
    INFO   = {"border_style": Colors.INFO,     "title_align": "left"}
