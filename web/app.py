"""AI Agent Cookbook — run every recipe in your browser.

A thin FastAPI front door over the cookbook: the home page lists all
six recipes, and each recipe page opens with a "Run the agent" panel
— the visitor presses the button and the demo runs in-process
(mock mode — no API key, no network, nothing to install), showing
the output exactly as the CLI prints it. Page loads never run
anything; they show a clearly labeled sample run instead.

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
        "input": "refund",
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
        "input": "scenario",
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
  .runpanel { border: 2px solid #173a2f; background: #fbfdfc; }
  .runpanel h2 { color: #173a2f; font-size: 15px; }
  pre.output { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  textarea, input[type=text], input[type=number], select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; font-family: inherit; background: #fff; }
  textarea { min-height: 150px; resize: vertical; }
  .fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 4px; }
  .fields label { display: block; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #555; margin-bottom: 4px; }
  .checkrow { display: flex; align-items: center; gap: 8px; margin: 10px 0 2px; font-size: 14px; }
  .checkrow input { width: 18px; height: 18px; }
  button[type=submit] { padding: 9px 16px; background: #173a2f; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; margin-top: 8px; }
  button.runbtn { display: block; width: 100%; padding: 14px 16px; font-size: 17px; font-weight: 600; margin-top: 12px; }
  button.runbtn:hover { background: #1f4d3d; }
  .btnrow { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
  .btnrow button { margin-top: 0; }
  button.altbtn { background: #fff; color: #173a2f; border: 2px solid #173a2f; }
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
    """Run a recipe's demo from a form submission; a bad input shows
    a message, never a 500. Runs happen only here — page loads show
    a labeled sample instead (see _sample)."""
    try:
        if recipe["slug"] == "mcp-vs-utcp":
            return runners.run_mcp_vs_utcp_try(
                kwargs.get("order_id") or "A-103",
                kwargs.get("amount"),
                bool(kwargs.get("approved")),
            )
        if recipe["slug"] == "ask-your-csv":
            return runners.run_ask_csv(kwargs.get("question"))
        if recipe["slug"] == "linkedin-post-to-code":
            return runners.run_post_to_code(kwargs.get("post"))
        if recipe["slug"] == "meeting-brief-agent":
            return runners.run_meeting_brief(kwargs.get("invite"))
        if recipe["slug"] == "prior-auth-agent":
            return runners.run_prior_auth(kwargs.get("case"))
        if recipe["slug"] == "deja-vu-agent":
            return runners.run_deja_vu(
                kwargs.get("path"),
                patient=kwargs.get("patient"),
                slot=kwargs.get("slot"),
                copay_cents=kwargs.get("copay_cents"),
            )
    except Exception as exc:  # keep the storefront up on odd input
        return f"(the demo hit an error: {exc})"
    raise HTTPException(status_code=404, detail="unknown recipe")


def _sample(recipe):
    """The canned sample run shown on page load — labeled as a
    sample, never presented as a fresh run."""
    try:
        return runners.run_sample(recipe["slug"])
    except Exception as exc:  # keep the storefront up
        return f"(the sample run hit an error: {exc})"


def _form(recipe, values):
    """The 'Run the agent' panel — every recipe page opens with one.
    Nothing runs until the visitor presses the button."""
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
            '<section class="panel runpanel"><h2>Run the agent — ask the sample sales CSV</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            f'<input type="text" name="question" value="{current}" '
            'placeholder="e.g. What is the total revenue in the North?">'
            '<button type="submit" class="runbtn">&#9654; Ask</button>'
            f'<div class="samples">{samples}</div>'
            '<p class="hint">Answered by the recipe\'s deterministic planner '
            "over its bundled 18-row sample CSV — no model, same question "
            "always gives the same answer.</p></form></section>"
        )
    if kind == "post":
        current = html.escape(values.get("post") or runners.SAMPLE_POSTS[0])
        samples = "".join(
            f'<a href="/recipes/{slug}?sample={i}">Load sample post {i}</a>'
            for i in (1, 2)
        )
        return (
            '<section class="panel runpanel"><h2>Run the agent — paste a post</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            f'<textarea name="post">{current}</textarea>'
            '<button type="submit" class="runbtn">&#9654; Generate code</button>'
            f'<div class="links" style="margin-top:10px">{samples}</div>'
            '<p class="hint">Mock mode routes by keyword to a sketch '
            "template — every sketch is valid Python, checked with ast "
            "before it is handed out.</p></form></section>"
        )
    if kind == "invite":
        current = html.escape(values.get("invite") or runners.SAMPLE_INVITE_TEXT)
        return (
            '<section class="panel runpanel"><h2>Run the agent — paste an invite</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            f'<textarea name="invite">{current}</textarea>'
            '<button type="submit" class="runbtn">&#9654; Brief me</button>'
            '<p class="hint">Understands Title / When / Where / Attendees / '
            "Agenda / Notes lines. The brief only states what the invite "
            "says — gaps are flagged, never invented. Try deleting the "
            "Agenda lines and watch it flag them instead of filling "
            "them in.</p></form></section>"
        )
    if kind == "case":
        active = values.get("case") or ""
        options = [("", "All 4 cases")] + [
            (case_id, case_id) for case_id in runners.PRIOR_AUTH_CASE_IDS
        ]
        opts = "".join(
            f'<option value="{v}"{" selected" if active == v else ""}>{label}</option>'
            for v, label in options
        )
        return (
            '<section class="panel runpanel"><h2>Run the agent — pick a case</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            '<div class="fields"><div><label for="case">Prior-auth case</label>'
            f'<select id="case" name="case">{opts}</select></div></div>'
            '<button type="submit" class="runbtn">&#9654; Run case</button>'
            '<p class="hint">Each case replays its scripted payer timeline, '
            "saving and reloading state at every step — the pause/resume "
            "is real. PA-1004 ends still waiting: that is the normal "
            "shape of prior auth.</p></form></section>"
        )
    if kind == "scenario":
        patient = html.escape(
            values.get("patient") or runners.DEJA_VU_DEFAULTS["patient"])
        slot = html.escape(
            values.get("slot") or runners.DEJA_VU_DEFAULTS["slot"])
        copay = html.escape(
            values.get("copay") or runners.DEJA_VU_DEFAULTS["copay"])
        return (
            '<section class="panel runpanel"><h2>Run the agent — book + charge, survive the timeout</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            '<div class="fields">'
            '<div><label for="patient">Patient ID</label>'
            f'<input type="text" id="patient" name="patient" value="{patient}"></div>'
            '<div><label for="slot">Appointment slot</label>'
            f'<input type="text" id="slot" name="slot" value="{slot}"></div>'
            '<div><label for="copay">Copay ($)</label>'
            f'<input type="number" id="copay" name="copay" value="{copay}" '
            'min="0.01" step="0.01"></div>'
            "</div>"
            '<div class="btnrow">'
            '<button type="submit" name="path" value="safe" class="runbtn">'
            "&#9654; Run WITH idempotency</button>"
            '<button type="submit" name="path" value="unsafe" class="runbtn altbtn">'
            "&#9654; Run WITHOUT idempotency</button>"
            "</div>"
            '<p class="hint">Both tools time out after committing on the '
            "first attempt. Same scenario, same timeouts — the only "
            "difference is whether the retry carries an idempotency key "
            "the ledger can recognize. Run both and compare the world "
            "counts.</p></form></section>"
        )
    if kind == "refund":
        active_order = values.get("order_id") or "A-103"
        opts = "".join(
            f'<option value="{oid}"{" selected" if active_order == oid else ""}>'
            f"{oid} (total ${total:,.2f})</option>"
            for oid, total in runners.MCP_ORDERS
        )
        amount = html.escape(str(values.get("amount") or "10000"))
        checked = " checked" if values.get("approved") else ""
        return (
            '<section class="panel runpanel"><h2>Run it — try a refund on both paths</h2>'
            f'<form method="post" action="/recipes/{slug}">'
            '<div class="fields">'
            '<div><label for="order_id">Order</label>'
            f'<select id="order_id" name="order_id">{opts}</select></div>'
            '<div><label for="amount">Refund amount ($)</label>'
            f'<input type="number" id="amount" name="amount" value="{amount}" '
            'min="0.01" step="0.01"></div>'
            "</div>"
            '<label class="checkrow">'
            f'<input type="checkbox" name="approved" value="yes"{checked}>'
            "A human approved this refund</label>"
            '<button type="submit" class="runbtn">&#9654; Try it</button>'
            '<p class="hint">The same refund goes direct to the native API '
            "(UTCP-style) and through the policy gateway (MCP-style). "
            "Try $10,000 unapproved, then $24.50 approved, and watch "
            "which path stops what — and which one keeps an audit "
            "log.</p></form></section>"
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


def _recipe_page(recipe, output, values, sample=False):
    slug = recipe["slug"]
    if sample:
        heading = "Sample run — what the output looks like"
        note = ('<p class="hint">This is a canned sample so you can see '
                "the shape of the output. Nothing has run yet — use "
                "the panel above to run it yourself.</p>")
    else:
        heading = "Your run (mock mode)"
        note = ""
    body = (
        '<p><a class="back" href="/">&larr; All recipes</a></p>'
        f'<span class="tier">{html.escape(recipe["tier"])}</span>'
        f"<h1 style=\"margin:0 0 6px;font-size:22px\">{html.escape(recipe['title'])}</h1>"
        f'<p class="meta">{html.escape(recipe["tagline"])}</p>'
        f"{_form(recipe, values)}"
        f'<section class="panel"><h2>{heading}</h2>'
        f'<pre class="output">{html.escape(output)}</pre>{note}</section>'
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
        "Click one, press Run, change the inputs, run it again — "
        "then steal the pattern from "
        f'<a href="{GITHUB_BASE}">the repo</a>.</p>'
        f'<div class="cards">{"".join(cards)}</div>'
    )
    return _page("Run every recipe", body)


@app.get("/recipes/{slug}", response_class=HTMLResponse)
def recipe_page(slug: str, sample: int = None):
    """Page load never runs the agent: it shows the run panel, the
    system prompt, and a clearly labeled sample run. The only query
    param is the LinkedIn recipe's sample-post prefill."""
    recipe = BY_SLUG.get(slug)
    if recipe is None:
        raise HTTPException(status_code=404, detail="unknown recipe")
    values = {}
    if slug == "linkedin-post-to-code" and sample in (1, 2):
        values["post"] = runners.SAMPLE_POSTS[sample - 1]
    return _recipe_page(recipe, _sample(recipe), values, sample=True)


def _parse_float(raw):
    try:
        return float((raw or "").replace(",", "").strip())
    except ValueError:
        return None


@app.post("/recipes/{slug}", response_class=HTMLResponse)
def recipe_run(slug: str, question: str = Form(default=None),
               post: str = Form(default=None), invite: str = Form(default=None),
               case: str = Form(default=None), path: str = Form(default=None),
               patient: str = Form(default=None), slot: str = Form(default=None),
               copay: str = Form(default=None), order_id: str = Form(default=None),
               amount: str = Form(default=None), approved: str = Form(default=None)):
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
    elif slug == "prior-auth-agent":
        values["case"] = case if case in runners.PRIOR_AUTH_CASE_IDS else None
    elif slug == "deja-vu-agent":
        values["path"] = path if path in ("safe", "unsafe") else None
        values["patient"] = (patient or "").strip()[:80] or None
        values["slot"] = (slot or "").strip()[:40] or None
        values["copay"] = (copay or "").strip()[:20] or None
        dollars = _parse_float(copay)
        values["copay_cents"] = (
            int(round(dollars * 100)) if dollars and dollars > 0 else None
        )
    elif slug == "mcp-vs-utcp":
        order_ids = [oid for oid, _total in runners.MCP_ORDERS]
        values["order_id"] = order_id if order_id in order_ids else "A-103"
        values["amount"] = _parse_float(amount)
        values["approved"] = bool(approved)
    return _recipe_page(recipe, _run(recipe, **values), values)
