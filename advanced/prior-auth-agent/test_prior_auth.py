"""Tests for the prior-auth state machine.

The machine is pure Python, so every rule pins down exactly: what
blocks a submit, what the wait looks like, what never gets re-asked,
and what an appeal must carry. No model, no network, no key.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prior_auth import (  # noqa: E402
    apply_event,
    load_cases,
    load_state,
    missing_documents,
    missing_fields,
    new_case,
    render_status,
    save_state,
)


def _case(**overrides):
    base = {
        "case_id": "PA-TEST",
        "patient_name": "Test Patient",
        "date_of_birth": "1990-01-01",
        "procedure": "MRI knee",
        "payer": "North Star Health Plan (mock payer)",
        "required_documents": ["prior_auth_form", "clinical_notes"],
    }
    base.update(overrides)
    return new_case(**base)


def _submitted(case):
    case["documents"]["prior_auth_form"] = "on file"
    apply_event(case, {"day": 0, "event": "submit"})
    apply_event(case, {"day": 1, "event": "received"})
    return case


def test_submit_blocked_when_a_required_field_is_missing():
    case = _case(patient_name="")
    assert missing_fields(case) == ["patient_name"]
    with pytest.raises(ValueError, match="missing patient_name"):
        apply_event(case, {"day": 0, "event": "submit"})
    assert case["state"] == "DRAFT"


def test_submit_allowed_with_a_missing_document_gap_flagged():
    case = _case()
    apply_event(case, {"day": 0, "event": "submit"})
    assert case["state"] == "SUBMITTED"
    assert missing_documents(case) == ["prior_auth_form", "clinical_notes"]
    assert "Still missing" in case["journal"][-1]["note"]


def test_illegal_transition_raises_plainly():
    case = _case()
    with pytest.raises(ValueError, match="Cannot 'approve' while the request is DRAFT"):
        apply_event(case, {"day": 0, "event": "approve"})
    with pytest.raises(ValueError, match="Cannot 'close' while the request is DRAFT"):
        apply_event(case, {"day": 0, "event": "close"})


def test_received_moves_submitted_to_pending():
    case = _case()
    apply_event(case, {"day": 0, "event": "submit"})
    apply_event(case, {"day": 1, "event": "received"})
    assert case["state"] == "PENDING"
    assert case["journal"][-1]["note"].endswith("Waiting.")


def test_request_info_for_a_document_already_on_file_is_a_noop():
    case = _submitted(_case())
    case["documents"]["clinical_notes"] = "on file"
    before = len(case["journal"])
    apply_event(case, {"day": 4, "event": "request_info",
                       "document": "clinical_notes"})
    assert case["state"] == "PENDING"
    assert len(case["journal"]) == before + 1
    assert "already on file" in case["journal"][-1]["note"]
    assert "clinical_notes" not in case.get("requested_documents", [])


def test_provide_document_twice_is_a_noop_the_second_time():
    case = _submitted(_case())
    apply_event(case, {"day": 4, "event": "request_info",
                       "document": "clinical_notes"})
    assert case["state"] == "INFO_REQUESTED"
    apply_event(case, {"day": 5, "event": "provide_document",
                       "document": "clinical_notes"})
    assert case["state"] == "PENDING"
    before = len(case["journal"])
    apply_event(case, {"day": 6, "event": "provide_document",
                       "document": "clinical_notes"})
    assert case["state"] == "PENDING"
    assert len(case["journal"]) == before + 1
    assert "already on file" in case["journal"][-1]["note"]


def test_info_requested_holds_until_the_document_arrives():
    case = _submitted(_case())
    apply_event(case, {"day": 4, "event": "request_info",
                       "document": "sleep_diary"})
    assert case["state"] == "INFO_REQUESTED"
    assert case["requested_documents"] == ["sleep_diary"]
    # A second, different request does not overwrite the first.
    apply_event(case, {"day": 5, "event": "provide_document",
                       "document": "sleep_diary"})
    assert case["state"] == "PENDING"
    assert case["requested_documents"] == []


def test_deny_needs_a_reason_and_records_it_verbatim():
    case = _submitted(_case())
    with pytest.raises(ValueError, match="needs a reason"):
        apply_event(case, {"day": 5, "event": "deny", "reason": "  "})
    apply_event(case, {"day": 5, "event": "deny",
                       "reason": "Insufficient documentation."})
    assert case["state"] == "DENIED"
    assert case["denial_reason"] == "Insufficient documentation."


def test_appeal_only_from_denied_and_carries_the_reason():
    case = _submitted(_case())
    with pytest.raises(ValueError, match="Cannot 'appeal'"):
        apply_event(case, {"day": 2, "event": "appeal", "grounds": "x"})
    apply_event(case, {"day": 5, "event": "deny",
                       "reason": "Insufficient documentation."})
    with pytest.raises(ValueError, match="needs grounds"):
        apply_event(case, {"day": 6, "event": "appeal", "grounds": ""})
    apply_event(case, {"day": 6, "event": "appeal",
                       "grounds": "Notes show six weeks of treatment."})
    assert case["state"] == "APPEALED"
    assert "Insufficient documentation." in case["journal"][-1]["note"]


def test_appeal_can_be_approved_and_closed():
    case = _submitted(_case())
    apply_event(case, {"day": 5, "event": "deny", "reason": "Not covered."})
    apply_event(case, {"day": 6, "event": "appeal", "grounds": "See notes."})
    apply_event(case, {"day": 10, "event": "approve",
                       "valid_until": "2027-04-30"})
    assert case["state"] == "APPROVED"
    apply_event(case, {"day": 10, "event": "close",
                       "outcome": "approved on appeal"})
    assert case["state"] == "CLOSED"
    assert case["outcome"] == "approved on appeal"


def test_save_load_round_trip_resumes_exactly(tmp_path):
    case = _submitted(_case())
    apply_event(case, {"day": 4, "event": "request_info",
                       "document": "clinical_notes"})
    save_state(case, str(tmp_path))
    resumed = load_state("PA-TEST", str(tmp_path))
    assert resumed == case
    assert resumed["state"] == "INFO_REQUESTED"
    # The resumed case continues from where it stopped, not from scratch.
    apply_event(resumed, {"day": 5, "event": "provide_document",
                          "document": "clinical_notes"})
    assert resumed["state"] == "PENDING"
    assert len(resumed["journal"]) == len(case["journal"]) + 1


def test_all_sample_cases_replay_to_their_expected_states(tmp_path):
    here = os.path.dirname(os.path.abspath(__file__))
    cases = load_cases(os.path.join(here, "data", "cases.json"))
    expected = {
        "PA-1001": ("CLOSED", "approved"),
        "PA-1002": ("CLOSED", "approved"),
        "PA-1003": ("CLOSED", "approved on appeal"),
        "PA-1004": ("INFO_REQUESTED", None),
    }
    for case, timeline in cases:
        save_state(case, str(tmp_path))
        for event in timeline:
            case = load_state(case["case_id"], str(tmp_path))
            apply_event(case, event)
            save_state(case, str(tmp_path))
        state, outcome = expected[case["case_id"]]
        assert case["state"] == state, case["case_id"]
        assert case["outcome"] == outcome, case["case_id"]


def test_render_status_shows_gaps_honestly():
    case = _case()
    rendered = render_status(case)
    assert "MISSING" in rendered
    assert "prior_auth_form: MISSING" in rendered
    assert "State: DRAFT" in rendered
