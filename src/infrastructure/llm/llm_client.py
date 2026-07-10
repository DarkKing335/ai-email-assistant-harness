"""
llm_client.py — LLM provider abstraction with retry and cost tracking.

Design:
  - Abstract base class LLMClient defines the contract.
  - OpenAILLMClient wraps the OpenAI SDK with retry/timeout.
  - Both support function-calling (tool_use) compatible output.

Inspired by the LLM invocation patterns in:
  - agents-from-scratch: init_chat_model() abstraction
  - deliberate: provider-agnostic invocation
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("email_assistant.llm")


class LLMResponse:
    """Standardised response from any LLM provider."""

    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
    ) -> None:
        self.content = content
        self.model = model
        self.provider = provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms

    def __repr__(self) -> str:
        return (
            f"LLMResponse(model={self.model!r}, "
            f"tokens={self.input_tokens}+{self.output_tokens}, "
            f"latency={self.latency_ms:.0f}ms)"
        )


class LLMClient:
    """Abstract base for LLM clients."""

    provider: str = "base"

    def __init__(self, model_name: str, api_key: str, timeout: int = 30, max_retries: int = 3) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        raise NotImplementedError

    async def _with_retry(self, coro_fn, *args, **kwargs) -> Any:
        """Execute a coroutine with exponential-backoff retry."""
        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(self.max_retries):
            try:
                return await asyncio.wait_for(coro_fn(*args, **kwargs), timeout=self.timeout)
            except asyncio.TimeoutError as e:
                last_exc = e
                logger.warning("LLM timeout on attempt %d/%d", attempt + 1, self.max_retries)
            except Exception as e:
                last_exc = e
                logger.warning("LLM error on attempt %d/%d: %s", attempt + 1, self.max_retries, e)

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # exponential backoff

        raise last_exc


class OpenAILLMClient(LLMClient):
    """OpenAI implementation.

    In production install: pip install openai
    Falls back to a mock response if openai is not installed.
    """

    provider = "openai"

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: str = "",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        super().__init__(model_name, api_key, timeout, max_retries)
        self._client = None
        try:
            import openai
            self._client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
            logger.info("OpenAI client initialised (model=%s)", model_name)
        except ImportError:
            logger.warning("openai package not installed — using mock LLM responses")

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        start = time.perf_counter()

        if self._client is None:
            # Mock fallback — useful for local dev without API key
            await asyncio.sleep(0.1)
            return LLMResponse(
                content=f"[MOCK] Draft reply for: {prompt[:60]}...",
                model=self.model_name,
                provider=self.provider,
                input_tokens=len(prompt.split()),
                output_tokens=50,
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        async def _call():
            kwargs: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
            return await self._client.chat.completions.create(**kwargs)

        response = await self._with_retry(_call)
        elapsed = (time.perf_counter() - start) * 1000

        content = response.choices[0].message.content or ""
        usage = response.usage

        logger.debug(
            "LLM call: model=%s tokens=%d+%d latency=%.0fms",
            self.model_name,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
            elapsed,
        )

        return LLMResponse(
            content=content,
            model=self.model_name,
            provider=self.provider,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=elapsed,
        )


class GeminiLLMClient(LLMClient):
    """Google Gemini implementation (has a genuinely free API tier).

    Install: pip install google-generativeai
    Falls back to a mock response if the library is not installed, so the rest
    of the system keeps working without it.
    """

    provider = "gemini"

    def __init__(
        self,
        model_name: str = "gemini-1.5-flash",
        api_key: str = "",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        super().__init__(model_name, api_key, timeout, max_retries)
        self._genai = None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai = genai
            logger.info("Gemini client initialised (model=%s)", model_name)
        except ImportError:
            logger.warning("google-generativeai not installed — using mock Gemini responses")

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        start = time.perf_counter()

        if self._genai is None:
            await asyncio.sleep(0.1)
            return LLMResponse(
                content=f"[MOCK GEMINI] Reply for: {prompt[:60]}",
                model=self.model_name,
                provider=self.provider,
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        model = self._genai.GenerativeModel(
            self.model_name,
            system_instruction=system_message or None,
        )

        async def _call():
            return await model.generate_content_async(
                prompt,
                generation_config={"temperature": temperature},
            )

        response = await self._with_retry(_call)
        elapsed = (time.perf_counter() - start) * 1000

        content = (getattr(response, "text", None) or "").strip()
        usage = getattr(response, "usage_metadata", None)

        return LLMResponse(
            content=content,
            model=self.model_name,
            provider=self.provider,
            input_tokens=getattr(usage, "prompt_token_count", 0) if usage else 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) if usage else 0,
            latency_ms=elapsed,
        )
