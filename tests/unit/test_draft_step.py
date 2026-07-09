"""
tests/unit/test_draft_step.py - Unit tests for the draft workflow adapter.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.models.draft import Draft
from src.models.email import EmailMessage, EmailThread
from src.workflow.steps.draft_step import DraftStep


class _FakeAgent:
    def __init__(self, draft: Draft) -> None:
        self.draft = draft
        self.calls: list[EmailThread] = []

    async def run(self, thread: EmailThread) -> Draft:
        self.calls.append(thread)
        return self.draft


def _thread() -> EmailThread:
    message = EmailMessage(
        message_id="msg_001",
        thread_id="thread_001",
        subject="Question",
        sender="Alex <client@example.com>",
        sender_email="client@example.com",
        recipients=["me@example.com"],
        body_plain="Can you help?",
    )
    return EmailThread(thread_id="thread_001", messages=[message])


@pytest.mark.asyncio
async def test_draft_step_delegates_to_agent_and_sets_context_draft():
    thread = _thread()
    draft = Draft(
        email_message_id="msg_001",
        thread_id="thread_001",
        subject="Re: Question",
        to="client@example.com",
        body="Yes, I can help.",
    )
    agent = _FakeAgent(draft)
    step = DraftStep(agent=agent)
    ctx = SimpleNamespace(thread=thread, draft=None)

    result = await step.run(ctx)

    assert result is ctx
    assert ctx.draft is draft
    assert agent.calls == [thread]


@pytest.mark.asyncio
async def test_draft_step_requires_thread():
    step = DraftStep(agent=_FakeAgent(Draft()))
    ctx = SimpleNamespace(thread=None, draft=None)

    with pytest.raises(ValueError, match="no email thread"):
        await step.run(ctx)
