"""Run each cookbook recipe's demo in-process, mock mode only.

Every recipe is standard-library-only in mock mode (the optional
``--live`` Gemini path needs litellm + a key and is never used here),
so the web UI can import the recipe modules directly and call the
same functions the CLI demos call. No API key, no network, no real
data — the output text is exactly what ``python3 demo.py`` prints.

The recipe folders are plain directories of modules (no packages),
and the modules import each other by bare name (``from tools import
...``), so each recipe folder goes on ``sys.path`` at import time.
Module names are unique across recipes, so nothing collides.
"""

import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_RECIPE_DIRS = [
    os.path.join(REPO_ROOT, "starter", "mcp-vs-utcp"),
    os.path.join(REPO_ROOT, "starter", "ask-your-csv"),
    os.path.join(REPO_ROOT, "starter", "linkedin-post-to-code"),
    os.path.join(REPO_ROOT, "starter", "meeting-brief-agent"),
    os.path.join(REPO_ROOT, "advanced", "prior-auth-agent"),
    os.path.join(REPO_ROOT, "advanced", "deja-vu-agent"),
]
for _path in _RECIPE_DIRS:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# --- recipe modules (imported after the path setup above) -----------
from decision import needs_protocol_layer  # noqa: E402
from direct_client import DirectClient  # noqa: E402
from native_api import NativeAPI  # noqa: E402
from policy_gateway import PolicyError, PolicyGateway  # noqa: E402

import ask_csv  # noqa: E402
import post_to_code  # noqa: E402
import meeting_brief  # noqa: E402
import prior_auth  # noqa: E402

from agent import render_journal, run_agent  # noqa: E402
from exactly_once import IdempotencyStore, render_ledger  # noqa: E402
from tools import MockWorld, render_world  # noqa: E402

# Sample inputs, mirrored from each recipe's demo.py.
CSV_QUESTIONS = [
    "What is the total revenue?",
    "What is the total revenue in the North?",
    "What is the average revenue?",
    "What is the highest revenue?",
    "How many Widget rows are there?",
    "Top 2 products by revenue",
]

SAMPLE_POSTS = [
    "Do you actually need an MCP server in front of every API? UTCP says "
    "no — let agents call native endpoints directly and reuse the auth the "
    "API already has. But removing a wrapper doesn't solve authorization or "
    "audit trails. A $10,000 refund nobody approved should never sail through.",
    "Our scheduling agent keeps asking the same question twice — visit type "
    "in the directory phase, then again when booking. And it booked an "
    "appointment once without confirming. The flow belongs in a state "
    "machine, not in the prompt.",
]

SAMPLE_INVITE_TEXT = """Title: Q1 planning sync — care journey squad
When: Monday, 10:00 AM – 11:00 AM
Where: Room 4B / meet link in calendar
Attendees: Maya Chen (Product manager), Dev Patel (Engineering lead), Sara Kim (Designer)
Agenda:
- Review Q4 outcomes and what carried over
- Agree the top 3 priorities for Q1
- Assign owners and first milestones
Notes: Decide the Q1 roadmap for the care journey squad. We need to leave with owners and dates for the top 3 priorities."""

# The sample sales CSV, loaded once (read-only).
_CSV_PATH = os.path.join(REPO_ROOT, "starter", "ask-your-csv", "data", "sales.csv")
_CSV_HEADERS, _CSV_ROWS = ask_csv.load_csv(_CSV_PATH)

_MEETINGS_PATH = os.path.join(
    REPO_ROOT, "starter", "meeting-brief-agent", "data", "meetings.json"
)
_CASES_PATH = os.path.join(
    REPO_ROOT, "advanced", "prior-auth-agent", "data", "cases.json"
)

PRIOR_AUTH_CASE_IDS = ["PA-1001", "PA-1002", "PA-1003", "PA-1004"]

# The prompt each recipe sends its model in live mode (--live),
# copied verbatim from the recipe's *_live function, with the
# interpolated parts shown as {placeholders}. Mock mode — what the
# web UI runs — calls no model; these are displayed for reading.
# mcp-vs-utcp has no model anywhere, so it has no entry.
SYSTEM_PROMPTS = {
    "ask-your-csv": (
        "Answer the question using only this CSV data. "
        "Give a short answer with the numbers.\n\n"
        "CSV:\n{csv_text}\n\nQuestion: {question}"
    ),
    "linkedin-post-to-code": (
        "Turn this short LinkedIn-style AI post into a small "
        "runnable Python sketch (under 40 lines, standard "
        "library only) plus a test outline. Reply with the "
        "sketch in one ```python block, then a 'Tests:' section "
        "with one bullet per test.\n\nPost: {post}"
    ),
    "meeting-brief-agent": (
        "You are preparing a meeting brief from this invite.\n\n"
        "RULE: only state what the invite actually says. Never "
        "invent attendee details, context, or decisions. Anything "
        "the invite does not say goes under 'What's missing'.\n\n"
        "Return sections: Purpose, Who's there (name + role, or "
        "'role unknown'), Agenda, Questions to ask (3-5, derived "
        "from the gaps), What's missing.\n\n"
        "Invite:\n{invite_json}"
    ),
    "prior-auth-agent": (
        "Write a short, plain-English status update for the patient "
        "about this prior authorization request. Use ONLY the facts "
        "in the journal below. Do not invent clinical details, dates, "
        "or reasons that are not in the journal. If something is "
        "missing, say it is still needed — do not fill it in.\n\n"
        "Request: {case_id}, {procedure}, payer {payer}, "
        "current state {state}.\n"
        "Journal:\n{journal}"
    ),
    "deja-vu-agent": (
        "Write a short, plain-English incident summary of this "
        "agent run for an engineer on call. Use ONLY the facts "
        "in the journal below. Do not invent events, timings, "
        "or causes that are not in the journal. Explain what "
        "timed out, what the retry did, and why the side "
        "effect happened exactly once (or did not).\n\n"
        "Journal:\n{journal}"
    ),
}


# --- starter/mcp-vs-utcp --------------------------------------------

def run_mcp_vs_utcp():
    """The demo.py scenario: one orders API, two paths, one decision."""
    api_key = "demo-key"
    lines = ["=== 1. Direct (UTCP-style): agent -> native API ==="]
    api = NativeAPI(api_key)
    direct = DirectClient(api, api_key)
    lines.append(f"refund $24.50: {direct.call_tool('create_refund', order_id='A-103', amount=24.50)}")
    lines.append(f"refund $10,000, unapproved: {direct.call_tool('create_refund', order_id='A-103', amount=10000)}")
    lines.append("audit trail kept by the API about *who/why*: none")
    lines.append("")
    lines.append("=== 2. Wrapped (MCP-style): agent -> gateway -> native API ===")
    api2 = NativeAPI(api_key)
    gateway = PolicyGateway(api2, api_key)
    try:
        gateway.call_tool("create_refund", order_id="A-103", amount=24.50)
    except PolicyError as exc:
        lines.append(f"unapproved refund: {exc}")
    try:
        gateway.call_tool(
            "create_refund", order_id="A-103", amount=10000, approved=True)
    except PolicyError as exc:
        lines.append(f"approved but absurd refund: {exc}")
    lines.append(f"approved refund $24.50: {gateway.call_tool('create_refund', order_id='A-103', amount=24.50, approved=True)}")
    lines.append("audit log:")
    for entry in gateway.audit_log:
        lines.append(f"   {entry}")
    lines.append("")
    lines.append("=== 3. So where does the layer belong? ===")
    read_only = needs_protocol_layer(
        has_side_effects=False, api_has_auth=True, api_has_audit_log=True,
        api_validates_inputs=True, multiple_agent_consumers=False)
    lines.append(f"read-only lookup on a mature API: {read_only}")
    refunding = needs_protocol_layer(
        has_side_effects=True, api_has_auth=True, api_has_audit_log=False,
        api_validates_inputs=False, multiple_agent_consumers=True)
    lines.append(f"refund tool on this API: {refunding}")
    return "\n".join(lines)


# --- starter/ask-your-csv -------------------------------------------

def run_ask_csv(question=None):
    """Answer one question, or the canned set (the demo's default)."""
    lines = [
        f"Loaded {len(_CSV_ROWS)} rows from data/sales.csv "
        f"({', '.join(_CSV_HEADERS)})",
        "",
    ]
    questions = [question] if question else CSV_QUESTIONS
    for q in questions:
        result = ask_csv.answer(q, _CSV_HEADERS, _CSV_ROWS)
        lines.append(f"Q: {q}")
        lines.append(f"  A [{result['mode']}]: {result['text']}")
        lines.append("")
    return "\n".join(lines).rstrip()


# --- starter/linkedin-post-to-code ----------------------------------

def _show_post_result(result):
    lines = [
        f"Topic: {result['topic']} [{result['mode']}]",
        f"Title: {result['title']}",
        "",
        result["sketch"].rstrip(),
        "",
        "Test outline:",
    ]
    lines += [f"  - {item}" for item in result["test_outline"]]
    return "\n".join(lines)


def run_post_to_code(post=None):
    """One pasted post, or both canned posts (the demo's default)."""
    posts = [post] if post else SAMPLE_POSTS
    chunks = []
    for p in posts:
        chunks.append(f"Post: {p[:100]}...\n")
        chunks.append(_show_post_result(post_to_code.generate(p)))
    return "\n\n".join(chunks)


# --- starter/meeting-brief-agent ------------------------------------

def run_meeting_brief(text=None):
    """One pasted text invite, or all sample invites (demo default)."""
    if text:
        invites = [meeting_brief.parse_text_invite(text)]
    else:
        invites = meeting_brief.load_samples(_MEETINGS_PATH)
    briefs = [
        meeting_brief.render_brief(meeting_brief.build_brief(invite))
        for invite in invites
    ]
    return ("\n\n" + "=" * 60 + "\n\n").join(briefs)


# --- advanced/prior-auth-agent --------------------------------------

def _replay_prior_auth(case, timeline, state_dir):
    """Same save/load-per-step replay as the recipe's demo.py."""
    prior_auth.save_state(case, state_dir)
    for event in timeline:
        case = prior_auth.load_state(case["case_id"], state_dir)
        prior_auth.apply_event(case, event)
        prior_auth.save_state(case, state_dir)
    return case


def run_prior_auth(case_id=None):
    """All four mock cases (or one), through their scripted waits."""
    cases = prior_auth.load_cases(_CASES_PATH)
    if case_id:
        cases = [(c, t) for c, t in cases if c["case_id"] == case_id]
        if not cases:
            return f"No case matches: {case_id}"
    rendered = []
    # A fresh temp state dir per run: the pause/resume is real (state
    # is saved and reloaded at every step), but web runs never touch
    # the recipe's own state/ folder or each other.
    with tempfile.TemporaryDirectory(prefix="prior-auth-web-") as state_dir:
        for case, timeline in cases:
            case = _replay_prior_auth(case, timeline, state_dir)
            rendered.append(prior_auth.render_status(case))
    return ("\n\n" + "=" * 60 + "\n\n").join(rendered)


# --- advanced/deja-vu-agent -----------------------------------------

def _deja_vu_safe(state_dir):
    lines = ["# With idempotency keys + ledger (the fix)", ""]
    world = MockWorld()
    store = IdempotencyStore(os.path.join(state_dir, "ledger.json"))
    result = run_agent(world, store, use_idempotency=True)
    lines.append(render_journal(result["journal"]))
    lines.append("")
    lines.append(render_world(world))
    lines.append("")
    lines.append(render_ledger(store))
    verdict = len(world.bookings) == 1 and len(world.charges) == 1
    lines.append("")
    lines.append(
        "Verdict: exactly one booking, exactly one charge. "
        "The timeout lied; the ledger didn't."
        if verdict else
        "Verdict: UNEXPECTED — the safe path did not stay exactly-once."
    )
    return "\n".join(lines)


def _deja_vu_unsafe():
    lines = ["# Without idempotency (the bug)", ""]
    world = MockWorld()
    result = run_agent(world, None, use_idempotency=False)
    lines.append(render_journal(result["journal"]))
    lines.append("")
    lines.append(render_world(world))
    verdict = len(world.bookings) == 2 and len(world.charges) == 2
    lines.append("")
    lines.append(
        "Verdict: double-booked and double-charged. Every retry "
        "looked like a brand-new request."
        if verdict else
        "Verdict: UNEXPECTED — the unsafe path did not double-execute."
    )
    return "\n".join(lines)


def run_deja_vu(path=None):
    """Both paths (demo default), or just 'safe' / 'unsafe'."""
    chunks = []
    if path != "unsafe":
        with tempfile.TemporaryDirectory(prefix="deja-vu-web-") as state_dir:
            chunks.append(_deja_vu_safe(state_dir))
    if path != "safe":
        chunks.append(_deja_vu_unsafe())
    return ("\n\n" + "=" * 60 + "\n\n").join(chunks)
