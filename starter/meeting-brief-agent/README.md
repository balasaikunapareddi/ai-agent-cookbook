# Meeting brief agent: paste an invite, walk in prepared

## The idea

Most meetings go sideways in the first five minutes — not because
people are unprepared, but because nobody knew what the meeting was
*for*. This recipe builds a one-page brief from a meeting invite:
purpose, who's there, agenda, questions to ask, and — the part that
matters — what's missing.

## What I built

- `meeting_brief.py` — a deterministic brief builder. It takes an
  invite (a JSON dict, a pasted text invite, or a sample from
  `data/meetings.json`) and returns a structured brief. It also
  parses plain-text invites: `Title:` / `When:` / `Attendees:` /
  `Agenda:` lines and bullets.
- `data/meetings.json` — four realistic invites: a well-run planning
  sync, a vague "quick sync" with no agenda, a vendor demo with one
  unknown attendee, and a bare-bones 1:1.
- `demo.py` — briefs all four samples in one command.
- `brief_live()` in `meeting_brief.py` — the same invite sent to a
  real Gemini model with the grounding rule in the prompt, when you
  want free-form phrasing instead of the builder's fixed shape.

## Run it

```bash
python3 demo.py                                   # brief all samples, mock mode
python3 demo.py data/meetings.json                # brief invites from a JSON file
python3 demo.py "Title: Design review
When: Thursday 3 PM
Attendees: Ada (PM), Grace"                       # brief a pasted text invite
python3 -m pytest -q                              # 13 tests (needs pytest: pip install pytest)
```

Mock mode needs nothing: no key, no extra packages, no network.

Live mode (optional):

```bash
pip install -r requirements.txt   # litellm
GEMINI_API_KEY=<redacted>  # free tier
```

The live model is `gemini/gemini-3.5-flash-lite` (Gemini free tier).
If the key is missing or litellm is not installed, `--live` says so
plainly and falls back to the mock builder.

## What to notice

- **Grounded, never invented.** The brief only states what the invite
  actually says. A role the invite doesn't give is "role unknown",
  a missing agenda is "no agenda attached" — never a guess dressed
  up as a fact. A brief that invents context is worse than no brief,
  because you walk in confident about things nobody told you.
- **The gaps are the product.** The "What's missing" section is what
  makes the brief useful: it tells you exactly what to ask before
  the meeting starts. The questions are generated from the gaps, so
  a vague invite produces sharper questions than a complete one.
- **Deterministic first, model second.** The builder answers the
  fixed shape (purpose, people, agenda, gaps) without a model, so
  the brief is exact and the tests can pin it down. The model is
  for phrasing, not for facts.
