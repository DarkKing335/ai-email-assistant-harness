"""
tests/unit/test_permissions.py — Unit tests for the permission engine and its
integration with the tool layer.
"""
import pytest
from pydantic import BaseModel

from src.config.constants import UserRole
from src.permissions.context import acting_as, current_role
from src.permissions.engine import permission_engine
from src.permissions.types import AccessRequest, Action, Permission, ResourceType
from src.tools.base_tool import BaseTool, ToolPermissionError

_SEND = Permission(Action.SEND, ResourceType.EMAIL)
_READ = Permission(Action.READ, ResourceType.THREAD)


# ── Policy evaluation ─────────────────────────────────────────────────────────

def _req(role, perm):
    return AccessRequest(role=role, permission=perm)


def test_operator_cannot_send():
    assert not permission_engine.evaluate(_req(UserRole.OPERATOR, _SEND)).allowed


def test_operator_can_read():
    assert permission_engine.evaluate(_req(UserRole.OPERATOR, _READ)).allowed


def test_reviewer_can_send():
    assert permission_engine.evaluate(_req(UserRole.REVIEWER, _SEND)).allowed


def test_system_can_do_everything():
    for perm in (_SEND, _READ, Permission(Action.CONFIGURE, ResourceType.CONFIG)):
        assert permission_engine.evaluate(_req(UserRole.SYSTEM, perm)).allowed


def test_policy_decision_is_truthy():
    decision = permission_engine.evaluate(_req(UserRole.SYSTEM, _SEND))
    assert bool(decision) is True


# ── Ambient principal (contextvar) ───────────────────────────────────────────

def test_acting_as_narrows_and_restores_role():
    assert current_role() == UserRole.SYSTEM  # default
    with acting_as(UserRole.OPERATOR):
        assert current_role() == UserRole.OPERATOR
    assert current_role() == UserRole.SYSTEM


# ── Tool-layer enforcement ────────────────────────────────────────────────────

class _Schema(BaseModel):
    payload: str


class _FakeSendTool(BaseTool):
    name = "fake_send"
    description = "A tool that requires SEND permission."
    args_schema = _Schema
    required_permission = _SEND

    async def _run(self, payload: str):
        return {"sent": payload}


@pytest.mark.asyncio
async def test_tool_denied_for_operator():
    tool = _FakeSendTool()
    with acting_as(UserRole.OPERATOR):
        with pytest.raises(ToolPermissionError, match="denied"):
            await tool(payload="hi")


@pytest.mark.asyncio
async def test_tool_allowed_for_reviewer():
    tool = _FakeSendTool()
    with acting_as(UserRole.REVIEWER):
        result = await tool(payload="hi")
    assert result == {"sent": "hi"}


@pytest.mark.asyncio
async def test_tool_without_required_permission_is_unrestricted():
    class _Open(BaseTool):
        name = "open_tool"
        description = "No permission required."
        args_schema = _Schema

        async def _run(self, payload: str):
            return {"ok": payload}

    with acting_as(UserRole.OPERATOR):
        assert await _Open()(payload="x") == {"ok": "x"}
