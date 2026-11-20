"""Smoke tests for the cookbook web UI.

Every recipe page must return 200 and show the verdict markers its
CLI demo prints — the web UI runs the same code in-process, so if a
marker disappears, the wiring broke. Run from the repo root:

    python3 -m pytest web -q
"""

import pytest
from fastapi.testclient import TestClient

from web.app import RECIPES, app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_lists_every_recipe():
    response = client.get("/")
    assert response.status_code == 200
    for recipe in RECIPES:
        assert recipe["title"] in response.text
        assert f"/recipes/{recipe['slug']}" in response.text


def test_unknown_recipe_is_404():
    assert client.get("/recipes/no-such-recipe").status_code == 404


def test_mcp_vs_utcp():
    response = client.get("/recipes/mcp-vs-utcp")
    assert response.status_code == 200
    # The direct path lets the absurd refund through; the gateway stops it.
    assert "refund $10,000, unapproved: (201" in response.text
    assert "unapproved refund:" in response.text
    assert "approved but absurd refund:" in response.text
    assert "audit log:" in response.text


def test_ask_your_csv_canned():
    response = client.get("/recipes/ask-your-csv")
    assert response.status_code == 200
    assert "Loaded 18 rows" in response.text
    assert "Total revenue: $18,250.00" in response.text
    assert "Top 2 products by revenue:" in response.text


def test_ask_your_csv_question():
    response = client.post(
        "/recipes/ask-your-csv",
        data={"question": "What is the total revenue in the North?"},
    )
    assert response.status_code == 200
    assert "Total revenue (region = North): $7,300.00" in response.text


def test_linkedin_post_to_code_canned():
    response = client.get("/recipes/linkedin-post-to-code")
    assert response.status_code == 200
    assert "Topic: mcp-vs-utcp" in response.text
    assert "Topic: state-machine-booking" in response.text
    assert "Test outline:" in response.text


def test_linkedin_post_to_code_pasted():
    response = client.post(
        "/recipes/linkedin-post-to-code",
        data={"post": "Retries keep double charging our customers. "
                      "We need idempotency keys and a ledger so a retry "
                      "is exactly once, not a second charge."},
    )
    assert response.status_code == 200
    assert "Topic: exactly-once-tools" in response.text


def test_meeting_brief_samples():
    response = client.get("/recipes/meeting-brief-agent")
    assert response.status_code == 200
    assert "Q1 planning sync" in response.text
    # (the apostrophe in "What's missing" is HTML-escaped in the page)
    assert "ask before you walk in" in response.text
    # The sparse "Quick sync" invite must be flagged, not filled in.
    assert "No agenda attached" in response.text


def test_meeting_brief_pasted():
    response = client.post(
        "/recipes/meeting-brief-agent",
        data={"invite": "Title: Budget review\nWhen: Friday 3 PM\n"
                        "Attendees: Sam, Jo (Finance lead)"},
    )
    assert response.status_code == 200
    assert "Budget review" in response.text
    assert "Role unknown for Sam" in response.text


def test_prior_auth_all_cases():
    response = client.get("/recipes/prior-auth-agent")
    assert response.status_code == 200
    # Three cases close out; PA-1004 is still waiting on a document.
    assert response.text.count("State: CLOSED") == 3
    assert "PA-1004" in response.text
    assert "State: INFO_REQUESTED" in response.text


def test_prior_auth_single_case():
    response = client.get("/recipes/prior-auth-agent?case=PA-1003")
    assert response.status_code == 200
    assert "# PA-1003" in response.text
    # "# PA-1001" is the status header; the bare ID appears in the
    # case-picker links, which is fine.
    assert "# PA-1001" not in response.text
    # The denial carried a reason and the appeal carried it along.
    assert "Denial reason:" in response.text
    assert "Appeal grounds:" in response.text


def test_deja_vu_both_paths():
    response = client.get("/recipes/deja-vu-agent")
    assert response.status_code == 200
    # Safe path: exactly one of each. Broken path: two of each.
    assert "Bookings in the world: 1" in response.text
    assert "Charges in the world: 1" in response.text
    assert "Bookings in the world: 2" in response.text
    assert "Charges in the world: 2" in response.text
    assert "exactly one booking, exactly one charge" in response.text
    assert "double-booked and double-charged" in response.text


def test_system_prompt_shown_where_defined():
    # Five recipes define a live-mode model prompt; mcp-vs-utcp runs
    # no model at all, so its page must not claim one.
    for slug in ("ask-your-csv", "linkedin-post-to-code",
                 "meeting-brief-agent", "prior-auth-agent", "deja-vu-agent"):
        response = client.get(f"/recipes/{slug}")
        assert "System prompt (live mode)" in response.text, slug
    response = client.get("/recipes/mcp-vs-utcp")
    assert "System prompt" not in response.text


def test_deja_vu_safe_only():
    response = client.get("/recipes/deja-vu-agent?path=safe")
    assert response.status_code == 200
    assert "Bookings in the world: 1" in response.text
    assert "Bookings in the world: 2" not in response.text
