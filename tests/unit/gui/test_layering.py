"""
tests/unit/gui/test_layering.py — Structural enforcement of the GUI boundary.

"The GUI can never send an email" is only a real guarantee if it is mechanically
true. These tests parse every module under src/gui/ and assert the import graph,
so the invariant cannot rot into a code-review convention.
"""

import ast
from pathlib import Path

import pytest

GUI_ROOT = Path(__file__).resolve().parents[3] / "src" / "gui"

#: No GUI module may touch these. GmailSendTool carries requires_approval=True
#: and is filtered out of get_agent_tools(); a GUI that can reach it is an agent
#: that can send mail. src.integrations is another Ring 3 adapter — reaching
#: sideways into it would let views render raw Gmail JSON.
FORBIDDEN_EVERYWHERE = ("src.tools", "src.integrations")

#: Only gateway.py may import these. Everything else goes through the seam.
GATEWAY_ONLY = ("src.workflow", "src.approval", "src.audit", "src.config.settings")


def _gui_modules() -> list[Path]:
    return sorted(GUI_ROOT.rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    """Every module named by an import in this file, including inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module)
    return found


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def test_gui_package_is_non_empty():
    assert _gui_modules(), f"no modules found under {GUI_ROOT}"


@pytest.mark.parametrize("path", _gui_modules(), ids=lambda p: p.name)
def test_no_gui_module_imports_tools_or_integrations(path: Path):
    for module in _imported_modules(path):
        for forbidden in FORBIDDEN_EVERYWHERE:
            assert not _matches(module, forbidden), (
                f"{path.name} imports {module!r}. The GUI must never reach "
                f"{forbidden} — sending is the orchestrator's job."
            )


@pytest.mark.parametrize("path", _gui_modules(), ids=lambda p: p.name)
def test_only_gateway_imports_ring_two(path: Path):
    if path.name == "gateway.py":
        return
    for module in _imported_modules(path):
        for restricted in GATEWAY_ONLY:
            assert not _matches(module, restricted), (
                f"{path.name} imports {module!r}. Only gateway.py may do that — "
                f"it is the seam that absorbs Ring 2 churn."
            )


def test_gateway_does_import_the_seam_it_owns():
    """Guards against the rule passing vacuously if gateway.py stops importing."""
    modules = _imported_modules(GUI_ROOT / "gateway.py")
    assert any(_matches(m, "src.approval") for m in modules)
    assert any(_matches(m, "src.audit") for m in modules)
    assert any(_matches(m, "src.workflow") for m in modules)
    assert any(_matches(m, "src.config.settings") for m in modules)


def test_gateway_exposes_no_send_operation():
    from src.gui.gateway import Gateway

    offenders = [name for name in dir(Gateway) if "send" in name.lower()]
    assert not offenders, (
        f"Gateway exposes {offenders}. The GUI approves; the orchestrator sends."
    )


def test_approve_does_not_accept_a_reviewer_argument():
    """Reviewer identity comes from the session, so the audit trail can't be forged."""
    import inspect

    from src.gui.gateway import Gateway

    for method in (Gateway.approve, Gateway.reject):
        params = inspect.signature(method).parameters
        assert "reviewer" not in params, (
            f"Gateway.{method.__name__} takes a reviewer argument — any view "
            f"could then forge AuditEvent.actor."
        )
