# Pub quiz

This is a project for learning pub quiz questions, and associated knowledge. Questions and answers are scraped from the web, such as The Guardian's weekly quiz, University Challenge, etc.

## Scraping

Each source has its own `scrape.py` file. For instance there is `sources/theguardian/scrape.py` for Thomas Eaton's weekly quiz. You can run it with `uv`:

```sh
uv run python sources/the_guardian_weekly/scrape.py
```

These scripts are mutable. They can raise an error because the structure of the pages they parse has changed. Fix them when that happens. Under no circumstances should you change the structure of the output format. You should only change whatever logic is used to extract the target data from the pages.
