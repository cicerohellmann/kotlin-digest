PYTHON := python3.11

.PHONY: run scout scout-youtube bible fetch recover-medium apply classify apply-snippets candidates assemble prerender preview edition-preview preflight promote bundle test

# Publish-time defaults injected into edition-preview/promote assembles.
# Games (crossword) are suppressed for now (owner decision); videos likewise.
# Override by setting ASSEMBLE_ARGS= on the command line if ever needed.
PUBLISH_ARGS := --no-videos --no-games

# Automated pipeline (steps 1-2) — safe to run unattended
run: scout bible

scout:
	$(PYTHON) pipeline/scout.py

# Scoped scout: fetch ONLY the youtube sources into articles.json (no full scout,
# no prune, no other source touched). Run this before assembling an edition that
# should carry videos, so the week's videos are in state — not just baked into a
# stale page. See docs/summarize.md §2c.
scout-youtube:
	$(PYTHON) pipeline/scout.py --only-type youtube

bible:
	$(PYTHON) pipeline/bible.py

# Step 3 — agent-driven summarization
# Usage: make fetch > state/queue.json   (then agent reviews and writes summaries.json)
#        make apply FILE=state/summaries.json
fetch:
	$(PYTHON) pipeline/summarize.py

# Step 2b — recover Medium-family bodies the HTTP fetcher gets 403 on, via a real
# browser NAVIGATION (cmux), which carries Cloudflare clearance that fetch() lacks.
# Run between `make fetch` and the batch split. Resumable; member-only stay gated
# and are dropped. Then build state/queue_medium.json (see docs/summarize.md §2b).
# Usage: make recover-medium EDITION=2026-W33
recover-medium:
	$(PYTHON) pipeline/recover_medium.py --edition $(EDITION)

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
# ASSEMBLE_ARGS forwards extra flags to assemble.py, e.g.
#   make assemble EDITION=2026-W31 ASSEMBLE_ARGS=--no-videos
assemble:
	$(PYTHON) pipeline/assemble.py --edition $(EDITION) $(ASSEMBLE_ARGS)
	$(MAKE) prerender EDITION=$(EDITION)

# Prerender: snapshot the JS reader's output into #digest for no-JS + crawlers.
# Run automatically by `assemble`; also runnable alone after a manual assemble.
# Usage: make prerender EDITION=2026-W28
prerender:
	$(PYTHON) pipeline/prerender.py site/index.html site/editions/$(EDITION).html

# Safe preview build: assemble an edition into the isolated /test slot with
# production left byte-identical. Restores ONLY the prod *site* files — it NEVER
# touches state/articles.json, so scouted videos + summaries persist (the bug that
# silently dropped the videos was a `git restore state/articles.json` here).
# Usage: make edition-preview EDITION=2026-W31   (then `make preview`, open /test/)
edition-preview:
	$(MAKE) assemble EDITION=$(EDITION) ASSEMBLE_ARGS="$(PUBLISH_ARGS) $(ASSEMBLE_ARGS)"
	mv site/index.html site/test/index.html
	$(PYTHON) -c "import pathlib; p=pathlib.Path('site/test/index.html'); t=p.read_text(encoding='utf-8'); \
	p.write_text(t.replace('<head>', '<head>\n  <meta name=\"robots\" content=\"noindex\">', 1) if 'name=\"robots\"' not in t else t, encoding='utf-8')"
	git restore site/index.html site/archive.html site/sources.html state/editions.json
	rm -f site/editions/$(EDITION).html
	@echo "Preview → site/test/index.html (noindex) · prod site files restored · articles.json UNTOUCHED"
	@echo "── preflight (advisory in preview) ──"
	-$(PYTHON) pipeline/preflight.py --edition $(EDITION)

# Preflight quality gate — run before promoting. HARD checks (density, unique
# article ids, valid urls) exit non-zero and BLOCK a promote; WARN checks
# (stale featured pins, comics pool) are advisory. Usage: make preflight EDITION=2026-W32
preflight:
	$(PYTHON) pipeline/preflight.py --edition $(EDITION)

# Promote a staged edition to the live front page ("flip the flag"). Runs the
# real assemble (front page + editions/ + archive + sources, NO restore), adds
# the edition to the sitemap, and drops the now-redundant /test/ preview. Pass
# the SAME ASSEMBLE_ARGS the edition was previewed with.
# Usage: make promote EDITION=2026-W31
# Runs the preflight gate FIRST — if any HARD check fails (too few articles,
# duplicate ids, bad urls) make aborts and nothing is assembled/committed.
# --no-videos --no-games are applied by default (PUBLISH_ARGS).
promote:
	$(PYTHON) pipeline/preflight.py --edition $(EDITION)
	$(MAKE) assemble EDITION=$(EDITION) ASSEMBLE_ARGS="$(PUBLISH_ARGS) $(ASSEMBLE_ARGS)"
	$(PYTHON) pipeline/sitemap.py --add editions/$(EDITION).html --touch / --touch archive.html
	rm -f site/test/index.html
	@echo "Promoted $(EDITION) → live front page. Review 'git diff', then commit + push."

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
