# Deja Vu Agent: the timeout lied to you

> ▶️ **Try it live:** [LIVE_URL/recipes/deja-vu-agent](LIVE_URL/recipes/deja-vu-agent) — runs in your browser, nothing to install.

## The idea

Agents retry. A tool call times out, the agent tries again — good
behavior, right up until the timeout lies. A timeout does not mean
"nothing happened." It means "I don't know what happened." The
booking may have committed and only the *response* was lost. Retry
blindly and the patient is booked twice, the card charged twice.

This is not hypothetical: a robustness test against a real
scheduling agent double-booked a slot exactly this way. The agent
did nothing wrong by retrying. It had no way to recognize its own
retry.

The fix is old and boring, which is the point: an **idempotency
key** per logical operation, plus a **ledger** that remembers what
each key already did — so a retry replays the stored result
instead of re-executing the side effect.

## What I built

- `exactly_once.py` — the ledger and the wrapper, pure Python:

  ```
  first call with key K    -> claim K, execute, store the result
  retry with key K         -> return the stored result (replay)
  retry after a timeout    -> outcome unknown: reconcile first,
                              re-execute only if nothing committed
  two calls with key K     -> one executes, the other waits and
  at the same time            gets the stored result
  ```

  The ledger is a JSON file, written before and after execution.
  An entry found `in_progress` after a restart becomes `unknown`
  — a crashed attempt is evidence to reconcile, not a clean slate.
- `tools.py` — flaky mock tools (`book_appointment`,
  `charge_payment`) over a mock world of bookings and charges.
  They fail in the two ways that matter: *after* committing (the
  side effect lands, then the response is "lost") and *before*
  committing (nothing lands). From the caller's side both look
  identical — that is the hazard. The world indexes committed
  records by idempotency key so `lookup(key)` can answer the
  reconcile question: did this key already commit?
- `agent.py` — the agent loop: book one appointment, charge one
  copay, survive the timeouts. Keys are derived from the intent
  (`book:patient-123:2026-11-25T09:00`), one per logical
  operation, reused on every retry. With `use_idempotency=False`
  the same loop mints a fresh key per attempt — the most common
  real-world bug shape — and double-books.
- `demo.py` — runs the same story both ways in one command: safe
  path first (one booking, one charge, ledger left in
  `state/ledger.json` to inspect), then the broken path (two of
  each). The verdicts are read from the world, not from the
  agent's own output — the agent in the broken path thinks it
  succeeded once.
- `explain_live()` in `exactly_once.py` — the same journal sent to
  a real Gemini model, which writes a plain-English incident
  summary. Message text only; the prompt forbids inventing events
  that are not in the journal.

All data is fictional: no real patients, no real payments, no
network.

## Run it

```bash
python3 demo.py                    # both paths, mock mode
python3 demo.py --idempotent       # only the safe path
python3 demo.py --no-idempotency   # only the broken path
python3 -m pytest -q               # 11 tests (needs pytest: pip install pytest)
```

Mock mode needs nothing: no key, no extra packages, no network.

Live mode (optional):

```bash
pip install -r requirements.txt   # litellm
GEMINI_API_KEY=<redacted>  # free tier
```

The live model is `gemini/gemini-3.5-flash-lite` (Gemini free
tier). If the key is missing or litellm is not installed, `--live`
says so plainly and the mock journal above it stands.

## What to notice

- **A timeout is not a failure.** It is an *unknown*. The ledger
  has a status for exactly that, and an unknown outcome is never
  silently retried — it is reconciled first. Found in the world:
  replay it. Not found: now it is safe to execute. No way to
  check: refuse, loudly, instead of guessing.
- **The key belongs to the intent, not the attempt.** One key per
  logical operation, derived from what is being done (patient +
  slot), reused across every retry. A fresh random key per
  attempt — what the broken path does — is the same as no key.
- **The ledger is written before the side effect.** The key is
  claimed and persisted *before* the tool runs, so a crash
  mid-flight leaves an `unknown` entry to reconcile, not a
  mystery. Kill the process between commit and response and the
  next run still ends with exactly one booking.
- **Concurrent duplicates wait, they don't race.** Two calls with
  the same key at the same time: one executes, the other blocks
  and replays the stored result. The test runs four threads at
  one key and counts exactly one execution.
- **The verdict comes from the world, not the agent.** In the
  broken path the agent's journal reads like a success story. The
  double-booking is only visible in the world's records — which
  is why the tests assert on the world, and why real systems
  reconcile against the system of record, not the agent's memory.
- **The model writes text, never retry policy.** The live mode
  exists to summarize the incident for a human. Whether a retry
  is safe is a code path, and the tests pin it.
