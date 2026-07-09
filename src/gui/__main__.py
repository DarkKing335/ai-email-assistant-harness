"""
__main__.py — Entry point for `python -m src.gui`.

Note what is deliberately absent: this does NOT call
``src.tools.registry.build_default_registry()``, the way ``cli/app.py:358``
does. Importing ``src.tools`` from the GUI would breach the boundary that keeps
``GmailSendTool`` out of the Experience Layer's reach.

The consequence is BLOCKER-7: ``EmailWorkflowOrchestrator`` depends on a global
tool registry that only the entry point populates. Until the orchestrator builds
its own, the drafting and sending steps will not find their tools when launched
from here. See docs/architecture/gui-gateway-contract.md §6.
"""

from src.gui.app import run

if __name__ == "__main__":
    run()
