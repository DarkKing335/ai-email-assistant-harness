"""
tests/unit/test_guardrail_policy.py — Unit tests for the config-driven
guardrail policy (Phase 6): defaults, YAML override semantics, reload, and the
shipped example file.
"""
import pytest

from src.guardrails import policy as policy_module
from src.guardrails.policy import default_policy, load_policy, reload_policy
from src.guardrails.result import FailMode


@pytest.fixture(autouse=True)
def _reset_policy_cache():
    """Keep the module-level policy cache from leaking across tests/files."""
    yield
    policy_module._policy_cache = None


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_default_policy_values():
    pol = default_policy()
    assert pol.length.min_chars == 10
    assert pol.length.max_chars == 5000
    assert "OpenAI API key" in [label for label, _ in pol.banned_patterns()]
    assert "ssn" in [label for label, _, _ in pol.pii_patterns()]
    assert pol.recipient_allowed_domains is None  # → env fallback


def test_missing_file_returns_defaults(tmp_path):
    pol = load_policy(str(tmp_path / "does-not-exist.yaml"))
    assert pol.length.max_chars == 5000


# ── YAML override ─────────────────────────────────────────────────────────────

def test_yaml_overrides_length_recipient_and_rails(tmp_path):
    f = tmp_path / "g.yaml"
    f.write_text(
        "length:\n  min_chars: 50\n  max_chars: 100\n"
        "recipient:\n  allowed_domains: [acme.com, partner.io]\n"
        "rails:\n"
        "  pii_redactor: { enabled: false }\n"
        "  length_rail: { fail_mode: closed }\n",
        encoding="utf-8",
    )
    pol = load_policy(str(f))

    assert (pol.length.min_chars, pol.length.max_chars) == (50, 100)
    assert pol.recipient_domains() == {"acme.com", "partner.io"}
    assert pol.toggle("pii_redactor").enabled is False
    assert pol.toggle("length_rail").fail_mode == FailMode.CLOSED
    # A section not named in the YAML keeps its defaults.
    assert "ssn" in [label for label, _, _ in pol.pii_patterns()]


def test_yaml_section_replaces_not_merges(tmp_path):
    f = tmp_path / "g.yaml"
    f.write_text(
        "banned_content:\n  - label: my-secret\n    pattern: 'TOPSECRET-\\d+'\n",
        encoding="utf-8",
    )
    pol = load_policy(str(f))
    # The default banned patterns are fully replaced, not appended to.
    assert [label for label, _ in pol.banned_patterns()] == ["my-secret"]


def test_malformed_yaml_falls_back_to_defaults(tmp_path):
    f = tmp_path / "g.yaml"
    f.write_text("length: [this is not a mapping]\n", encoding="utf-8")
    pol = load_policy(str(f))  # must not raise
    assert pol.length.max_chars == 5000


# ── Reload affects live rail behaviour ───────────────────────────────────────

@pytest.mark.asyncio
async def test_reload_changes_rail_behaviour(tmp_path):
    from src.guardrails.rails.length_rail import LengthRail
    from src.guardrails.result import GuardrailContext, GuardrailStage, Verdict
    from src.models.draft import Draft

    f = tmp_path / "g.yaml"
    f.write_text("length:\n  min_chars: 1000\n  max_chars: 2000\n", encoding="utf-8")
    reload_policy(str(f))

    draft = Draft(to="a@acme.com", subject="Hi", body="a short body well under 1000 chars")
    result = await LengthRail().check(GuardrailContext(GuardrailStage.OUTPUT, draft=draft))
    assert result.verdict == Verdict.REQUIRE_APPROVAL  # now considered too short


# ── Shipped example file ─────────────────────────────────────────────────────

def test_example_file_parses_and_reproduces_defaults():
    pol = load_policy("config/guardrails.example.yaml")
    assert "OpenAI API key" in [label for label, _ in pol.banned_patterns()]
    assert pol.length.max_chars == 5000
    # Example leaves the recipient allow-list commented out → env fallback.
    assert pol.recipient_allowed_domains is None
    assert pol.toggle("length_rail").fail_mode == FailMode.OPEN
