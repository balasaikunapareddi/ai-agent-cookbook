# Cookbook web UI

The storefront: every recipe demo, runnable in the browser. No
install, no API key, no network — each page runs the recipe's own
code in-process in mock mode and shows the output exactly as
`python3 demo.py` prints it.

## Run it locally

```bash
pip install -r web/requirements.txt
uvicorn web.app:app --reload        # http://127.0.0.1:8000
```

(from the repo root — `web` is imported as a package.)

## Test it

```bash
pip install httpx pytest
python3 -m pytest web -q
```

## How it works

- `app.py` — FastAPI app: home page, one page per recipe, `/health`.
  Server-rendered HTML with inline CSS (same look as the scheduler
  and booking UIs); no build step, no frontend framework.
- `runners.py` — one function per recipe that calls the same
  functions the CLI demo calls and returns the demo's text output.
  Recipe folders go on `sys.path` (they are plain module folders,
  and the modules import each other by bare name).
- Recipes with a natural input get a form: a question for
  ask-your-csv, a paste box for linkedin-post-to-code and
  meeting-brief-agent, case/path pickers for prior-auth-agent and
  deja-vu-agent. Everything else runs its built-in scenario.
- State-writing recipes (prior-auth, deja-vu) run against a fresh
  temp directory per request, so web runs never touch the recipes'
  own `state/` folders or each other.

Mock mode only, by design: the optional `--live` Gemini paths need
a key and are never reachable from the web UI.

## Deploy

`render.yaml` at the repo root is a Render Blueprint (free tier,
`plan: free`): build installs `web/requirements.txt`, start runs
uvicorn on `$PORT`, health check is `/health`. Nothing to configure
in the dashboard — no keys, no database.
