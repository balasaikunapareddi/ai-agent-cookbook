"""One-command demo: two LinkedIn-style posts, two code sketches.

Usage:
    python3 demo.py                        # two canned posts, mock mode
    python3 demo.py "your post text here"  # one post, mock mode
    python3 demo.py --live "your post"     # the same, via real Gemini
                                           # (needs GEMINI_API_KEY)

Mock mode needs nothing: no key, no extra packages, no network.
"""

import sys

from post_to_code import generate, generate_live

CANNED = [
    "Do you actually need an MCP server in front of every API? UTCP says "
    "no — let agents call native endpoints directly and reuse the auth the "
    "API already has. But removing a wrapper doesn't solve authorization or "
    "audit trails. A $10,000 refund nobody approved should never sail through.",
    "Our scheduling agent keeps asking the same question twice — visit type "
    "in the directory phase, then again when booking. And it booked an "
    "appointment once without confirming. The flow belongs in a state "
    "machine, not in the prompt.",
]


def show(result):
    print(f"Topic: {result['topic']} [{result['mode']}]")
    print(f"Title: {result['title']}\n")
    print(result["sketch"])
    print("Test outline:")
    for item in result["test_outline"]:
        print(f"  - {item}")
    print()


def main(argv):
    live = "--live" in argv
    post = next((a for a in argv[1:] if not a.startswith("--")), None)
    posts = [post] if post else CANNED
    for p in posts:
        print(f"Post: {p[:100]}...\n")
        if live:
            try:
                show(generate_live(p))
                continue
            except RuntimeError as exc:
                print(f"(live mode unavailable: {exc} — using mock)\n")
        show(generate(p))


if __name__ == "__main__":
    main(sys.argv)
