PYTHON := python3.11

.PHONY: run scout bible fetch apply classify apply-snippets candidates youtube-audit assemble bundle test

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

# Show current emergence candidates
candidates:
	@$(PYTHON) -c "\
import json; from pathlib import Path; \
f = Path('state/candidates.json'); \
data = json.loads(f.read_text()) if f.exists() else []; \
[print(f'  {c[\"count\"]}x  {c[\"term\"]}\n     ' + '\n     '.join(c['seen_in'])) for c in data] \
if data else print('  No candidates.')"

# Show which YouTube/video URLs would be placed or dropped for an edition
# Usage: make youtube-audit EDITION=2026-W29 ARGS=--live
youtube-audit:
	$(PYTHON) pipeline/audit_youtube.py --edition $(EDITION) $(ARGS)

# Tests
test:
	$(PYTHON) -m pytest tests/ -v
