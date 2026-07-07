"""
draft_step.py — Generate an email draft using the LLM agent.

Implements a simple Plan→Execute→Reflect loop inspired by:
  - agents-from-scratch: triage_router → response_agent flow
  - Email-AI-Agent: supervisor with summarization + response nodes
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.workflow.engine.orchestrator import WorkflowContext

from src.models.draft import Draft
from src.infrastructure.llm.llm_router import llm_router
from src.tools.registry import tool_registry

logger = logging.getLogger("email_assistant.workflow.steps.draft")

_SYSTEM_PROMPT = """You are a professional email assistant. Your job is to draft clear, 
concise, and appropriate email replies on behalf of the user.

Guidelines:
- Match the tone of the incoming email (formal if formal, friendly if friendly)
- Be concise — no unnecessary filler phrases
- Address all questions or points raised in the thread
- Never invent facts; if you don't know something, say so politely
- Do not include a greeting or signature — the user will add those
"""


class DraftStep:
    """Generates a draft reply using the LLM with tool support."""

    async def run(self, ctx: "WorkflowContext") -> "WorkflowContext":
        if ctx.thread is None:
            raise ValueError("DraftStep: no email thread in context")

        thread = ctx.thread
        latest = thread.latest_message
        if latest is None:
            raise ValueError("DraftStep: thread has no messages")

        # ── 1. Optionally summarise long threads ────────────────────────────
        thread_text = thread.full_text
        if len(thread_text) > 3000 and "summarize_email_thread" in tool_registry:
            logger.info("DraftStep: thread is long (%d chars) — summarising", len(thread_text))
            summary_result = await tool_registry.call(
                "summarize_email_thread",
                thread_text=thread_text,
            )
            context_text = summary_result.get("summary", thread_text)
        else:
            context_text = thread_text

        # ── 2. Look up contact context ─────────────────────────────────────
        contact_ctx = ""
        if "lookup_contact" in tool_registry:
            contact = await tool_registry.call(
                "lookup_contact",
                email_address=latest.sender_email,
            )
            if contact.get("found"):
                contact_ctx = (
                    f"\nContact context: {contact['name']} from {contact['company']}. "
                    f"Notes: {contact.get('notes', '')}"
                )

        # ── 3. Draft via LLM ───────────────────────────────────────────────
        llm = llm_router.get_client("draft_email")
        prompt = (
            f"Please draft a reply to the following email thread.{contact_ctx}\n\n"
            f"Thread:\n{context_text}\n\n"
            f"The latest message is from {latest.sender} with subject: {latest.subject}\n\n"
            "Write only the body of the reply — no greeting, no signature."
        )

        response = await llm.generate(prompt=prompt, system_message=_SYSTEM_PROMPT, temperature=0.3)
        draft_body = response.content

        # ── 4. Create draft domain object ─────────────────────────────────
        draft = Draft(
            email_message_id=latest.message_id,
            thread_id=thread.thread_id,
            subject=f"Re: {latest.subject}",
            to=latest.sender_email,
            body=draft_body,
            guardrails_passed=False,  # Will be set by guardrails step
        )

        # ── 5. Create draft in Gmail ───────────────────────────────────────
        if "gmail_create_or_update_draft" in tool_registry:
            gmail_result = await tool_registry.call(
                "gmail_create_or_update_draft",
                to=draft.to,
                subject=draft.subject,
                body=draft.body,
                thread_id=draft.thread_id,
            )
            draft.gmail_draft_id = gmail_result.get("gmail_draft_id")
            logger.info("DraftStep: Gmail draft created: %s", draft.gmail_draft_id)

        ctx.draft = draft
        logger.info("DraftStep: draft generated (%d chars)", len(draft_body))
        return ctx
