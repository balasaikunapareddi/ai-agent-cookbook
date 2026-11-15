"""One-command demo: build a meeting brief from a sample invite.

Usage:
    python3 demo.py                              # brief all samples, mock mode
    python3 demo.py data/meetings.json           # brief invites from a JSON file
    python3 demo.py "Title: Quick sync\\nWhen: ..."  # brief a pasted text invite
    python3 demo.py --live                       # the same, via real Gemini
                                                 # (needs GEMINI_API_KEY)

Mock mode needs nothing: no key, no extra packages, no network.
"""

import json
import os
import sys

from meeting_brief import (
    brief_live,
    build_brief,
    load_samples,
    parse_text_invite,
    render_brief,
)


def _load_arg(arg):
    """A file path (JSON) or a raw pasted invite -> list of invite dicts."""
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else [data]
    return [parse_text_invite(arg)]


def main(argv):
    live = "--live" in argv
    rest = [a for a in argv[1:] if not a.startswith("--")]
    invites = _load_arg(rest[0]) if rest else load_samples(
        os.path.join("data", "meetings.json")
    )

    for invite in invites:
        if live:
            try:
                print(f"# {invite.get('title', 'Untitled meeting')}\n")
                print(brief_live(invite))
                print()
                continue
            except RuntimeError as exc:
                print(f"(live mode unavailable: {exc} — using mock)\n")
        print(render_brief(build_brief(invite)))
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main(sys.argv)
