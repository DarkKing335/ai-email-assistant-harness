"""
tests/unit/test_tool_registry.py — Unit tests for the ToolRegistry.
"""
import pytest
from src.tools.base_tool import BaseTool, ToolError
from src.tools.registry import ToolRegistry
from pydantic import BaseModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

class _DummySchema(BaseModel):
    message: str


class _DummyTool(BaseTool):
    name = "dummy_tool"
    description = "A dummy tool for testing."
    args_schema = _DummySchema

    async def _run(self, message: str):
        return {"echo": message}


class _RequiresApprovalTool(BaseTool):
    name = "approval_required_tool"
    description = "Requires approval."
    args_schema = _DummySchema
    requires_approval = True

    async def _run(self, message: str):
        return {"sent": message}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_register_and_get():
    registry = ToolRegistry()
    tool = _DummyTool()
    registry.register(tool)
    assert registry.get("dummy_tool") is tool


def test_get_nonexistent_returns_none():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_len():
    registry = ToolRegistry()
    registry.register(_DummyTool())
    registry.register(_RequiresApprovalTool())
    assert len(registry) == 2


def test_contains():
    registry = ToolRegistry()
    registry.register(_DummyTool())
    assert "dummy_tool" in registry
    assert "other_tool" not in registry


def test_get_agent_tools_excludes_approval_required():
    registry = ToolRegistry()
    registry.register(_DummyTool())
    registry.register(_RequiresApprovalTool())

    agent_tools = registry.get_agent_tools()
    names = [t.name for t in agent_tools]

    assert "dummy_tool" in names
    assert "approval_required_tool" not in names


def test_get_llm_tool_dicts_format():
    registry = ToolRegistry()
    registry.register(_DummyTool())
    dicts = registry.get_llm_tool_dicts()

    assert len(dicts) == 1
    d = dicts[0]
    assert d["type"] == "function"
    assert d["function"]["name"] == "dummy_tool"
    assert "parameters" in d["function"]


@pytest.mark.asyncio
async def test_call_tool():
    registry = ToolRegistry()
    registry.register(_DummyTool())
    result = await registry.call("dummy_tool", message="hello")
    assert result == {"echo": "hello"}


@pytest.mark.asyncio
async def test_call_unknown_tool_raises():
    registry = ToolRegistry()
    with pytest.raises(ToolError, match="not found"):
        await registry.call("nonexistent_tool", message="x")
