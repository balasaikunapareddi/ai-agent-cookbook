"""Tests for the mock router. The sketches must be valid Python and
the router must pick the right template for each kind of post.
"""

import ast
import os

import pytest

from post_to_code import SKETCHES, detect_topic, generate, generate_live

MCP_POST = (
    "Do you actually need an MCP server in front of every API? "
    "UTCP says no — let agents call native endpoints directly. "
    "But a $10,000 refund nobody approved should never sail through."
)
CSV_POST = (
    "Our sales spreadsheet has the answers, but nobody wants to build "
    "a pivot table. What if we just asked it questions in plain English?"
)
BOOKING_POST = (
    "Our scheduling agent asks the visit type twice and once booked an "
    "appointment without confirming. The flow belongs in a state machine."
)
IDEMPOTENCY_POST = (
    "A retried webhook charged the customer twice. We need idempotency "
    "keys so a duplicate request returns the stored result."
)
UNKNOWN_POST = "I love rainy Sundays and strong filter coffee."


def test_every_sketch_is_valid_python():
    for topic, spec in SKETCHES.items():
        ast.parse(spec["sketch"])  # raises SyntaxError if invalid


def test_mcp_post_routes_to_policy_gateway():
    result = generate(MCP_POST)
    assert result["topic"] == "mcp-vs-utcp"
    assert "PolicyGateway" in result["sketch"]
    assert "approval" in result["sketch"]
    assert result["mode"] == "mock"


def test_csv_post_routes_to_ask_your_csv():
    result = generate(CSV_POST)
    assert result["topic"] == "ask-your-csv"
    assert "DictReader" in result["sketch"]


def test_booking_post_routes_to_state_machine():
    result = generate(BOOKING_POST)
    assert result["topic"] == "state-machine-booking"
    assert "AWAITING_CONFIRMATION" in result["sketch"]


def test_idempotency_post_routes_to_ledger():
    result = generate(IDEMPOTENCY_POST)
    assert result["topic"] == "exactly-once-tools"
    assert "IdempotencyLedger" in result["sketch"]


def test_unknown_post_falls_back_to_the_scaffold():
    result = generate(UNKNOWN_POST)
    assert result["topic"] == "agent-scaffold"
    assert "run_agent" in result["sketch"]


def test_every_result_has_a_test_outline():
    for post in (MCP_POST, CSV_POST, BOOKING_POST, IDEMPOTENCY_POST, UNKNOWN_POST):
        result = generate(post)
        assert len(result["test_outline"]) >= 3
        assert result["readme_snippet"].startswith("## ")


def test_detect_topic_prefers_the_strongest_match():
    assert detect_topic("mcp refund approval audit") == "mcp-vs-utcp"
    assert detect_topic("csv spreadsheet revenue rows") == "ask-your-csv"


def test_empty_post_is_rejected_not_sketched():
    with pytest.raises(ValueError):
        generate("   ")


def test_live_mode_without_a_key_says_so_plainly():
    os.environ.pop("GEMINI_API_KEY", None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        generate_live(MCP_POST)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
