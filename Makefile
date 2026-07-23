PYTHON := python3.11

.PHONY: run scout bible fetch apply classify apply-snippets candidates assemble bundle nojs test

# Automated pipeline (steps 1-2) — safe to run unattended
run: scout bible

scout:
	$(PYTHON) pipeline/scout.py

bible:
	$(PYTHON) pipeline/bible.py

# Step 3 — agent-driven summarization
# Usage: make fetch > state/queue.json   (then agent reviews and writes summaries.json)
#        make apply FILE=state/summaries.json
fetch:
	$(PYTHON) pipeline/summarize.py

apply:
	$(PYTHON) pipeline/summarize.py --apply $(FILE)

# Step 3b — classify: agent adds code snippets to already-summarized articles
# Usage: make classify > state/classify-queue.json
#        agent reviews classify-queue.json, writes snippets.json
#        make apply-snippets FILE=state/snippets.json
classify:
	$(PYTHON) pipeline/summarize.py --classify

apply-snippets:
	$(PYTHON) pipeline/summarize.py --apply-snippets $(FILE)

# Step 4 — assemble an edition
# Usage: make assemble EDITION=2026-W28
assemble:
	$(PYTHON) pipeline/assemble.py --edition $(EDITION)

# Bundle: single portable HTML file anyone can open or email
# Usage: make bundle EDITION=2026-W28
bundle:
	$(PYTHON) pipeline/bundle.py --edition $(EDITION)

# Open the generated site in an isolated Chrome profile with JavaScript disabled.
# Does not change your normal Chrome profile/session.
nojs:
	scripts/open-nojs-chrome.sh site/index.html

# Show current emergence candidates
candidates:
	@$(PYTHON) -c "\
import json; from pathlib import Path; \
f = Path('state/candidates.json'); \
data = json.loads(f.read_text()) if f.exists() else []; \
[print(f'  {c[\"count\"]}x  {c[\"term\"]}\n     ' + '\n     '.join(c['seen_in'])) for c in data] \
if data else print('  No candidates.')"

# Tests
test:
	$(PYTHON) -m pytest tests/ -v
