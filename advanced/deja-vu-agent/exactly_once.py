"""Exactly-once tool execution: make retries boring.

Agents retry. A tool call times out, the agent tries again — that
is good behavior, right up until the timeout lied. A timeout does
not mean "nothing happened." It means "I don't know what happened."
The booking may have committed and only the *response* was lost.
Retry blindly and the patient is booked twice, the card charged
twice. (This is not hypothetical: a robustness test against a real
scheduling agent double-booked a slot exactly this way.)

The fix is old and boring, which is the point: an **idempotency
key** per logical operation, plus a **ledger** that remembers what
each key already did.

    first call with key K    -> claim K, execute, store the result
    retry with key K         -> return the stored result (replay)
    retry after a timeout    -> outcome unknown: reconcile first,
                                re-execute only if nothing committed
    two calls with key K     -> one executes, the other waits and
    at the same time            gets the stored result

Three rules make it work:

- **The key is derived from the intent, not the attempt.** One key
  per logical operation ("book:patient-123:2026-11-25T09:00"),
  reused on every retry. A fresh random key per attempt is the
  same as no key at all.
- **The ledger is written before the side effect.** The key is
  claimed (status ``in_progress``) and persisted to JSON before
  the tool runs, so a crash mid-flight leaves evidence, not a
  mystery.
- **Unknown is not failed.** If the tool raises, the outcome is
  *unknown* — the side effect may have committed. The entry is
  marked ``unknown``, never silently retried. A retry must first
  reconcile: ask the tool's world "did this key already commit?"
  Found: store and replay that result. Not found: now it is safe
  to execute. No reconcile function: refuse to guess, loudly.

Mock mode needs nothing: no key, no extra packages, no network.
The tools in this recipe are flaky on purpose (see tools.py) — they
commit the side effect and then "lose the response", which is the
exact hazard the ledger exists for.

Live: set GEMINI_API_KEY and pass --live, and the same journal goes
to a real Gemini model, which writes a plain-English incident
summary. The model writes message text only — it never decides
whether a retry is safe. That decision is code, and the tests pin
it. Needs `pip install litellm`.
"""

import json
import os
import threading

# Ledger entry statuses.
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
UNKNOWN = "unknown"


class UnknownOutcomeError(RuntimeError):
    """A previous attempt with this key may have committed, and there
    is no way to check. Refusing to guess — re-executing could
    double the side effect."""


class IdempotencyStore:
    """A JSON-file ledger: idempotency key -> what already happened.

    Each entry records the tool, a status (in_progress / completed /
    unknown), the stored result, and how many attempts were made.
    The ledger is written to disk on every change, before and after
    execution — the same pause/resume discipline as the prior-auth
    recipe: a restart resumes from the file, not from memory.

    Entries found ``in_progress`` at load time belong to a process
    that died mid-flight. Their outcome is unknown by definition,
    so they are re-marked ``unknown`` and must be reconciled before
    anyone executes them again.
    """

    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()
        self._events = {}
        self._entries = self._load()

    # -- persistence -------------------------------------------------

    def _load(self):
        if not os.path.exists(self._path):
            return {}
        with open(self._path, encoding="utf-8") as handle:
            entries = json.load(handle)
        for entry in entries.values():
            if entry["status"] == IN_PROGRESS:
                entry["status"] = UNKNOWN
                entry["error"] = "process restarted during execution"
        return entries

    def _save(self):
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self._entries, handle, indent=2)
        os.replace(tmp, self._path)

    # -- concurrency -------------------------------------------------

    def _event_for(self, key):
        event = self._events.get(key)
        if event is None:
            event = threading.Event()
            self._events[key] = event
        return event

    def wait_for(self, key, timeout=10):
        """Block until the in-flight attempt for this key settles."""
        self._event_for(key).wait(timeout)

    # -- ledger operations -------------------------------------------

    def get(self, key):
        """The ledger entry for a key, or None if never seen."""
        with self._lock:
            entry = self._entries.get(key)
            return dict(entry) if entry else None

    def entries(self):
        """A snapshot of the whole ledger, for display."""
        with self._lock:
            return {k: dict(v) for k, v in self._entries.items()}

    def claim(self, key, tool):
        """Claim a key for execution. Returns (entry, claimed).

        ``claimed`` is True only for the caller that owns execution.
        Everyone else gets the existing entry and must replay, wait,
        or reconcile — never execute. Reusing a key for a different
        tool is refused: one key, one logical operation.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = {
                    "key": key,
                    "tool": tool,
                    "status": IN_PROGRESS,
                    "result": None,
                    "attempts": 1,
                    "error": None,
                }
                self._entries[key] = entry
                self._save()
                self._event_for(key).clear()
                return dict(entry), True
            if entry["tool"] != tool:
                raise ValueError(
                    f"Idempotency key {key!r} was already used for "
                    f"{entry['tool']!r}, not {tool!r}. One key, one operation."
                )
            return dict(entry), False

    def complete(self, key, result):
        """Record the result. From now on, retries replay it."""
        with self._lock:
            entry = self._entries[key]
            entry["status"] = COMPLETED
            entry["result"] = result
            entry["error"] = None
            self._save()
            self._event_for(key).set()

    def mark_unknown(self, key, error):
        """The attempt raised. The side effect may have committed —
        the outcome is unknown, which is not the same as failed."""
        with self._lock:
            entry = self._entries[key]
            entry["status"] = UNKNOWN
            entry["error"] = error
            self._save()
            self._event_for(key).set()

    def reclaim(self, key):
        """unknown -> in_progress, for the one caller that reconciled
        and found nothing committed. Returns False if someone else
        already took it (or it settled in the meantime)."""
        with self._lock:
            entry = self._entries[key]
            if entry["status"] != UNKNOWN:
                return False
            entry["status"] = IN_PROGRESS
            entry["attempts"] += 1
            entry["error"] = None
            self._save()
            self._event_for(key).clear()
            return True


def execute_once(store, key, tool, fn, reconcile=None):
    """Run ``fn()`` at most once for ``key``. Returns (result, replayed).

    - First call: claim the key, execute, store the result.
    - Retry after success: return the stored result, ``replayed=True``,
      without executing.
    - Retry after ``fn`` raised: the outcome is unknown. If
      ``reconcile`` is given, ask it whether the side effect already
      committed (``reconcile(key)`` -> result or None). Found: store
      and replay it. Not found: safe to execute again. Without a
      reconcile function, raise UnknownOutcomeError — never guess.
    - Concurrent duplicate: wait for the in-flight attempt, then
      replay its result.

    If ``fn`` raises, the entry is marked unknown and the exception
    propagates, so the caller knows the attempt "failed" and can
    retry — the retry is where the ledger earns its keep.
    """
    while True:
        entry, claimed = store.claim(key, tool)

        if entry["status"] == COMPLETED:
            return entry["result"], True

        if entry["status"] == IN_PROGRESS and not claimed:
            # Another caller owns this key right now. Wait for it to
            # settle, then loop: replay, or reconcile if it crashed.
            store.wait_for(key)
            continue

        if entry["status"] == UNKNOWN:
            if reconcile is None:
                raise UnknownOutcomeError(
                    f"The outcome of {key!r} is unknown (last error: "
                    f"{entry['error']}) and no reconcile function was "
                    "provided. Refusing to re-execute and risk doubling "
                    "the side effect."
                )
            found = reconcile(key)
            if found is not None:
                store.complete(key, found)
                return found, True
            if not store.reclaim(key):
                continue  # someone else took it; loop and wait/replay
            claimed = True

        if claimed:
            try:
                result = fn()
            except Exception as exc:
                store.mark_unknown(key, f"{type(exc).__name__}: {exc}")
                raise
            store.complete(key, result)
            return result, False


def render_ledger(store):
    """The ledger as a readable summary: every key, its status, and
    how many attempts it took. This is the audit trail a retry
    leaves behind — inspectable after the fact, not reconstructed."""
    lines = ["## Idempotency ledger"]
    entries = store.entries()
    if not entries:
        lines.append("- (empty)")
    for key in sorted(entries):
        entry = entries[key]
        lines.append(
            f"- {key} [{entry['tool']}]: {entry['status']} "
            f"(attempts: {entry['attempts']})"
        )
        if entry["status"] == COMPLETED:
            lines.append(f"    result: {json.dumps(entry['result'])}")
        elif entry["error"]:
            lines.append(f"    last error: {entry['error']}")
    return "\n".join(lines)


def explain_live(journal):
    """A plain-English incident summary from a real Gemini model.

    The model writes message text only — it never decides whether a
    retry was safe, and the prompt forbids inventing events: it may
    only restate what the journal says.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm is not installed (pip install litellm).")
    os.environ["GEMINI_API_KEY"] = api_key
    lines = "\n".join(f"step {e['step']}: {e['note']}" for e in journal)
    response = litellm.completion(
        model="gemini/gemini-3.5-flash-lite",
        messages=[{
            "role": "user",
            "content": (
                "Write a short, plain-English incident summary of this "
                "agent run for an engineer on call. Use ONLY the facts "
                "in the journal below. Do not invent events, timings, "
                "or causes that are not in the journal. Explain what "
                "timed out, what the retry did, and why the side "
                "effect happened exactly once (or did not).\n\n"
                f"Journal:\n{lines}"
            ),
        }],
    )
    return response.choices[0].message.content.strip()
