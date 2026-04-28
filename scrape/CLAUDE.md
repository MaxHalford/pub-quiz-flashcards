Run the scrape script: `uv run python scrape/<source>/scrape.py`

It scrapes one page at a time. If nothing new, it exits without changes.

After running, QA the results: use `jq '.[-1]'` on the source's `questions.json`. Do not read the entire file. Verify questions and answers are properly paired. If wrong, delete the bad entry, fix `scrape.py`, and re-run.

If the script errors because page structure changed, fix the parsing logic. Rules:
- Never add try/catch. Make the parsing work directly.
- Do not change the output format.
- No need for retro-compatibility — only handle the current format.
- After fixing, review the whole script and simplify if needed.

After modifying any Python file, run:
```sh
uv run ruff check --fix .
uv run ruff format .
uv run ty check .
```

Your final response is logged. Keep it to one short line, e.g.:
- `Scraped 1 quiz (2015-11-21, 15 questions). No code changes.`
- `Fixed date parsing in scrape.py. Scraped 1 quiz (2015-11-21, 15 questions).`
