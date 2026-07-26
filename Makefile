PYTHON := python3.11

.PHONY: run scout bible fetch apply classify apply-snippets candidates assemble prerender preview bundle test

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

# Step 4 — assemble an edition, then prerender its no-JS/crawlable snapshot.
# This is the publication build: `make assemble` always produces pages whose
# <main id="digest"> is pre-filled, so no-JS readers and search crawlers get the
# full digest (the JS reader stays the single source of truth — prerender just
# freezes its output).
# Usage: make assemble EDITION=2026-W28
assemble:
	$(PYTHON) pipeline/assemble.py --edition $(EDITION)
	$(MAKE) prerender EDITION=$(EDITION)

# Prerender: snapshot the JS reader's output into #digest for no-JS + crawlers.
# Run automatically by `assemble`; also runnable alone after a manual assemble.
# Usage: make prerender EDITION=2026-W28
prerender:
	$(PYTHON) pipeline/prerender.py site/index.html site/editions/$(EDITION).html

# Preview the built site locally. Visit http://localhost:8000/ for the reader,
# or http://localhost:8000/?nojs to see exactly what a no-JS visitor/crawler
# gets (the prerendered digest with the interactive chrome hidden).
preview:
	@echo "Serving site/ at http://localhost:8000  (?nojs for the no-JS view)"
	@cd site && $(PYTHON) -m http.server 8000

# Bundle: single portable HTML file anyone can open or email
# Usage: make bundle EDITION=2026-W28
bundle:
	$(PYTHON) pipeline/bundle.py --edition $(EDITION)

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
