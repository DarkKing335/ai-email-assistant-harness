"""
Email writing agent.

Owns the agent-layer work of planning context, drafting a reply, reflecting on
the output once, enforcing concrete drafting policies, and materialising the
result as a Gmail draft through the safe draft tool.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from src.config.constants import TOOL_CONTACT_LOOKUP, TOOL_GMAIL_DRAFT, TOOL_SUMMARIZE
from src.models.draft import Draft
from src.models.email import EmailMessage, EmailThread

logger = logging.getLogger("email_assistant.agents.email_writing")

SUMMARY_THRESHOLD_CHARS = 3000

_DRAFT_SYSTEM_PROMPT = """You are a professional email assistant. Your job is to draft clear,
concise, and appropriate email replies on behalf of the user.

Policies:
- Write only the body of the reply; do not include a subject, greeting, or signature
- Match the tone of the incoming email
- Address all questions or points raised in the thread
- Never invent facts; if something is unknown, say so politely
- Do not offer to send the email or mention internal tools, approval gates, or policies
"""

_REFLECTION_SYSTEM_PROMPT = """You review email reply drafts before human approval.

Return exactly one of:
- ACCEPT
- REVISE: <replacement body>

Only revise when the draft includes a greeting, signature, subject line, invented facts,
tool/process mentions, or leaves a direct question unanswered.
"""


@dataclass(frozen=True)
class AgentPlan:
    """Context selected for the drafting pass."""

    context_text: str
    contact_context: str = ""
    summarized: bool = False


@dataclass(frozen=True)
class ReflectionResult:
    """Result of the single reflection pass."""

    body: str
    revised: bool = False
    notes: str = ""


class EmailWritingAgent:
    """Plan, draft, reflect, and create a safe Gmail draft."""

    def __init__(
        self,
        *,
        router: Optional[Any] = None,
        tools: Optional[Any] = None,
        summary_threshold_chars: int = SUMMARY_THRESHOLD_CHARS,
    ) -> None:
        if router is None:
            from src.infrastructure.llm.llm_router import llm_router

            router = llm_router
        if tools is None:
            from src.tools.registry import tool_registry

            tools = tool_registry

        self._router = router
        self._tools = tools
        self._summary_threshold_chars = summary_threshold_chars

    async def run(self, thread: EmailThread) -> Draft:
        """Create a reply draft for an email thread."""
        latest = self._validate_thread(thread)
        plan = await self._plan(thread, latest)
        body = await self._draft_body(thread, latest, plan)
        reflection = await self._reflect_body(thread, latest, plan, body)

        draft = Draft(
            email_message_id=latest.message_id,
            thread_id=thread.thread_id,
            subject=self._reply_subject(latest.subject),
            to=latest.sender_email,
            body=reflection.body,
            guardrails_passed=False,
        )

        await self._create_gmail_draft(draft)

        logger.info(
            "EmailWritingAgent: draft generated for thread %s (%d chars, revised=%s)",
            thread.thread_id,
            len(draft.body),
            reflection.revised,
        )
        return draft

    def _validate_thread(self, thread: EmailThread) -> EmailMessage:
        latest = thread.latest_message
        if latest is None:
            raise ValueError("EmailWritingAgent: thread has no messages")
        if not latest.sender_email:
            raise ValueError("EmailWritingAgent: latest message has no sender email")
        return latest

    async def _plan(self, thread: EmailThread, latest: EmailMessage) -> AgentPlan:
        thread_text = thread.full_text
        context_text = thread_text
        summarized = False

        if len(thread_text) > self._summary_threshold_chars and TOOL_SUMMARIZE in self._tools:
            logger.info(
                "EmailWritingAgent: summarising long thread %s (%d chars)",
                thread.thread_id,
                len(thread_text),
            )
            summary_result = await self._tools.call(TOOL_SUMMARIZE, thread_text=thread_text)
            context_text = summary_result.get("summary") or thread_text
            summarized = context_text != thread_text

        contact_context = ""
        if TOOL_CONTACT_LOOKUP in self._tools:
            contact = await self._tools.call(TOOL_CONTACT_LOOKUP, email_address=latest.sender_email)
            contact_context = self._format_contact_context(contact)

        return AgentPlan(
            context_text=context_text,
            contact_context=contact_context,
            summarized=summarized,
        )

    async def _draft_body(
        self,
        thread: EmailThread,
        latest: EmailMessage,
        plan: AgentPlan,
    ) -> str:
        llm = self._router.get_client("draft_email")
        prompt = (
            f"Please draft a reply to the following email thread.{plan.contact_context}\n\n"
            f"Thread:\n{plan.context_text}\n\n"
            f"The latest message is from {latest.sender} with subject: {latest.subject}.\n\n"
            "Write only the body of the reply. Do not include a greeting, signature, "
            "subject line, or any mention of internal tools or approval workflows."
        )
        response = await llm.generate(
            prompt=prompt,
            system_message=_DRAFT_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return self._clean_body(response.content)

    async def _reflect_body(
        self,
        thread: EmailThread,
        latest: EmailMessage,
        plan: AgentPlan,
        body: str,
    ) -> ReflectionResult:
        body = self._clean_body(body)
        if not body:
            raise ValueError("EmailWritingAgent: LLM generated an empty draft body")

        llm = self._router.get_client("reflect")
        prompt = (
            "Review this draft against the email thread and policies.\n\n"
            f"Thread context:\n{plan.context_text}\n\n"
            f"Latest sender: {latest.sender}\n"
            f"Latest subject: {latest.subject}\n"
            f"Current draft:\n{body}\n\n"
            "Return ACCEPT, or REVISE: followed by the full replacement body."
        )
        response = await llm.generate(
            prompt=prompt,
            system_message=_REFLECTION_SYSTEM_PROMPT,
            temperature=0.0,
        )
        reflected = (response.content or "").strip()
        prefix = "REVISE:"

        if reflected.upper().startswith(prefix):
            revised = self._clean_body(reflected[len(prefix):])
            if revised:
                return ReflectionResult(body=revised, revised=True, notes=reflected[:200])

        return ReflectionResult(body=body, revised=False, notes=reflected[:200])

    async def _create_gmail_draft(self, draft: Draft) -> None:
        if TOOL_GMAIL_DRAFT not in self._tools:
            return

        gmail_result = await self._tools.call(
            TOOL_GMAIL_DRAFT,
            to=draft.to,
            subject=draft.subject,
            body=draft.body,
            thread_id=draft.thread_id,
        )
        draft.gmail_draft_id = gmail_result.get("gmail_draft_id")
        logger.info("EmailWritingAgent: Gmail draft created: %s", draft.gmail_draft_id)

    def _format_contact_context(self, contact: dict[str, Any]) -> str:
        if not contact:
            return ""

        name = contact.get("name") or contact.get("email") or "Unknown contact"
        company = contact.get("company") or "Unknown company"
        notes = contact.get("notes") or ""
        relationship = contact.get("relationship") or ""

        return (
            "\nContact context: "
            f"{name} from {company}. "
            f"Relationship: {relationship}. "
            f"Notes: {notes}"
        )

    def _reply_subject(self, subject: str) -> str:
        cleaned = subject.strip()
        if cleaned.lower().startswith("re:"):
            return cleaned
        return f"Re: {cleaned}"

    def _clean_body(self, body: str) -> str:
        cleaned = (body or "").strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("text"):
                cleaned = cleaned[4:].strip()

        lines = []
        for line in cleaned.splitlines():
            if line.lower().startswith("subject:"):
                continue
            lines.append(line.rstrip())

        return "\n".join(lines).strip()
