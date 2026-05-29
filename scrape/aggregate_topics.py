"""Aggregate per-entity topic scores into one editorial topic per card.

Reads scrape/wikipedia_annotations.json (which entities belong to which card)
and scrape/wikipedia_topics.json (ORES topic probabilities per entity title),
then collapses the 52-leaf ORES taxonomy into a smaller editorial taxonomy
defined by EDITORIAL below.

For each card:
  1. Collect topic probabilities from every linked entity.
  2. Map each leaf topic to its editorial bucket via EDITORIAL.
  3. Sum probabilities per bucket; the top bucket is the card's topic.

If wikipedia_topics.json contains any leaf not listed in EDITORIAL, the
script raises — the editorial taxonomy must cover everything the model
emits. Update EDITORIAL when LiftWing introduces new leaves.

Output (committed) at scrape/wikipedia_card_topics.json:

    { "abc123def456": "Sport", ... }
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

SCRAPE_DIR = Path(__file__).parent
ANNOTATIONS_FILE = SCRAPE_DIR / "wikipedia_annotations.json"
TOPICS_FILE = SCRAPE_DIR / "wikipedia_topics.json"
CARD_TOPICS_FILE = SCRAPE_DIR / "wikipedia_card_topics.json"

# Editorial mapping: ORES leaf topic → quiz-friendly bucket.
# Every leaf the model emits must be listed here; aggregate_topics will
# raise if a leaf seen in wikipedia_topics.json is missing.
# Edit freely to rebalance buckets.
EDITORIAL: dict[str, str] = {
    # Culture
    "Culture.Biography": "People",
    "Culture.Biography.Women": "People",
    "Culture.Food and drink": "Food & drink",
    "Culture.Internet culture": "Technology",
    "Culture.Linguistics": "Language",
    "Culture.Literature": "Literature",
    "Culture.Media": "Media",
    "Culture.Media.Books": "Literature",
    "Culture.Media.Entertainment": "Media",
    "Culture.Media.Films": "Film & TV",
    "Culture.Media.Music": "Music",
    "Culture.Media.Radio": "Media",
    "Culture.Media.Software": "Technology",
    "Culture.Media.Television": "Film & TV",
    "Culture.Media.Video games": "Games",
    "Culture.Performing arts": "Performing arts",
    "Culture.Philosophy and religion": "Religion & philosophy",
    "Culture.Sports": "Sport",
    "Culture.Visual arts": "Visual arts",
    "Culture.Visual arts.Architecture": "Architecture",
    "Culture.Visual arts.Comics and Anime": "Visual arts",
    "Culture.Visual arts.Fashion": "Fashion",
    # Geography (every region collapses to one bucket; subregion signal is
    # rarely useful for quiz topic routing)
    "Geography.Geographical": "Geography",
    "Geography.Regions.Africa": "Geography",
    "Geography.Regions.Africa.Central Africa": "Geography",
    "Geography.Regions.Africa.Eastern Africa": "Geography",
    "Geography.Regions.Africa.Northern Africa": "Geography",
    "Geography.Regions.Africa.Southern Africa": "Geography",
    "Geography.Regions.Africa.Western Africa": "Geography",
    "Geography.Regions.Americas.Central America": "Geography",
    "Geography.Regions.Americas.North America": "Geography",
    "Geography.Regions.Americas.South America": "Geography",
    "Geography.Regions.Asia": "Geography",
    "Geography.Regions.Asia.Central Asia": "Geography",
    "Geography.Regions.Asia.East Asia": "Geography",
    "Geography.Regions.Asia.North Asia": "Geography",
    "Geography.Regions.Asia.South Asia": "Geography",
    "Geography.Regions.Asia.Southeast Asia": "Geography",
    "Geography.Regions.Asia.West Asia": "Geography",
    "Geography.Regions.Europe": "Geography",
    "Geography.Regions.Europe.Eastern Europe": "Geography",
    "Geography.Regions.Europe.Northern Europe": "Geography",
    "Geography.Regions.Europe.Southern Europe": "Geography",
    "Geography.Regions.Europe.Western Europe": "Geography",
    "Geography.Regions.Oceania": "Geography",
    # History and Society
    "History and Society.Business and economics": "Business",
    "History and Society.Education": "Society",
    "History and Society.History": "History",
    "History and Society.Military and warfare": "History",
    "History and Society.Politics and government": "Politics",
    "History and Society.Society": "Society",
    "History and Society.Transportation": "Society",
    # STEM
    "STEM": "Science",
    "STEM.Biology": "Nature",
    "STEM.Chemistry": "Science",
    "STEM.Computing": "Technology",
    "STEM.Earth and environment": "Nature",
    "STEM.Engineering": "Technology",
    "STEM.Libraries & Information": "Society",
    "STEM.Mathematics": "Science",
    "STEM.Medicine & Health": "Science",
    "STEM.Physics": "Science",
    "STEM.Space": "Science",
    "STEM.Technology": "Technology",
}


def main() -> None:
    if not TOPICS_FILE.exists():
        raise SystemExit(
            f"{TOPICS_FILE.name} not found — run `make wiki-topics` first."
        )
    ann = json.loads(ANNOTATIONS_FILE.read_text())
    titles_table: list[list[str]] = ann["titles"]  # each entry: [lang, title]
    cards_ann: dict[str, dict] = ann["cards"]
    topics: dict[str, dict[str, float]] = json.loads(TOPICS_FILE.read_text())

    seen = {leaf for scores in topics.values() for leaf in scores}
    missing = sorted(seen - EDITORIAL.keys())
    if missing:
        raise SystemExit(
            "EDITORIAL is missing mappings for these ORES leaves:\n  "
            + "\n  ".join(missing)
            + "\nAdd them to scrape/aggregate_topics.py and re-run."
        )

    out: dict[str, str] = {}
    for cid in sorted(cards_ann):
        # Only English entities are scored by ORES; non-en entities contribute
        # no topic signal.
        entity_titles = [
            titles_table[span[2]][1]
            for key in ("q", "a")
            for span in cards_ann[cid].get(key, [])
            if titles_table[span[2]][0] == "en"
        ]
        buckets: dict[str, float] = {}
        for t in entity_titles:
            for leaf, p in topics.get(t, {}).items():
                bucket = EDITORIAL[leaf]
                buckets[bucket] = buckets.get(bucket, 0.0) + p
        if not buckets:
            continue
        top = max(buckets.items(), key=lambda x: x[1])
        out[cid] = top[0]

    CARD_TOPICS_FILE.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    print(f"Wrote topic for {len(out):,}/{len(cards_ann):,} cards")
    dist = Counter(out.values())
    for bucket, n in dist.most_common():
        print(f"  {bucket:<25} {n}")


if __name__ == "__main__":
    main()
