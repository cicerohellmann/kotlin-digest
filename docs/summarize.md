# Runbook: Summarize a Composed Edition

**Audience:** any agent handed *"the edition is composed, now write the summaries."*
Follow this top to bottom. Do **not** re-derive it, re-filter the edition, or ask
the user to explain it again. Everything you need is here.

---

## 0. The one rule that keeps getting broken

**The edition is already curated. Do not recompute it.**

When someone says "the mag is composed, run the summaries," a specific edition has
**already been selected** — its articles, its cover, its cuts. Your job is *only*
to write summaries for that existing set and re-render it. You are finishing a
composed edition, not choosing one.

So before anything else, **read the composed edition** and take its article set as
given:

- **Preview builds live in `site/test/index.html`** (prod stays untouched — see §6).
  The article set is the `const CHAPTERS = [...]` block in that file. That list —
  its `id` fields — **is the curated edition.** Read it; don't rebuild it.
- **Editorial pins live in `state/featured.json`**, keyed by edition
  (`"2026-W30": { "cover": "<id>", "also": ["<id>", ...] }`). These are hand-picked.
  Never overwrite them.

If you catch yourself counting the raw week window (`151 articles in window`,
`276 pending`) or proposing to "tighten the cut," **stop** — you're re-curating an
edition that was already curated. The raw window is not the edition.

> Why this matters: a naïve `assemble` reports `0 placed articles` for a fresh week
> because nothing is summarized yet — clustering needs topics. That does **not** mean
> the edition is empty or needs re-filtering. It means: write the summaries, then
> re-assemble.

---

## 1. What "summarize" actually is

Per-article summaries + topic tags are written by **AI agents**, in parallel, via
the **Workflow tool** — not by hand, and not by an API call from Python. The agents
running the workflow *are* the LLM. Then a merge → `make apply` → `make assemble`
turns the composed-but-blank edition into a rendered one.

Pipeline of files (know these names — one of them is whatever "the curated files" means):

| Stage | File(s) | Who writes it |
|---|---|---|
| Fetch content | `state/queue.json` | `make fetch` (§2) |
| Split for fan-out | `state/batches/batch_NN.json` | you (§3) |
| Agent summaries | `state/batches/out_NN.json` | the Workflow agents (§4) |
| Merge + verify | `state/summaries.json` | you (§5) |
| Apply to articles | `state/articles.json` (`summary`, `topics`, `code_snippet`) | `make apply` (§5) |
| Editorial pins | `state/featured.json` | the user / `--feature` (§6) |
| Rendered edition | `site/test/index.html` then prod | `make assemble` (§6) |

---

## 2. Fetch the content

```bash
python3.11 pipeline/summarize.py > state/queue.json 2> state/fetch.log
```

This is slow (a network fetch per pending article, ~20s timeout each) — run it in
the background and move on.

**Expected:** the HTTP fetcher gets **403 Forbidden** on almost every `medium-*`
article — Medium now hard-blocks it at the Cloudflare layer (a browser User-Agent
does **not** help; the RSS feed carries only a ~20-word teaser). So a plain
`make fetch` yields only ~80 non-Medium/lucky articles and drops the rest as "fetch
error." **Never** force-summarize a Medium article from its bare title/teaser — that
fabricates detail, and the ≥80-word content gate (`_has_usable_content`) correctly
benches it.

To actually include Medium, recover the bodies with a **real browser** — see §2b.
Do not skip this: without it an edition is ~40 articles; with it, ~65–75.

`queue.json` is the set you will summarize. It is not edition-scoped — it's every
fetchable pending article — but §5's verify step and `assemble`'s window filter
handle that: only in-window, summarized articles land in the edition.

---

## 2b. Recover Medium bodies via a real browser (the 403 workaround)

The HTTP fetcher can't get Medium content (§2), but a **headless real browser can**:
once a tab is on `medium.com`, a same-origin `fetch()` from inside the page carries
the browser's Cloudflare clearance and returns the full article HTML (200, not 403).
This is how you get the ~90 Medium articles back into an edition.

Use the Playwright MCP (`mcp__playwright-brave__*`):

1. **Collect the blocked Medium URLs** — the in-window Medium articles that are still
   `not summarized` and `not unfetchable`. Strip the `?source=…` query but keep the
   trailing hex id (Medium 404s without it). Dump `[[id, url], …]`.
2. **Navigate once** to any real Medium article so the browser holds a medium.com
   origin + Cloudflare cookie:
   `browser_navigate("https://medium.com/@nagarjuna3/…-<hexid>")`.
3. **Batch-fetch from inside the page** with `browser_evaluate`, ~12 URLs per call.
   The function loops `await fetch(u, {credentials:'include'})`, parses
   `article`/`main`/`body` textContent, truncates to 6000 chars, and returns
   `[{id, status, words, content}]`. **Save each call to a file** via the evaluate
   `filename` param — the path MUST be under the repo (e.g.
   `<repo>/.playwright-mcp/medium_out_NN.json`); paths outside the repo are denied.
   Space calls with a ~250ms per-URL delay. A few will `Failed to fetch` (member-only
   / deleted) — retry once, then leave them.
4. **Build a Medium queue**: join the harvested `content` back to each article's
   `title/excerpt/date/source_id` (keep only `words ≥ 60` — shorter is real junk like
   "TSM PRO EDITION … Unlock"), and write it as `state/queue_medium.json` in the exact
   `queue.json` shape.

Then feed `state/queue_medium.json` through §3–§5 like any other queue. Give the
summarization agents an extra instruction for this batch: **be ruthless about junk** —
Medium tag feeds are full of game-APK guides, forex/rummy/teen-patti, movie reviews,
phone-spec news, and Flutter-only posts; those must get `topics: []` so they drop.

> Rights note: this is fetch-to-summarize, identical to what the HTTP fetcher did —
> not republishing. Same `content-rights.md` rules apply (summarize, attribute, link).

## 2c. YouTube videos — scout them, and DON'T let them get reverted

Videos come from `type: youtube` sources (Atom feeds). They are **only** in an edition
if they're in `articles.json` at assemble time — and the trap is: a `make scout` (or a
surgical youtube scout) writes them into `articles.json`, but the §6 preview flow's
`git restore state/…` can **revert them right back out**, leaving them baked into the
old test page but absent from state. Re-assemble later → videos vanish. This has bitten
us; it looks like "someone deleted the videos" when nothing was deleted.

Rules:
- Before assembling an edition that should carry videos, run **`make scout-youtube`**.
  It scouts ONLY the `type: youtube` sources into `articles.json`, skips the 90-day
  prune, and touches no other source (`pipeline/scout.py --only-type youtube`). Safe
  and idempotent — re-running adds nothing.
- Summarize the new videos from **feed metadata** (title + description) — never scrape
  the watch page. Build their queue content as
  `"YouTube video metadata…\nTitle: …\nDescription: …"` and run them through §4 like any
  batch. Official Android Developers / Kotlin / JetBrains videos are on-topic
  (`android-developers` + specifics); a stray conference/marketing clip gets
  `topics: []` and drops.
- **Build the preview with `make edition-preview EDITION=<ed>`, never a hand-typed
  restore.** That target assembles into `site/test/index.html` and restores only the
  prod *site* files — it **never** touches `state/articles.json`, so scouted videos +
  summaries persist. (The bug that silently dropped the videos was exactly a
  `git restore state/articles.json` in a hand-run preview flow.)

## 3. Split into batches

Fan-out wants one batch file per agent. ~8 articles per batch is the proven size.

```bash
python3.11 - <<'PY'
import json, math, os
q = json.load(open('state/queue.json'))
os.makedirs('state/batches', exist_ok=True)
for f in os.listdir('state/batches'):        # clear stale batch_/out_ files
    os.remove('state/batches/' + f)
B = 8
n = math.ceil(len(q) / B)
for i in range(n):
    json.dump(q[i*B:(i+1)*B], open(f'state/batches/batch_{i:02d}.json', 'w'),
              ensure_ascii=False, indent=2)
print('batches:', n, 'covering', len(q), 'articles')
PY
```

Note the batch count `n` — it's the `N` in the workflow below.

---

## 4. Run the summarization workflow

Launch the **Workflow tool** with the script below. Set `N` to the batch count from
§3 and the edition string in the rules. It spawns one **Sonnet** `general-purpose`
agent per batch; each reads `batch_NN.json`, writes `out_NN.json`, and returns the
ids it wrote so §5 can verify none were dropped.

> This is a multi-agent workflow — it needs the user's explicit go-ahead once ("run
> the summarization workflow" / "parallelize on Sonnet"). Ask once, then run it.

```javascript
export const meta = {
  name: 'summarize-edition',
  description: 'Parallel Sonnet summarization of the composed edition\'s batches',
  phases: [{ title: 'Summarize', detail: 'one Sonnet agent per batch file' }],
}

const DIR = '/Users/cicerohellmann/Projects/kotlin-digest/state/batches'
const N = 14   // <-- set to the batch count printed in §3
const EDITION = '2026-W31'   // <-- set to the edition being composed

const RULES = `You are summarizing Kotlin/Android developer articles for the Kotlin Digest magazine (edition ${EDITION}).

For EACH item in the batch file, produce one output object:
- id: MUST equal the item's "id" field verbatim (a mismatch silently drops the article).
- summary: An abstract of what's inside so a reader knows the content without opening it. 2-3 sentences, MAX 50 words. Say what changed / what it covers and why it matters to Android/KMP/Kotlin developers. NO marketing words ("exciting", "powerful", "game-changing"). Never write "this article" or "the author". If content is "[fetch error...]" or thin, write a minimal abstract from the title + excerpt anyway — never skip an id.
- topics: 1-4 IDs, SEMANTIC match, chosen ONLY from this exact list of 59 valid topics:
  adaptive-ui, android-api, android-auto, android-developers, animation, architecture, build-logic, clean-architecture, compose, compose-multiplatform, context-receivers, coroutines, datastore, droidcon, exposed, flows, google-io, gradle, gradle-plugin, hilt, ios-interop, jetbrains, jetpack, k2-compiler, kapt, kmp, kodein, koin, kotlin, kotlin-backend, kotlin-js, kotlin-scripting, kotlin-stdlib, kotlinconf, ksp, ktor, ktor-server, material3, media3, mvi, mvvm, navigation, okhttp, paparazzi, r8-proguard, retrofit, room, sealed-classes, shot, spring-kotlin, swift-export, testing, turbine, value-classes, version-catalog, viewmodel, wasm, wear-os, workmanager.
  If the article is off-topic / spam / not about Kotlin-Android-KMP (e.g. generic "best VPN", crypto, hiring posts), return topics: [] — do NOT force a tag. Empty topics = it gets dropped from the edition, which is correct for junk.
- code_snippet (OPTIONAL): include ONLY if the article shows one concrete API call/pattern/DSL/breaking change expressible in <=10 lines. Kotlin or Swift ONLY. RAW code text with \\n newlines — NO markdown fences, NO HTML, NEVER any <span> tags (highlighting is applied later; literal spans render as text). Strip imports/package/@Preview. Omit the field entirely if no strong snippet applies.
- snippet_label (only if code_snippet present): 2-4 word ALL-CAPS label, e.g. "ANIMATE ITEM", "NEW ROUTING DSL", "BEFORE AFTER".`

phase('Summarize')

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['written', 'ids'],
  properties: {
    written: { type: 'integer' },
    ids: { type: 'array', items: { type: 'string' } },
  },
}

const results = await parallel(
  Array.from({ length: N }, (_, i) => () => {
    const nn = String(i).padStart(2, '0')
    const inPath = `${DIR}/batch_${nn}.json`
    const outPath = `${DIR}/out_${nn}.json`
    const prompt = `${RULES}

Steps:
1. Read the batch file: ${inPath}
2. Produce one output object per item (process ALL items; do not skip any id).
3. Write a JSON array of those objects to: ${outPath}
   (a plain JSON array [ {...}, {...} ], UTF-8, one object per input item).
4. Return { written: <number of objects>, ids: [<every id you wrote>] }.`
    return agent(prompt, { label: `batch_${nn}`, phase: 'Summarize', model: 'sonnet', agentType: 'general-purpose', schema: SCHEMA })
  })
)

const ok = results.filter(Boolean)
const totalWritten = ok.reduce((s, r) => s + (r.written || 0), 0)
const allIds = ok.flatMap(r => r.ids || [])
log(`batches ok: ${ok.length}/${N} | objects written: ${totalWritten} | ids: ${allIds.length}`)
return { batchesOk: ok.length, totalWritten, uniqueIds: new Set(allIds).size }
```

---

## 5. Merge, verify, apply

Merge the `out_NN.json` files into `state/summaries.json` and **verify every queued
id got summarized** — a missing id silently vanishes from the edition, so catch it here.

```bash
python3.11 - <<'PY'
import json, glob
q = json.load(open('state/queue.json'))
qids = [a['id'] for a in q]; qset = set(qids)
merged, seen = [], set()
for f in sorted(glob.glob('state/batches/out_*.json')):
    for o in json.load(open(f)):
        merged.append(o); seen.add(o['id'])
missing = [i for i in qids if i not in seen]
extra   = [i for i in seen if i not in qset]
print('merged:', len(merged), '| unique:', len(seen))
print('MISSING (queued but not summarized):', len(missing))
for i in missing:
    a = next(x for x in q if x['id'] == i)
    print('  ', i, '|', a['source_id'], '|', a['title'][:70])
print('EXTRA/mismatched ids:', extra[:10])
json.dump(merged, open('state/summaries.json', 'w'), ensure_ascii=False, indent=2)
PY
```

- If **MISSING** is non-empty, re-run just those ids (add them to a batch and rerun
  the workflow, or hand-write from the queue item's excerpt) until it's zero.
- **EXTRA** must be empty — a non-empty list means an agent invented or corrupted an
  id; fix it, those articles won't apply.

Then write summaries + topics back into `articles.json`:

```bash
python3.11 pipeline/summarize.py --apply state/summaries.json
```

Optional second pass — code snippets for already-summarized articles that still lack
one (`docs/classifier.md` has the selection criteria):

```bash
python3.11 pipeline/summarize.py --classify > state/classify-queue.json
# agent writes state/snippets.json = [{id, code_snippet, snippet_label}, ...]
python3.11 pipeline/summarize.py --apply-snippets state/snippets.json
```

---

## 6. Assemble — preview first, prod never clobbered

`make assemble` overwrites the **live** `site/index.html`. For a preview, use the
**`edition-preview`** target — it assembles into `site/test/index.html` and restores
only the prod *site* files, leaving `state/articles.json` (summaries + scouted videos)
and production byte-identical. Do NOT hand-type the mv/restore — a stray
`git restore state/articles.json` is what silently dropped the videos.

```bash
git status --short                          # clean tree first
make edition-preview EDITION=2026-W31       # assemble → /test, prod site restored, articles.json untouched
```

Serve and open the preview:

```bash
cd site && python3.11 -m http.server 8931   # then open /test/index.html
```

Cover + "also inside" are **hand-curated** into `state/featured.json`. To set them
for this edition, either edit that file directly (keyed by edition) or:

```bash
python3.11 pipeline/assemble.py --edition 2026-W31 --feature <cover_id>
```

Only when the user approves the preview do you publish for real: a plain
`make assemble EDITION=<ed>` (no move/restore) writes prod, then commit. Respect the
**no-republish rule** — regenerating changes older editions' bytes is a bug; the
W28/W29 files must stay byte-identical (see the assemble gate and
`no-republish-existing-editions`).

---

## 7. Rollup summaries (if assemble asks)

If `make assemble` prints `N rollup(s) need synthesis → state/rollup-queue.json`,
that's a separate one-paragraph task per bulky-changelog rollup. Follow
`docs/rollup.md`: write `[{rollup_id, summary}]`, then
`python3.11 pipeline/rollup.py --apply <file>`, then re-assemble. Most weeks the
answer is Outcome B — *"Nightly dev builds only — no notable API or behaviour
changes this week."*

---

## Checklist

- [ ] Read the composed edition's article set from `site/test/index.html` — did **not** recompute the window
- [ ] `make fetch` run; Medium fetch failures accepted as dropped (not forced)
- [ ] Queue split into `batch_NN.json`
- [ ] Summarization workflow run (Sonnet, one agent per batch) → `out_NN.json`
- [ ] Merged + **MISSING ids = 0**, EXTRA = 0 → `state/summaries.json`
- [ ] `make apply` written back into `articles.json`
- [ ] Assembled to `site/test/index.html`, prod restored, previewed
- [ ] `state/featured.json` cover/also set, prod published only on approval, no-republish gate green
