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

# Editorial mapping: ORES leaf topic → quiz-friendly bucket. Every leaf the
# model emits must be listed here; aggregate_topics raises if a leaf seen in
# wikipedia_topics.json is missing. Map a leaf to SKIP to ignore its signal
# (used for ORES rollups that fire on almost every article and would otherwise
# drown out topical signal — e.g. regional Geography tags).
SKIP = ""

# Minimum top-bucket score required to assign a topic. Cards with weaker
# signal (sparse / low-confidence entities) get no topic rather than a
# coin-flip bucket. Tuned by QA — at 0.4 we keep real classifications like
# "Braudel → History" (top=0.45) while dropping near-zero noise.
MIN_CONFIDENCE = 0.4

EDITORIAL: dict[str, str] = {
    # Culture
    # Culture.Biography{,.Women}: fires for any article about a person —
    # a musician already gets Music, an athlete Sport, etc., so the biography
    # tag just dilutes the specific signal. People bucket retired.
    "Culture.Biography": SKIP,
    "Culture.Biography.Women": SKIP,
    "Culture.Food and drink": "Food & drink",
    "Culture.Internet culture": "Technology",
    # Culture.Linguistics: model treats most "what is X called" / dictionary-
    # style articles as linguistics. In QA every Language-bucketed card was
    # actually about food, anatomy, places, TV, etc. Real language questions
    # are rare in trivia and still pick up topical signal from other leaves.
    "Culture.Linguistics": SKIP,
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
    # Geography. Geography.Geographical is the model's actual "this article is
    # a geography topic" leaf — kept. Geography.Regions.* roll-ups fire on
    # almost every article that has any locale (people, events, works,
    # cuisine, …), so summing them across a card's entities drowns out the
    # real topical signal. Dropped via SKIP.
    "Geography.Geographical": "Geography",
    "Geography.Regions.Africa": SKIP,
    "Geography.Regions.Africa.Central Africa": SKIP,
    "Geography.Regions.Africa.Eastern Africa": SKIP,
    "Geography.Regions.Africa.Northern Africa": SKIP,
    "Geography.Regions.Africa.Southern Africa": SKIP,
    "Geography.Regions.Africa.Western Africa": SKIP,
    "Geography.Regions.Americas.Central America": SKIP,
    "Geography.Regions.Americas.North America": SKIP,
    "Geography.Regions.Americas.South America": SKIP,
    "Geography.Regions.Asia": SKIP,
    "Geography.Regions.Asia.Central Asia": SKIP,
    "Geography.Regions.Asia.East Asia": SKIP,
    "Geography.Regions.Asia.North Asia": SKIP,
    "Geography.Regions.Asia.South Asia": SKIP,
    "Geography.Regions.Asia.Southeast Asia": SKIP,
    "Geography.Regions.Asia.West Asia": SKIP,
    "Geography.Regions.Europe": SKIP,
    "Geography.Regions.Europe.Eastern Europe": SKIP,
    "Geography.Regions.Europe.Northern Europe": SKIP,
    "Geography.Regions.Europe.Southern Europe": SKIP,
    "Geography.Regions.Europe.Western Europe": SKIP,
    "Geography.Regions.Oceania": SKIP,
    # History and Society
    "History and Society.Business and economics": "Business",
    # Education / Society / Transportation: none align with a quiz bucket, and
    # they fire as low-confidence catch-alls when no stronger signal exists.
    # Skipped — real questions about schools/transport route via stronger
    # leaves (History, Politics, Technology, Business) anyway.
    "History and Society.Education": SKIP,
    "History and Society.History": "History",
    "History and Society.Military and warfare": "History",
    "History and Society.Politics and government": "Politics",
    "History and Society.Society": SKIP,
    "History and Society.Transportation": SKIP,
    # STEM
    "STEM": "Science",
    "STEM.Biology": "Nature",
    "STEM.Chemistry": "Science",
    "STEM.Computing": "Technology",
    "STEM.Earth and environment": "Nature",
    "STEM.Engineering": "Technology",
    # STEM.Libraries & Information: niche leaf, no quiz bucket; skipped.
    "STEM.Libraries & Information": SKIP,
    "STEM.Mathematics": "Science",
    "STEM.Medicine & Health": "Science",
    "STEM.Physics": "Science",
    "STEM.Space": "Science",
    # STEM.Technology: the catch-all "this article has a technical angle"
    # leaf, fires broadly. Real tech questions still route to Technology via
    # Computing / Engineering / Software / Internet culture.
    "STEM.Technology": SKIP,
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
                if not bucket:
                    continue
                buckets[bucket] = buckets.get(bucket, 0.0) + p
        if not buckets:
            continue
        top = max(buckets.items(), key=lambda x: x[1])
        if top[1] < MIN_CONFIDENCE:
            continue
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
