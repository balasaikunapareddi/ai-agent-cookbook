# AI Agent Cookbook

**Small, runnable AI agent recipes. Clone it, run one in one command,
steal the pattern — 100% free and open-source, Apache-2.0.**

Every recipe runs with local mock data and no paid API key. When a
recipe can use a real model, it uses the Gemini free tier
(`gemini/gemini-3.5-flash-lite`) — a key is optional, never required
for the basics.

> 📬 New recipes drop weekly.

## 🌐 Run it in your browser (local UI)

Every recipe also runs in a local web UI: click a recipe, type your
own inputs, watch the agent work. Mock data, no API key. Run it from
the repo:

```bash
pip install -r web/requirements.txt
uvicorn web.app:app --reload        # http://127.0.0.1:8000
```

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
- [advanced/deja-vu-agent](advanced/deja-vu-agent) — Deja Vu Agent:
  exactly-once tool execution — idempotency keys plus a replayable
  ledger, so a retry after a lost response replays the stored result
  instead of double-booking or double-charging. Includes the broken
  path for contrast. 11 tests.

**Standalone repos:**

Healthcare:

- [agent-appointment-scheduler](https://github.com/balasaikunapareddi/agent-appointment-scheduler) — Production scheduling agent: live CMS NPI Registry search, FastAPI system of record, policy-as-code guardrails, deterministic crisis screen.
- [agent-eligibility-claims](https://github.com/balasaikunapareddi/agent-eligibility-claims) — Healthcare eligibility and claims agent: four deterministic MCP tools, idempotent submissions, cost estimates from pure Python.
- [agent-clinical-inference](https://github.com/balasaikunapareddi/agent-clinical-inference) — Seven-agent clinical data pipeline (arXiv:2507.18115): deterministic state machine, local PII anonymizer, interpretable predictions on synthetic data. Research demo, not for clinical use.

Production patterns:

- [agent-support-resolution](https://github.com/balasaikunapareddi/agent-support-resolution) — Support tickets resolved behind policy-as-code: classify → retrieve → draft → confidence gate → human approval queue, with a full audit trail. Risky replies never auto-send.
- [agent-research-pipeline](https://github.com/balasaikunapareddi/agent-research-pipeline) — Multi-agent research with a fact-check gate: a planner fans out to parallel researchers, every claim is verified against its source before the writer cites it. Checkpointed, resumable, cost-ledgered.
- [agent-code-review](https://github.com/balasaikunapareddi/agent-code-review) — PR review that is measured, not vibed: deterministic static checks plus structured LLM review with severity and confidence, scored on seeded bugs (recall/precision).
- [agent-policy-gateway](https://github.com/balasaikunapareddi/agent-policy-gateway) — The MCP vs UTCP gateway, generalized: declarative rules, money-transfer caps, deny-lists, role checks, full audit log.
- [agent-idempotency-kit](https://github.com/balasaikunapareddi/agent-idempotency-kit) — Exactly-once tool execution: the same call twice runs once, with a replayable ledger.
- [agent-model-router](https://github.com/balasaikunapareddi/agent-model-router) — Routes each task to the cheapest model that can do it, escalates when the quality gate fails, and ledgers the cost against an always-big-model baseline.
- [agent-prompt-versioning](https://github.com/balasaikunapareddi/agent-prompt-versioning) — System prompts under version control: every change is eval-scored before promotion, and regressions roll back automatically with a changelog entry.
- [agent-memory](https://github.com/balasaikunapareddi/agent-memory) — Agent memory end to end: session and long-term memory across restarts, learned preferences, and context compaction that keeps the facts.
- [agent-email-triage](https://github.com/balasaikunapareddi/agent-email-triage) — Inbox triage with a deadline-aware priority queue and draft replies that are never sent — a human always sends.
- [agent-red-team-tester](https://github.com/balasaikunapareddi/agent-red-team-tester) — Attacker/target/judge red-teaming: prompt injections and jailbreaks scored per category, with a hardening checklist.
- [agent-interview-prep](https://github.com/balasaikunapareddi/agent-interview-prep) — Resume plus job description → gap analysis backed by resume evidence, mapped questions, a scored mock interview, and a study plan.
- [agent-data-simulator](https://github.com/balasaikunapareddi/agent-data-simulator) — Generates messy, realistic enterprise data (retry duplicates, unit changes, NULLs, legacy keys) plus a benchmark with gold answers, so you can test agents against data that fights back. Live Gemini: 9/10, zero traps.
- [agent-eval-harness](https://github.com/balasaikunapareddi/agent-eval-harness) — Regression tests for agent configs: declarative YAML scenarios, every run fingerprinted (prompt + tool schemas), one command diffs two runs and names every regression. CI gate included.
- [agent-tool-firewall](https://github.com/balasaikunapareddi/agent-tool-firewall) — Tool-permission firewall for agents: least-privilege scopes, credential isolation, approval gates, sandboxed execution, and a full audit trail. Demo blocks 5/5 prompt-injected attacks that succeed without it.
- [agent-self-learning](https://github.com/balasaikunapareddi/agent-self-learning) — Self-improving support agent: grades its own replies, extracts lessons into a store with helped/hurt accounting, and retrieves them next time. Memory-only learning — no self-modifying code.
- [agent-mcp-apps](https://github.com/balasaikunapareddi/agent-mcp-apps) — Clinic booking agent delivered as an MCP server with MCP Apps interactive UI: slot picker, intake form, approval card, patient details bound server-side and never seen by the model.
- [agent-app-verifier](https://github.com/balasaikunapareddi/agent-app-verifier) — Agent-native app verification in the spirit of Expo Exact: an LLM agent builds a todo app from a declarative spec, then drives it through ten operations (tree, screenshot, tap, type, state, layout, logs, clock, prefer, perf) — seeing it and running scripted tests, including a virtual-clock jump, until it passes.
- [agent-fast-decider](https://github.com/balasaikunapareddi/agent-fast-decider) — System-1/System-2 ticket triage in the spirit of Strands Decider v2: a fast decision layer routes, flags urgency, and scores frustration in ~0.04 ms per decision with calibrated confidence; only decisions under 0.9 escalate to the big LLM.
- [agent-voice-pipeline](https://github.com/balasaikunapareddi/agent-voice-pipeline) — Modular voice-agent pipeline in the spirit of HuggingFace speech-to-speech: swappable VAD, speech-to-text, LLM, and text-to-speech stages in their own threads connected by queues, with an OpenAI Realtime-compatible server. The STT stage stands alone — one command or a copy-pasteable example script.
- [agent-resolution-workflow](https://github.com/balasaikunapareddi/agent-resolution-workflow) — Customer resolution agent in the spirit of the n8n demo: a Google ADK multi-agent (coordinator + order and policy sub-agents) checks policies and orders, then a deterministic Process Resolution Request workflow validates the resolution and writes a pending_review record — it never issues refunds or ships replacements.
- [agentic-ai-training](https://github.com/balasaikunapareddi/agentic-ai-training) — Hands-on Agentic AI training in the spirit of Vinay Kumar's 3-day course, built from real portfolio agents: day-wise labs from a basic tool-using agent and RAG, through multi-agent research and planning, to a production FastAPI deployment — every lab runnable in one command.
- [agent-eval-levels](https://github.com/balasaikunapareddi/agent-eval-levels) — Three-level agent evaluation that explains why a session failed: outcome, response, and tool scores with a diagnosis naming the failing level — the wrong tool with a plausible result can no longer hide behind a polite reply.
- [agent-assistant-memory](https://github.com/balasaikunapareddi/agent-assistant-memory) — How an AI assistant maintains memory and sessions: a durable memory store with provenance and corrections, multi-session continuity, and LLM compaction that keeps long conversations inside a token budget.
- [agent-governance](https://github.com/balasaikunapareddi/agent-governance) — Governed agent in the spirit of Palanisamy Ramasamy's governance stack: five controls enforced in code — trusted data with provenance, least-privilege access, output guardrails, human approval for high-impact actions, and a full audit log — plus runtime checks, escalation, and rollback.
- [prior-auth-api](https://github.com/balasaikunapareddi/prior-auth-api) — Prior authorization API in the spirit of Oxbridge Health's hiring take-home: FastAPI + SQLAlchemy + PostgreSQL; offices submit requests with full validation (every error at once, each with a fix), reviewers claim and decide procedure-by-procedure from a queue, members see approvals only, and every step lands in an immutable audit trail.
- [agent-rag-ingestion](https://github.com/balasaikunapareddi/agent-rag-ingestion) — Local, open mirror of Google's Agent Retrieval in the spirit of Vibhavari Bellutagi's post: one-call RAG ingestion (parse, segment, embed, store) and one-call hybrid search returning cited answers — page ranges for documents, timestamps for video — with every knob the managed service hides (chunk size, segmentation, embedding model, hybrid weights, reranking) visible and configurable, plus an eval that shows what the knobs do.
- [agent-prior-auth](https://github.com/balasaikunapareddi/agent-prior-auth) — The agentic layer over prior-auth-api: a Google ADK multi-agent team (intake, coverage, review assistant, member explainer, audit) around the deterministic API. Agents turn messy faxes into submissions and prepare recommendations; humans decide — no agent can approve or deny — and every agent step lands in a hash-chained activity log.
- [agent-evo-ontology](https://github.com/balasaikunapareddi/agent-evo-ontology) — A versioned, evolving ontology layer over MCP for text-to-SQL, mirroring EvoOntology: the agent never sees the raw schema, and ontology edits ship only when a paired McNemar-gated evaluation beats the parent version, with newly-won questions flagged for gold-query review.
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
make demo-deja-vu     # Deja Vu Agent (exactly-once tools)
make web              # cookbook web UI on http://127.0.0.1:8000
```

## Why this cookbook

Most agent collections show you a demo. This one shows you the
decision: where the logic lives (in code, not the prompt), what the
model may and may not decide, and what breaks when the guardrail is
missing. The starter recipes teach one pattern each; the advanced
repos show the same patterns at production scale.

## License

Apache-2.0 — clone it, ship it, sell it.
