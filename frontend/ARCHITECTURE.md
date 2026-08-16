# UI internals

A code-level walkthrough of the frontend: `app/`, `components/` and `lib/` — how the design
system is encoded, how the components are wired together, and where the state actually lives.

[`README.md`](README.md) is the orientation document — how to run it, what the folders are, the
three things to know before touching anything. This one assumes you have read it and are about to
change something. `../specifications/specs_mvp.md` §9–13 remains the source of truth for *what*
the UI should do; this document explains *how* the implementation gets there, and which choices
resolve ambiguities in the spec.

---

## Contents

1. [The problem the architecture solves](#1-the-problem-the-architecture-solves)
2. [Layering and dependency direction](#2-layering-and-dependency-direction)
3. [`app/globals.css` — the design system as constraint](#3-appglobalscss--the-design-system-as-constraint)
4. [`lib/useAnalysisState.ts` — the state machine](#4-libuseanalysisstatets--the-state-machine)
5. [Derived state, and why none of it is stored](#5-derived-state-and-why-none-of-it-is-stored)
6. [Running an analysis: the request and its guards](#6-running-an-analysis-the-request-and-its-guards)
7. [`lib/history.ts` — `localStorage` as an external store](#7-libhistoryts--localstorage-as-an-external-store)
8. [`lib/api.ts` — the API boundary](#8-libapits--the-api-boundary)
9. [Component architecture — the single-prop controller](#9-component-architecture--the-single-prop-controller)
10. [One tree, two layouts](#10-one-tree-two-layouts)
11. [`TierSelector` — the picker builds itself](#11-tierselector--the-picker-builds-itself)
12. [`MetricRow` — rendering by shape, not by name](#12-metricrow--rendering-by-shape-not-by-name)
13. [State that deliberately stays local](#13-state-that-deliberately-stays-local)
14. [Data flow: three traces](#14-data-flow-three-traces)
15. [The invariants, and what breaks if you violate them](#15-the-invariants-and-what-breaks-if-you-violate-them)
16. [Adding to the UI: the common paths](#16-adding-to-the-ui-the-common-paths)

---

## 1. The problem the architecture solves

Three panes have to agree, permanently, about five things: the mode, the two texts, the feature
selection, the current results, and which history entry is being viewed. The spec (§11) names the
drift between them as the risk to design against — a History pane showing one analysis while the
Results pane shows another is the failure mode.

The conventional fix at this size is a store library, or React context, or lifting three or four
individual values and threading them through props. This app does none of those. Instead:

- **One hook owns everything shared.** `useAnalysisState()` returns a single `AnalysisController`
  object. There is no second source for any of those five values.
- **The panes receive that object whole,** as one prop named `controller`. A pane that needs the
  mode reads `controller.mode`; it cannot hold a copy, because there is nothing to copy from
  except the thing everyone else is also reading.
- **Only one pane writes.** `AnalysisFormPane` is the only component that calls a mutator that
  changes mode, text or selection. History calls navigation and deletion; Results calls retry and
  toast. That write-discipline, not the physical location of the state, is what §11 is protecting.

The second problem is narrower but shapes almost as much code: **the backend's feature set is not
known at build time.** Feature names, tiers and the per-text/comparison split all arrive from
`GET /api/v1/features` at runtime. So no component may contain a feature name, and no component
may know a feature's response shape. §11 and §12 turn those into two specific mechanisms — the
catalog-driven picker and shape-based result rendering — which are the subjects of §11 and §12
below.

---

## 2. Layering and dependency direction

```
  app/layout.tsx                 server component: fonts + globals.css, nothing else
        │
  app/page.tsx                   "use client" — calls the hook, owns tab state
        │   const controller = useAnalysisState()
        │
        ├──────────────┬─────────────────────┬──────────────┐
        ▼              ▼                     ▼              ▼
  HistoryPane    AnalysisFormPane       ResultsPane       Toast
   (reads)        (reads + WRITES)        (reads)
        │              │                     │
        └──────────────┴─────────────────────┴──▶ lib/format.ts   (pure, no state)
                       │
                       ▼
              lib/useAnalysisState.ts        the only stateful module
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   lib/api.ts                   lib/history.ts
   (fetch wrapper)              (localStorage + external store)
        │                             │
        └─────────────┬───────────────┘
                      ▼
                 lib/types.ts          mirrors backend schemas; imports nothing
```

Three rules give the layering its teeth:

1. **No component imports `api.ts` or `history.ts`.** Every network call and every storage write
   goes through the hook. A component that fetched directly would be creating state the panes
   cannot see.
2. **`lib/format.ts` and `lib/types.ts` are pure and import nothing from the app.** They are safe
   to use anywhere and impossible to make stateful.
3. **`layout.tsx` is the only server component.** Everything below `page.tsx` is client-side,
   because the whole app is one interactive surface over a browser-local store. There is no data
   to fetch on the server: history lives in `localStorage`, and analysis is user-triggered.

---

## 3. `app/globals.css` — the design system as constraint

### Two layers of tokens, for two consumers

`globals.css:11-21` declares the nine colours from spec §12.2 under **the spec's own names**:

```css
:root {
  --bg: #fafaf9;        --surface: #ffffff;    --border: #e4e1dc;
  --ink: #1c1b1a;       --ink-muted: #6b6862;
  --accent: #3a5a73;    --accent-soft: #e8eef2;
  --positive: #3f7857;  --negative: #a14c43;
}
```

`@theme inline` (`globals.css:23-47`) then re-exports each as `--color-*`, which is what makes
Tailwind v4 generate `bg-surface`, `text-ink-muted`, `border-border`, `text-negative` as real
utility classes. There is no `tailwind.config.js`; in Tailwind v4 this file *is* the config.

The two layers exist because they have different readers. Raw `var(--border)` is what the spec's
prose uses — "panes divided by `1px solid var(--border)`" is literally the code. `--color-*` is
what components use, which is why **no hex appears in any component**.

### Three constraints enforced structurally rather than by discipline

This is the part most worth understanding before editing:

```css
--radius-xs: 4px;  --radius-sm: 4px;  --radius-md: 4px;  --radius-lg: 4px;
--default-transition-duration: 140ms;
--default-transition-timing-function: cubic-bezier(0, 0, 0.2, 1);
```

- **All four radius steps are 4px.** `rounded`, `rounded-md` and `rounded-lg` are the same value,
  so a component cannot introduce a second radius even by picking the wrong utility. §12.4 asks
  for 4px everywhere; this makes "everywhere" unfalsifiable rather than a review checklist item.
- **Bare `transition-colors` already lands in §12.4's 120–150ms ease-out band.** The correct
  duration is the *default*, so getting it right requires no knowledge.
- **Focus rings are one global rule** (`globals.css:58-61`), not a class each element opts into.
  §12.5 calls visible 2px `--accent` focus outlines non-negotiable; a per-component approach makes
  that a thing 19 components must each remember.

The single component that needs an exception is `FeatureCheckbox`, where the real `<input>` is
`opacity-0` and the visible box is a sibling `<span>`. The ring is forwarded explicitly with
`peer-focus-visible:outline-accent` (`FeatureCheckbox.tsx:41`). That is the only place in the app
where focus styling is written by hand, and it is written by hand precisely *because* the element
that receives focus is not the element that is seen.

### Typography — the one deliberate signature

`layout.tsx:7-18` loads Inter and IBM Plex Mono through `next/font/google` as CSS variables,
wired into `--font-sans` / `--font-mono` in the `@theme` block and applied at `layout.tsx:33`.

Spec §12.1 asks for one signature and one only: **every numeric value renders in monospace against
a sans UI face.** It appears in exactly four places:

| Where | Code |
|---|---|
| Metric values | `MetricRow.tsx:22` |
| Char / word counters | `TextInput.tsx:67` |
| Tier badges and selection counts | `HistoryListItem.tsx:12`, `TierSelector.tsx:123` |
| `elapsed_ms` footer | `ResultsPane.tsx:103` |

Labels are always sans and `text-ink-muted`; values are always mono and `text-ink`. That contrast
*is* the visual identity — there is nothing else decorative in the app. Elevation is near-absent
by the same logic: flat surfaces, hairline borders, and `shadow-md` appears exactly once, on
`Toast.tsx:30`.

---

## 4. `lib/useAnalysisState.ts` — the state machine

Spec §10 defines five states (`useAnalysisState.ts:49`):

```
                     ┌──────────── any edit (mode/text/feature) ────────────┐
                     ▼                                                      │
  idle ──────▶ editing ──── Analyze ────▶ analyzing ──┬── ok ──▶ editing ───┘
    ▲            ▲                                    │          + history entry saved
    │            │                                    └── err ─▶ error
    │            │                                                   │
    │            │                                              Retry / edit
    │            └──── "Duplicate as new" ◀────┐                     │
    │                                          │                     ▼
    └──── "New analysis" ◀───────────── viewing_history ◀──── click a history item
                                        (fully read-only)
```

Two encoding decisions are worth internalising because they explain shapes elsewhere.

**Success returns to `editing`, not to a distinct "done" state** (`useAnalysisState.ts:281`).
Whether results exist is answered by `response !== null`, never by the state value. So the enum
tracks only *what the user is allowed to do*, and results presence is orthogonal data. That is why
`ResultsPane` branches on `analyzing`, then `error`, then falls through to
`!response ? empty : results` (`ResultsPane.tsx:51-65`) — three states plus a data check, rather
than five states.

**Read-only is derived, not stored:**

```ts
const readOnly = state === "analyzing" || state === "viewing_history";
```

Two states disable the same controls for different reasons (§10 requires `viewing_history` to be
fully read-only: mode toggle, both textboxes and Analyze). One expression drives every `disabled`
prop in the form, so the two reasons cannot diverge.

Note that `AnalysisFormPane` passes `disabled={state === "analyzing"}` but
`readOnly={viewingHistory}` to `TextInput` (`AnalysisFormPane.tsx:82-83`). The distinction is
deliberate: a disabled textarea is not selectable, and a user viewing a saved analysis should be
able to select and copy the text they analysed.

---

## 5. Derived state, and why none of it is stored

Four values that could plausibly have been state are computed on every render instead
(`useAnalysisState.ts:154-200`):

| Value | Derivation | What storing it would break |
|---|---|---|
| `visibleFeatures` | catalog filtered by mode | Mode toggle would need to rebuild it in two places |
| `effectiveSelection` | `selectedFeatures ∩ visibleFeatures` | See below — the important one |
| `requiredTextCount` | `mode === "single" ? 1 : 2` | Trivially derivable; a second source could disagree |
| `validation` | selection + text length + `readOnly` | Button enablement could drift from the reason shown |

**`effectiveSelection` is the one that earns its keep.** When you switch compare → single, the
comparison-scope features you had ticked are *not deleted* from `selectedFeatures` — they merely
stop appearing in `visibleFeatures`, so they drop out of the intersection. Switch back and they
return, exactly as they were. The obvious alternative (pruning the array on mode change) silently
destroys user input on a toggle that reads as navigational.

The same principle governs the texts: `texts` is a `[string, string]` tuple that keeps Text B even
in single mode (`useAnalysisState.ts:60`), so toggling modes twice is lossless. The one case where
data genuinely is at risk — Text B is non-empty and the user switches to single mode, where it
stops being sent — is the case §13.2 asks to confirm, handled at `useAnalysisState.ts:211-219`.

**`validation` returns a reason string, not a boolean** (`useAnalysisState.ts:51-55`). That single
value does two jobs: it is the `title` on the disabled Analyze button, and it is the status line
beside it (`AnalysisFormPane.tsx:106`, `AnalyzeButton.tsx:27`). A disabled button always explains
itself, and the explanation cannot fall out of sync with the disablement because they are the same
object.

### The catalog effect

`useAnalysisState.ts:127-152` is the only network effect in the app. Three details:

- **`catalogAttempt` is a retry key, not a counter anyone reads.** `reloadCatalog`
  (`useAnalysisState.ts:389-393`) resets `catalogLoading` / `catalogError` *and* bumps the key, so
  the effect re-runs. Resetting them inside the effect body would be a synchronous `setState`
  during an effect, which React 19's `set-state-in-effect` rule bans and which causes a cascading
  render. `catalogLoading` is therefore initialised to `true` rather than being set on mount.
- **An `AbortController` cleans up in-flight requests,** and both `.catch` and `.finally` check
  `signal.aborted` before touching state.
- **Tier 1 is selected by default** on first successful load (`useAnalysisState.ts:135-139`), but
  only if nothing is selected yet — so a catalog reload never clobbers a selection the user made.

---

## 6. Running an analysis: the request and its guards

```ts
const payload: AnalyzeRequest = {
  mode,
  texts: texts.slice(0, requiredTextCount),
  tiers: tiersOf(effectiveSelection, catalog),
  feature_names: effectiveSelection,
};
```

**`feature_names` is always sent, and `tiers` is derived from it** by looking each name up in the
catalog (`useAnalysisState.ts:96-104`). This leans directly on the backend's "`feature_names` is
an override, not a filter within `tiers`" semantics: ticking 2 of 5 Tier 1 features sends exactly
those 2, and a half-selected tier never silently expands to the whole tier. The picker's selection
*is* the request.

`texts` is sliced to `requiredTextCount`, so single mode sends one element even though the tuple
always has two — matching the backend's `len(texts) == 1 | 2` validation.

### The stale-response guard

`requestId` (`useAnalysisState.ts:125`) is a monotonic ref. `runAnalysis` captures
`const id = ++requestId.current`, and both `.then` and `.catch` return early if
`id !== requestId.current`.

The subtlety is that **it is also incremented by `newAnalysis`, `viewHistoryEntry` and
`duplicateHistoryEntry`** (`useAnalysisState.ts:316`, `:328`, `:344`). So it is not only a
last-write-wins guard between two analyses; it prevents an in-flight response from landing on top
of a history entry the user navigated to while it was running. It is a cancellation token for
*state application*, deliberately separate from aborting the fetch itself.

### A storage failure is not an analysis failure

`useAnalysisState.ts:280-294` commits the response to state **first**, then writes history inside
its own `try/catch` that only raises a toast:

```ts
setResponse(result);
setState("editing");
try {
  const entry = createEntry(payload, result);
  saveEntry(entry);
  setSelectedHistoryId(entry.id);
} catch (cause) {
  showToast(/* quota message, or a generic one */);
}
```

An analysis that succeeded but could not be saved shows its results and a warning. It never
presents as an error, because it was not one — the ordering is what guarantees that.

---

## 7. `lib/history.ts` — `localStorage` as an external store

This is the least conventional module in the app, and the reasoning matters more than the code.

`localStorage` genuinely *is* state outside React. The usual approach — mirror it into `useState`
via a mount effect — is wrong three separate ways:

1. It is a synchronous `setState` in an effect body, which React 19's `set-state-in-effect` rule
   bans.
2. The server render and the hydrating client render disagree (server has no storage), which is a
   hydration mismatch.
3. It cannot see a write from another browser tab.

So the module implements the `useSyncExternalStore` contract instead — `subscribe` /
`getSnapshot` / `getServerSnapshot` (`history.ts:85-106`), consumed at `useAnalysisState.ts:122`.
`getServerSnapshot` returns the same shared `EMPTY` array the client sees before subscription, so
both renders agree; `subscribe` attaches a `window "storage"` listener on the first subscriber
(`history.ts:86-88`) and removes it on the last, so a second tab stays in sync for free.

**The cache at `history.ts:73` is a requirement, not an optimisation.** `useSyncExternalStore`
compares snapshots by reference; re-parsing JSON on every call returns a fresh array each time and
loops forever. The cache is invalidated on write and on storage event, and nowhere else.

### Quota is an expected path, not an exception

A single Tier 3 compare response is large enough that a full history can exceed the ~5MB budget.
`persist` (`history.ts:127-144`) therefore retries in a loop, shedding the oldest entry each time:

```ts
let candidates = entries.slice(0, MAX_ENTRIES);
while (candidates.length > 0) {
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(candidates));
    return candidates;
  } catch (error) {
    if (!isQuotaError(error)) throw error;
    candidates = candidates.slice(0, candidates.length - 1);
  }
}
throw new HistoryQuotaError();
```

`HistoryQuotaError` is only reached when even a single entry will not fit, in which case whatever
was already stored is left untouched. `commit` (`history.ts:165-172`) wraps this in `try/finally`
so subscribers are notified even when the write throws — the in-memory list and the pane stay
consistent with what actually happened.

### Every read is defensive

`isEntry` (`history.ts:34`) validates each parsed element before it is trusted. The store is
user-writable, survives across deploys, and is versioned only by the key name
(`textropy.history.v1`), so malformed or stale JSON must degrade to "no history" rather than crash
the pane. `storage()` (`history.ts:23`) additionally guards SSR and browsers where merely
*accessing* `localStorage` throws (private mode, blocked third-party storage).

---

## 8. `lib/api.ts` — the API boundary

Roughly 100 lines around two endpoints. Three things worth keeping:

**`API_BASE_URL` is read from `process.env.NEXT_PUBLIC_API_BASE_URL` at module scope**
(`api.ts:20-22`), with the trailing slash stripped. Because `NEXT_PUBLIC_*` values are inlined by
`next build`, this is a build-time constant in production — see the README's Docker section for
the consequence.

**`readErrorDetail` (`api.ts:37`) unwraps FastAPI's `detail`,** including the array-of-`{msg}`
shape a 422 returns, joined with `; `. Without it, a validation error would surface as
`[object Object]`. A non-JSON body (a proxy error page) falls through to `statusText`.

**A thrown `fetch` becomes a message naming the base URL** (`api.ts:68-74`):

> `Could not reach the Textropy API at http://localhost:8000. Is the backend running?`

The browser's native message is `Failed to fetch`, which distinguishes neither "backend is down"
nor "CORS rejected this origin" — the two overwhelmingly likely causes in development, and the two
that the backend's `TEXTROPY_CORS_ORIGINS` / `NEXT_PUBLIC_API_BASE_URL` pairing exists to prevent.

---

## 9. Component architecture — the single-prop controller

Every pane has the same signature:

```ts
export default function HistoryPane({ controller }: { controller: AnalysisController })
```

No pane takes individual value props. The consequences are worth spelling out:

- **A pane cannot be handed stale data,** because it is handed the live object, not a snapshot of
  selected fields.
- **Adding a shared value costs one line** in the `AnalysisController` interface plus its return
  object. No prop threading through intermediate components.
- **The write-discipline is visible in imports.** Grep for `controller.setMode` or
  `controller.setText` and you find `AnalysisFormPane` and nothing else.

The trade-off, stated plainly: the controller object is **recreated on every render and is not
memoised**, so any state change re-renders all three panes. At this scale — three panes, a few
dozen rows — that is imperceptible, and the alternative (memoising ~20 fields and every callback)
would add machinery that obscures the design. If the results pane ever renders thousands of rows,
this is the first thing to revisit, and the fix is `useMemo` on the returned object plus
`React.memo` on the panes, not a different architecture.

### The composite-row problem

`HistoryListItem` needs a full-row click target *plus* two action buttons. Nested `<button>` is
invalid HTML, so the row button fills the `<li>` with `pr-16` of reserved padding, and the actions
sit in an absolutely-positioned overlay (`HistoryListItem.tsx:64`):

```
group-hover:opacity-100 group-focus-within:opacity-100
```

`focus-within` is load-bearing, not decoration: hover alone would make the Duplicate and Delete
actions invisible — and effectively unreachable — for anyone navigating by keyboard.

---

## 10. One tree, two layouts

Spec §9 requires three panes at ≥1024px and a single column behind **History / Analyze / Results**
tabs below it, and explicitly flags cutting the responsive fallback as a known risk. It is
therefore built from the same component tree rather than a second one (`page.tsx:37`):

```ts
const paneVisibility = (id: Tab) => (tab === id ? "flex" : "hidden lg:flex");
```

Below `lg`, the tab bar renders and only the active pane is displayed. At `lg` and above, the tab
bar is `lg:hidden` and all three panes are unconditionally `flex`. Sizing (`lg:w-[280px]`,
`lg:w-2/5`, `flex-1`) and the hairline `lg:border-r` dividers live on the same three `<section>`
elements that serve the mobile layout.

There is no mobile component tree to keep in sync, which is the entire point: the failure mode for
a responsive fallback built as a parallel tree is that it silently rots as the desktop layout
evolves.

`min-h-0` appears on every flex container in the chain (`page.tsx:66`, `:72`, `:83`, `:94`, and in
each pane's root). It is required, not incidental — a flex child defaults to `min-height: auto`,
which refuses to shrink below its content, so without it the inner `overflow-y-auto` never
activates and the whole page scrolls instead of the pane.

---

## 11. `TierSelector` — the picker builds itself

`TierSelector` receives `FeatureCatalogEntry[]` and derives every visible thing from it:

| Rendered thing | Derived from |
|---|---|
| Which tiers appear | `TIERS.map` filtered to tiers with ≥1 catalog entry (`TierSelector.tsx:75-77`) |
| Which features are in a tier | `entry.tier` |
| "Per text" vs "Comparison" groups | `entry.scope`, in compare mode only (`TierSelector.tsx:144-169`) |
| Feature labels | `humanizeFeatureName(entry.name)` (`format.ts:24`) |
| The `↔` asymmetry marker | `entry.symmetric === false` (`FeatureCheckbox.tsx:50`) |
| `3/5` selection counts | Set arithmetic over the catalog slice |

**No feature name appears in any component.** (The only occurrences in the whole app are a
doc-comment example in `types.ts:56` and the cosmetic acronym map below.) Add a computer to the
backend registry and
it shows up here with a sensible label, in the right tier, on the correct side of the
per-text/comparison split, with no frontend change. `humanizeFeatureName`'s `ACRONYMS` map
(`format.ts:10-21`) is the only place feature-name-shaped strings legitimately appear, and it is
purely cosmetic — an unknown name still renders acceptably, just without special casing.

The one tier-specific constant is `SLOW_TIER = 3` (`TierSelector.tsx:19`), which drives the
"may take several seconds" note §13.2 requires. That is a property of the *deployment* — Tier 3
runs synchronously because the MVP has no job queue — not of any feature, which is why it lives
here rather than coming from the catalog.

### Two implementation details

**The tier checkbox is tri-state** via a ref callback (`TierSelector.tsx:92-94`):

```tsx
ref={(node) => { if (node) node.indeterminate = selectedCount > 0 && !allSelected; }}
```

`indeterminate` has no HTML attribute and can only be set on the DOM node. This is a ref *write
during commit*, which React 19 permits; reading a ref during render is what is banned.

**Expand/collapse animates via grid rows** (`TierSelector.tsx:136-141`, and identically in
`TierResultSection.tsx:43-48`):

```tsx
"grid transition-[grid-template-rows] duration-150 ease-out",
isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
```

with an `overflow-hidden` child. This is the standard way to animate to *content height* without
measuring it in JavaScript — `height: auto` is not animatable, and a hardcoded max-height either
clips long content or makes short content ease slowly.

---

## 12. `MetricRow` — rendering by shape, not by name

`MetricRow` is the load-bearing component of the results pane. Backend feature values are open
JSON (`types.ts:48-54`), so it branches on **runtime shape**, never on the feature name
(`MetricRow.tsx:47-85`):

| Shape | Test | Render |
|---|---|---|
| `{available: false, reason?}` | `isUnavailable` (`types.ts:92`) | "Unavailable" row, `reason` in the `title` |
| any other object | `isValueGroup` (`types.ts:101`) | Label + **recursive** nested rows |
| scalar | fallthrough | Label (sans, muted) + value (mono) |

This is why `{label: "positive", score: 0.99}` and `{a_given_b: 24.7, b_given_a: 31.2}` both
display correctly with zero per-feature code — they are objects, and the component recurses.

Value-derived styling follows the same rule. `polarityOf` (`format.ts:60`) colours a value green
or red if the *value string* reads `positive` / `negative` (`MetricRow.tsx:17`), so any future
polarity-bearing feature is coloured for free, and a feature *named* something sentiment-like but
returning a number is not miscoloured.

The unavailable branch is the frontend half of the backend's optional-model degradation path
(§13.4): one feature renders an "Unavailable" row while every other feature in the tier renders
normally. Request-level failure is a different thing entirely and surfaces as the `error` state.

Two smaller details in the same pane:

- **Tier ordering is numeric, not lexical** (`ResultsPane.tsx:18-24`). `Object.entries` gives
  insertion order and string sorting would place `tier10` before `tier9`; the keys are parsed to
  numbers and sorted.
- **`ComparisonDiffView` is illustrative only.** It re-derives its own LCS word alignment client-side
  (`ComparisonDiffView.tsx:28`) so a reader can *see* what the Tier 1 comparison metrics measure.
  The `lcs_length` metric displayed alongside it comes from the API like every other value. The
  table is O(n·m), hence `MAX_WORDS = 1200` per side (`ComparisonDiffView.tsx:19`) and the
  computation being gated on the section actually being open (`ComparisonDiffView.tsx:86`).

**Known wart:** `MetricRow`'s `depth` prop is never passed a non-zero value — neither
`TierResultSection.tsx:52` nor the recursive call at `MetricRow.tsx:71` supplies it — so
`paddingLeft: depth * 16` is always `0`. Nesting is actually conveyed by the `border-l pl-3`
wrapper at `MetricRow.tsx:68`. The prop is vestigial; either thread it through or delete it, but
do not assume it is currently doing anything.

---

## 13. State that deliberately stays local

Five pieces of state are intentionally *not* in the controller:

| State | Owner | Why local |
|---|---|---|
| Which tiers are expanded | `TierSelector.tsx:71` | Presentation of one component |
| Whether a results section is open | `TierResultSection.tsx:21` | Same |
| Whether the diff is shown | `ComparisonDiffView.tsx:79` | Same, and it gates an expensive computation |
| Copy-confirmation flash | `CopyResultsButton.tsx:17` | Transient, 2s, nobody else cares |
| Active tab | `page.tsx:34` | Layout, not analysis state |

The line is: **if two panes must agree on it, it belongs in the controller; if it is one
component's presentation, it stays local.** Hoisting these would grow the controller's surface
without buying anything, and would make `AnalysisController` a grab-bag rather than a description
of the analysis.

`Toast` is the borderline case that went the other way — the message lives in the controller
(`useAnalysisState.ts:118`) because three different subsystems raise toasts (history quota, delete
failure, clipboard failure) and the toast is rendered once at the root (`page.tsx:101`).

---

## 14. Data flow: three traces

### An analysis, from click to rendered result

```
AnalyzeButton onClick  (or Cmd/Ctrl+Enter in TextInput.tsx:46-51)
  │
  └─ controller.runAnalysis()
       ├─ validation.canAnalyze guard — no-ops if invalid
       ├─ payload = {mode, texts.slice(0, n), tiers: tiersOf(effectiveSelection), feature_names}
       ├─ id = ++requestId.current
       ├─ setState("analyzing"); clear error/response/selectedHistoryId
       │     └─▶ ResultsPane renders <ResultsSkeleton slow={tier3Selected} />
       │         AnalysisFormPane disables everything via readOnly
       │
       └─ api.analyze(payload)
            │
            ├─ ok ──▶ id still current?
            │          ├─ setResponse(result); setState("editing")
            │          │     └─▶ ResultsPane renders TierResultSection → MetricRow…
            │          └─ try: createEntry → saveEntry → commit → persist → emit()
            │                   └─▶ useSyncExternalStore fires
            │                         └─▶ HistoryPane re-renders with the new entry
            │                catch: showToast(...)   ← analysis still succeeded
            │
            └─ err ─▶ id still current?
                       └─ setError(msg); setState("error")
                             └─▶ ResultsPane renders <ErrorBanner onRetry={runAnalysis} />
                                 inputs are untouched, so retry needs no re-entry (§13.4)
```

### Viewing a history entry

```
HistoryListItem onClick
  └─ controller.viewHistoryEntry(id)
       ├─ requestId.current += 1        ← any in-flight analysis can no longer land
       ├─ setState("viewing_history")   ← readOnly becomes true everywhere at once
       ├─ restore mode, texts, featureNames from the entry
       ├─ setResponse(entry.response)   ← no API call: the entry holds the full response
       └─ setSelectedHistoryId(entry.id)
             └─▶ HistoryPane highlights the row via aria-current + bg-accent-soft
                 AnalysisFormPane shows the "Viewing saved analysis" badge and disables input
                 ResultsPane renders the stored response exactly as if it were fresh
```

The entry stores the full request *and* response (`types.ts:81-90`), which is what makes replay
free and offline. "Duplicate as new" (`useAnalysisState.ts:340-356`) restores the same inputs but
sets `editing`, clears `response` and `selectedHistoryId` — forking into a fresh editable state
rather than mutating the stored entry, per §10.

### Catalog load, on mount

```
useAnalysisState mount
  └─ effect [catalogAttempt] → fetchFeatureCatalog(signal)
       ├─ ok  ──▶ setCatalog(entries)
       │           └─ select all tier-1 features IF nothing is selected yet
       │                 └─▶ TierSelector renders itself from the catalog
       └─ err ─▶ setCatalogError(msg)
                   └─▶ AnalysisFormPane renders <ErrorBanner onRetry={reloadCatalog} />
                         └─ reloadCatalog resets loading/error and bumps catalogAttempt
                               └─ effect re-runs
```

---

## 15. The invariants, and what breaks if you violate them

| Invariant | Enforced by | Failure if violated |
|---|---|---|
| Panes never copy controller values into local state | Single-prop wiring; nothing else to copy from | The three-pane drift §11 exists to prevent |
| Only `AnalysisFormPane` mutates mode/text/selection | Convention, visible by grepping `controller.set*` | Two writers race; the form shows one thing and the request sends another |
| No feature name appears in a component | Catalog-driven picker + shape-based rendering | A backend feature silently fails to appear, or renders wrongly |
| `getSnapshot` returns a referentially stable value | The `cache` at `history.ts:73` | Infinite render loop |
| No `setState` synchronously in an effect body | `catalogAttempt` retry key pattern | React 19 lint error; cascading renders |
| No ref reads during render | `setMode` depends on `textB` instead of a ref | React 19 lint error; stale closure bugs |
| Colours and radii come from tokens | `@theme inline` + a flat radius scale | Design drift that no test catches |
| A per-feature `available: false` degrades one row | `isUnavailable` branch in `MetricRow` | One optional model takes down the whole results pane |

The first two are the ones to guard hardest, because they are the only ones nothing mechanical
checks. The lint rules catch the React 19 violations, the type system catches most shape
violations, and the token system makes design drift require active effort — but a pane that
mirrors `controller.mode` into its own `useState` will compile, lint, and look correct right up
until the two disagree.

---

## 16. Adding to the UI: the common paths

**A new backend feature** — nothing to do. It arrives in the catalog, the picker renders it in its
tier and scope, and `MetricRow` renders whatever shape it returns. Add an entry to `ACRONYMS`
(`format.ts:10`) only if its name contains an initialism that title-casing would mangle.

**A new shared value** (something two panes must agree on) — add it to the `AnalysisController`
interface (`useAnalysisState.ts:57`), produce it in the hook, return it. Derive it rather than
storing it if it is a function of existing state; see §5 for why.

**A new pane-local UI affordance** — keep the state in the component. See §13 for the line.

**A new colour or spacing value** — add a token in `globals.css:11-21` and alias it in the
`@theme inline` block. Never a literal in a component.

**A new response shape from the backend** — check whether `MetricRow`'s three branches already
cover it. Scalars and nested objects are handled; arrays currently are not (they would hit
`isValueGroup` and render numeric keys as labels). If a feature starts returning a list, that is a
fourth branch in `MetricRow`, not a special case in `ResultsPane`.

**A modal** — one is genuinely needed. Both confirmations (`useAnalysisState.ts:216` for the
compare → single switch, `ClearHistoryButton.tsx:18` for Clear all) use `window.confirm` because
§11 defines no modal component. §12.4 already reserves `shadow-md` for modals and toasts, so the
design tokens are waiting; replacing both call sites is the follow-up.
