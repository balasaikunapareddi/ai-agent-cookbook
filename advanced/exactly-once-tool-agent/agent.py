"""The agent loop: book, charge, and survive the timeout.

The agent's job is small — book one appointment, charge one copay —
but the network is not cooperating: the first attempt at each tool
commits and then loses the response (see tools.py). What the agent
does next is the whole recipe:

- With idempotency (the default), each logical operation gets ONE
  key, derived from the intent — patient + slot, patient + copay —
  and every retry reuses it through execute_once. The retry after
  the timeout reconciles against the world and replays the
  committed result. One booking, one charge.
- Without it (``use_idempotency=False``), the agent calls the tools
  directly and mints a fresh key per attempt — the most common
  real-world bug shape. The retry cannot be recognized as a retry,
  so the booking and the charge happen twice.

Like the other recipes, the "agent" here is deterministic code
with a journal: the retry policy is a decision a model should
never be trusted to improvise, so it lives in code where the tests
can pin it. The journal records every attempt, timeout, and
replay, so the run can be audited after the fact.
"""

import uuid

from exactly_once import execute_once
from tools import ToolTimeout, flaky_book_appointment, flaky_charge_payment

PATIENT = "patient-123 (mock)"
SLOT = "2026-11-25T09:00"
COPAY_CENTS = 2500

# One key per logical operation, derived from the intent. Every
# retry of the same operation reuses the same key — that stability
# is what makes a retry recognizable as a retry.
BOOKING_KEY = f"book:{PATIENT}:{SLOT}"
CHARGE_KEY = f"charge:{PATIENT}:copay:{SLOT}"


def _note(journal, event, text):
    journal.append({"step": len(journal), "event": event, "note": text})


def _call_with_retries(journal, label, tool_name, tool, key, store,
                       use_idempotency, reconcile, max_retries):
    """Call one tool, retrying on timeout. Returns the tool result.

    Idempotent path: every attempt goes through execute_once with
    the same key. Unsafe path: direct calls, fresh key per attempt.
    """
    for attempt in range(1, max_retries + 1):
        try:
            if use_idempotency:
                result, replayed = execute_once(
                    store, key, tool_name,
                    lambda: tool(key),
                    reconcile=reconcile,
                )
                if replayed:
                    _note(journal, "replay",
                          f"{label}: attempt {attempt} returned the stored "
                          "result from the ledger — the tool did not run again.")
                else:
                    _note(journal, "executed",
                          f"{label}: attempt {attempt} executed and stored "
                          "the result in the ledger.")
                return result
            fresh_key = uuid.uuid4().hex[:8]
            result = tool(fresh_key)
            _note(journal, "executed",
                  f"{label}: attempt {attempt} executed directly "
                  f"(fresh key {fresh_key} — nothing recognizes a retry).")
            return result
        except ToolTimeout as exc:
            _note(journal, "timeout",
                  f"{label}: attempt {attempt} timed out ({exc}). "
                  "Retrying — the side effect may already have committed.")
    raise RuntimeError(f"{label}: still timing out after {max_retries} attempts.")


def run_agent(world, store, use_idempotency=True, max_retries=3):
    """Book the appointment and charge the copay, surviving timeouts.

    Returns {"booking": ..., "charge": ..., "journal": [...]}.
    In idempotent mode ``store`` is the ledger; in unsafe mode it
    is ignored (pass None) — that absence is the bug being shown.
    """
    journal = []
    book = flaky_book_appointment(world, PATIENT, SLOT)
    charge = flaky_charge_payment(world, PATIENT, COPAY_CENTS)

    mode = "idempotent" if use_idempotency else "NO idempotency"
    _note(journal, "start",
          f"Agent starting ({mode}): book {SLOT} for {PATIENT}, "
          f"then charge the ${COPAY_CENTS / 100:.2f} copay.")

    booking = _call_with_retries(
        journal, "book_appointment", "book_appointment", book,
        BOOKING_KEY, store, use_idempotency, world.lookup, max_retries,
    )
    charge_record = _call_with_retries(
        journal, "charge_payment", "charge_payment", charge,
        CHARGE_KEY, store, use_idempotency, world.lookup, max_retries,
    )

    _note(journal, "done",
          f"Done. Booking {booking['booking_id']}, "
          f"charge {charge_record['charge_id']}.")
    return {"booking": booking, "charge": charge_record, "journal": journal}


def render_journal(journal):
    """The run, step by step — what the agent tried, what timed out,
    and what the ledger answered."""
    lines = ["## Agent journal"]
    for entry in journal:
        lines.append(f"- step {entry['step']}: {entry['note']}")
    return "\n".join(lines)
