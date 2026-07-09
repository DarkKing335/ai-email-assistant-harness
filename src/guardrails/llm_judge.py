"""
llm_judge.py — Base class for LLM-as-judge guardrails (Phase 5).

These rails use the LLM to make *semantic* judgments the deterministic rails
cannot — grounding/hallucination and prompt-injection intent. They are the
exception to "deterministic-first", so they carry three hard rules:

  1. OPT-IN. They are not registered unless the policy explicitly enables them
     (`opt_in = True`). The deterministic rails remain the safety baseline.
  2. CACHED. Identical inputs are judged once (free/rate-limited endpoints).
  3. FAIL-OPEN. A timeout, error, missing API key, or unparseable answer never
     blocks — the rail returns ALLOW and the deterministic verdict stands.

A judge NEVER returns BLOCK. The strongest action it can take is
REQUIRE_APPROVAL (escalate to a human) — an LLM is not trustworthy enough to
be a hard gate, especially on a free model.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections import OrderedDict
from typing import Any, Dict, Optional

from src.config.settings import settings
from src.guardrails.base import Guardrail
from src.guardrails.result import FailMode, GuardrailContext, GuardrailResult

logger = logging.getLogger("email_assistant.guardrails.llm_judge")


# ── Verdict cache (process-lifetime, bounded LRU) ─────────────────────────────

class _JudgeCache:
    """Small bounded LRU cache keyed by sha256(rail_name + input)."""

    def __init__(self, maxsize: int = 512) -> None:
        self._d: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._max = maxsize

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self._max:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()


judge_cache = _JudgeCache()


def _cache_key(rail_name: str, text: str) -> str:
    h = hashlib.sha256()
    h.update(rail_name.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8", "ignore"))
    return h.hexdigest()


def parse_judgment(content: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from an LLM reply and normalise it.

    Returns {"flag": bool, "reason": str} or None if the reply is unusable
    (which the caller treats as fail-open).
    """
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if "flag" not in data:
        return None
    return {"flag": bool(data.get("flag")), "reason": str(data.get("reason", ""))[:200]}


# ── Base rail ─────────────────────────────────────────────────────────────────

class LLMJudgeRail(Guardrail):
    """Abstract base for LLM-backed guardrails. Concrete rails implement the
    four hooks below; this base owns availability, caching, and fail-open."""

    _abstract_base = True
    opt_in = True
    fail_mode = FailMode.OPEN
    llm_task = "reflect"  # which routed model to use (see llm_router)

    def __init__(self, client: Any = None) -> None:
        # An injected client makes the rail active without an env API key
        # (used in tests). In production the router provides the client.
        self._client = client

    # ── Subclass hooks ──────────────────────────────────────────────────────
    def _cache_text(self, ctx: GuardrailContext) -> str:
        """The semantic input to hash + judge (empty → skip)."""
        raise NotImplementedError

    def _system_prompt(self) -> str:
        raise NotImplementedError

    def _user_prompt(self, ctx: GuardrailContext) -> str:
        raise NotImplementedError

    def _interpret(self, judgment: Dict[str, Any], ctx: GuardrailContext) -> GuardrailResult:
        raise NotImplementedError

    # ── Machinery ───────────────────────────────────────────────────────────
    def _available(self) -> bool:
        return self._client is not None or bool(settings.active_llm_api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from src.infrastructure.llm.llm_router import llm_router
        return llm_router.get_client(self.llm_task)

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        if not self._available():
            return self.allow("LLM judge inactive (no API key / client)")

        text = self._cache_text(ctx)
        if not text.strip():
            return self.allow("nothing to judge")

        key = _cache_key(self.name, text)
        judgment = judge_cache.get(key)
        if judgment is None:
            judgment = await self._ask(ctx)
            if judgment is None:
                return self.allow("LLM judge unavailable (fail-open)")
            judge_cache.set(key, judgment)

        return self._interpret(judgment, ctx)

    async def _ask(self, ctx: GuardrailContext) -> Optional[Dict[str, Any]]:
        """Call the LLM with a hard timeout. Any failure → None (fail-open)."""
        client = self._get_client()
        try:
            resp = await asyncio.wait_for(
                client.generate(
                    prompt=self._user_prompt(ctx),
                    system_message=self._system_prompt(),
                    temperature=0.0,
                ),
                timeout=settings.guardrails_llm_timeout,
            )
        except Exception as e:  # noqa: BLE001 — every failure is fail-open by design
            logger.warning("LLM judge '%s' failed (fail-open): %s", self.name, e)
            return None
        return parse_judgment(resp.content)
