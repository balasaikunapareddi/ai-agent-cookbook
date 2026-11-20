# Prior-auth agent: the wait is the job

> ▶️ **Try it live:** [https://ai-agent-cookbook.onrender.com/recipes/prior-auth-agent](https://ai-agent-cookbook.onrender.com/recipes/prior-auth-agent) — runs in your browser, nothing to install.

## The idea

Prior authorization is not a form. It is a wait. A request can sit
pending with a payer for days — and the agent's real job is holding
state across that silence and resuming exactly where it left off when
the payer responds. Never re-asking for a document that is already on
file. Never guessing at a clinical detail it was never given.

This recipe is an **advanced** one: it takes the state-machine pattern
from the starter recipes and applies it to a long-lived, interruptible
workflow — the kind where the hard part is not the next answer but the
next *week*.

## What I built

- `prior_auth.py` — a deterministic state machine, pure Python:

  ```
  DRAFT -> SUBMITTED -> PENDING -> APPROVED -> CLOSED
                            |  |          ^
                            |  +-> DENIED +-> APPEALED -+
                            |                            |
                            +-> INFO_REQUESTED ----------+
  ```

  Every transition is a function, every rule is a check. The LLM is
  never in the loop for a decision.
- `data/cases.json` — four mock cases with scripted payer timelines
  (all names, payers, and diagnoses are fictional; no real PHI, no
  real payer APIs):
  - **PA-1001** — MRI, approved straight through.
  - **PA-1002** — biologic therapy; the payer asks for prior-therapy
    history, the agent supplies it once, approved.
  - **PA-1003** — physical therapy; denied, appealed with the denial
    reason attached, approved on appeal.
  - **PA-1004** — sleep study; the payer asks for a sleep diary that
    never arrives. The request holds in `INFO_REQUESTED` — still
    waiting when the demo ends. That is the normal shape of prior
    auth, and the machine does not re-ask or guess its way out of it.
- `demo.py` — replays all four timelines in one command. After every
  step the case is saved to `state/<case_id>.json` and loaded back
  before the next step, so the pause/resume is real and the state
  files are left behind to inspect.
- `status_update_live()` in `prior_auth.py` — the same case journal
  sent to a real Gemini model, which writes a patient-friendly status
  update. Message text only; the prompt forbids inventing clinical
  details.

## Run it

```bash
python3 demo.py                  # all four cases, mock mode
python3 demo.py PA-1003          # one case only
python3 -m pytest -q             # 13 tests (needs pytest: pip install pytest)
```

Mock mode needs nothing: no key, no extra packages, no network.

Live mode (optional):

```bash
pip install -r requirements.txt   # litellm
GEMINI_API_KEY=<redacted>  # free tier
```

The live model is `gemini/gemini-3.5-flash-lite` (Gemini free tier).
If the key is missing or litellm is not installed, `--live` says so
plainly and the mock status above it stands.

## What to notice

- **The wait is a state, not a timeout.** `PENDING` and
  `INFO_REQUESTED` are first-class states with a day counter in the
  journal. A request that waits nine days is not stuck — it is
  exactly where the machine says it is, and the state file proves it.
- **Pause/resume is a file, not a memory.** Every step is saved to
  JSON and reloaded before the next one. Kill the process mid-wait
  and the request resumes on the next run — the demo does exactly
  this on every step.
- **Never re-asked, never guessed.** Asking for a document that is
  already on file is a journal note, not a second request. A missing
  required *field* blocks the submit and the machine names it; a
  missing *document* is a gap the payer may ask about, not something
  the agent invents.
- **A denial travels with its reason.** A denial without a reason is
  refused by the machine. An appeal always carries the denial reason
  with it, so the appeal is argued against the actual decision, not
  against a summary of it.
- **The model writes text, never transitions.** The live mode exists
  to phrase a status update for a patient. It cannot approve, deny,
  or appeal anything — those are code paths, and the tests pin them.
