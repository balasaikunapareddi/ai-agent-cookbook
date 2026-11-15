"""Tests for the meeting brief builder.

The grounding rule is what gets tested hardest: a brief must never
state anything the invite did not say. Every expectation below is
computed from data/meetings.json by hand.
"""

import os

import pytest

from meeting_brief import build_brief, load_samples, parse_text_invite

HERE = os.path.dirname(__file__)
SAMPLES = load_samples(os.path.join(HERE, "data", "meetings.json"))


def test_samples_load_four_invites():
    assert len(SAMPLES) == 4


def test_well_formed_invite_has_no_agenda_gap():
    brief = build_brief(SAMPLES[0])
    assert brief["title"] == "Q1 planning sync — care journey squad"
    assert "No agenda attached" not in brief["missing"]
    assert len(brief["agenda"]) == 3
    assert brief["meeting_type"] == "planning session"
    assert brief["mode"] == "mock"


def test_well_formed_invite_lists_roles():
    brief = build_brief(SAMPLES[0])
    roles = {a["name"]: a["role"] for a in brief["attendees"]}
    assert roles["Maya Chen"] == "Product manager"
    assert roles["Dev Patel"] == "Engineering lead"
    assert not any("Role unknown" in gap for gap in brief["missing"])


def test_vague_invite_flags_everything_missing():
    brief = build_brief(SAMPLES[1])
    assert "No agenda attached" in brief["missing"]
    assert "Role unknown for Jordan" in brief["missing"]
    assert "Role unknown for Alex" in brief["missing"]
    assert "No background notes or context" in brief["missing"]
    assert "No location or meeting link" in brief["missing"]


def test_vague_invite_never_invents_roles():
    brief = build_brief(SAMPLES[1])
    assert all(a["role"] is None for a in brief["attendees"])
    rendered_roles = " ".join(
        a["role"] or "" for a in brief["attendees"]
    )
    assert rendered_roles.strip() == ""


def test_vague_invite_asks_for_outcomes_first():
    brief = build_brief(SAMPLES[1])
    assert brief["questions"][0] == (
        "What are the 2–3 outcomes we need from this meeting?"
    )


def test_vendor_demo_flags_the_unknown_role_only():
    brief = build_brief(SAMPLES[2])
    assert "Role unknown for Ruth Alvarez" in brief["missing"]
    assert "No agenda attached" not in brief["missing"]
    assert "Which agenda item matters most if we run short on time?" in (
        brief["questions"]
    )


def test_brief_asks_what_done_looks_like_when_purpose_exists():
    brief = build_brief(SAMPLES[0])
    assert "What does 'done' look like for this meeting?" in brief["questions"]


def test_minimal_invite_purpose_is_not_stated():
    brief = build_brief(SAMPLES[3])
    assert brief["purpose"] == "Not stated in the invite."
    assert brief["meeting_type"] == "one-on-one"


def test_empty_invite_is_all_gaps():
    brief = build_brief({})
    assert brief["title"] == "Untitled meeting"
    assert "No agenda attached" in brief["missing"]
    assert "No attendees listed" in brief["missing"]
    assert "No background notes or context" in brief["missing"]
    assert "No date or time in the invite" in brief["missing"]
    assert "No location or meeting link" in brief["missing"]
    assert brief["questions"]  # still gives you something to ask


def test_text_invite_parses_key_value_lines():
    invite = parse_text_invite(
        "Title: Design review\n"
        "When: Thursday 3 PM\n"
        "Attendees: Ada Lovelace (PM), Grace Hopper\n"
        "Agenda:\n"
        "- New onboarding flow\n"
        "- Rollout plan\n"
        "Notes: Decide whether to ship the new flow next week."
    )
    brief = build_brief(invite)
    assert brief["title"] == "Design review"
    assert brief["when"] == "Thursday 3 PM"
    assert len(brief["agenda"]) == 2
    assert brief["agenda"][0] == "New onboarding flow"
    assert "Role unknown for Grace Hopper" in brief["missing"]
    assert "No agenda attached" not in brief["missing"]


def test_unstructured_text_becomes_title_and_notes():
    brief = build_brief(parse_text_invite("Coffee with the new hire\nJust a chat, nothing formal."))
    assert brief["title"] == "Coffee with the new hire"
    assert brief["purpose"] == "Just a chat, nothing formal."
    assert "No attendees listed" in brief["missing"]


def test_live_mode_without_a_key_raises_plainly(monkeypatch):
    from meeting_brief import brief_live

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        brief_live(SAMPLES[0])
