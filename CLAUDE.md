# Pub quiz

This is a project for learning pub quiz questions, and associated knowledge. Questions and answers are scraped from the web, such as The Guardian's weekly quiz, University Challenge, etc.

## Scraping

Each source has its own `scrape.py` file. For instance there is `scrape/the_guardian_weekly/scrape.py` for Thomas Eaton's weekly quiz.

Run the scrape script for a given source:

```sh
uv run python scrape/<source>/scrape.py
```

The script scrapes **one page at a time**. If there is nothing new to scrape, it exits without changes.

### Q/A the results

After running the script, use `jq '.[-1]'` to extract and review only the last entry from the source's `questions.json`. Do not read the entire file. Verify that questions and answers are properly paired and make sense. If the output looks wrong, delete the bad entry from the JSON file, fix `scrape.py` to handle the page format correctly, and re-run.

### Fixing scripts

These scripts are mutable. They can raise an error because the structure of the pages they parse has changed. Fix them when that happens. Under no circumstances should you change the structure of the output format. You should only change whatever logic is used to extract the target data from the pages.

When updating a script, you should avoid adding try/catch exceptions. Instead, make the necessary changes to make the parsing go through. Further changes can always be made later for future formats. You also do not need to make the code retro-compatible, because the goal is only to keep the scripts up-to-date with the latest format.

## Refactoring

When you done repairing and running a scraping script, please take some time to review it as a whole. You can refactor and simplify it when it makes sense. The goal is to avoid patching it incrementally and ending up with a castle of cards. The script should be lean because what matters is that it works with the latest page, and does not need to support all formats.

### Linting and type checking

After modifying any Python file, run ruff and ty to format, lint, and type check:

```sh
uv run ruff check --fix .
uv run ruff format .
uv run ty check .
```

Fix any reported issue.
