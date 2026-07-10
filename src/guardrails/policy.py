"""
policy.py — Declarative, config-driven guardrail policy.

Moves the rail patterns, thresholds, and per-rail enable/fail-mode out of the
rail code and into data. Ops can tune detection without a code change by
copying `config/guardrails.example.yaml` → `config/guardrails.yaml`.

Design:
  - The built-in DEFAULT_POLICY (below) is the single source of truth and is
    fully functional with zero config — no YAML file is required.
  - If the file at settings.guardrails_policy_path exists, each section it
    declares REPLACES that section of the default (section-level override, not
    deep merge — so a partial file only changes what it names).
  - Patterns are compiled once at load and cached on the policy object.
  - PyYAML is imported lazily, so the guardrails work (and unit-test) without it
    unless a YAML file is actually present.

Recipient allow-listing stays deployment/secret config: if the policy does not
set `recipient.allowed_domains`, the rail falls back to
settings.allowed_recipient_domains (env-driven), read live.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Tuple

from src.config.settings import BASE_DIR, settings
from src.guardrails.result import FailMode

logger = logging.getLogger("email_assistant.guardrails.policy")


# ── Value types ───────────────────────────────────────────────────────────────

@dataclass
class PatternRule:
    """One named regex, optionally with a redaction replacement."""
    label: str
    pattern: str
    replacement: Optional[str] = None
    ignorecase: bool = False

    def compiled(self) -> Pattern[str]:
        return re.compile(self.pattern, re.IGNORECASE if self.ignorecase else 0)


@dataclass
class LengthPolicy:
    min_chars: int = 10
    max_chars: int = 5000


@dataclass
class RailToggle:
    """Per-rail runtime overrides. fail_mode=None keeps the rail's own default."""
    enabled: bool = True
    fail_mode: Optional[FailMode] = None


@dataclass
class GuardrailPolicy:
    length: LengthPolicy
    banned_content: List[PatternRule]
    pii: List[PatternRule]
    injection: List[PatternRule]
    rails: Dict[str, RailToggle] = field(default_factory=dict)
    # None → fall back to settings.allowed_recipient_domains (env), read live.
    recipient_allowed_domains: Optional[List[str]] = None

    # Compiled caches (populated in __post_init__).
    _banned: List[Tuple[str, Pattern[str]]] = field(default_factory=list, repr=False)
    _pii: List[Tuple[str, Pattern[str], str]] = field(default_factory=list, repr=False)
    _injection: List[Pattern[str]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._banned = [(r.label, r.compiled()) for r in self.banned_content]
        self._pii = [(r.label, r.compiled(), r.replacement or "[REDACTED]") for r in self.pii]
        self._injection = [r.compiled() for r in self.injection]

    # ── Accessors used by the rails ─────────────────────────────────────────
    def banned_patterns(self) -> List[Tuple[str, Pattern[str]]]:
        return self._banned

    def pii_patterns(self) -> List[Tuple[str, Pattern[str], str]]:
        return self._pii

    def injection_patterns(self) -> List[Pattern[str]]:
        return self._injection

    def toggle(self, rail_name: str) -> RailToggle:
        return self.rails.get(rail_name, RailToggle())

    def recipient_domains(self) -> set[str]:
        if self.recipient_allowed_domains is not None:
            return {d.strip().lower() for d in self.recipient_allowed_domains if d.strip()}
        return settings.allowed_recipient_domains  # env fallback, read live


# ── Built-in defaults (mirror the original hardcoded rail constants) ──────────

def default_policy() -> GuardrailPolicy:
    return GuardrailPolicy(
        length=LengthPolicy(min_chars=10, max_chars=5000),
        banned_content=[
            PatternRule("OpenAI API key", r"sk-[A-Za-z0-9]{20,}"),
            PatternRule("Google API key", r"AIza[0-9A-Za-z\-_]{20,}"),
            PatternRule("AWS access key", r"AKIA[0-9A-Z]{16}"),
            PatternRule("private key block", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            PatternRule("bearer token", r"\b[Bb]earer\s+[A-Za-z0-9\-._~+/]{20,}"),
            PatternRule("password disclosure", r"\bpassword\s*[:=]\s*\S+", ignorecase=True),
        ],
        pii=[
            PatternRule("credit card", r"\b(?:\d[ -]?){13,16}\b", "[REDACTED_CC]"),
            PatternRule("ssn", r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
            PatternRule("iban", r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", "[REDACTED_IBAN]"),
        ],
        injection=[
            PatternRule("ignore-previous", r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|above|prior)\s+instructions?", ignorecase=True),
            PatternRule("disregard", r"disregard\s+(?:all\s+)?(?:the\s+)?(?:previous|above|system)", ignorecase=True),
            PatternRule("you-are-now", r"you\s+are\s+now\s+(?:a|an|acting)", ignorecase=True),
            PatternRule("new-instructions", r"new\s+(?:instructions?|system\s+prompt)\s*[:\-]", ignorecase=True),
            PatternRule("fake-role-tags", r"</?(?:system|assistant|user)\s*>", ignorecase=True),
            PatternRule("system-prompt", r"\bsystem\s+prompt\b", ignorecase=True),
            PatternRule("reveal", r"reveal\s+(?:your\s+)?(?:system\s+prompt|instructions|api\s+key)", ignorecase=True),
            PatternRule("redirect-send", r"send\s+(?:an?\s+)?email\s+to\b", ignorecase=True),
        ],
        rails={},
        recipient_allowed_domains=None,
    )


# ── Loading & merging ─────────────────────────────────────────────────────────

def _rules_from(raw: List[dict]) -> List[PatternRule]:
    return [
        PatternRule(
            label=str(item["label"]),
            pattern=str(item["pattern"]),
            replacement=item.get("replacement"),
            ignorecase=bool(item.get("ignorecase", False)),
        )
        for item in raw
    ]


def _merge(base: GuardrailPolicy, data: dict) -> GuardrailPolicy:
    """Section-level override: only sections present in `data` replace defaults."""
    length = base.length
    if "length" in data:
        length = LengthPolicy(
            min_chars=int(data["length"].get("min_chars", length.min_chars)),
            max_chars=int(data["length"].get("max_chars", length.max_chars)),
        )

    banned = _rules_from(data["banned_content"]) if "banned_content" in data else base.banned_content
    pii = _rules_from(data["pii"]) if "pii" in data else base.pii
    injection = _rules_from(data["injection"]) if "injection" in data else base.injection

    recipient_domains = base.recipient_allowed_domains
    if "recipient" in data and data["recipient"] is not None:
        recipient_domains = list(data["recipient"].get("allowed_domains", []) or [])

    rails: Dict[str, RailToggle] = {}
    for name, cfg in (data.get("rails") or {}).items():
        cfg = cfg or {}
        fm = cfg.get("fail_mode")
        rails[name] = RailToggle(
            enabled=bool(cfg.get("enabled", True)),
            fail_mode=FailMode(str(fm).upper()) if fm else None,
        )

    return GuardrailPolicy(
        length=length,
        banned_content=banned,
        pii=pii,
        injection=injection,
        rails=rails,
        recipient_allowed_domains=recipient_domains,
    )


def load_policy(path: Optional[str] = None) -> GuardrailPolicy:
    """Load the policy, applying a YAML override if the file exists."""
    raw_path = Path(path or settings.guardrails_policy_path)
    if not raw_path.is_absolute():
        raw_path = BASE_DIR / raw_path

    if not raw_path.exists():
        logger.info("No guardrail policy file at %s — using built-in defaults", raw_path)
        return default_policy()

    try:
        import yaml  # lazy — only needed when a policy file is actually present
    except ImportError:
        logger.warning("PyYAML not installed; ignoring %s and using defaults", raw_path)
        return default_policy()

    try:
        data = yaml.safe_load(raw_path.read_text(encoding="utf-8")) or {}
        policy = _merge(default_policy(), data)
        logger.info("Loaded guardrail policy from %s", raw_path)
        return policy
    except Exception as e:  # noqa: BLE001 — a bad policy file must fail loudly, then safe-default
        logger.error("Failed to load guardrail policy %s: %s — using defaults", raw_path, e)
        return default_policy()


# ── Singleton with reload ─────────────────────────────────────────────────────

_policy_cache: Optional[GuardrailPolicy] = None


def get_policy() -> GuardrailPolicy:
    global _policy_cache
    if _policy_cache is None:
        _policy_cache = load_policy()
    return _policy_cache


def reload_policy(path: Optional[str] = None) -> GuardrailPolicy:
    """Force a reload (e.g. after editing the YAML, or in tests)."""
    global _policy_cache
    _policy_cache = load_policy(path)
    return _policy_cache
