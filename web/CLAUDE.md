# Web app

Static flashcard site for the trivia data scraped under `../scrape/`. No backend. Deployed to GitHub Pages under `/pub-quiz-flashcards/`.

## Principles

- **Static, no backend.** All state lives in the user's browser. The app is just HTML/JS/CSS served from Pages.
- **Build-time over runtime.** Anything that can be precomputed (card merging, stable IDs, eventually NER entity linking) happens in the build, not in the browser.
- **Cards are immutable once published.** A card's `id` is `sha1(source_url + question)[:12]` — stable across re-scrapes so user progress survives. If a question's text changes, that's effectively a new card and the old state is orphaned (rare, acceptable).
- **State schema is versioned.** localStorage key `quiz:state:vN`. Mismatched versions reset to empty rather than migrating — the app hasn't shipped, so cost of resets is low. Bump the version when the shape changes incompatibly.
- **Spaced repetition via FSRS.** Two buttons map to `Again` / `Good`. We deliberately throw away the `Hard`/`Easy` signal for UI simplicity.
- **The session queue is persistent.** `appState.daily.queue` holds the upcoming card IDs. We replan only when the queue empties AND the user has remaining daily capacity. This is what makes refresh stable.
- **Daily reset on local midnight.** `ensureToday` wipes the daily counters and the queue. Yesterday's unfinished cards are abandoned, not carried over.
- **The 10/day limit is soft.** "Keep going (+10)" bumps `daily.extras` and replans. No hard ceiling.
- **`revealed` is ephemeral.** It's not persisted. A refresh re-hides the answer; the user clicks "Show answer" again. Persisting it would be weird across long page-open gaps.

## Data flow

```
scrape/*/questions.json
  → build-data.ts  (merge, dedup by id, sort)
  → static/cards.[hash].json + cards-manifest.json
  → fetched by lib/cards.ts on every page load
```

The manifest is fetched `no-cache`; the hashed cards file is immutable so the browser/CDN can cache it forever.

## Visual direction

Editorial, not gamey. Serif (Source Serif) for question text, sans for chrome. Warm off-white / deep ink-blue with one accent (terracotta). Auto dark mode. Mobile-first: 100dvh layout, big bottom-anchored buttons, generous tap targets.

## Out of scope (for now)

These were considered and explicitly deferred:

- Service worker / offline mode.
- Filtering by source or question type.
- "Suspend this card" / blocklist.
- Sync across devices (state schema is sync-ready — `deviceId` field, single JSON blob — but no remote layer).
- Recency boost for new-card selection (uniform random).
- FSRS parameter optimization (default params; revisit after ~1000 reviews accumulated).
- A third "Easy" rating button or gesture.

## Workflows

- `npm run dev` — Vite dev server with base path `''`. Runs `build-data` first.
- `npm run build` — production build to `build/`. Runs `build-data` first.
- `npm run check` — `svelte-check`. Run after edits.
- `.github/workflows/publish.yml` — monthly cron + manual trigger. Builds and deploys to Pages.

The publish workflow is **separate from scraping**: new scraped questions sit in `main` until the next monthly publish (or a manual run). This is deliberate — it batches changes and keeps the live site stable.
