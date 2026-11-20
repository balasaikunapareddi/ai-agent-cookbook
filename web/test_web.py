"""Smoke tests for the cookbook web UI.

Every recipe page must open with a "Run the agent" panel and run
nothing on page load — GET shows a clearly labeled sample run, and
only a form submission (POST) produces a fresh run. The web UI runs
the same code in-process as the CLI demos, so if a verdict marker
disappears, the wiring broke. Run from the repo root:

    python3 -m pytest web -q
"""

import pytest
from fastapi.testclient import TestClient

from web.app import RECIPES, app

client = TestClient(app)

# The big run button each page must show.
RUN_BUTTONS = {
    "mcp-vs-utcp": "Try it",
    "ask-your-csv": "Ask",
    "linkedin-post-to-code": "Generate code",
    "meeting-brief-agent": "Brief me",
    "prior-auth-agent": "Run case",
    "deja-vu-agent": "Run WITH idempotency",
}


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


def test_every_page_opens_with_run_panel_and_sample_only():
    # Page load must never present a fresh run: a run panel with a
    # submit button, a labeled sample section, and no "Your run".
    for recipe in RECIPES:
        slug = recipe["slug"]
        response = client.get(f"/recipes/{slug}")
        assert response.status_code == 200, slug
        assert "runpanel" in response.text, slug
        assert 'method="post"' in response.text, slug
        assert RUN_BUTTONS[slug] in response.text, slug
        assert "Sample run" in response.text, slug
        assert "Your run" not in response.text, slug


# --- mcp-vs-utcp ------------------------------------------------------

def test_mcp_vs_utcp_sample():
    response = client.get("/recipes/mcp-vs-utcp")
    assert response.status_code == 200
    # The sample is the canned scenario: the direct path lets the
    # absurd refund through; the gateway stops it.
    assert "refund $10,000, unapproved: (201" in response.text
    assert "unapproved refund:" in response.text
    assert "approved but absurd refund:" in response.text
    assert "audit log:" in response.text
    # The panel offers the interactive version.
    assert 'name="order_id"' in response.text
    assert 'name="amount"' in response.text
    assert 'name="approved"' in response.text


def test_mcp_vs_utcp_try_unapproved_absurd():
    response = client.post(
        "/recipes/mcp-vs-utcp",
        data={"order_id": "A-103", "amount": "10000"},
    )
    assert response.status_code == 200
    assert "Your run" in response.text
    # Direct path: the native API processes it anyway (201).
    assert "(201" in response.text
    # Gateway path: refused before it reaches the API, and audited.
    assert "rejected: create_refund has side effects and needs approval" in response.text
    assert "audit log:" in response.text


def test_mcp_vs_utcp_try_approved_sane():
    response = client.post(
        "/recipes/mcp-vs-utcp",
        data={"order_id": "A-103", "amount": "24.50", "approved": "yes"},
    )
    assert response.status_code == 200
    # Approved and within the order total: the gateway lets it through.
    assert "rejected:" not in response.text
    # (quotes are HTML-escaped in the page: &#x27; is ')
    assert "&#x27;outcome&#x27;: &#x27;allowed&#x27;" in response.text


def test_mcp_vs_utcp_try_approved_absurd():
    response = client.post(
        "/recipes/mcp-vs-utcp",
        data={"order_id": "A-103", "amount": "10000", "approved": "yes"},
    )
    assert response.status_code == 200
    # Approval is not enough: the amount is outside 0..24.5.
    assert "outside 0..24.5" in response.text


# --- ask-your-csv -----------------------------------------------------

def test_ask_your_csv_sample():
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
    assert "Your run" in response.text
    assert "Total revenue (region = North): $7,300.00" in response.text


# --- linkedin-post-to-code --------------------------------------------

def test_linkedin_post_to_code_sample():
    response = client.get("/recipes/linkedin-post-to-code")
    assert response.status_code == 200
    # The sample run covers the first canned post only.
    assert "Topic: mcp-vs-utcp" in response.text
    assert "Test outline:" in response.text
    assert "Topic: state-machine-booking" not in response.text


def test_linkedin_post_to_code_sample_prefill():
    response = client.get("/recipes/linkedin-post-to-code?sample=2")
    assert response.status_code == 200
    # The second sample post is loaded into the textarea, not run.
    assert "keeps asking the same question twice" in response.text
    assert "Your run" not in response.text


def test_linkedin_post_to_code_pasted():
    response = client.post(
        "/recipes/linkedin-post-to-code",
        data={"post": "Retries keep double charging our customers. "
                      "We need idempotency keys and a ledger so a retry "
                      "is exactly once, not a second charge."},
    )
    assert response.status_code == 200
    assert "Topic: exactly-once-tools" in response.text


# --- meeting-brief-agent ----------------------------------------------

def test_meeting_brief_sample():
    response = client.get("/recipes/meeting-brief-agent")
    assert response.status_code == 200
    # The sample briefs the invite prefilled in the textarea.
    assert "Q1 planning sync" in response.text
    assert "ask before you walk in" in response.text


def test_meeting_brief_pasted():
    response = client.post(
        "/recipes/meeting-brief-agent",
        data={"invite": "Title: Budget review\nWhen: Friday 3 PM\n"
                        "Attendees: Sam, Jo (Finance lead)"},
    )
    assert response.status_code == 200
    assert "Budget review" in response.text
    assert "Role unknown for Sam" in response.text
    # No agenda in the pasted invite: flagged, never invented.
    assert "No agenda attached" in response.text


# --- prior-auth-agent -------------------------------------------------

def test_prior_auth_sample_all_cases():
    response = client.get("/recipes/prior-auth-agent")
    assert response.status_code == 200
    # The sample runs all four cases: three close out, PA-1004 waits.
    assert response.text.count("State: CLOSED") == 3
    assert "PA-1004" in response.text
    assert "State: INFO_REQUESTED" in response.text
    # The panel is a case picker + submit, not links.
    assert '<select id="case" name="case">' in response.text
    assert "Run case" in response.text


def test_prior_auth_run_single_case():
    response = client.post(
        "/recipes/prior-auth-agent", data={"case": "PA-1003"})
    assert response.status_code == 200
    assert "Your run" in response.text
    assert "# PA-1003" in response.text
    # "# PA-1001" is the status header; the bare ID appears in the
    # case-picker options, which is fine.
    assert "# PA-1001" not in response.text
    # The denial carried a reason and the appeal carried it along.
    assert "Denial reason:" in response.text
    assert "Appeal grounds:" in response.text


def test_prior_auth_run_all_cases():
    response = client.post("/recipes/prior-auth-agent", data={"case": ""})
    assert response.status_code == 200
    assert response.text.count("State: CLOSED") == 3


# --- deja-vu-agent ----------------------------------------------------

def test_deja_vu_sample_both_paths():
    response = client.get("/recipes/deja-vu-agent")
    assert response.status_code == 200
    # The sample shows both endings: exactly once vs twice.
    assert "Bookings in the world: 1" in response.text
    assert "Charges in the world: 1" in response.text
    assert "Bookings in the world: 2" in response.text
    assert "Charges in the world: 2" in response.text
    assert "exactly one booking, exactly one charge" in response.text
    assert "double-booked and double-charged" in response.text
    # The panel: scenario fields + both run buttons.
    assert 'name="patient"' in response.text
    assert 'name="slot"' in response.text
    assert 'name="copay"' in response.text
    assert "Run WITH idempotency" in response.text
    assert "Run WITHOUT idempotency" in response.text


def test_deja_vu_run_with_idempotency_custom_scenario():
    response = client.post(
        "/recipes/deja-vu-agent",
        data={"path": "safe", "patient": "patient-999 (mock)",
              "slot": "2026-12-01T10:30", "copay": "40.00"},
    )
    assert response.status_code == 200
    assert "Your run" in response.text
    # The visitor's scenario ran — and still landed exactly once.
    assert "patient-999 (mock)" in response.text
    assert "2026-12-01T10:30" in response.text
    assert "$40.00" in response.text
    assert "Bookings in the world: 1" in response.text
    assert "Charges in the world: 1" in response.text
    assert "Bookings in the world: 2" not in response.text
    assert "exactly one booking, exactly one charge" in response.text


def test_deja_vu_run_without_idempotency():
    response = client.post(
        "/recipes/deja-vu-agent",
        data={"path": "unsafe", "patient": "patient-999 (mock)",
              "slot": "2026-12-01T10:30", "copay": "40.00"},
    )
    assert response.status_code == 200
    assert "Bookings in the world: 2" in response.text
    assert "Charges in the world: 2" in response.text
    assert "double-booked and double-charged" in response.text
    assert "Bookings in the world: 1" not in response.text


# --- system prompts ---------------------------------------------------

def test_system_prompt_shown_where_defined():
    # Five recipes define a live-mode model prompt; mcp-vs-utcp runs
    # no model at all, so its page must not claim one.
    for slug in ("ask-your-csv", "linkedin-post-to-code",
                 "meeting-brief-agent", "prior-auth-agent", "deja-vu-agent"):
        response = client.get(f"/recipes/{slug}")
        assert "System prompt (live mode)" in response.text, slug
    response = client.get("/recipes/mcp-vs-utcp")
    assert "System prompt" not in response.text
