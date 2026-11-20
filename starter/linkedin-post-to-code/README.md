# LinkedIn post → code: the post-to-code loop in miniature

> ▶️ **Try it live:** [https://ai-agent-cookbook.onrender.com/recipes/linkedin-post-to-code](https://ai-agent-cookbook.onrender.com/recipes/linkedin-post-to-code) — runs in your browser, nothing to install.

## The idea

Bala's loop: post an AI idea on LinkedIn, then implement it as a
small runnable, tested entry. This recipe does the first step of that
loop — paste a short post, get back a runnable code sketch and a test
outline. It is the same idea as the
[linkedin-ai-lab](https://github.com/balasaikunapareddi/linkedin-ai-lab),
packaged so anyone can run it.

## What I built

- `post_to_code.py` — a keyword router picks one of five sketch
  templates (policy gateway, ask-your-CSV, state-machine booking,
  exactly-once tools, minimal agent loop), and `generate()` returns
  the sketch, a test outline, and a README snippet. Every sketch is
  real, valid Python — the tests parse each one with `ast` to prove it.
- `demo.py` — runs two canned posts (MCP vs UTCP, scheduling agent)
  through the router.
- `generate_live()` in `post_to_code.py` — the same post sent to a
  real Gemini model, which writes the sketch and the test outline.

## Run it

```bash
python3 demo.py                              # two canned posts, mock mode
python3 demo.py "your post text here"        # one post, mock mode
python3 -m pytest -q                         # 10 tests (needs pytest: pip install pytest)
```

Mock mode needs nothing: no key, no extra packages, no network.

Live mode (optional):

```bash
pip install -r requirements.txt   # litellm
GEMINI_API_KEY=... python3 demo.py --live "your post text here"
```

The live model is `gemini/gemini-3.5-flash-lite` (Gemini free tier).
If the key is missing or litellm is not installed, `--live` says so
plainly and falls back to the mock router.

## What to notice

- **Routing is keyword scoring, not magic.** The router counts
  keyword hits per template and picks the best. A post about refunds
  and approvals lands on the policy gateway; a post about double
  charges lands on the idempotency ledger. When nothing matches, it
  falls back to the minimal agent loop — and says so in the topic.
- **The sketch is checked before it is shown.** `generate()` parses
  the sketch with `ast` first, so a broken template can never reach
  the reader. The live path does the same to the model's reply.
- **Templates are starting points, not products.** Each sketch is
  15–30 lines: enough to run, small enough to rewrite. The test
  outline is the real deliverable — it says what "done" looks like.

## Limits

Keyword routing is brittle by design: it matches words, not meaning,
so a post that uses none of the keywords falls back to the scaffold.
The live mode fixes that, but a model's sketch still needs a human
read before it is trusted. Neither mode writes files — the sketch is
printed for the reader to keep or discard.
