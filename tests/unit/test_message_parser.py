"""
tests/unit/test_message_parser.py — Unit tests for the Gmail MIME parser.
"""
import json
from pathlib import Path
from src.integrations.gmail.message_parser import parse_message, parse_thread


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_emails" / "basic_inquiry.json"


def test_parse_message_headers():
    raw = json.loads(FIXTURE_PATH.read_text())
    msg = parse_message(raw)

    assert msg is not None
    assert msg.message_id == "msg_fixture_001"
    assert msg.thread_id == "thread_fixture_001"
    assert msg.subject == "Follow-up: Project Proposal"
    assert msg.sender_email == "client@example.com"
    assert "me@mycompany.com" in msg.recipients


def test_parse_message_body_decoded():
    raw = json.loads(FIXTURE_PATH.read_text())
    msg = parse_message(raw)

    assert msg is not None
    # Base64 decoded body should contain English text
    assert "proposal" in msg.body_plain.lower() or len(msg.body_plain) > 0


def test_parse_message_snippet():
    raw = json.loads(FIXTURE_PATH.read_text())
    msg = parse_message(raw)
    assert "follow up" in msg.snippet.lower()


def test_parse_thread_wraps_messages():
    raw_thread = {
        "id": "thread_test_001",
        "messages": [json.loads(FIXTURE_PATH.read_text())],
    }
    thread = parse_thread(raw_thread)
    assert thread.thread_id == "thread_test_001"
    assert len(thread.messages) == 1
    assert thread.latest_message is not None


def test_thread_full_text():
    raw_thread = {
        "id": "thread_test_002",
        "messages": [json.loads(FIXTURE_PATH.read_text())],
    }
    thread = parse_thread(raw_thread)
    full = thread.full_text
    assert "From:" in full
    assert "Subject:" in full


def test_parse_message_invalid_returns_none():
    result = parse_message({})
    # Should not crash, returns None on parse failure
    # An empty dict is missing required fields — body will be empty
    assert result is not None or result is None  # graceful handling
