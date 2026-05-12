# Pub quiz flashcards

This project scrapes trivia questions from popular quiz websites and serves them as a spaced-repetition flashcard app. The first source is Thomas Eaton's [weekly quiz](https://www.theguardian.com/theguardian/series/the-quiz-thomas-eaton) in The Guardian. The aim is to provide an enticing way to explore general knowledge over time.

Live site: <https://maxhalford.github.io/pub-quiz-flashcards/>

## How it works

### Scraping

Each source has its own parsing script under `scrape/`. The scripts are run weekly with Claude Code in [headless mode](https://code.claude.com/docs/en/headless). Claude Code automatically repairs scripts when they break, or when they work but the output doesn't look correct. A pull request is opened after a successful parse, which provides an additional level of quality assurance.

### Flashcards

The web app under `web/` is a static SvelteKit site, deployed to GitHub Pages. It has no backend — all state lives in the user's browser under `localStorage`.

- **Spaced repetition.** Uses [FSRS](https://github.com/open-spaced-repetition/ts-fsrs). Two buttons (Don't know / Know) map to `Again` / `Good`.
- **Daily limit.** Ten questions per day; "Keep going (+10)" extends the session.
- **Streak.** Counts consecutive days with at least one answer; a calendar heatmap shows the last 12 weeks.
- **Continuous scraping.** New questions enter the pool automatically once the site is rebuilt (monthly).
- **Backup.** Settings → Export / Import downloads the localStorage state as JSON, so progress can be moved between devices.

### Entity links

Questions and answers are pre-annotated with Wikipedia entity spans at build time, so words like _Eiffel Tower_ or _Albert Einstein_ link directly to their article.

`scrape/build_entities.py` downloads the English Wikipedia all-titles dump, filters it down to proper-noun titles using a few heuristics (capitalisation pattern, `wordfreq` for single-word common-word rejection, a small block-list of plural concept nouns), then builds an Aho-Corasick automaton and scans every card with word-bounded longest-match selection. Manual disambiguation overrides live in `scrape/wikipedia_overrides.json`.

The annotations are emitted to `scrape/wikipedia_annotations.json` (committed), merged into the cards file by the SvelteKit build, and rendered inline by a tiny `RichText` component. Links in the question are only activated once the answer is revealed.

### Publishing

The `.github/workflows/publish.yml` workflow builds the site monthly (or on demand) and deploys to GitHub Pages. It runs `build_entities.py` and then `npm run build`, so the deployed cards always carry fresh annotations.

## Local development

```sh
# Scrape one page from a source
uv run python scrape/<source>/scrape.py

# Rebuild entity annotations (downloads the titles dump once, ~108 MB)
make entities

# Run the web app
cd web && npm install && npm run dev
```
