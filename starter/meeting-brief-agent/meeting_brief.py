"""Build a meeting brief from an invite — grounded, never invented.

Two modes:

- Mock (default): a small deterministic builder reads the invite
  (a JSON dict, a pasted text invite, or a sample from
  data/meetings.json) and returns a structured brief — purpose,
  attendees and their roles, agenda, questions to ask, and what's
  missing. No model, no key, no network.
- Live: set GEMINI_API_KEY and pass --live, and the same invite goes
  to a real Gemini model (LiteLLM gemini/gemini-3.5-flash-lite, free
  tier) with the grounding rule in the prompt. Needs
  `pip install litellm`.

The one rule that matters: the brief only states what the invite
actually says. Anything the invite does not say is flagged in the
"What's missing" section — "no agenda attached", "role unknown for
Sam" — never filled in with a guess. A brief that invents context
is worse than no brief, because you walk in confident about things
nobody told you.
"""

import json
import os
import re

MODEL = "gemini/gemini-3.5-flash-lite"

# Keywords that hint at the meeting type. This is labelled as an
# inference in the brief ("looks like"), never stated as fact.
TYPE_KEYWORDS = {
    "planning": "planning session",
    "plan": "planning session",
    "review": "review",
    "retro": "retrospective",
    "retrospective": "retrospective",
    "interview": "interview",
    "1:1": "one-on-one",
    "one-on-one": "one-on-one",
    "standup": "standup",
    "sync": "sync",
    "demo": "demo",
    "kickoff": "kickoff",
    "brainstorm": "brainstorm",
    "decision": "decision meeting",
}


def load_samples(path):
    """Return the list of sample invite dicts in a JSON file."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalize_invite(raw):
    """Coerce an invite dict into a canonical shape.

    Accepts attendees as a list of strings ("Ada Lovelace") or dicts
    ({"name": "Ada Lovelace", "role": "PM"}). A bare string is a name
    with an unknown role — never a guessed role.
    """
    attendees = []
    for person in raw.get("attendees") or []:
        if isinstance(person, dict):
            attendees.append(
                {"name": person.get("name", ""), "role": person.get("role")}
            )
        else:
            name, role = _split_name_role(str(person))
            attendees.append({"name": name, "role": role})
    return {
        "title": raw.get("title") or "Untitled meeting",
        "when": raw.get("when"),
        "where": raw.get("where"),
        "attendees": attendees,
        "agenda": list(raw.get("agenda") or []),
        "notes": raw.get("notes"),
    }


def _split_name_role(text):
    """'Ada Lovelace (PM)' -> ('Ada Lovelace', 'PM'). No parens, no role."""
    match = re.match(r"^\s*(.+?)\s*\(([^)]+)\)\s*$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text.strip(), None


def parse_text_invite(text):
    """Parse a pasted plain-text invite into an invite dict.

    Understands `Key: value` lines (Title, When, Where, Attendees,
    Agenda, Notes) and bullet lines under Agenda. Anything it cannot
    place goes into notes. If nothing matches at all, the first line
    is the title and the rest is notes.
    """
    invite = {"title": None, "when": None, "where": None,
              "attendees": [], "agenda": [], "notes": None}
    lines = [line.rstrip() for line in text.strip().splitlines()]
    section = None
    notes_lines = []
    matched = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        key_match = re.match(r"^(title|when|time|date|where|location|link|attendees|people|with|agenda|notes|description|details)\s*:\s*(.*)$", stripped, re.IGNORECASE)
        if key_match:
            matched = True
            key = key_match.group(1).lower()
            value = key_match.group(2).strip()
            section = None
            if key == "title":
                invite["title"] = value
            elif key in ("when", "time", "date"):
                invite["when"] = value
            elif key in ("where", "location", "link"):
                invite["where"] = value
            elif key in ("attendees", "people", "with"):
                invite["attendees"] = [p.strip() for p in value.split(",") if p.strip()]
            elif key == "agenda":
                section = "agenda"
                if value:
                    invite["agenda"].append(value.lstrip("-•* ").strip())
            elif key in ("notes", "description", "details"):
                section = "notes"
                if value:
                    notes_lines.append(value)
            continue
        if section == "agenda":
            invite["agenda"].append(stripped.lstrip("-•* ").strip())
        elif section == "notes":
            notes_lines.append(stripped)
        else:
            notes_lines.append(stripped)

    if not matched:
        # No structure at all: first line is the title, rest is notes.
        invite["title"] = lines[0].strip() if lines else None
        notes_lines = lines[1:]
    if notes_lines:
        invite["notes"] = " ".join(notes_lines)
    return normalize_invite(invite)


def _infer_type(title, notes):
    """A labelled guess at the meeting type, from keywords only."""
    haystack = f"{title or ''} {notes or ''}".lower()
    for keyword, label in TYPE_KEYWORDS.items():
        if keyword in haystack:
            return label
    return None


def build_brief(raw_invite):
    """Build the structured brief. Returns a dict.

    Keys: title, when, where, purpose, meeting_type, attendees,
    agenda, notes, questions, missing, mode.
    """
    invite = normalize_invite(raw_invite)
    missing = []

    if not invite["agenda"]:
        missing.append("No agenda attached")
    unknown_roles = [a["name"] for a in invite["attendees"] if not a["role"]]
    for name in unknown_roles:
        missing.append(f"Role unknown for {name}")
    if not invite["attendees"]:
        missing.append("No attendees listed")
    if not invite["notes"]:
        missing.append("No background notes or context")
    if not invite["when"]:
        missing.append("No date or time in the invite")
    if not invite["where"]:
        missing.append("No location or meeting link")
    if not any(word in (invite["notes"] or "").lower()
               for word in ("decid", "decision", "approve", "approval")):
        missing.append("No decision owner named")

    purpose = invite["notes"] or "Not stated in the invite."

    questions = []
    if not invite["agenda"]:
        questions.append(
            "What are the 2–3 outcomes we need from this meeting?"
        )
    if unknown_roles:
        names = ", ".join(unknown_roles)
        questions.append(f"What is {names}'s role in this decision?")
    if invite["agenda"]:
        questions.append(
            "Which agenda item matters most if we run short on time?"
        )
    if not invite["notes"]:
        questions.append(
            "Is there a doc or pre-read to review before we start?"
        )
    if len(invite["attendees"]) > 6:
        questions.append(
            f"With {len(invite['attendees'])} people in the room, who "
            "needs to be here for the decision — and who is FYI?"
        )
    if invite["notes"]:
        questions.append("What does 'done' look like for this meeting?")

    return {
        "title": invite["title"],
        "when": invite["when"],
        "where": invite["where"],
        "purpose": purpose,
        "meeting_type": _infer_type(invite["title"], invite["notes"]),
        "attendees": invite["attendees"],
        "agenda": invite["agenda"],
        "notes": invite["notes"],
        "questions": questions,
        "missing": missing,
        "mode": "mock",
    }


def render_brief(brief):
    """Render a brief dict as plain text, ready to skim in 30 seconds."""
    lines = [f"# {brief['title']}"]
    if brief["when"]:
        lines.append(f"When: {brief['when']}")
    if brief["where"]:
        lines.append(f"Where: {brief['where']}")
    if brief["meeting_type"]:
        lines.append(f"Looks like: {brief['meeting_type']} (inferred from the invite)")
    lines.append("")
    lines.append("## Purpose")
    lines.append(brief["purpose"])
    lines.append("")
    lines.append("## Who's there")
    if brief["attendees"]:
        for person in brief["attendees"]:
            role = person["role"] or "role unknown"
            lines.append(f"- {person['name']} ({role})")
    else:
        lines.append("- (nobody listed)")
    lines.append("")
    lines.append("## Agenda")
    if brief["agenda"]:
        for item in brief["agenda"]:
            lines.append(f"- {item}")
    else:
        lines.append("- (none attached)")
    lines.append("")
    lines.append("## Questions to ask")
    for question in brief["questions"]:
        lines.append(f"- {question}")
    lines.append("")
    lines.append("## What's missing — ask before you walk in")
    if brief["missing"]:
        for gap in brief["missing"]:
            lines.append(f"- {gap}")
    else:
        lines.append("- Nothing — the invite covers the basics.")
    return "\n".join(lines)


def brief_live(raw_invite):
    """Build a brief with a real Gemini model. Needs GEMINI_API_KEY + litellm.

    The prompt carries the same grounding rule as the mock builder:
    only use what the invite says, flag the rest as missing.
    Raises RuntimeError with a plain-English reason when the live
    path is not available, so callers can fall back to mock.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm is not installed (pip install litellm).")
    os.environ["GEMINI_API_KEY"] = api_key
    response = litellm.completion(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are preparing a meeting brief from this invite.\n\n"
                    "RULE: only state what the invite actually says. Never "
                    "invent attendee details, context, or decisions. Anything "
                    "the invite does not say goes under 'What's missing'.\n\n"
                    "Return sections: Purpose, Who's there (name + role, or "
                    "'role unknown'), Agenda, Questions to ask (3-5, derived "
                    "from the gaps), What's missing.\n\n"
                    f"Invite:\n{json.dumps(raw_invite, indent=2)}"
                ),
            }
        ],
    )
    return response.choices[0].message.content.strip()
