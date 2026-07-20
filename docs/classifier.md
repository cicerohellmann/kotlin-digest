# Code Snippet Classifier

Used during summarization to decide whether an article deserves a code snippet card and, if so, what to show.

The snippet is a **sneak peek, not a tutorial**. It should make a developer look at it and immediately understand why the article is worth their time. One glance = one clear signal of what's new, what changed, or what's possible. Think of it as the article's hook, not its explanation.

---

## When to Include a Snippet

Include a snippet when the article shows **one concrete API call, pattern, or DSL that a developer could use in their own project tomorrow**. The test: would an experienced developer look at this snippet and think "oh, I didn't know you could do that" or "that's cleaner than what I'm doing now"?

### Yes — include a snippet

| Signal | Example |
|---|---|
| New API with a clear usage pattern | `LazyColumn { items(...) { Modifier.animateItem() } }` |
| A before/after showing the improvement | Old: `LiveData<List<T>>` → New: `StateFlow<List<T>>` |
| A DSL or builder that shows the shape of an API | Ktor routing, Compose animation spec |
| A migration one-liner that replaces a verbose pattern | `@OptIn` annotation, `rememberSaveable` vs `remember` |
| A function signature that shows a new capability | `suspend fun` + structured concurrency, `@Composable` + `remember` |
| A changelog entry with a breaking change | changed parameter name, removed API, new required argument |
| A library that lives in code, not prose | A Gradle convention plugin, a KSP processor, an Arrow Raise DSL block |

### No — omit the snippet

| Signal | Reason |
|---|---|
| The article is conceptual / architectural | A diagram or prose explanation doesn't compress into code |
| The code is just a boilerplate setup | Environment config, imports, build.gradle blocks with no novel API |
| The snippet needs 15+ lines of context to make sense | If you can't cut it to ≤10 lines, the article isn't snippet-friendly |
| The article is a discussion, opinion, or hiring post | No API to show |
| The code is in Java, Python, Swift (non-KMP), or JavaScript | Only Kotlin or Swift-consuming-Kotlin is in scope |
| The article has code but all of it is trivially obvious | `val x = listOf(1, 2, 3)` is not a sneak peek |
| Changelog with only version bumps and no API change | "dependency updates" releases, dev builds |

---

## Selecting the Right Snippet

If the article has multiple code blocks, pick the one that maximizes **novelty × clarity**:

- **Novelty**: shows something the reader probably hasn't seen yet
- **Clarity**: understandable in isolation without reading the article first

Tiebreak rules, in order:
1. Prefer the API/function call over the wiring code
2. Prefer a pattern that shows the result (composable UI) over the infrastructure (ViewModel setup)
3. Prefer a before-or-after comparison if one exists — it immediately communicates the improvement
4. For library changelogs: prefer the new API call over the migration steps

---

## Writing the Label

The label appears as `▸ LABEL` above the code. It is the **title of the sneak peek**, not a description of the article. It should name what the snippet *does*, not what the article *discusses*.

**Rules:**
- ALL CAPS, 2–4 words
- Names the capability demonstrated in the snippet, not the topic category
- Should feel like a pull quote: "if you read nothing else, read this part"

**Good labels:**
```
▸ ANIMATE ITEM
▸ NEW RAISE DSL
▸ BEFORE → AFTER
▸ KMP ROOM SETUP
▸ MIGRATION GUIDE
▸ SHARED VIEWMODEL
▸ CHANNEL PATTERN
▸ SWIFT INTEROP
```

**Bad labels (too generic):**
```
▸ CODE EXAMPLE        ← says nothing
▸ SAMPLE              ← useless
▸ IMPLEMENTATION      ← what implementation?
▸ KOTLIN CODE         ← every snippet is Kotlin code
▸ HOW IT WORKS        ← that's what the article is for
```

---

## Formatting the Code

The snippet is rendered in a dark-background code block. The `code_snippet` field is **plain Kotlin text with `\n` for newlines**. No markdown fences.

**Syntax highlighting is automatic — do NOT add HTML.** The build step
(`highlight_kotlin` in `pipeline/_assemble/render.py`) runs Pygments over the
plain code, which HTML-escapes it and wraps tokens in the `.snap-code` palette.
If you hand-write `<span class="kw">…</span>` tags, Pygments escapes them and they
render as **literal text** on the card. Emit raw Kotlin only — keywords,
function names, strings, and comments are coloured for you.

> The `<span>` examples elsewhere in this doc are historical (pre-Pygments) and
> illustrate which tokens matter, not literal output. Never put spans in
> `code_snippet`.

**Length:** ≤10 lines. If you need more to make the point, the snippet is the wrong choice; write a stronger summary instead.

**Strip:**
- Import statements
- Package declarations
- `@Preview` annotations (unless the article is specifically about previews)
- Boilerplate constructor args that aren't relevant to the new API

**Preserve:**
- Enough context to understand what the snippet does in isolation
- The function/composable name that the article is teaching
- Any modifier chain or argument that is the point of the article

---

## Examples

### Example 1 — New modifier API

**Article:** "Compose 1.7 adds `animateItem()` for LazyList reorder animations"

**Label:** `ANIMATE ITEM`

**Code:**
```
LazyColumn {
  items(list, key = { it.id }) { item ->
    ItemCard(
      modifier = Modifier.<span class="fn">animateItem</span>()
    )
  }
}
```

Why: shows exactly the new modifier, on the right element, in one glance.

---

### Example 2 — KMP setup

**Article:** "Using Jetpack Room in Kotlin Multiplatform shared code"

**Label:** `KMP ROOM DAO`

**Code:**
```
<span class="com">// commonMain</span>
<span class="kw">@Dao</span>
<span class="kw">interface</span> <span class="fn">PersonDao</span> {
  <span class="kw">@Query</span>(<span class="str">"SELECT * FROM person"</span>)
  <span class="kw">fun</span> <span class="fn">getAll</span>(): Flow<List<Person>>
}
```

Why: the DAO in commonMain is the surprising thing — that's what makes the reader click.

---

### Example 3 — Before / after

**Article:** "Replacing LiveData with StateFlow in existing ViewModels"

**Label:** `BEFORE → AFTER`

**Code:**
```
<span class="com">// before</span>
<span class="kw">val</span> items: LiveData<List<Item>> = liveData { … }

<span class="com">// after</span>
<span class="kw">val</span> items: StateFlow<List<Item>> = flow { … }
  .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())
```

Why: the migration intent is immediately clear; reader knows what they're getting.

---

### Example 4 — DSL shape

**Article:** "Ktor 3 routing DSL changes"

**Label:** `NEW ROUTING DSL`

**Code:**
```
routing {
  <span class="fn">get</span>(<span class="str">"/users/{id}"</span>) {
    <span class="kw">val</span> id = call.pathParameters[<span class="str">"id"</span>]
    call.respond(userRepository.<span class="fn">find</span>(id))
  }
}
```

---

### Example 5 — Changelog with breaking change

**Article:** "KSP 2.3.10 — `KSPLogger.warn()` parameter renamed"

**Label:** `API CHANGE`

**Code:**
```
<span class="com">// was: message, symbol</span>
logger.<span class="fn">warn</span>(message = <span class="str">"deprecated"</span>, symbol = element)

<span class="com">// now: message, node</span>
logger.<span class="fn">warn</span>(message = <span class="str">"deprecated"</span>, node = element)
```

---

## Anti-Patterns

```
// ✗ Too much setup, point gets lost
val context = LocalContext.current
val scope = rememberCoroutineScope()
val scaffoldState = rememberScaffoldState()
val snackbarHostState = remember { SnackbarHostState() }
LaunchedEffect(key) {
    snackbarHostState.showSnackbar("Hello")
}
Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }) { ... }
```

```
// ✓ Show the key API call, cut the rest
LaunchedEffect(key) {
    snackbarHostState.<span class="fn">showSnackbar</span>(<span class="str">"Hello"</span>)
}
```

---

## Output Format

When a snippet applies, return these two fields alongside `id`, `summary`, and `topics`:

```json
{
  "id": "...",
  "summary": "...",
  "topics": ["compose", "animation"],
  "code_snippet": "LazyColumn {\n  items(list, key = { it.id }) { item ->\n    ItemCard(modifier = Modifier.animateItem())\n  }\n}",
  "snippet_label": "ANIMATE ITEM"
}
```

When no snippet applies, omit both fields entirely — do not include `"code_snippet": null`.
