"""
tools — Tool Layer (Ring 4).

All agent-callable tools. Each tool is a BaseTool subclass with:
  - Schema-enforced inputs (Pydantic)
  - Permission check via the permission engine
  - Audit logging on execution/failure
  - Proxy interception for cross-cutting concerns

All tool calls from the ToolRegistry are routed through the ToolProxy (Proxy Layer)
before reaching the Infrastructure Layer.

Public API:
    from src.tools import tool_registry, build_default_registry
    from src.tools.proxy import tool_proxy, ToolProxy
"""
from src.tools.registry import ToolRegistry, tool_registry, build_default_registry
from src.tools.base_tool import BaseTool, ToolError, ToolPermissionError
from src.tools.proxy import ToolProxy, tool_proxy

__all__ = [
    "ToolRegistry",
    "tool_registry",
    "build_default_registry",
    "BaseTool",
    "ToolError",
    "ToolPermissionError",
    "ToolProxy",
    "tool_proxy",
]
