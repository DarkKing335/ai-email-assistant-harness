"""
AI Email Assistant Harness CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Entry point for the AI Email Assistant Harness.

Commands:
    (no subcommand)        — Interactive mode (review queue)
    email process <thread> — Process a specific Gmail thread
    email demo             — Run a demo workflow with mock data
    email review           — Show pending approval queue
    email approve <id>     — Approve a draft
    email reject <id>      — Reject a draft
    email audit            — Show recent audit log
    version                — Show version
    config                 — Show current configuration
"""

__version__ = "1.0.0"
__app_name__ = "ai-email-assistant"
