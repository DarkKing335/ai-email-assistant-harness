"""
src/gui — Desktop Experience Layer (Ring 3, Interface Adapter).

Layering rules, enforced by tests/unit/gui/test_layering.py:

  * ``gateway.py`` is the ONLY module here permitted to import
    ``src.workflow``, ``src.approval``, ``src.audit``, or ``src.config.settings``.
  * NOTHING here may import ``src.tools`` or ``src.integrations``.
    ``GmailSendTool`` carries ``requires_approval=True`` and is filtered out of
    ``get_agent_tools()``. A GUI that can reach it is an agent that can send mail.
  * ``src.config.constants`` (pure enums) and ``src.models`` (Ring 1 entities)
    are shared and may be imported anywhere.

See docs/architecture/gui-gateway-contract.md.
"""

__all__ = []
