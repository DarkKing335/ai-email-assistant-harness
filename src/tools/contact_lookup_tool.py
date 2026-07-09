"""
contact_lookup_tool.py — Tool to fetch contact context from a CRM/directory.

In this implementation, the tool uses an in-memory mock store.
In production, replace _mock_lookup() with a real CRM API call
(Salesforce, HubSpot, Google Contacts, etc.) without touching the agent code.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.permissions.types import Action, Permission, ResourceType

logger = logging.getLogger("email_assistant.tools.contact_lookup")


# ── Mock contact database ─────────────────────────────────────────────────────

_MOCK_CONTACTS: Dict[str, Dict[str, Any]] = {
    "client@example.com": {
        "name": "Alex Johnson",
        "company": "Acme Corp",
        "title": "Product Manager",
        "relationship": "Customer",
        "notes": "Prefers concise, bullet-point replies. Decision-maker for enterprise plan.",
        "previous_interactions": 12,
    },
    "partner@partner.io": {
        "name": "Sam Lee",
        "company": "Partner.io",
        "title": "CTO",
        "relationship": "Strategic Partner",
        "notes": "Technical background. Appreciates detailed explanations.",
        "previous_interactions": 5,
    },
}


class ContactLookupSchema(BaseModel):
    email_address: str = Field(
        ...,
        description="The email address of the contact to look up.",
    )


class ContactLookupTool(BaseTool):
    """Retrieves relationship and preference context for an email sender.

    Use this before drafting a reply to personalise tone and content.
    Returns name, company, relationship type, and communication preferences.
    """
    name = "lookup_contact"
    description = (
        "Look up a contact by email address to get their name, company, "
        "relationship context, and communication preferences. "
        "Call this before drafting a reply to personalise the response."
    )
    args_schema = ContactLookupSchema
    required_permission = Permission(Action.LOOKUP, ResourceType.CONTACT)

    async def _run(self, email_address: str) -> Dict[str, Any]:
        normalised = email_address.lower().strip()

        # Exact match
        if normalised in _MOCK_CONTACTS:
            contact = _MOCK_CONTACTS[normalised]
            logger.info("Contact found: %s → %s", email_address, contact["name"])
            return {"found": True, "email": email_address, **contact}

        # Domain match fallback
        domain = normalised.split("@")[-1] if "@" in normalised else ""
        for email, contact in _MOCK_CONTACTS.items():
            if email.endswith(f"@{domain}"):
                return {
                    "found": True,
                    "email": email_address,
                    "match_type": "domain",
                    **contact,
                }

        # Unknown contact
        logger.info("Contact not found: %s", email_address)
        return {
            "found": False,
            "email": email_address,
            "name": email_address.split("@")[0].replace(".", " ").title(),
            "company": "Unknown",
            "relationship": "Unknown",
            "notes": "No prior contact data available. Use a professional, neutral tone.",
            "previous_interactions": 0,
        }
