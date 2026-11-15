"""Prior authorization tracker: a state machine for a long wait.

Prior authorization is not a form. It is a wait. A request can sit
pending with a payer for days, and the agent's real job is holding
state across that silence and resuming exactly where it left off
when the payer responds — never re-asking for a document that is
already on file, never guessing at a clinical detail it was never
given.

The machine (all rules in pure Python, no model involved):

    DRAFT -> SUBMITTED -> PENDING -> APPROVED -> CLOSED
                              |  |          ^
                              |  +-> DENIED +-> APPEALED -+
                              |                            |
                              +-> INFO_REQUESTED ----------+  (supply the
                                  (hold until the doc      |   requested doc,
                                   is supplied, once)      |   then back to
                                                           |   PENDING)

Rules the machine enforces:

- Submitting needs the required *fields* (patient, date of birth,
  procedure, payer). A missing field blocks the submit and the
  machine says exactly which field is missing — it never fills one
  in. A missing *document* does not block submission; it is recorded
  as a gap, and the payer may ask for it later.
- Requesting a document that is already on file is a no-op with a
  journal note, not a second request. Providing a document that is
  already on file is the same.
- A denial must carry a reason, recorded verbatim. An appeal must
  carry grounds and always travels with the denial reason attached.
- Every transition is written to a journal with a simulated day, so
  the wait is visible: submitted day 0, payer answers day 4, appeal
  day 9. State is saved to JSON after every step and loaded back
  before the next one — the pause/resume is real, not a comment.

Mock mode needs nothing: no key, no extra packages, no network.
The payer in this recipe is scripted (see data/cases.json) — a
timeline of the responses the mock payer sends on each day.

Live: set GEMINI_API_KEY and pass --live, and the same case journal
goes to a real Gemini model, which writes a patient-friendly status
update. The model writes message text only — it never decides a
transition, and the prompt forbids inventing clinical details.
Needs `pip install litellm`.
"""

import json
import os

STATES = {
    "DRAFT",
    "SUBMITTED",
    "PENDING",
    "INFO_REQUESTED",
    "APPROVED",
    "DENIED",
    "APPEALED",
    "CLOSED",
}

# Fields a submission must have. Missing one blocks the submit.
REQUIRED_FIELDS = ["patient_name", "date_of_birth", "procedure", "payer"]

# Transitions the machine allows, as {from_state: {event: to_state}}.
# Events that need an argument (deny, appeal, request_info) are
# handled in apply_event; this table is the shape of the machine.
ALLOWED = {
    "DRAFT": {"submit", "provide_document"},
    "SUBMITTED": {"received", "provide_document"},
    "PENDING": {"approve", "deny", "request_info", "provide_document"},
    "INFO_REQUESTED": {"provide_document"},
    "APPROVED": {"close"},
    "DENIED": {"appeal", "close"},
    "APPEALED": {"approve", "deny"},
    "CLOSED": set(),
}


def new_case(case_id, patient_name, date_of_birth, procedure, payer,
             required_documents, diagnosis=None):
    """A fresh prior-auth request, in DRAFT, with an empty journal."""
    return {
        "case_id": case_id,
        "patient_name": patient_name,
        "date_of_birth": date_of_birth,
        "procedure": procedure,
        "diagnosis": diagnosis,
        "payer": payer,
        "required_documents": list(required_documents),
        "documents": {},
        "state": "DRAFT",
        "denial_reason": None,
        "appeal_grounds": None,
        "outcome": None,
        "day": 0,
        "journal": [
            {"step": 0, "day": 0, "event": "created",
             "note": f"Request {case_id} drafted for {procedure}."}
        ],
    }


def missing_fields(case):
    """Required fields that are empty or absent — these block a submit."""
    return [f for f in REQUIRED_FIELDS if not case.get(f)]


def missing_documents(case):
    """Required documents not yet on file — gaps, not blockers."""
    return [d for d in case["required_documents"]
            if d not in case["documents"]]


def _journal(case, day, event, note):
    case["day"] = day
    case["journal"].append({
        "step": len(case["journal"]),
        "day": day,
        "event": event,
        "note": note,
    })


def _move(case, day, event, to_state, note):
    case["state"] = to_state
    _journal(case, day, event, note)
    return case


def apply_event(case, event):
    """Apply one event to a case. Returns the (mutated) case.

    event is a dict: {"day": int, "event": str, ...extra args}.
    Illegal transitions raise ValueError with a plain-English reason.
    Supplying a document that is already on file, or asking for one
    that is, is a journal note — never a second request.
    """
    day = event.get("day", case["day"])
    name = event["event"]
    state = case["state"]

    if name not in ALLOWED.get(state, set()):
        raise ValueError(
            f"Cannot '{name}' while the request is {state}."
        )

    if name == "submit":
        missing = missing_fields(case)
        if missing:
            raise ValueError(
                "Cannot submit: missing " + ", ".join(missing) +
                ". The request stays in DRAFT — nothing is guessed."
            )
        gaps = missing_documents(case)
        note = f"Submitted to {case['payer']}."
        if gaps:
            note += " Still missing: " + ", ".join(gaps) + "."
        return _move(case, day, "submit", "SUBMITTED", note)

    if name == "received":
        return _move(case, day, "received", "PENDING",
                     f"{case['payer']} confirmed receipt. Waiting.")

    if name == "approve":
        valid = event.get("valid_until")
        note = "Approved by the payer."
        if valid:
            note += f" Authorization valid through {valid}."
        return _move(case, day, "approve", "APPROVED", note)

    if name == "deny":
        reason = (event.get("reason") or "").strip()
        if not reason:
            raise ValueError("A denial needs a reason — it cannot be blank.")
        case["denial_reason"] = reason
        return _move(case, day, "deny", "DENIED",
                     f"Denied. Reason recorded: {reason}")

    if name == "request_info":
        document = event["document"]
        if document in case["documents"]:
            _journal(case, day, "request_info",
                     f"Payer asked for {document} — already on file. "
                     "Not requested again.")
            return case
        case.setdefault("requested_documents", []).append(document)
        return _move(case, day, "request_info", "INFO_REQUESTED",
                     f"Payer asked for {document}. Holding until it arrives.")

    if name == "provide_document":
        document = event["document"]
        if document in case["documents"]:
            _journal(case, day, "provide_document",
                     f"{document} was already on file. Not sent twice.")
            return case
        case["documents"][document] = event.get("content", "on file")
        requested = case.get("requested_documents", [])
        if document in requested:
            requested.remove(document)
        if state == "INFO_REQUESTED" and not requested:
            return _move(case, day, "provide_document", "PENDING",
                         f"{document} supplied. Back to waiting on the payer.")
        _journal(case, day, "provide_document",
                 f"{document} added to the file.")
        return case

    if name == "appeal":
        grounds = (event.get("grounds") or "").strip()
        if not grounds:
            raise ValueError("An appeal needs grounds — it cannot be blank.")
        case["appeal_grounds"] = grounds
        return _move(case, day, "appeal", "APPEALED",
                     f"Appealed with the denial reason attached: "
                     f"{case['denial_reason']} — {grounds}")

    if name == "close":
        outcome = event.get("outcome") or case["state"].lower()
        case["outcome"] = outcome
        return _move(case, day, "close", "CLOSED",
                     f"Closed. Outcome: {outcome}.")

    raise ValueError(f"Unknown event: {name}")


def save_state(case, state_dir):
    """Persist a case to JSON. This is the pause: the wait can be days,
    and the next run resumes from this file, not from memory."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"{case['case_id']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(case, handle, indent=2)
    return path


def load_state(case_id, state_dir):
    """Resume a case exactly where the last run left it."""
    path = os.path.join(state_dir, f"{case_id}.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_cases(path):
    """Sample cases + their scripted payer timelines, from JSON."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = []
    for raw in data:
        case = new_case(
            raw["case_id"], raw["patient_name"], raw["date_of_birth"],
            raw["procedure"], raw["payer"], raw["required_documents"],
            diagnosis=raw.get("diagnosis"),
        )
        for doc in raw.get("documents_on_file", []):
            case["documents"][doc] = "on file"
        cases.append((case, raw["timeline"]))
    return cases


def render_status(case):
    """A one-page status: where the request is, what is collected,
    what is missing, and the journal of the wait so far."""
    lines = [
        f"# {case['case_id']} — {case['procedure']}",
        f"Patient: {case['patient_name']} (DOB {case['date_of_birth']})",
        f"Payer: {case['payer']}",
        f"State: {case['state']} (day {case['day']})",
        "",
        "## On file",
    ]
    for doc in case["required_documents"]:
        mark = "yes" if doc in case["documents"] else "MISSING"
        lines.append(f"- {doc}: {mark}")
    if case["denial_reason"]:
        lines.append(f"\nDenial reason: {case['denial_reason']}")
    if case["appeal_grounds"]:
        lines.append(f"Appeal grounds: {case['appeal_grounds']}")
    if case["outcome"]:
        lines.append(f"Outcome: {case['outcome']}")
    lines.append("\n## Journal")
    for entry in case["journal"]:
        lines.append(f"- day {entry['day']}: {entry['note']}")
    return "\n".join(lines)


def status_update_live(case):
    """A patient-friendly status update from a real Gemini model.

    The model writes message text only — it never decides a
    transition, and the prompt forbids inventing clinical details:
    it may only restate what the journal says.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm is not installed (pip install litellm).")
    os.environ["GEMINI_API_KEY"] = api_key
    journal = "\n".join(
        f"day {e['day']}: {e['note']}" for e in case["journal"]
    )
    response = litellm.completion(
        model="gemini/gemini-3.5-flash-lite",
        messages=[{
            "role": "user",
            "content": (
                "Write a short, plain-English status update for the patient "
                "about this prior authorization request. Use ONLY the facts "
                "in the journal below. Do not invent clinical details, dates, "
                "or reasons that are not in the journal. If something is "
                "missing, say it is still needed — do not fill it in.\n\n"
                f"Request: {case['case_id']}, {case['procedure']}, "
                f"payer {case['payer']}, current state {case['state']}.\n"
                f"Journal:\n{journal}"
            ),
        }],
    )
    return response.choices[0].message.content.strip()
