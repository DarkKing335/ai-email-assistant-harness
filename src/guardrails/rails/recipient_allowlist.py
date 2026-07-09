"""
recipient_allowlist.py — OUTPUT rail. The email-domain analog of a coding
agent's "is this repo allowed?" tool permission.

If the recipient's domain is not on the configured allowlist, the draft is
escalated to human approval (never silently blocked — the whole point of the
assistant is to reach external people, but a human confirms external sends).

Validator, fail-closed: if we cannot determine the domain, escalate.
"""
from __future__ import annotations

from src.guardrails.base import Guardrail
from src.guardrails.policy import get_policy
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult, GuardrailStage


def _domain_of(address: str) -> str:
    return address.split("@")[-1].strip().lower() if "@" in address else ""


class RecipientAllowlistRail(Guardrail):
    """Escalates sends to recipients outside the allowed-domain set."""

    name = "recipient_allowlist"
    stage = GuardrailStage.OUTPUT
    fail_mode = FailMode.CLOSED

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        draft = ctx.draft
        if draft is None or not draft.to:
            return self.block("no recipient to check")

        allowed = get_policy().recipient_domains()
        domain = _domain_of(draft.to)
        if not domain:
            return self.require_approval(f"could not parse recipient domain from {draft.to!r}")

        # No allowlist configured → every recipient is "external"; a human confirms.
        if not allowed:
            return self.require_approval(
                f"external recipient {domain} (no allowlist configured)", domain=domain
            )

        if domain in allowed:
            return self.allow(f"recipient domain {domain} is allowlisted")

        return self.require_approval(
            f"recipient domain {domain} is not on the allowlist", domain=domain
        )
