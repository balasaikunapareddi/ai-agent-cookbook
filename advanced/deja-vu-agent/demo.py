"""One-command demo: the same timeout, two endings.

Usage:
    python3 demo.py                    # both paths, mock mode
    python3 demo.py --idempotent       # only the safe path
    python3 demo.py --no-idempotency   # only the broken path
    python3 demo.py --live             # plus a real Gemini incident
                                       # summary (needs GEMINI_API_KEY)

Mock mode needs nothing: no key, no extra packages, no network.
The tools are flaky on purpose: the first attempt at each one
commits the side effect and then loses the response. Watch what
the retry does in each path:

- With idempotency keys + the ledger, the retry reconciles and
  replays the committed result. One booking, one charge. The
  ledger is persisted to state/ledger.json and left behind so you
  can inspect exactly what each key did.
- Without them (fresh key per attempt), the retry is
  indistinguishable from a new request. Two bookings, two charges
  — the patient is double-booked and double-charged, and nothing
  in the agent's own output says so. Only the world shows it.
"""

import os
import shutil
import sys

from agent import render_journal, run_agent
from exactly_once import IdempotencyStore, explain_live, render_ledger
from tools import MockWorld, render_world

HERE = os.path.dirname(os.path.abspath(__file__))


def run_safe(state_dir, live):
    print("# With idempotency keys + ledger (the fix)\n")
    world = MockWorld()
    store = IdempotencyStore(os.path.join(state_dir, "ledger.json"))
    result = run_agent(world, store, use_idempotency=True)
    print(render_journal(result["journal"]))
    print()
    print(render_world(world))
    print()
    print(render_ledger(store))
    verdict = (
        len(world.bookings) == 1 and len(world.charges) == 1
    )
    print(
        "\nVerdict: exactly one booking, exactly one charge. "
        "The timeout lied; the ledger didn't."
        if verdict else
        "\nVerdict: UNEXPECTED — the safe path did not stay exactly-once."
    )
    if live:
        try:
            print("\n--- Incident summary (live Gemini) ---")
            print(explain_live(result["journal"]))
        except RuntimeError as exc:
            print(f"(live mode unavailable: {exc} — mock journal above stands)")
    return verdict


def run_unsafe():
    print("# Without idempotency (the bug)\n")
    world = MockWorld()
    result = run_agent(world, None, use_idempotency=False)
    print(render_journal(result["journal"]))
    print()
    print(render_world(world))
    verdict = len(world.bookings) == 2 and len(world.charges) == 2
    print(
        "\nVerdict: double-booked and double-charged. Every retry "
        "looked like a brand-new request."
        if verdict else
        "\nVerdict: UNEXPECTED — the unsafe path did not double-execute."
    )
    return verdict


def main(argv):
    live = "--live" in argv
    only_safe = "--idempotent" in argv
    only_unsafe = "--no-idempotency" in argv
    state_dir = os.path.join(HERE, "state")
    shutil.rmtree(state_dir, ignore_errors=True)

    ok = True
    if not only_unsafe:
        ok = run_safe(state_dir, live) and ok
        print("\n" + "=" * 60 + "\n")
    if not only_safe:
        ok = run_unsafe() and ok
        print("\n" + "=" * 60 + "\n")
    if not only_unsafe:
        print("Ledger left in state/ledger.json — open it to see what")
        print("each key did, or run again to replay the same story.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
