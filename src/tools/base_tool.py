"""
base_tool.py — Abstract base class for all tools.

Design goals:
  - Schema-enforced inputs via Pydantic (prevents agent hallucinating args)
  - OpenAI function-calling compatible JSON schema export
  - Permission check hook (consulted before execution)
  - Audit log hook (called after execution)
  - Consistent error handling

Inspired by:
  - agenticmail: tool-catalog pattern with typed manifests
  - agents-from-scratch: @tool decorator pattern (reimplemented without LangChain dependency)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel

if TYPE_CHECKING:
    from src.permissions.types import Permission

logger = logging.getLogger("email_assistant.tools")


class ToolError(Exception):
    """Raised when a tool encounters an unrecoverable error."""


class ToolPermissionError(ToolError):
    """Raised when the caller lacks permission to invoke the tool."""


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    Subclass requirements:
        name (str):           Unique tool identifier — used as registry key.
        description (str):    Human/LLM-readable description of what the tool does.
        args_schema (class):  A Pydantic BaseModel class defining input parameters.

    Example:
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Does something useful."
            args_schema = MyToolSchema

            async def _run(self, param: str) -> Any:
                return f"result: {param}"
    """

    name: str
    description: str
    args_schema: Type[BaseModel]

    # Tools with requires_approval=True cannot be called without an approval record
    requires_approval: bool = False

    # RUNTIME guardrail: the capability the caller must hold to invoke this tool.
    # None → no authorization required (backwards-compatible default).
    required_permission: ClassVar[Optional["Permission"]] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for attr in ("name", "description", "args_schema"):
            if not hasattr(cls, attr):
                raise TypeError(f"Tool '{cls.__name__}' must define '{attr}'")

    async def __call__(self, **kwargs: Any) -> Any:
        """Authorize, validate inputs, and execute the tool."""
        validated = self.args_schema(**kwargs)
        self._authorize(validated)
        logger.debug("Tool '%s' invoked with: %s", self.name, validated.model_dump())
        try:
            result = await self._run(**validated.model_dump())
            return result
        except ToolError:
            raise
        except Exception as e:
            logger.error("Tool '%s' raised unexpected error: %s", self.name, e, exc_info=True)
            raise ToolError(f"Tool '{self.name}' failed: {e}") from e

    def _authorize(self, validated: BaseModel) -> None:
        """Consult the permission engine before execution.

        Uses the ambient principal from src.permissions.context. Raises
        ToolPermissionError (and audits PERMISSION_DENIED) if the acting role
        lacks this tool's required_permission. No-op when the tool declares no
        required_permission.
        """
        if self.required_permission is None:
            return

        # Imported lazily so the tool layer has no hard dependency on the
        # permission engine (keeps unit tests of BaseTool self-contained).
        from src.permissions.context import current_actor, current_role
        from src.permissions.engine import permission_engine
        from src.permissions.types import AccessRequest

        role = current_role()
        decision = permission_engine.evaluate(
            AccessRequest(
                role=role,
                permission=self.required_permission,
                resource_scope=self._resource_scope(validated),
                actor=current_actor(),
            )
        )
        if not decision.allowed:
            self._audit_denied(decision.reason)
            raise ToolPermissionError(
                f"Tool '{self.name}' denied: {decision.reason}"
            )

    def _resource_scope(self, validated: BaseModel) -> Dict[str, Any]:
        """Value-level scope for the permission check. Override where needed."""
        return {}

    def _audit_denied(self, reason: str) -> None:
        """Best-effort audit of a permission denial (never raises)."""
        try:
            import asyncio

            from src.audit.logger import audit_logger
            from src.config.constants import AuditAction
            from src.permissions.context import current_actor

            coro = audit_logger.log(
                action=AuditAction.PERMISSION_DENIED,
                actor=current_actor(),
                resource_type="tool",
                resource_id=self.name,
                outcome="DENIED",
                detail=reason,
            )
            # Fire-and-forget if a loop is running; otherwise skip (audit is best-effort).
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(coro)
            else:
                coro.close()
        except Exception as e:  # noqa: BLE001
            logger.debug("Permission-denied audit skipped: %s", e)

    @abstractmethod
    async def _run(self, **kwargs: Any) -> Any:
        """Implement the tool's core logic here. Args match args_schema fields."""

    def to_llm_dict(self) -> Dict[str, Any]:
        """Return an OpenAI-compatible function definition for this tool.

        This allows the tool to be registered directly with
        openai.chat.completions.create(tools=[...]).
        """
        schema = self.args_schema.model_json_schema()
        # Remove title fields that clutter LLM prompts
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def __repr__(self) -> str:
        return f"<Tool name={self.name!r} requires_approval={self.requires_approval}>"
