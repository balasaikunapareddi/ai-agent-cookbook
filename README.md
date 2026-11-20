# AI Agent Cookbook

**Small, runnable AI agent recipes. Clone it, run one in one command,
steal the pattern — 100% free and open-source, Apache-2.0.**

Every recipe runs with local mock data and no paid API key. When a
recipe can use a real model, it uses the Gemini free tier
(`gemini/gemini-3.5-flash-lite`) — a key is optional, never required
for the basics.

> 📬 New recipes drop weekly.

## 🚀 Run one now

```bash
git clone https://github.com/balasaikunapareddi/ai-agent-cookbook.git
cd ai-agent-cookbook/starter/ask-your-csv
python3 demo.py
```

That is the whole install: no dependencies, no key, no network. Each
recipe's README shows its one command and what it demonstrates.

## 📂 Browse all recipes

### 🌱 Starter

*Small, single-purpose recipes. The fastest way to see a pattern work.*

- [starter/mcp-vs-utcp](starter/mcp-vs-utcp) — Do you need a server in front of every API? One orders API, two paths: direct calls let a $10,000 refund sail through, a thin policy gateway stops it.
- [starter/ask-your-csv](starter/ask-your-csv) — Plain-English questions over a spreadsheet: totals, averages, top N, filters — answered by a deterministic planner, no model required.
- [starter/linkedin-post-to-code](starter/linkedin-post-to-code) — Paste a LinkedIn-style AI post, get back a runnable code sketch and a test outline. The post-to-code loop in miniature.
- [starter/meeting-brief-agent](starter/meeting-brief-agent) — Paste a meeting invite, walk in prepared: purpose, who's there, agenda, questions to ask — and what's missing, flagged honestly instead of invented.

### 🚀 Advanced

*Production-grade agent patterns. Some live here in the cookbook; the
rest are standalone repos linked below — the cookbook never duplicates
one of those.*

**In the cookbook:**

- [advanced/prior-auth-agent](advanced/prior-auth-agent) — A prior
  authorization request tracker: a deterministic state machine that
  holds state across days of waiting and resumes exactly where it
  left off — never re-asking for a document, never guessing at a
  clinical detail. 4 mock cases, 13 tests.
- [advanced/exactly-once-tool-agent](advanced/exactly-once-tool-agent) — Exactly-once
  tool execution: idempotency keys plus a replayable ledger, so a
  retry after a lost response replays the stored result instead of
  double-booking or double-charging. Includes the broken path for
  contrast. 11 tests.

**Standalone repos:**

- [agent-appointment-scheduler](https://github.com/balasaikunapareddi/agent-appointment-scheduler) — Production scheduling agent: live CMS NPI Registry search, FastAPI system of record, policy-as-code guardrails, deterministic crisis screen.
- [agent-eligibility-claims](https://github.com/balasaikunapareddi/agent-eligibility-claims) — Healthcare eligibility and claims agent: four deterministic MCP tools, idempotent submissions, cost estimates from pure Python.
- [agent-policy-gateway](https://github.com/balasaikunapareddi/agent-policy-gateway) — The MCP vs UTCP gateway, generalized: declarative rules, money-transfer caps, deny-lists, role checks, full audit log.
- [agent-idempotency-kit](https://github.com/balasaikunapareddi/agent-idempotency-kit) — Exactly-once tool execution: the same call twice runs once, with a replayable ledger.
- *State-machine booking (pattern, no link)* — A booking agent where the flow lives in a deterministic state machine, not in the prompt: typed tools, an adapter layer for chained legacy APIs, and a structured UI envelope. The private reference build stays private; the pattern is what the starter recipes teach.

### Coming soon

`always-on/` · `mcp/` · `rag/` · `voice/` · `agent-skills/` — folders
are open, recipes land weekly.

## How a recipe is built

Every recipe in this cookbook meets the same bar:

1. **One command to run.** `python3 demo.py` from the recipe folder.
2. **Mock data, no paid key.** The demo works offline. A live model
   is always optional, via `GEMINI_API_KEY` and `--live`.
3. **Tests prove it works.** `python3 -m pytest -q` in the recipe
   folder (needs pytest: `pip install pytest`).
4. **Small and readable.** One idea per recipe, dependency-light,
   Python 3.10+.

Run the whole suite from the repo root:

```bash
make test        # every recipe's tests
make demo-mcp    # MCP vs UTCP side-by-side
make demo-csv    # ask-your-CSV
make demo-post   # LinkedIn post → code
make demo-brief  # meeting brief agent
make demo-prior-auth  # prior-auth tracker
```

## Why this cookbook

Most agent collections show you a demo. This one shows you the
decision: where the logic lives (in code, not the prompt), what the
model may and may not decide, and what breaks when the guardrail is
missing. The starter recipes teach one pattern each; the advanced
repos show the same patterns at production scale.

## License

Apache-2.0 — clone it, ship it, sell it.
