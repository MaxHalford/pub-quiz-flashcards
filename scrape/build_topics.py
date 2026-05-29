"""Fetch ORES articletopic scores for every Wikipedia title we link to.

Pure script: takes the list of titles that appear in
`scrape/wikipedia_annotations.json` and, for any title not already in
`scrape/wikipedia_topics.json`, queries LiftWing for topic probabilities.

The output file is committed and acts as our cache — re-runs only hit the
network for new titles. Titles that no longer appear in the annotations
are pruned, so the file mirrors the current entity set.

Output (committed) at scrape/wikipedia_topics.json:

    {
      "Albert Einstein": {"STEM.Physics": 0.84, ...},
      "Some Article We Tried":   {}    # tried, no score available
    }

Probabilities are the raw model output minus the parent-rollup labels
(those ending in '*'), which double-count signal already covered by the
leaves.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

SCRAPE_DIR = Path(__file__).parent
ANNOTATIONS_FILE = SCRAPE_DIR / "wikipedia_annotations.json"
TOPICS_FILE = SCRAPE_DIR / "wikipedia_topics.json"

USER_AGENT = "PubQuizFlashcards/1.0 (https://github.com/MaxHalford/pub-quiz-flashcards)"
LIFTWING_URL = (
    "https://api.wikimedia.org/service/lw/inference/v1/models/"
    "enwiki-articletopic:predict"
)
WIKI_API = "https://en.wikipedia.org/w/api.php"

REQUEST_TIMEOUT = 30
POLITENESS_DELAY = 0.1
REV_ID_BATCH = 50


def fetch_rev_ids(titles: list[str]) -> dict[str, int]:
    """Batch latest rev_id lookups, honouring normalisations and redirects."""
    out: dict[str, int] = {}
    for i in range(0, len(titles), REV_ID_BATCH):
        batch = titles[i : i + REV_ID_BATCH]
        r = requests.get(
            WIKI_API,
            params={
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "ids",
                "format": "json",
                "formatversion": "2",
                "redirects": "1",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json().get("query", {})
        redirects = {r["from"]: r["to"] for r in data.get("redirects", [])}
        normalized = {n["from"]: n["to"] for n in data.get("normalized", [])}
        resolved_rev: dict[str, int] = {}
        for page in data.get("pages", []):
            if page.get("missing") or not page.get("revisions"):
                continue
            resolved_rev[page["title"]] = page["revisions"][0]["revid"]
        for orig in batch:
            resolved = normalized.get(orig, orig)
            resolved = redirects.get(resolved, resolved)
            if resolved in resolved_rev:
                out[orig] = resolved_rev[resolved]
    return out


def fetch_topics(rev_id: int) -> dict[str, float] | None:
    """Return raw topic probabilities for one revision, or None if unscored."""
    r = requests.post(
        LIFTWING_URL,
        json={"rev_id": rev_id},
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    # LiftWing returns 400 for revisions it can't score (redirects, very short
    # articles, etc.). Treat as "no topics" — we still cache the empty result
    # so we don't retry next run.
    if r.status_code == 400:
        return None
    r.raise_for_status()
    score = r.json()["enwiki"]["scores"][str(rev_id)]["articletopic"]["score"]
    return score["probability"]


def strip_parents(probs: dict[str, float]) -> dict[str, float]:
    """Drop '*' parent-rollup labels (e.g. 'STEM.STEM*')."""
    return {t: p for t, p in probs.items() if not t.endswith("*")}


def main() -> None:
    ann = json.loads(ANNOTATIONS_FILE.read_text())
    # ORES articletopic only scores English revisions, so we ignore non-en
    # entities — French-only entities have no topic score and simply don't
    # contribute to the per-card editorial topic.
    needed = {title for lang, title in ann["titles"] if lang == "en"}

    cache: dict[str, dict[str, float]] = (
        json.loads(TOPICS_FILE.read_text()) if TOPICS_FILE.exists() else {}
    )

    todo = sorted(needed - cache.keys())
    pruned = sorted(cache.keys() - needed)
    print(f"{len(needed)} titles needed, {len(cache)} cached, {len(todo)} to fetch")
    if pruned:
        print(f"  pruning {len(pruned)} orphan cache entries")
        for t in pruned:
            del cache[t]

    if todo:
        print("Looking up rev_ids…")
        rev_ids = fetch_rev_ids(todo)
        print(f"  resolved {len(rev_ids)}/{len(todo)} titles")
        for i, title in enumerate(todo, start=1):
            rid = rev_ids.get(title)
            if rid is None:
                cache[title] = {}
                continue
            try:
                probs = fetch_topics(rid)
            except requests.HTTPError as e:
                print(f"  [{i}/{len(todo)}] {title}: skip ({e})")
                cache[title] = {}
                continue
            cache[title] = strip_parents(probs) if probs else {}
            if i % 25 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] cached through {title}")
                # Flush periodically so a crash doesn't lose progress.
                _write(cache)
            time.sleep(POLITENESS_DELAY)

    _write(cache)
    scored = sum(1 for v in cache.values() if v)
    print(f"Done: {scored}/{len(cache)} titles have topic scores")


def _write(cache: dict[str, dict[str, float]]) -> None:
    TOPICS_FILE.write_text(
        json.dumps(
            {k: cache[k] for k in sorted(cache)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
