"""
tests/unit/gui/test_viewmodels.py — Headless. No display, no third-party deps
beyond pytest, no settings, no filesystem.
"""

from datetime import datetime, timedelta

from src.config.constants import AuditAction, WorkflowStatus
from src.gui.types import ConfigSummary, GmailMode, GuardrailState, PendingItem
from src.gui.viewmodels import audit_vm, config_vm, draft_vm, queue_vm, timeline_vm
from src.models.audit_event import AuditEvent
from src.models.draft import Draft


def _draft(**overrides) -> Draft:
    return Draft(
        draft_id="dr_test",
        thread_id="th_test",
        to="client@example.com",
        subject="Re: Timeline",
        body="Dear Client,\n\nThe deliverables land on the 14th.\n",
        **overrides,
    )


# ── Guardrail tri-state ───────────────────────────────────────────────────────
# This is the load-bearing inference: guardrails_passed is False for a draft
# that failed AND for a draft nothing ever looked at.


def test_guardrail_state_passed():
    assert draft_vm.guardrail_state(_draft(guardrails_passed=True)) is GuardrailState.PASSED


def test_guardrail_state_not_evaluated_when_no_evidence_of_a_run():
    # Every draft in the system today: src/guardrails/ is an empty package.
    assert draft_vm.guardrail_state(_draft()) is GuardrailState.NOT_EVALUATED


def test_guardrail_state_failed_on_pii():
    assert draft_vm.guardrail_state(_draft(pii_detected=True)) is GuardrailState.FAILED


def test_guardrail_state_failed_on_content_flag():
    assert draft_vm.guardrail_state(_draft(content_flagged=True)) is GuardrailState.FAILED


def test_guardrail_state_failed_on_notes():
    d = _draft(guardrail_notes="Blocked: contains a bank account number")
    assert draft_vm.guardrail_state(d) is GuardrailState.FAILED


def test_guardrail_state_whitespace_notes_are_not_evidence():
    assert draft_vm.guardrail_state(_draft(guardrail_notes="   ")) is GuardrailState.NOT_EVALUATED


def test_not_evaluated_label_does_not_claim_failure():
    label = draft_vm.GUARDRAIL_LABELS[GuardrailState.NOT_EVALUATED]
    assert "not evaluated" in label.lower()
    assert "blocked" not in label.lower()


# ── draft_to_dict ─────────────────────────────────────────────────────────────


def test_draft_to_dict_none_in_none_out():
    assert draft_vm.draft_to_dict(None) is None


def test_draft_to_dict_never_leaks_the_gmail_draft_handle():
    d = _draft(gmail_draft_id="draft_mock_001")
    out = draft_vm.draft_to_dict(d)
    assert out["is_in_gmail"] is True
    assert "gmail_draft_id" not in out


def test_draft_to_dict_carries_body_and_verdict():
    out = draft_vm.draft_to_dict(_draft())
    assert out["body"].startswith("Dear Client")
    assert out["guardrail_state"] == GuardrailState.NOT_EVALUATED.value


# ── Timeline ──────────────────────────────────────────────────────────────────


def test_timeline_rows_cover_every_workflow_status():
    """Regression guard: GUARDRAILS_FAILED becomes reachable when guardrails ship."""
    rows = timeline_vm.timeline_rows(None)
    assert len(rows) == len(list(WorkflowStatus))
    assert {r["status"] for r in rows} == {s.value for s in WorkflowStatus}


def test_timeline_includes_guardrails_failed():
    statuses = {r["status"] for r in timeline_vm.timeline_rows(None)}
    assert WorkflowStatus.GUARDRAILS_FAILED.value in statuses


def test_timeline_unavailable_when_history_is_none():
    # BLOCKER-1: orchestrator never writes ctx.status.
    rows = timeline_vm.timeline_rows(None)
    assert all(r["state"] == timeline_vm.UNKNOWN for r in rows)
    assert all(r["available"] is False for r in rows)


def test_timeline_marks_done_current_and_pending():
    history = [WorkflowStatus.RECEIVED, WorkflowStatus.INGESTED]
    rows = {r["status"]: r["state"] for r in timeline_vm.timeline_rows(history)}
    assert rows[WorkflowStatus.RECEIVED.value] == timeline_vm.DONE
    assert rows[WorkflowStatus.INGESTED.value] == timeline_vm.CURRENT
    assert rows[WorkflowStatus.DRAFTED.value] == timeline_vm.PENDING


def test_timeline_unavailable_reason_names_the_blocker():
    assert "BLOCKER-1" in timeline_vm.timeline_unavailable_reason()


# ── Approval queue ────────────────────────────────────────────────────────────


def _item(**overrides) -> PendingItem:
    base = dict(
        draft_id="dr_test",
        to="client@example.com",
        subject="Re: Timeline",
        preview="Dear Client, the deliverables land on the 14th.",
        requested_at=datetime(2026, 7, 10, 9, 0, 0),
        timeout_at=None,
    )
    base.update(overrides)
    return PendingItem(**base)


def test_queue_row_reports_missing_body_rather_than_showing_nothing():
    row = queue_vm.pending_to_dict(_item())
    assert row["body"] is None
    assert "BLOCKER-2" in row["body_unavailable_reason"]


def test_queue_row_uses_full_body_once_the_gate_exposes_it():
    row = queue_vm.pending_to_dict(_item(draft=_draft()))
    assert row["body"].startswith("Dear Client")
    assert row["body_unavailable_reason"] is None
    assert row["guardrail_state"] == GuardrailState.NOT_EVALUATED.value


def test_queue_row_reports_missing_thread():
    row = queue_vm.pending_to_dict(_item())
    assert row["thread_available"] is False
    assert "BLOCKER-3" in row["thread_unavailable_reason"]


def test_is_expired_is_false_without_a_timeout():
    assert queue_vm.is_expired(_item(timeout_at=None)) is False


def test_is_expired_compares_against_injected_now():
    now = datetime(2026, 7, 10, 12, 0, 0)
    assert queue_vm.is_expired(_item(timeout_at=now - timedelta(minutes=1)), now) is True
    assert queue_vm.is_expired(_item(timeout_at=now + timedelta(minutes=1)), now) is False


def test_queue_summary_warns_that_pending_drafts_are_in_memory():
    summary = queue_vm.queue_summary([])
    assert summary["count"] == 0
    assert summary["has_items"] is False
    assert "restart" in summary["empty_message"]


def test_queue_rows_maps_all_items():
    assert len(queue_vm.queue_rows([_item(), _item(draft_id="dr_2")])) == 2


# ── Audit ─────────────────────────────────────────────────────────────────────


def _event(**overrides) -> AuditEvent:
    base = dict(
        action=AuditAction.DRAFT_APPROVED,
        actor="alice@example.com",
        resource_type="draft",
        resource_id="dr_test",
        workflow_id="wf_test",
        outcome="SUCCESS",
    )
    base.update(overrides)
    return AuditEvent(**base)


def test_audit_row_flags_success_and_failure():
    assert audit_vm.audit_to_dict(_event())["ok"] is True
    assert audit_vm.audit_to_dict(_event(outcome="FAILURE"))["ok"] is False


def test_audit_row_formats_resource():
    assert audit_vm.audit_to_dict(_event())["resource"] == "draft/dr_test"


def test_audit_row_omits_slash_when_no_resource_type():
    row = audit_vm.audit_to_dict(_event(resource_type="", resource_id="dr_test"))
    assert row["resource"] == "dr_test"


def test_audit_timestamps_are_declared_unreliable():
    # BLOCKER-6: read_recent() drops the persisted timestamp.
    assert audit_vm.timestamps_reliable() is False
    assert "BLOCKER-6" in audit_vm.TIMESTAMP_WARNING


def test_audit_rows_maps_all_events():
    assert len(audit_vm.audit_rows([_event(), _event()])) == 2


# ── Config ────────────────────────────────────────────────────────────────────


def _summary(**overrides) -> ConfigSummary:
    base = dict(
        app_env="development",
        app_version="1.0.0",
        llm_provider="openai",
        llm_model_draft="gpt-4o",
        llm_api_key_last4="1234",
        gmail_user_email="me@example.com",
        gmail_mode=GmailMode.READY,
        audit_log_path="./data/audit/audit.jsonl",
        approval_timeout_seconds=3600,
        reviewer="alice@example.com",
        permissions_enforced=False,
    )
    base.update(overrides)
    return ConfigSummary(**base)


def test_fingerprint_shows_only_last_four():
    assert config_vm.fingerprint("1234") == "••••1234"


def test_fingerprint_of_missing_key():
    assert config_vm.fingerprint("") == config_vm.NOT_SET


def test_config_rows_never_contain_a_full_key():
    rows = dict(config_vm.config_rows(_summary()))
    assert rows["LLM API key"] == "••••1234"


def test_mock_mode_is_a_warning():
    warnings = config_vm.config_warnings(_summary(gmail_mode=GmailMode.MOCK))
    assert any("MOCK" in w for w in warnings)


def test_needs_auth_is_a_warning():
    warnings = config_vm.config_warnings(_summary(gmail_mode=GmailMode.NEEDS_AUTH))
    assert any("Not authorised" in w for w in warnings)


def test_connected_gmail_is_not_a_warning():
    warnings = config_vm.config_warnings(_summary(gmail_mode=GmailMode.READY))
    assert not any("Gmail" in w for w in warnings)


def test_absent_permissions_are_surfaced_honestly():
    warnings = config_vm.config_warnings(_summary(permissions_enforced=False))
    assert any("permissions" in w.lower() for w in warnings)


def test_missing_llm_key_is_a_warning():
    warnings = config_vm.config_warnings(_summary(llm_api_key_last4=""))
    assert any("API key" in w for w in warnings)


def test_config_to_dict_shape():
    out = config_vm.config_to_dict(_summary())
    assert "rows" in out and "warnings" in out
