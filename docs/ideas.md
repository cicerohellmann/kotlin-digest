# Kotlin Digest — Ideas Backlog

Captured from an early brainstorm, split into two lists:

- **A. Automatable** — has an engineering path; sorted highest-priority first.
- **B. Human / editorial** — inherently needs a person; can't be automated
  (AI may assist, but a human owns the judgment).

---

## A. Automatable — build these (highest first)

1. **Relevance scoring — the keystone.** Weight a change by its *magnitude* ×
   the library's *importance to the ecosystem* (e.g. a navigation library
   entering or leaving alpha is a big deal). Everything visual downstream depends
   on this signal existing.

2. **Collapse library nightlies into one readable update.** *Strong
   requirement.* No seven `v1.12.10-alpha01+dev4438` cards — one card, "**Kotlin
   core update**" / "**KMP update**", with a short summary of what actually
   changed across the releases. (Collapse step exists; the summary is the weak
   part.)

3. **`screen.py` (Phase 2) — publish only verified articles.** Reachable,
   genuinely an article, on-topic, this-week, summary-grounded. The reliability
   foundation that lets the catalog grow without re-introducing junk.

4. **Extraction + small local model, per article.** Move off big cluster-level
   models. Structured extraction first, then a small model (Gemma-class)
   summarizing one article at a time. Powers #2 and lowers AI cost/dependency.

5. **Visual hierarchy by relevance.** Size cards by importance — big changes big,
   minor ones small — instead of the current repetitive grid. *Depends on #1.*

6. **YouTube / video as a first-class, reliable source.** A proper video source
   with real metadata and dates — never the Slack link-dump path removed this
   session.

7. **"What have we built?" — library-releases + GitHub-trending section.** A
   dedicated releases section, plus trending Kotlin repos ("ripples" picking up).
   Builds on #2.

8. **Bigger source catalog.** Broaden ingested blogs and voices.

9. **Multiple languages.** Read the edition in different languages (translation
   is largely automatable).

10. **Multiple visual styles / themes.** Swappable magazine "skins" beyond the
    night toggle.

11. **Comic interludes — one up top + one every 14 articles.** A recurring
    webcomic as a print-magazine-style palate-cleanser: one comic before the
    magazine starts, then one after every 14 article cards.
    **No repeats:** track which comics have already run (persist a used-comics
    list to `state/`) so a strip never appears twice across editions; draw the
    next unused one from the pool each time.
    Automatable core: a link-out comic card (any strip — zero ToS risk), or a
    *licensed embed* via the **xkcd** JSON API (CC BY-NC: attribution + link
    back, non-commercial only). Indie dev comics (SMBC, CommitStrip, MonkeyUser…)
    are all-rights-reserved — need the artist's permission, see §B.

**Loose ends (config / small eng):** Slack topic-signal decision (currently
signal-off after the real-date fix) · paywall down-rank vs. exclude · Reddit
OAuth if Reddit is ever wanted back as more than signal.

---

## B. Human / editorial — cannot be automated

- **Weekly Sunday editorial pass.** The inversion of today's AI-first flow: skim
  the week's articles, write proper summaries by hand, then use AI only to
  correct, aggregate, and format (including the Kotlin snippets). Human owns the
  judgment.

- **Illustrated covers from community artists.** Commission/feature covers from
  Android & Kotlin community artists, ideally local/regional. Per edition.

- **Opinion columns.** Recurring human-written editorial/opinion pieces.

- **Regional / local contributors.** Feature writers who publish in their own
  language and country, so editions reflect local community voices, not just
  English-language global sources.

- **Editorial-design research: how magazines are cut & laid out.** Study cover
  story / columns / sidebars / rhythm and content distribution. A human learning
  task whose output feeds the automatable layout work (#5).

- **Comic-reproduction permissions.** For licensed comic embeds (§A #11), email
  indie dev cartoonists (SMBC, CommitStrip, MonkeyUser…) for permission to
  display attributed strips. Fits the community-artist ethos and reuses the same
  relationships as the illustrated covers. (xkcd/Geek & Poke are already CC-
  licensed and need no outreach.)
