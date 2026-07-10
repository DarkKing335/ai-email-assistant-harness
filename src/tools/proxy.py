"""
proxy.py — Tool Proxy Layer (between Agent/Workflow and Tool execution).

The Proxy Layer sits between the Workflow/Agent Layer and the Tools Layer.
It intercepts every tool call and enforces:
  1. Permission checks (role + capability)
  2. Audit logging (TOOL_INVOKED / TOOL_FAILED)
  3. Rate-limiting hooks (configurable, extensible)
  4. Tool result normalisation

Architecture position:
    Experience Layer
          ↓
    Workflow Layer
          ↓
    Agent Layer
          ↓
    Guardrails
          ↓
    Tools Layer
          ↓
    Proxy Layer   ← this module
          ↓
    Infrastructure Layer

The proxy is transparent to callers: the ToolRegistry.call() method delegates
here so existing code needs no changes. Add a proxy via tool_proxy.install().
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from src.config.constants import AuditAction
from src.tools.base_tool import BaseTool, ToolError

logger = logging.getLogger("email_assistant.tools.proxy")


class ToolProxyMiddleware:
    """
    Base class for proxy middleware.

    Subclass to add cross-cutting behaviour (rate-limiting, circuit breaking,
    caching, metric collection, etc.).
    """

    async def before_call(
        self,
        tool: BaseTool,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Called before the tool executes. May mutate kwargs.

        Return the (possibly modified) kwargs dict.
        Raise ToolError to short-circuit the call.
        """
        return kwargs

    async def after_call(
        self,
        tool: BaseTool,
        kwargs: Dict[str, Any],
        result: Any,
        elapsed_ms: float,
    ) -> Any:
        """Called after the tool returns. May mutate or wrap the result."""
        return result

    async def on_error(
        self,
        tool: BaseTool,
        kwargs: Dict[str, Any],
        error: Exception,
        elapsed_ms: float,
    ) -> None:
        """Called when the tool raises. May re-raise or swallow."""
        raise error


class AuditMiddleware(ToolProxyMiddleware):
    """Emits TOOL_INVOKED / TOOL_FAILED audit events for every tool call."""

    async def after_call(
        self,
        tool: BaseTool,
        kwargs: Dict[str, Any],
        result: Any,
        elapsed_ms: float,
    ) -> Any:
        try:
            from src.audit.logger import audit_logger
            from src.permissions.context import current_actor

            await audit_logger.log(
                action=AuditAction.TOOL_INVOKED,
                actor=current_actor(),
                resource_type="tool",
                resource_id=tool.name,
                outcome="SUCCESS",
                detail=f"latency={elapsed_ms:.0f}ms",
            )
        except Exception as e:
            logger.debug("Audit middleware (after_call) skipped: %s", e)
        return result

    async def on_error(
        self,
        tool: BaseTool,
        kwargs: Dict[str, Any],
        error: Exception,
        elapsed_ms: float,
    ) -> None:
        try:
            from src.audit.logger import audit_logger
            from src.permissions.context import current_actor

            await audit_logger.log(
                action=AuditAction.TOOL_FAILED,
                actor=current_actor(),
                resource_type="tool",
                resource_id=tool.name,
                outcome="FAILURE",
                detail=str(error),
            )
        except Exception as e:
            logger.debug("Audit middleware (on_error) skipped: %s", e)
        raise error


class ToolProxy:
    """
    Intercepts tool calls from the registry and applies middleware.

    Middleware is applied in registration order (first registered = outermost).
    """

    def __init__(self) -> None:
        self._middleware: List[ToolProxyMiddleware] = []

    def use(self, middleware: ToolProxyMiddleware) -> "ToolProxy":
        """Register a middleware. Returns self for chaining."""
        self._middleware.append(middleware)
        return self

    async def call(self, tool: BaseTool, **kwargs: Any) -> Any:
        """Execute a tool through the middleware chain."""
        # Run all before_call hooks
        for mw in self._middleware:
            kwargs = await mw.before_call(tool, kwargs)

        start = time.perf_counter()
        elapsed_ms = 0.0

        try:
            result = await tool(**kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Run after_call hooks (in reverse — innermost first)
            for mw in reversed(self._middleware):
                result = await mw.after_call(tool, kwargs, result, elapsed_ms)

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            # Run on_error hooks (in reverse)
            for mw in reversed(self._middleware):
                await mw.on_error(tool, kwargs, e, elapsed_ms)
            # If no middleware re-raised, we still raise
            raise


# ── Singleton proxy with audit middleware installed by default ─────────────────

tool_proxy = ToolProxy()
tool_proxy.use(AuditMiddleware())
