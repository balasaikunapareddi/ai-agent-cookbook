"""Ask plain-English questions about a CSV file.

Two modes:

- Mock (default): a small deterministic planner reads the question,
  picks an aggregation, a numeric column, and any filter values, and
  answers from the rows. No model, no key, no network — the same
  question always gives the same answer, which is what makes this
  recipe testable.
- Live: set GEMINI_API_KEY and pass --live, and the question goes to
  a real Gemini model (LiteLLM gemini/gemini-3.5-flash-lite, free
  tier) with the CSV pasted as context. Needs `pip install litellm`.

The planner understands: total / average / max / min / count,
"top N <group> by <metric>", and filters by any value in the file
("in the North", "for Widget", "in March").
"""

import csv
import os
import re

MODEL = "gemini/gemini-3.5-flash-lite"

# Words the planner recognises, mapped to what they mean.
AGGREGATIONS = {
    "total": "sum",
    "sum": "sum",
    "average": "mean",
    "avg": "mean",
    "mean": "mean",
    "max": "max",
    "maximum": "max",
    "highest": "max",
    "largest": "max",
    "biggest": "max",
    "min": "min",
    "minimum": "min",
    "lowest": "min",
    "smallest": "min",
}

# Synonyms for numeric columns, so "sales" finds "revenue".
COLUMN_SYNONYMS = {
    "sales": "revenue",
    "money": "revenue",
    "income": "revenue",
    "sold": "units",
    "quantity": "units",
    "amount": "revenue",
}

GROUP_WORDS = {
    "product": "product",
    "products": "product",
    "region": "region",
    "regions": "region",
    "month": "month",
    "months": "month",
}


def load_csv(path):
    """Return (headers, rows) — rows are dicts of str -> str."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return reader.fieldnames or [], rows


def _numeric_columns(headers, rows):
    numeric = []
    for header in headers:
        values = [row[header] for row in rows if row.get(header) not in ("", None)]
        if values and all(_is_number(v) for v in values):
            numeric.append(header)
    return numeric


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _find_column(question_words, headers):
    """The numeric column the question is about, or None."""
    for word in question_words:
        candidate = COLUMN_SYNONYMS.get(word, word)
        if candidate in headers:
            return candidate
    return None


def _find_filters(question_words, headers, rows):
    """(filtered rows, human-readable filter description)."""
    # "may" is both a month and an ordinary English word; never treat
    # it as a filter, or "what may be..." would silently drop rows.
    skip_values = {"may"}
    filtered = list(rows)
    applied = []
    for header in headers:
        if header in _numeric_columns(headers, rows):
            continue
        values = sorted({row[header] for row in rows if row.get(header)})
        for value in values:
            if value.lower() in skip_values:
                continue
            if value.lower() in question_words:
                filtered = [r for r in filtered if r[header] == value]
                applied.append(f"{header} = {value}")
    return filtered, applied


def answer(question, headers, rows):
    """Answer a question deterministically. Returns a dict.

    Keys: text (the answer), rows_used (int), mode ("mock").
    When the question cannot be parsed, text says so and lists
    what the planner does understand.
    """
    if not rows:
        return {
            "text": "No rows to answer from — the CSV is empty.",
            "rows_used": 0,
            "mode": "mock",
        }
    words = _words(question)
    word_set = set(words)

    filtered, applied = _find_filters(words, headers, rows)
    numeric = _numeric_columns(headers, filtered or rows)
    column = _find_column(words, numeric)

    # "top N products by revenue"
    top_match = re.search(r"top\s+(\d+)", question.lower())
    if top_match:
        group = next(
            (GROUP_WORDS[w] for w in words if w in GROUP_WORDS), None
        )
        metric = column or (numeric[0] if numeric else None)
        if group and metric:
            return _top_n(int(top_match.group(1)), group, metric, filtered)

    # "how many ..." / count
    if "how" in word_set and "many" in word_set or "count" in word_set:
        label = f" ({', '.join(applied)})" if applied else ""
        return {
            "text": f"{len(filtered)} rows match{label}.",
            "rows_used": len(filtered),
            "mode": "mock",
        }

    # Aggregations over a numeric column.
    for word in words:
        if word in AGGREGATIONS and column:
            return _aggregate(AGGREGATIONS[word], column, filtered, applied)

    # A filter with no aggregation: show the matching rows.
    if applied:
        lines = [f"{len(filtered)} rows match ({', '.join(applied)}):"]
        for row in filtered[:5]:
            lines.append("  " + ", ".join(f"{k}={v}" for k, v in row.items()))
        if len(filtered) > 5:
            lines.append(f"  ... and {len(filtered) - 5} more")
        return {"text": "\n".join(lines), "rows_used": len(filtered), "mode": "mock"}

    return {
        "text": (
            "I couldn't parse that question. I can answer: total / average / "
            "max / min / count of a numeric column, top N by a metric, and "
            "filters by any value in the file. Try e.g. "
            "'What is the total revenue?' or 'Top 2 products by revenue'."
        ),
        "rows_used": 0,
        "mode": "mock",
    }


def _aggregate(kind, column, rows, applied):
    values = [float(r[column]) for r in rows]
    label = f" ({', '.join(applied)})" if applied else ""
    if not values:
        return {"text": f"No rows to aggregate{label}.", "rows_used": 0, "mode": "mock"}
    if kind == "sum":
        text = f"Total {column}{label}: ${sum(values):,.2f} across {len(values)} rows."
    elif kind == "mean":
        text = f"Average {column}{label}: ${sum(values) / len(values):,.2f} across {len(values)} rows."
    elif kind == "max":
        row = max(rows, key=lambda r: float(r[column]))
        text = f"Highest {column}{label}: ${float(row[column]):,.2f} ({_describe(row)})."
    else:  # min
        row = min(rows, key=lambda r: float(r[column]))
        text = f"Lowest {column}{label}: ${float(row[column]):,.2f} ({_describe(row)})."
    return {"text": text, "rows_used": len(rows), "mode": "mock"}


def _top_n(n, group, metric, rows):
    totals = {}
    for row in rows:
        totals[row[group]] = totals.get(row[group], 0.0) + float(row[metric])
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:n]
    lines = [f"Top {n} {group}s by {metric}:"]
    for rank, (name, total) in enumerate(ranked, start=1):
        lines.append(f"  {rank}. {name}: ${total:,.2f}")
    return {"text": "\n".join(lines), "rows_used": len(rows), "mode": "mock"}


def _describe(row):
    return ", ".join(f"{k}={v}" for k, v in row.items())


def answer_live(question, headers, rows):
    """Answer with a real Gemini model. Needs GEMINI_API_KEY + litellm.

    Raises RuntimeError with a plain-English reason when the live path
    is not available, so callers can fall back to the mock planner.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm is not installed (pip install litellm).")
    os.environ["GEMINI_API_KEY"] = api_key
    csv_text = ",".join(headers) + "\n" + "\n".join(
        ",".join(row[h] for h in headers) for row in rows[:50]
    )
    response = litellm.completion(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "Answer the question using only this CSV data. "
                    "Give a short answer with the numbers.\n\n"
                    f"CSV:\n{csv_text}\n\nQuestion: {question}"
                ),
            }
        ],
    )
    return {
        "text": response.choices[0].message.content.strip(),
        "rows_used": len(rows),
        "mode": "gemini",
    }
