.PHONY: test demo-mcp demo-csv demo-post demo-brief demo-prior-auth demo-deja-vu web

# Run every recipe's tests (needs pytest: pip install pytest).
test:
	python3 -m pytest starter advanced web -q

# Cookbook web UI: every demo in the browser (needs web/requirements.txt).
web:
	uvicorn web.app:app --reload

# One-command demos, one per recipe (no key, no extra deps).
demo-mcp:
	cd starter/mcp-vs-utcp && python3 demo.py

demo-csv:
	cd starter/ask-your-csv && python3 demo.py

demo-post:
	cd starter/linkedin-post-to-code && python3 demo.py

demo-brief:
	cd starter/meeting-brief-agent && python3 demo.py

demo-prior-auth:
	cd advanced/prior-auth-agent && python3 demo.py

demo-deja-vu:
	cd advanced/deja-vu-agent && python3 demo.py
