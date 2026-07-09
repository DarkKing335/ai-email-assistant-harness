"""
tests/unit/test_email_writing_agent.py - Unit tests for the email writing agent.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.agents.email_writing_agent import EmailWritingAgent
from src.config.constants import TOOL_CONTACT_LOOKUP, TOOL_GMAIL_DRAFT, TOOL_GMAIL_SEND, TOOL_SUMMARIZE
from src.models.email import EmailMessage, EmailThread


@dataclass
class _FakeLLMResponse:
    content: str


class _FakeLLM:
    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        content = self._responses.pop(0) if self._responses else "ACCEPT"
        return _FakeLLMResponse(content=content)


class _FakeRouter:
    def __init__(self, draft: _FakeLLM, reflect: _FakeLLM) -> None:
        self.clients = {
            "draft_email": draft,
            "reflect": reflect,
        }

    def get_client(self, task: str):
        return self.clients[task]


class _FakeTools:
    def __init__(self, available: dict[str, dict]) -> None:
        self.available = available
        self.calls: list[tuple[str, dict]] = []

    def __contains__(self, name: str) -> bool:
        return name in self.available

    async def call(self, name: str, **kwargs):
        self.calls.append((name, kwargs))
        return self.available[name]


def _thread(body: str = "Can you confirm the timeline and pricing?") -> EmailThread:
    message = EmailMessage(
        message_id="msg_001",
        thread_id="thread_001",
        subject="Follow-up: Project Proposal",
        sender="Alex Johnson <client@example.com>",
        sender_email="client@example.com",
        recipients=["me@example.com"],
        body_plain=body,
    )
    return EmailThread(thread_id="thread_001", messages=[message])


@pytest.mark.asyncio
async def test_short_thread_skips_summary_uses_contact_and_creates_draft():
    draft_llm = _FakeLLM("Thanks for following up. The timeline is still on track.")
    reflect_llm = _FakeLLM("ACCEPT")
    tools = _FakeTools(
        {
            TOOL_CONTACT_LOOKUP: {
                "found": True,
                "name": "Alex Johnson",
                "company": "Acme Corp",
                "relationship": "Customer",
                "notes": "Prefers concise replies.",
            },
            TOOL_GMAIL_DRAFT: {"gmail_draft_id": "gmail_draft_001"},
        }
    )
    agent = EmailWritingAgent(router=_FakeRouter(draft_llm, reflect_llm), tools=tools)

    draft = await agent.run(_thread())

    assert draft.to == "client@example.com"
    assert draft.subject == "Re: Follow-up: Project Proposal"
    assert draft.gmail_draft_id == "gmail_draft_001"
    assert draft.body == "Thanks for following up. The timeline is still on track."
    assert [name for name, _ in tools.calls] == [TOOL_CONTACT_LOOKUP, TOOL_GMAIL_DRAFT]
    assert "Acme Corp" in draft_llm.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_long_thread_uses_summary_in_draft_prompt():
    draft_llm = _FakeLLM("Summary-based reply.")
    reflect_llm = _FakeLLM("ACCEPT")
    tools = _FakeTools(
        {
            TOOL_SUMMARIZE: {"summary": "SUMMARY TEXT: pricing and timeline questions."},
            TOOL_GMAIL_DRAFT: {"gmail_draft_id": "gmail_draft_002"},
        }
    )
    agent = EmailWritingAgent(router=_FakeRouter(draft_llm, reflect_llm), tools=tools)

    await agent.run(_thread(body="question " * 700))

    assert [name for name, _ in tools.calls] == [TOOL_SUMMARIZE, TOOL_GMAIL_DRAFT]
    assert "SUMMARY TEXT" in draft_llm.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_missing_message_raises_clear_error():
    agent = EmailWritingAgent(
        router=_FakeRouter(_FakeLLM("unused"), _FakeLLM("unused")),
        tools=_FakeTools({}),
    )

    with pytest.raises(ValueError, match="thread has no messages"):
        await agent.run(EmailThread(thread_id="empty", messages=[]))


@pytest.mark.asyncio
async def test_agent_never_invokes_send_tool_even_when_registered():
    draft_llm = _FakeLLM("Safe draft.")
    reflect_llm = _FakeLLM("ACCEPT")
    tools = _FakeTools(
        {
            TOOL_GMAIL_SEND: {"status": "sent"},
            TOOL_GMAIL_DRAFT: {"gmail_draft_id": "gmail_draft_003"},
        }
    )
    agent = EmailWritingAgent(router=_FakeRouter(draft_llm, reflect_llm), tools=tools)

    await agent.run(_thread())

    assert TOOL_GMAIL_SEND not in [name for name, _ in tools.calls]
    assert [name for name, _ in tools.calls] == [TOOL_GMAIL_DRAFT]


@pytest.mark.asyncio
async def test_reflection_can_revise_body_once():
    draft_llm = _FakeLLM("Hi Alex,\nInitial draft.\nBest,\nMe")
    reflect_llm = _FakeLLM("REVISE: Initial draft, without greeting or signature.")
    tools = _FakeTools({TOOL_GMAIL_DRAFT: {"gmail_draft_id": "gmail_draft_004"}})
    agent = EmailWritingAgent(router=_FakeRouter(draft_llm, reflect_llm), tools=tools)

    draft = await agent.run(_thread())

    assert draft.body == "Initial draft, without greeting or signature."
    assert len(reflect_llm.calls) == 1
    assert tools.calls[0][1]["body"] == "Initial draft, without greeting or signature."
