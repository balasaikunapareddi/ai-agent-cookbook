"""One-command demo: ask the sample sales CSV plain-English questions.

Usage:
    python3 demo.py                        # canned questions, mock mode
    python3 demo.py "total revenue"        # one question, mock mode
    python3 demo.py --live "total revenue" # the same, via real Gemini
                                           # (needs GEMINI_API_KEY)

Mock mode needs nothing: no key, no extra packages, no network.
"""

import os
import sys

from ask_csv import answer, answer_live, load_csv

CANNED = [
    "What is the total revenue?",
    "What is the total revenue in the North?",
    "What is the average revenue?",
    "What is the highest revenue?",
    "How many Widget rows are there?",
    "Top 2 products by revenue",
]


def main(argv):
    live = "--live" in argv
    question = next((a for a in argv[1:] if not a.startswith("--")), None)
    headers, rows = load_csv(os.path.join("data", "sales.csv"))
    print(f"Loaded {len(rows)} rows from data/sales.csv "
          f"({', '.join(headers)})\n")

    questions = [question] if question else CANNED
    for q in questions:
        print(f"Q: {q}")
        if live:
            try:
                result = answer_live(q, headers, rows)
            except RuntimeError as exc:
                print(f"  (live mode unavailable: {exc} — using mock)\n")
                result = answer(q, headers, rows)
        else:
            result = answer(q, headers, rows)
        print(f"  A [{result['mode']}]: {result['text']}\n")


if __name__ == "__main__":
    main(sys.argv)
