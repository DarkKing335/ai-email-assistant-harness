"""
registry.py — Central tool registry.

Inspired by agenticmail's tool-catalog pattern.
Tools register themselves at import time. The agent executor asks the registry
for its tool list at runtime — so adding a new tool requires zero changes
to the agent or orchestrator.

Usage:
    # Registering a tool:
    from src.tools.registry import tool_registry
    tool_registry.register(MyTool())

    # Getting tools for an agent:
    tools = tool_registry.get_agent_tools()
    tool_dicts = tool_registry.get_llm_tool_dicts()

    # Calling a tool by name:
    result = await tool_registry.call("gmail_read_thread", thread_id="abc123")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.tools.base_tool import BaseTool, ToolError
from src.tools.proxy import tool_proxy

logger = logging.getLogger("email_assistant.tools.registry")


class ToolRegistry:
    """Central registry for all agent-callable tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> "ToolRegistry":
        """Register a tool instance. Returns self for fluent chaining."""
        if tool.name in self._tools:
            logger.warning("Tool '%s' is already registered — overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)
        return self

    def get(self, name: str) -> Optional[BaseTool]:
        """Return a tool by name, or None if not found."""
        return self._tools.get(name)

    def all(self) -> List[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_agent_tools(self, exclude_approval_required: bool = True) -> List[BaseTool]:
        """Return tools safe for the agent to invoke autonomously.

        Tools with requires_approval=True (e.g., gmail_send_draft) are excluded
        from the agent's tool list. They can only be called by the orchestrator
        after a human has approved.
        """
        if exclude_approval_required:
            return [t for t in self._tools.values() if not t.requires_approval]
        return self.all()

    def get_llm_tool_dicts(self, exclude_approval_required: bool = True) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible function definitions for all agent tools."""
        return [t.to_llm_dict() for t in self.get_agent_tools(exclude_approval_required)]

    async def call(self, name: str, **kwargs: Any) -> Any:
        """Look up and invoke a registered tool by name via the Proxy Layer."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Tool '{name}' not found in registry")
        # Route through the proxy (Proxy Layer) for audit, rate-limiting, etc.
        return await tool_proxy.call(tool, **kwargs)

    def list_names(self) -> List[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={self.list_names()}>"


# ── Singleton registry ────────────────────────────────────────────────────────

tool_registry = ToolRegistry()


def build_default_registry() -> ToolRegistry:
    """Register all default tools and return the populated registry.

    Call this once at application startup (e.g., from CLI main entry point).
    """
    from src.tools.gmail_reader_tool import GmailReaderTool
    from src.tools.gmail_draft_tool import GmailDraftTool
    from src.tools.gmail_send_tool import GmailSendTool
    from src.tools.thread_summarizer_tool import ThreadSummarizerTool
    from src.tools.contact_lookup_tool import ContactLookupTool

    tool_registry.register(GmailReaderTool())
    tool_registry.register(GmailDraftTool())
    tool_registry.register(GmailSendTool())
    tool_registry.register(ThreadSummarizerTool())
    tool_registry.register(ContactLookupTool())

    logger.info("Default tool registry built: %s", tool_registry.list_names())
    return tool_registry
