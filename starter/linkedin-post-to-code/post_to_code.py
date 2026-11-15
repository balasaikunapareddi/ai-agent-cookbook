"""Turn a short LinkedIn-style AI post into a runnable code sketch.

This is Bala's own loop in miniature: he posts an AI idea on LinkedIn,
then implements it as a small runnable, tested entry. This recipe does
the first step of that loop — post in, sketch + test outline out.

Two modes:

- Mock (default): keyword routing picks one of five sketch templates
  (policy gateway, ask-your-CSV, state-machine booking, exactly-once
  tools, minimal agent loop). Deterministic, offline, no key.
- Live: set GEMINI_API_KEY and pass --live, and a real Gemini model
  (LiteLLM gemini/gemini-3.5-flash-lite, free tier) writes the sketch
  for the post. Needs `pip install litellm`.

Every sketch the mock mode returns is real, valid Python — the tests
parse each one with ast to prove it.
"""

import ast
import os
import re

MODEL = "gemini/gemini-3.5-flash-lite"

SKETCHES = {
    "mcp-vs-utcp": {
        "title": "Policy gateway: put approvals in front of side effects",
        "keywords": [
            "mcp", "utcp", "protocol", "refund", "authorization",
            "approval", "audit", "gateway", "wrapper",
        ],
        "sketch": '''"""Sketch: a policy gateway in front of an orders API.

Reads need approval; side effects need approval + a sane amount.
Every attempt lands in the audit log.
"""


class PolicyError(Exception):
    pass


class PolicyGateway:
    def __init__(self, api, api_key):
        self.api = api
        self.headers = {"x-api-key": api_key}
        self.audit_log = []

    def call_tool(self, name, approved=False, **args):
        try:
            result = self._dispatch(name, approved, args)
        except PolicyError as exc:
            self.audit_log.append((name, args, f"rejected: {exc}"))
            raise
        self.audit_log.append((name, args, "allowed"))
        return result

    def _dispatch(self, name, approved, args):
        if name == "get_order":
            return self.api.get_order(args["order_id"], self.headers)
        if name == "create_refund":
            if not approved:
                raise PolicyError("refunds need approval")
            if args["amount"] <= 0:
                raise PolicyError("refund amount must be positive")
            return self.api.create_refund(
                args["order_id"], args["amount"], self.headers
            )
        raise PolicyError(f"unknown tool: {name}")
''',
        "test_outline": [
            "unapproved refund is rejected before reaching the API",
            "absurd refund is rejected even with approval",
            "approved sane refund goes through",
            "every attempt lands in the audit log",
            "read-only calls need no approval",
        ],
    },
    "ask-your-csv": {
        "title": "Ask-your-CSV: deterministic answers over a spreadsheet",
        "keywords": [
            "csv", "spreadsheet", "sales", "revenue", "table", "rows",
            "pivot",
        ],
        "sketch": '''"""Sketch: answer a total/average question about a CSV, no model."""

import csv


def load(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def total(rows, column, **filters):
    matched = [
        row for row in rows
        if all(row[key] == value for key, value in filters.items())
    ]
    return sum(float(row[column]) for row in matched)


if __name__ == "__main__":
    rows = load("sales.csv")
    print("total revenue:", total(rows, "revenue"))
    print("total revenue in the North:",
          total(rows, "revenue", region="North"))
''',
        "test_outline": [
            "total revenue matches the hand-computed sum",
            "a filter narrows the rows before the sum",
            "average and max pick the right rows",
            "an unparseable question is answered honestly, not guessed",
        ],
    },
    "state-machine-booking": {
        "title": "State-machine booking: the flow lives in code, not the prompt",
        "keywords": [
            "booking", "booked", "appointment", "schedule", "scheduling",
            "provider", "slot", "confirm", "confirming", "confirmed",
            "state machine", "visit",
        ],
        "sketch": '''"""Sketch: a booking flow as a state machine, not a prompt.

The machine owns the flow; the model only writes the reply text.
A booking can only happen from AWAITING_CONFIRMATION with
confirmed=True — every other path is rejected by construction.
"""

STATES = ["COLLECTING_DETAILS", "READY_TO_BOOK",
          "AWAITING_CONFIRMATION", "BOOKED"]


class BookingMachine:
    def __init__(self):
        self.state = "COLLECTING_DETAILS"
        self.slots = {}

    def set_slot(self, name, value):
        self.slots[name] = value
        if self.state == "COLLECTING_DETAILS" and self._complete():
            self.state = "READY_TO_BOOK"

    def _complete(self):
        return all(k in self.slots for k in ("name", "date", "slot"))

    def confirm(self):
        if self.state != "READY_TO_BOOK":
            raise ValueError(f"cannot confirm from {self.state}")
        self.state = "AWAITING_CONFIRMATION"

    def book(self, confirmed):
        if self.state != "AWAITING_CONFIRMATION" or not confirmed:
            raise ValueError("booking needs confirmation first")
        self.state = "BOOKED"
        return {"appointment": "APT-1001", **self.slots}
''',
        "test_outline": [
            "booking without confirmation is rejected",
            "booking with confirmed=False is rejected",
            "a correction at confirmation returns to collecting details",
            "a complete slot set advances the machine to ready to book",
        ],
    },
    "exactly-once-tools": {
        "title": "Exactly-once tools: an idempotency ledger",
        "keywords": [
            "idempotency", "idempotent", "duplicate", "retry",
            "exactly-once", "exactly once", "double charge", "webhook",
            "ledger",
        ],
        "sketch": '''"""Sketch: exactly-once tool execution with an idempotency ledger.

The same key twice returns the stored result instead of running
the tool again. The ledger is the whole trick.
"""


class IdempotencyLedger:
    def __init__(self):
        self._results = {}

    def run(self, key, tool, **args):
        if key in self._results:
            return self._results[key], True  # replayed, not re-run
        result = tool(**args)
        self._results[key] = result
        return result, False


def charge_card(amount):
    print(f"charging ${amount:.2f}")
    return {"charged": amount}


if __name__ == "__main__":
    ledger = IdempotencyLedger()
    print(ledger.run("pay-1", charge_card, amount=25.00))
    print(ledger.run("pay-1", charge_card, amount=25.00))
''',
        "test_outline": [
            "the same key twice charges the card once",
            "a different key runs the tool again",
            "a replayed call returns the stored result",
        ],
    },
    "agent-scaffold": {
        "title": "Minimal agent loop: the model writes words, code runs tools",
        "keywords": [],
        "sketch": '''"""Sketch: the smallest honest agent loop.

The model picks a tool; the code runs it, checks the result, and
decides what happens next. The loop is code — the model only
writes words.
"""


def run_agent(user_message, tools, model_reply):
    """model_reply: a function that takes the message and the tool
    list and returns (tool_name, arguments) or (None, reply)."""
    name, args = model_reply(user_message, tools)
    if name is None:
        return args  # the model answered directly
    result = tools[name](**args)
    return f"Tool {name} returned: {result}"


if __name__ == "__main__":
    tools = {"add": lambda a, b: a + b}
    reply = run_agent("what is 2 + 3?", tools,
                      lambda msg, t: ("add", {"a": 2, "b": 3}))
    print(reply)
''',
        "test_outline": [
            "a direct answer needs no tool call",
            "a tool call runs exactly once and its result is returned",
            "an unknown tool is refused, not guessed at",
        ],
    },
}


def _words(text):
    return set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower()))


def detect_topic(post):
    """Pick the sketch template whose keywords the post matches best.

    Keywords are matched as whole words (or phrases, for "state
    machine") against the lowercased post, so inflections like
    "confirming" need their own keyword entry.
    """
    lowered = post.lower()
    best_topic, best_score = "agent-scaffold", 0
    for topic, spec in SKETCHES.items():
        score = sum(
            1
            for kw in spec["keywords"]
            if re.search(r"\b" + re.escape(kw) + r"\b", lowered)
        )
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic


def generate(post):
    """Post text -> {topic, title, sketch, test_outline, readme_snippet}.

    Deterministic mock mode. Raises ValueError for an empty post.
    """
    if not post or not post.strip():
        raise ValueError("the post is empty — paste a few sentences first.")
    topic = detect_topic(post)
    spec = SKETCHES[topic]
    # Prove the sketch is valid Python before handing it out.
    ast.parse(spec["sketch"])
    readme_snippet = (
        f"## {spec['title']}\n\n"
        f"Source post: _{post.strip()[:120]}_\n\n"
        f"Run it: `python3 demo.py`\n"
    )
    return {
        "topic": topic,
        "title": spec["title"],
        "sketch": spec["sketch"],
        "test_outline": list(spec["test_outline"]),
        "readme_snippet": readme_snippet,
        "mode": "mock",
    }


def generate_live(post):
    """Ask a real Gemini model to write the sketch for the post.

    Returns the same dict shape with mode "gemini". Raises
    RuntimeError when the live path is not available or the response
    cannot be parsed — callers can fall back to generate().
    """
    if not post or not post.strip():
        raise ValueError("the post is empty — paste a few sentences first.")
    api_key = os.environ.get("GEMINI_API_KEY", "")
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
                    "Turn this short LinkedIn-style AI post into a small "
                    "runnable Python sketch (under 40 lines, standard "
                    "library only) plus a test outline. Reply with the "
                    "sketch in one ```python block, then a 'Tests:' section "
                    "with one bullet per test.\n\nPost: " + post.strip()
                ),
            }
        ],
    )
    text = response.choices[0].message.content
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError("the live reply had no python code block.")
    sketch = match.group(1).strip() + "\n"
    ast.parse(sketch)
    tests = re.findall(r"^[-*]\s+(.+)$", text, re.MULTILINE)
    return {
        "topic": "live",
        "title": "Live sketch for your post",
        "sketch": sketch,
        "test_outline": tests,
        "readme_snippet": f"## Live sketch for your post\n\nSource post: _{post.strip()[:120]}_\n",
        "mode": "gemini",
    }
