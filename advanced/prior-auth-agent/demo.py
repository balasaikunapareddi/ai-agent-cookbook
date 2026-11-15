"""One-command demo: track four mock prior-auth requests through the wait.

Usage:
    python3 demo.py                              # all four cases, mock mode
    python3 demo.py PA-1002                      # one case only
    python3 demo.py --live                       # the same, plus a real
                                                 # Gemini status update per
                                                 # case (needs GEMINI_API_KEY)

Mock mode needs nothing: no key, no extra packages, no network.
The payer is scripted (data/cases.json): each case carries the timeline
of responses the mock payer sends on each day. After every step the
case is saved to state/<case_id>.json and loaded back before the next
step — the pause/resume is real, and the state files are left behind
so you can inspect them.

PA-1004 ends still waiting in INFO_REQUESTED: the sleep diary was
requested on day 4 and has not arrived. That is the normal shape of
prior auth — the request holds, it does not get re-asked or guessed at.
"""

import os
import shutil
import sys

from prior_auth import (
    apply_event,
    load_cases,
    load_state,
    render_status,
    save_state,
    status_update_live,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def replay(case, timeline, state_dir):
    """Run one case's timeline, saving and reloading state at every step."""
    save_state(case, state_dir)
    for event in timeline:
        # Resume exactly where the last step left off — across the wait.
        case = load_state(case["case_id"], state_dir)
        apply_event(case, event)
        save_state(case, state_dir)
    return case


def main(argv):
    live = "--live" in argv
    rest = [a for a in argv[1:] if not a.startswith("--")]
    state_dir = os.path.join(HERE, "state")
    shutil.rmtree(state_dir, ignore_errors=True)
    cases = load_cases(os.path.join(HERE, "data", "cases.json"))
    if rest:
        cases = [(c, t) for c, t in cases if c["case_id"] in rest]
        if not cases:
            print(f"No case matches: {', '.join(rest)}")
            return 1
    for case, timeline in cases:
        case = replay(case, timeline, state_dir)
        print(render_status(case))
        if live:
            try:
                print("\n--- Patient status update (live Gemini) ---")
                print(status_update_live(case))
            except RuntimeError as exc:
                print(f"(live mode unavailable: {exc} — mock status above stands)")
        print("\n" + "=" * 60 + "\n")
    print("State files left in state/ — run again to see the same story,")
    print("or open one to see exactly where a request is waiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
