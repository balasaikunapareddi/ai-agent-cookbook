"""AI Agent Cookbook — run every recipe in your browser.

A thin FastAPI front door over the cookbook: the home page lists all
six recipes, and each recipe page runs that recipe's demo in-process
(mock mode — no API key, no network, nothing to install) and shows
the output exactly as the CLI prints it.

    pip install -r web/requirements.txt
    uvicorn web.app:app --reload        # http://127.0.0.1:8000

Deployed on Render's free tier (see render.yaml at the repo root).
No auth, no database — every run is a fresh mock scenario.
"""

import html

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse

from . import runners

GITHUB_BASE = "https://github.com/balasaikunapareddi/ai-agent-cookbook/tree/main"

# slug -> page metadata. Titles and one-liners come from each
# recipe's README / the root README index.
RECIPES = [
    {
        "slug": "mcp-vs-utcp",
        "title": "MCP vs UTCP",
        "tier": "Starter",
        "folder": "starter/mcp-vs-utcp",
        "tagline": "Do you need a server in front of every API? One orders API, "
                   "two paths: direct calls let a $10,000 refund sail through, "
                   "a thin policy gateway stops it.",
        "input": None,
    },
    {
        "slug": "ask-your-csv",
        "title": "Ask your CSV",
        "tier": "Starter",
        "folder": "starter/ask-your-csv",
        "tagline": "Plain-English questions over a spreadsheet: totals, "
                   "averages, top N, filters — answered by a deterministic "
                   "planner, no model required.",
        "input": "question",
    },
    {
        "slug": "linkedin-post-to-code",
        "title": "LinkedIn post → code",
        "tier": "Starter",
        "folder": "starter/linkedin-post-to-code",
        "tagline": "Paste a LinkedIn-style AI post, get back a runnable code "
                   "sketch and a test outline. The post-to-code loop in "
                   "miniature.",
        "input": "post",
    },
    {
        "slug": "meeting-brief-agent",
        "title": "Meeting brief agent",
        "tier": "Starter",
        "folder": "starter/meeting-brief-agent",
        "tagline": "Paste a meeting invite, walk in prepared: purpose, who's "
                   "there, agenda, questions to ask — and what's missing, "
                   "flagged honestly instead of invented.",
        "input": "invite",
    },
    {
        "slug": "prior-auth-agent",
        "title": "Prior-auth agent",
        "tier": "Advanced",
        "folder": "advanced/prior-auth-agent",
        "tagline": "A prior authorization request tracker: a deterministic "
                   "state machine that holds state across days of waiting "
                   "and resumes exactly where it left off — never re-asking "
                   "for a document, never guessing at a clinical detail.",
        "input": "case",
    },
    {
        "slug": "deja-vu-agent",
        "title": "Deja Vu Agent",
        "tier": "Advanced",
        "folder": "advanced/deja-vu-agent",
        "tagline": "Exactly-once tool execution: idempotency keys plus a "
                   "replayable ledger, so a retry after a lost response "
                   "replays the stored result instead of double-booking or "
                   "double-charging. Includes the broken path for contrast.",
        "input": "path",
    },
]
BY_SLUG = {r["slug"]: r for r in RECIPES}

app = FastAPI(title="AI Agent Cookbook")

STYLE = """
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; color: #1a1a1a; background: #f6f6f4; }
  header { background: #173a2f; color: #fff; padding: 14px 20px; }
  header h1 { margin: 0; font-size: 18px; }
  header h1 a { color: #fff; text-decoration: none; }
  header p { margin: 4px 0 0; font-size: 13px; opacity: .8; }
  main { max-width: 960px; margin: 0 auto; padding: 20px 16px 40px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
  .card { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }
  .card h2 { margin: 0 0 6px; font-size: 16px; }
  .card h2 a { color: #173a2f; text-decoration: none; }
  .card h2 a:hover { text-decoration: underline; }
  .card p { margin: 0 0 10px; font-size: 13px; line-height: 1.5; color: #444; }
  .tier { display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #173a2f; background: #eef4f1; border: 1px solid #cfded6; border-radius: 10px; padding: 2px 8px; margin-bottom: 8px; }
  .run { display: inline-block; background: #173a2f; color: #fff; text-decoration: none; font-size: 13px; padding: 7px 12px; border-radius: 6px; }
  .panel { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 14px; margin-bottom: 14px; }
  .panel h2 { margin: 0 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: #555; }
  pre.output { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  textarea, input[type=text] { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; font-family: inherit; }
  textarea { min-height: 150px; resize: vertical; }
  button[type=submit] { padding: 9px 16px; background: #173a2f; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; margin-top: 8px; }
  .samples { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
  .samples button { margin-top: 0; padding: 6px 10px; background: #fafafa; color: #173a2f; border: 1px solid #cfded6; font-size: 12px; }
  .links { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .links a { font-size: 13px; color: #173a2f; background: #eef4f1; border: 1px solid #cfded6; border-radius: 6px; padding: 5px 10px; text-decoration: none; }
  .links a.active { background: #173a2f; color: #fff; }
  .back { font-size: 13px; color: #173a2f; text-decoration: none; }
  .back:hover { text-decoration: underline; }
  .hint { font-size: 12px; color: #888; margin-top: 8px; }
  .meta { font-size: 13px; color: #555; line-height: 1.6; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #f0f0ec; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
  details summary { cursor: pointer; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: #555; }
  details pre.output { margin-top: 10px; }
"""


def _page(title, body):
    return HTMLResponse(
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(title)} — AI Agent Cookbook</title>\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n"
        "<header><h1><a href=\"/\">AI Agent Cookbook</a></h1>"
        "<p>Small, runnable AI agent recipes — run every demo right here, "
        "nothing to install. Mock data, no API key.</p></header>\n"
        f"<main>{body}</main>\n</body>\n</html>"
    )


def _run(recipe, **kwargs):
    """Run a recipe's demo; a bad input shows a message, never a 500."""
    try:
        if recipe["slug"] == "mcp-vs-utcp":
            return runners.run_mcp_vs_utcp()
        if recipe["slug"] == "ask-your-csv":
            return runners.run_ask_csv(kwargs.get("question"))
        if recipe["slug"] == "linkedin-post-to-code":
            return runners.run_post_to_code(kwargs.get("post"))
        if recipe["slug"] == "meeting-brief-agent":
            return runners.run_meeting_brief(kwargs.get("invite"))
        if recipe["slug"] == "prior-auth-agent":
            return runners.run_prior_auth(kwargs.get("case"))
        if recipe["slug"] == "deja-vu-agent":
            return runners.run_deja_vu(kwargs.get("path"))
    except Exception as exc:  # keep the storefront up on odd input
        return f"(the demo hit an error: {exc})"
    raise HTTPException(status_code=404, detail="unknown recipe")


def _form(recipe, values):
    """The input form for recipes that take one; '' for the rest."""
    slug = recipe["slug"]
    kind = recipe["input"]
    if kind == "question":
        current = html.escape(values.get("question") or "")
        samples = "".join(
            f'<button type="submit" name="question" value="{html.escape(q)}">'
            f"{html.escape(q)}</button>"
            for q in runners.CSV_QUESTIONS
        )
        return (
            '<section class="panel"><h2>Ask the sample sales CSV</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            f'<input type="text" name="question" value="{current}" '
            'placeholder="e.g. What is the total revenue in the North?">'
            '<button type="submit">Ask</button>'
            f'<div class="samples">{samples}</div>'
            '<p class="hint">Answered by the recipe\'s deterministic planner '
            "over its bundled 18-row sample CSV — no model, same question "
            "always gives the same answer.</p></form></section>"
        )
    if kind == "post":
        current = html.escape(values.get("post") or runners.SAMPLE_POSTS[0])
        samples = "".join(
            f'<a href="/recipes/{slug}?sample={i}">Sample post {i}</a>'
            for i in (1, 2)
        )
        return (
            '<section class="panel"><h2>Paste a post</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            f'<textarea name="post">{current}</textarea>'
            '<button type="submit">Turn it into code</button>'
            f'<div class="links" style="margin-top:10px">{samples}</div>'
            '<p class="hint">Mock mode routes by keyword to a sketch '
            "template — every sketch is valid Python, checked with ast "
            "before it is handed out.</p></form></section>"
        )
    if kind == "invite":
        current = html.escape(values.get("invite") or runners.SAMPLE_INVITE_TEXT)
        return (
            '<section class="panel"><h2>Paste an invite</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            f'<textarea name="invite">{current}</textarea>'
            '<button type="submit">Build the brief</button>'
            '<p class="hint">Understands Title / When / Where / Attendees / '
            "Agenda / Notes lines. The brief only states what the invite "
            "says — gaps are flagged, never invented. "
            f'<a href="/recipes/{slug}">Or brief all 4 sample invites</a>.'
            "</p></form></section>"
        )
    if kind == "case":
        active = values.get("case") or ""
        links = [f'<a href="/recipes/{slug}" class="{"active" if not active else ""}">All 4 cases</a>']
        for case_id in runners.PRIOR_AUTH_CASE_IDS:
            cls = "active" if active == case_id else ""
            links.append(f'<a href="/recipes/{slug}?case={case_id}" class="{cls}">{case_id}</a>')
        return (
            '<section class="panel"><h2>Pick a case</h2>'
            f'<div class="links">{"".join(links)}</div>'
            '<p class="hint">Each case replays its scripted payer timeline, '
            "saving and reloading state at every step — the pause/resume "
            "is real. PA-1004 ends still waiting: that is the normal "
            "shape of prior auth.</p></section>"
        )
    if kind == "path":
        active = values.get("path") or ""
        options = [("", "Both paths"), ("safe", "With idempotency (the fix)"),
                   ("unsafe", "Without idempotency (the bug)")]
        links = "".join(
            f'<a href="/recipes/{slug}{("?path=" + v) if v else ""}" '
            f'class="{"active" if active == v else ""}">{label}</a>'
            for v, label in options
        )
        return (
            '<section class="panel"><h2>Pick a path</h2>'
            f'<div class="links">{links}</div>'
            '<p class="hint">Same flaky tools, same timeouts — the only '
            "difference is whether the retry carries an idempotency key "
            "the ledger can recognize.</p></section>"
        )
    return ""


def _system_prompt_section(recipe):
    """The recipe's live-mode model prompt, collapsed — or '' when the
    recipe defines none (mcp-vs-utcp runs no model at all)."""
    prompt = runners.SYSTEM_PROMPTS.get(recipe["slug"])
    if not prompt:
        return ""
    return (
        '<details class="panel"><summary>System prompt (live mode)</summary>'
        f'<pre class="output">{html.escape(prompt)}</pre>'
        '<p class="hint">Sent to the model only in live mode '
        "(<code>--live</code>). Mock mode — what runs on this page — "
        "calls no model; the logic is deterministic code.</p></details>"
    )


def _recipe_page(recipe, output, values):
    slug = recipe["slug"]
    body = (
        '<p><a class="back" href="/">&larr; All recipes</a></p>'
        f'<span class="tier">{html.escape(recipe["tier"])}</span>'
        f"<h1 style=\"margin:0 0 6px;font-size:22px\">{html.escape(recipe['title'])}</h1>"
        f'<p class="meta">{html.escape(recipe["tagline"])}</p>'
        f"{_form(recipe, values)}"
        '<section class="panel"><h2>Demo output (mock mode)</h2>'
        f'<pre class="output">{html.escape(output)}</pre></section>'
        f"{_system_prompt_section(recipe)}"
        '<section class="panel"><h2>Run it yourself</h2>'
        f'<p class="meta">Code: <a href="{GITHUB_BASE}/{recipe["folder"]}">'
        f'{recipe["folder"]}</a> on GitHub.<br>'
        f'Locally: <code>cd {recipe["folder"]} &amp;&amp; python3 demo.py</code> '
        "— no dependencies, no key, no network. "
        "Tests: <code>python3 -m pytest -q</code> in the same folder.</p>"
        "</section>"
    )
    return _page(recipe["title"], body)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home():
    cards = []
    for recipe in RECIPES:
        cards.append(
            '<article class="card">'
            f'<span class="tier">{html.escape(recipe["tier"])}</span>'
            f'<h2><a href="/recipes/{recipe["slug"]}">{html.escape(recipe["title"])}</a></h2>'
            f'<p>{html.escape(recipe["tagline"])}</p>'
            f'<a class="run" href="/recipes/{recipe["slug"]}">Run the demo</a>'
            "</article>"
        )
    body = (
        '<p class="meta" style="margin-top:0">Every recipe below runs '
        "in your browser on mock data — no install, no API key. "
        "Click one, watch it work, then steal the pattern from "
        f'<a href="{GITHUB_BASE}">the repo</a>.</p>'
        f'<div class="cards">{"".join(cards)}</div>'
    )
    return _page("Run every recipe", body)


@app.get("/recipes/{slug}", response_class=HTMLResponse)
def recipe_page(slug: str, case: str = None, path: str = None,
                sample: int = None):
    recipe = BY_SLUG.get(slug)
    if recipe is None:
        raise HTTPException(status_code=404, detail="unknown recipe")
    values = {}
    if slug == "prior-auth-agent":
        values["case"] = case if case in runners.PRIOR_AUTH_CASE_IDS else None
    elif slug == "deja-vu-agent":
        values["path"] = path if path in ("safe", "unsafe") else None
    elif slug == "linkedin-post-to-code" and sample in (1, 2):
        values["post"] = runners.SAMPLE_POSTS[sample - 1]
    return _recipe_page(recipe, _run(recipe, **values), values)


@app.post("/recipes/{slug}", response_class=HTMLResponse)
def recipe_run(slug: str, question: str = Form(default=None),
               post: str = Form(default=None), invite: str = Form(default=None)):
    recipe = BY_SLUG.get(slug)
    if recipe is None:
        raise HTTPException(status_code=404, detail="unknown recipe")
    values = {}
    if slug == "ask-your-csv":
        values["question"] = (question or "").strip()[:500] or None
    elif slug == "linkedin-post-to-code":
        values["post"] = (post or "").strip()[:5000] or None
    elif slug == "meeting-brief-agent":
        values["invite"] = (invite or "").strip()[:5000] or None
    return _recipe_page(recipe, _run(recipe, **values), values)
