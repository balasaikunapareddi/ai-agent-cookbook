# Ask your CSV: plain-English questions over a spreadsheet

> ▶️ **Try it live:** [https://ai-agent-cookbook.onrender.com/recipes/ask-your-csv](https://ai-agent-cookbook.onrender.com/recipes/ask-your-csv) — runs in your browser, nothing to install.

## The idea

Spreadsheets are where small-business answers live, and most people
still open a pivot table to get them. This recipe answers questions
like "total revenue in the North?" or "top 2 products by revenue"
straight from a CSV file — no database, no SQL, no model call by
default.

## What I built

- `ask_csv.py` — a small deterministic planner: it reads the
  question, picks an aggregation (total / average / max / min /
  count), a numeric column, and any filter values, then answers from
  the rows. Same question, same answer, every time — which is what
  makes it testable.
- `data/sales.csv` — 18 rows of sample sales (month, region, product,
  units, revenue).
- `demo.py` — runs six canned questions through the planner.
- `answer_live()` in `ask_csv.py` — the same question sent to a real
  Gemini model with the CSV as context, when you want free-form
  answers instead of the planner's fixed shapes.

## Run it

```bash
python3 demo.py                             # canned questions, mock mode
python3 demo.py "total revenue in the North?"  # one question, mock mode
python3 -m pytest -q                        # 13 tests (needs pytest: pip install pytest)
```

Mock mode needs nothing: no key, no extra packages, no network.

Live mode (optional):

```bash
pip install -r requirements.txt   # litellm
GEMINI_API_KEY=... python3 demo.py --live "why did Gizmo sell so little in April?"
```

The live model is `gemini/gemini-3.5-flash-lite` (Gemini free tier).
If the key is missing or litellm is not installed, `--live` says so
plainly and falls back to the mock planner.

## What to notice

- **Deterministic first, model second.** The planner answers the
  common shapes (totals, averages, top N, filters) without a model,
  so the answers are exact and the tests can pin them down. The model
  is for questions the planner cannot parse, not for arithmetic.
- **The planner never guesses.** A question it cannot parse gets an
  honest "I couldn't parse that" plus examples of what it can do —
  never a made-up number.
- **The filter trap.** "May" is both a month and an ordinary word, so
  the planner never treats it as a filter — otherwise "what may be the
  total..." would silently drop rows. Small data, real edge cases.

## Limits

The planner understands one aggregation, one numeric column, and
filters by exact cell values. It does not do joins, dates, or
free-form reasoning — that is what the live mode is for. It reads the
whole CSV into memory, so it suits small files, not warehouse tables.
