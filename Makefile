.PHONY: test demo-mcp demo-csv demo-post

# Run every recipe's tests (needs pytest: pip install pytest).
test:
	python3 -m pytest starter -q

# One-command demos, one per recipe (no key, no extra deps).
demo-mcp:
	cd starter/mcp-vs-utcp && python3 demo.py

demo-csv:
	cd starter/ask-your-csv && python3 demo.py

demo-post:
	cd starter/linkedin-post-to-code && python3 demo.py
