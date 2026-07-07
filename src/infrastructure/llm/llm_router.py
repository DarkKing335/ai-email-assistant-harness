"""
llm_router.py — Task-based LLM routing.

Routes different tasks to different models based on configuration.
Complex tasks (drafting) use the most capable model.
Simple tasks (summarization, triage) use the fastest/cheapest model.

Inspired by:
  - agents-from-scratch: llm = init_chat_model(model, temperature=0.0)
  - deliberate: policy-driven routing concept
"""

from __future__ import annotations

import logging
from typing import Literal

from src.config.settings import settings
from src.infrastructure.llm.llm_client import (
    GeminiLLMClient,
    LLMClient,
    OpenAILLMClient,
)

logger = logging.getLogger("email_assistant.llm_router")

TaskType = Literal["draft_email", "summarize", "triage", "reflect", "default"]


class LLMRouter:
    """Routes LLM requests to the appropriate model based on task type."""

    def __init__(self) -> None:
        self._clients: dict[str, LLMClient] = {}
        self._build_clients()

    def _build_clients(self) -> None:
        provider = settings.llm_provider
        api_key = settings.active_llm_api_key

        if provider == "openai":
            # Primary — most capable model for complex tasks
            self._clients["primary"] = OpenAILLMClient(
                model_name=settings.llm_model_draft,
                api_key=api_key,
                timeout=settings.llm_request_timeout,
                max_retries=settings.llm_max_retries,
            )
            # Secondary — faster/cheaper model for simple tasks
            self._clients["secondary"] = OpenAILLMClient(
                model_name=settings.llm_model_summarize,
                api_key=api_key,
                timeout=settings.llm_request_timeout,
                max_retries=settings.llm_max_retries,
            )
        elif provider == "gemini":
            self._clients["primary"] = GeminiLLMClient(
                model_name=settings.llm_model_draft,
                api_key=api_key,
            )
            self._clients["secondary"] = GeminiLLMClient(
                model_name=settings.llm_model_summarize,
                api_key=api_key,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        logger.info(
            "LLM Router initialised: provider=%s primary=%s secondary=%s",
            provider,
            settings.llm_model_draft,
            settings.llm_model_summarize,
        )

    def get_client(self, task: TaskType = "default") -> LLMClient:
        """Return the appropriate LLM client for a given task type.

        Routing table:
            draft_email → primary (most capable)
            reflect     → primary (needs reasoning)
            summarize   → secondary (fast/cheap)
            triage      → secondary (fast/cheap)
            default     → primary
        """
        if task in ("summarize", "triage"):
            return self._clients["secondary"]
        return self._clients["primary"]


# Singleton router — initialised once at import time
llm_router = LLMRouter()
