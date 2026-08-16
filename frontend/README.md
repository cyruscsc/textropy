# Textropy — frontend

Next.js (App Router) UI for the Textropy analysis API, implementing §9–13 of
`../specifications/specs_mvp.md`. Read those sections before changing layout, state or
design tokens — the spec is the source of truth, not this README.

This README is the orientation document. For a code-level walkthrough of the UI — how the
design tokens are encoded, how the three panes are wired to one state machine, how the
results pane renders unknown feature shapes, and the invariants that hold it together —
see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Commands

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build (also typechecks)
npm run start      # serve the production build
npm run lint       # eslint (flat config, next/core-web-vitals)
npx tsc --noEmit   # typecheck only
```

The API must be running for anything to work: from `../backend`, `uv run fastapi dev
app/main.py`. The UI targets `http://localhost:8000` by default; override with
`NEXT_PUBLIC_API_BASE_URL` and add the matching origin to the backend's
`TEXTROPY_CORS_ORIGINS` (its default allowlist is `http://localhost:3000` only).

## Docker

```bash
docker build -t textropy-frontend .
docker run --rm -p 3000:3000 textropy-frontend
```

The image is a three-stage build (deps → build → runtime) producing a standalone Next
server on `node:24-alpine`, running as uid 10001 with no dev dependencies and no npm
install at runtime.

**The API URL is baked in at build time.** `NEXT_PUBLIC_API_BASE_URL` is inlined into the
client bundle by `next build`, so `docker run -e NEXT_PUBLIC_API_BASE_URL=…` does nothing.
Point an image at a different API by rebuilding:

```bash
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com -t textropy-frontend .
```

Whatever URL you use must also be in the backend's `TEXTROPY_CORS_ORIGINS`.

## Shape

```
app/          layout.tsx (fonts) · page.tsx (composes the 3 panes, owns the tab state)
              globals.css (design tokens — every colour lives here, §12.2)
components/   history/ · analysis-form/ · results/ · shared/
lib/          api.ts · history.ts · types.ts · useAnalysisState.ts · format.ts
ARCHITECTURE.md   code-level walkthrough of all three
```

Three things worth knowing before editing:

- **The feature picker is built from `GET /api/v1/features`.** Feature names, tiers and
  the per-text/comparison split all come from the backend catalog. Never hardcode a
  feature list; a feature added to the backend registry should appear here for free.
- **`useAnalysisState` is the entire state layer.** It holds the one state-machine value
  (§10); `HistoryPane` and `ResultsPane` render from it rather than keeping their own
  copies of the mode, texts or results.
- **Results render by value shape, not by feature name.** `MetricRow` turns a scalar into
  a row and an object into a nested group, so `{label, score}` and `{a_given_b, b_given_a}`
  both display without special-casing. A feature reporting `{"available": false}` degrades
  to an "Unavailable" row instead of failing the pane (§13.4).

[`ARCHITECTURE.md`](ARCHITECTURE.md) covers all three in detail, along with the design-token
system and the invariants a new component has to respect.

## Not yet built

- `feature_names` round-trips through history, but editing a loaded entry is out of scope
  for the first pass (§10 note) — "Duplicate as new" is the supported path.
- The compare → single mode-switch confirmation uses `window.confirm`; §11 defines no
  modal component yet.
