"""Annotate scraped questions with Wikipedia entity links.

Downloads the English Wikipedia article-titles dump once, builds an
Aho-Corasick automaton over the titles, and tags every card's question
and answer with the spans that match a Wikipedia article. No online
lookups at annotation time — fully offline once the dump is cached.

Output (committed) at scrape/wikipedia_annotations.json:

    {
      "titles": ["Pastern", "Fetlock", ...],   # sorted unique titles
      "cards": {
        "abc123def456": {
          "q": [[start, end, title_idx], ...],
          "a": [[start, end, title_idx], ...]
        }
      }
    }

URLs are derived at read time from the title (https://en.wikipedia.org/wiki/...).

Manual disambiguation lives in scrape/wikipedia_overrides.json:
    {
      "Apple":   { "title": "Apple Inc.", "url": "https://en.wikipedia.org/wiki/Apple_Inc." },
      "Mercury": null   // suppress entirely (too ambiguous)
    }
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import ahocorasick
import requests
from wordfreq import zipf_frequency

SCRAPE_DIR = Path(__file__).parent
DUMP_FILE = SCRAPE_DIR / "_enwiki_titles.gz"
DUMP_URL = (
    "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-all-titles-in-ns0.gz"
)
OVERRIDES_FILE = SCRAPE_DIR / "wikipedia_overrides.json"
ANNOTATIONS_FILE = SCRAPE_DIR / "wikipedia_annotations.json"

USER_AGENT = "PubQuizFlashcards/1.0 (https://github.com/MaxHalford/pub-quiz-flashcards)"

# Skip Wikipedia pages whose titles start with these — they're never useful
# trivia entities, just meta/list articles.
SKIP_PREFIXES = (
    "List_of_",
    "Lists_of_",
    "Timeline_of_",
    "Timelines_of_",
    "History_of_",
    "Outline_of_",
    "Index_of_",
    "Glossary_of_",
)

# Small connector words allowed to be lowercase inside multi-word titles
# (e.g., "The Lord of the Rings", "United States of America"). Used to detect
# proper-noun-style titles vs common-noun concept articles.
TITLE_STOPWORDS = frozenset(
    {
        "the",
        "of",
        "in",
        "and",
        "or",
        "a",
        "an",
        "for",
        "to",
        "with",
        "on",
        "at",
        "by",
        "from",
        "as",
        "but",
        "into",
        "onto",
        "is",
        "are",
        "vs",
    }
)

# Skip single-significant-word titles whose lowercase form has zipf-frequency
# >= this. 3.8 catches "fictional" (3.86), "Who is" (Who=6.34), "singers" (3.81)
# while keeping "Einstein" (3.74), "octopus" (3.46), "Rihanna" (3.46).
COMMON_WORD_THRESHOLD = 3.8

# Plural concept-noun articles that wordfreq doesn't separate from real
# entities by frequency alone. These all appeared as top-linked surfaces in
# inspections and are never useful trivia links.
SURFACE_BLOCKLIST = frozenset(
    {
        "Nicknames",
        "Nicknamed",
        "Surnames",
        "Footballers",
        "Singers",
        "Sculptors",
        "Sculptures",
        "Artworks",
        "Composers",
        "Authors",
        "Directors",
        "Actors",
        "Actresses",
        "Athletes",
        "Olympians",
        "Capitals",
        "Meanings",
        "Homophones",
        "Anagrams",
        "Palindromes",
        "Letters",
        "Symbols",
        "Numbers",
        "Colours",
        "Colors",
        "Shapes",
        "Cities",
        "Towns",
        "Villages",
        "Countries",
        "Continents",
        "Rivers",
        "Mountains",
        "Islands",
        "Lakes",
        "Oceans",
        "Deserts",
        "Animals",
        "Birds",
        "Fish",
        "Insects",
        "Mammals",
        "Plants",
        "Trees",
        "Flowers",
        "Vegetables",
        "Fruits",
        "Spices",
        "Drinks",
        "Foods",
        "Films",
        "Movies",
        "Books",
        "Albums",
        "Songs",
        "Bands",
        "Groups",
        "Teams",
        "Players",
        "Members",
        "Leaders",
        "Presidents",
        "Kings",
        "Queens",
        "Prime Ministers",
        "Saints",
        "Types",
        "Forms",
        "Kinds",
        "Parts",
        "Pieces",
        "Sounds",
        "Names",
        "Words",
        "Phrases",
        "Proverbs",
        "Idioms",
        "Inventions",
        "Discoveries",
        "Theories",
        "Equations",
        "Formulas",
        "Diseases",
        "Vaccines",
        "Drugs",
        "Medicines",
    }
)

MIN_LEN = 3
MAX_LEN = 80
WORD_CHAR = re.compile(r"[A-Za-z0-9]")
DATE_LIKE = re.compile(r"^[0-9][0-9_BCs]+$|^[0-9]+(st|nd|rd|th)_century$")


def short_id(source_url: str, question: str) -> str:
    return hashlib.sha1(f"{source_url}\n{question}".encode()).hexdigest()[:12]


def ensure_dump() -> None:
    """Download the all-titles dump if we don't have it yet."""
    if DUMP_FILE.exists():
        return
    print(f"Downloading {DUMP_URL}…", flush=True)
    with requests.get(DUMP_URL, stream=True, headers={"User-Agent": USER_AGENT}) as r:
        r.raise_for_status()
        tmp = DUMP_FILE.with_suffix(".gz.part")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(DUMP_FILE)
    size_mb = DUMP_FILE.stat().st_size / 1e6
    print(f"  saved {size_mb:.0f} MB", flush=True)


def iter_titles():
    """Yield space-separated surface forms from the dump, after filtering."""
    with gzip.open(DUMP_FILE, "rt", encoding="utf-8") as f:
        # The file has a one-line header: "page_namespace\tpage_title".
        header = f.readline()
        # If the header isn't the expected one, rewind and treat as data.
        if not header.startswith("page_"):
            yield from _filter_line(header)
        for line in f:
            yield from _filter_line(line)


def _filter_line(line: str):
    line = line.rstrip("\n")
    if not line:
        return
    # File format: "0\tTitle" — the namespace prefix is "0" for NS0 only.
    title = line.split("\t", 1)[-1]
    if not title:
        return
    if title.startswith(SKIP_PREFIXES):
        return
    if "(" in title:  # disambiguation suffix like "Mercury_(planet)"
        return
    if not title[0].isupper():
        return
    if len(title) < MIN_LEN or len(title) > MAX_LEN:
        return
    if DATE_LIKE.match(title):
        return

    # Significant words: everything that isn't a small connector. A title that
    # consists solely of stopwords or whose significant words aren't all
    # capitalised is a common-noun concept article ("Pig farmer", "Computer
    # language"), not a proper noun — skip it.
    words = title.split("_")
    significant = [w for w in words if w and w.lower() not in TITLE_STOPWORDS]
    if not significant or not all(w[0].isupper() for w in significant):
        return

    # If a single significant word, additionally drop common English words.
    # ("Who is" -> significant=["Who"], zipf("who")=6.34, drop.)
    if (
        len(significant) == 1
        and zipf_frequency(significant[0].lower(), "en") >= COMMON_WORD_THRESHOLD
    ):
        return

    surface = title.replace("_", " ")
    if surface in SURFACE_BLOCKLIST:
        return
    yield surface


def title_to_url(title: str) -> str:
    return f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


def _boundary_before(text: str, pos: int) -> bool:
    """True if there is a word boundary immediately before position `pos`
    (start-of-string or a non-word char just before the match)."""
    if pos <= 0:
        return True
    return WORD_CHAR.match(text[pos - 1]) is None


def _boundary_after(text: str, pos: int) -> bool:
    """True if there is a word boundary at position `pos` (end-of-string or
    the char at `pos` is non-word)."""
    if pos >= len(text):
        return True
    return WORD_CHAR.match(text[pos]) is None


_SENTINEL: object = object()


def find_spans(text: str, automaton, overrides: dict) -> list[tuple[int, int, str]]:
    """Non-overlapping, word-bounded, longest-match-wins entity spans.

    Returns (start, end, title) tuples. URLs are reconstructed from the title
    by the consumer via `title_to_url`. Matching is case-insensitive: the
    automaton holds lowercase surfaces, and we scan the lowercased text. The
    canonical (capitalised) title comes from the automaton's value payload.
    """
    candidates: list[tuple[int, int, str]] = []
    haystack = text.lower()
    for end_idx, canonical in automaton.iter(haystack):
        start = end_idx - len(canonical) + 1
        end = end_idx + 1
        if not _boundary_before(text, start):
            continue
        if not _boundary_after(text, end):
            continue
        override = overrides.get(canonical.lower(), _SENTINEL)
        if override is None:
            continue
        title = override["title"] if override is not _SENTINEL else canonical
        candidates.append((start, end, title))

    candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
    kept: list[tuple[int, int, str]] = []
    for c in candidates:
        if any(not (c[1] <= k[0] or c[0] >= k[1]) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=lambda c: c[0])
    return kept


def collect_cards():
    """Yield (card_id, question, answer) over all scrape sources."""
    for src_dir in sorted(SCRAPE_DIR.iterdir()):
        if not src_dir.is_dir() or src_dir.name.startswith((".", "_")):
            continue
        qfile = src_dir / "questions.json"
        if not qfile.exists():
            continue
        entries = json.loads(qfile.read_text())
        for entry in entries:
            url = entry.get("source_url") or entry["url"]
            for pair in entry["pairs"]:
                cid = short_id(url, pair["question"])
                yield cid, pair["question"], pair["answer"]


def main() -> None:
    ensure_dump()

    raw_overrides = (
        json.loads(OVERRIDES_FILE.read_text()) if OVERRIDES_FILE.exists() else {}
    )
    overrides = {k.lower(): v for k, v in raw_overrides.items()}

    print("Building automaton…", flush=True)
    t0 = time.time()
    automaton = ahocorasick.Automaton()
    count = 0
    for surface in iter_titles():
        # Lowercase key for case-insensitive matching; value keeps the
        # canonical (capitalised) form used to build the Wikipedia URL.
        automaton.add_word(surface.lower(), surface)
        count += 1
        if count % 500_000 == 0:
            print(f"  {count:,} surfaces loaded", flush=True)
    print(f"  {count:,} surfaces total, finalising…", flush=True)
    automaton.make_automaton()
    print(f"  done in {time.time() - t0:.1f}s", flush=True)

    cards = list(collect_cards())
    print(f"Annotating {len(cards)} cards…", flush=True)
    t0 = time.time()

    # First pass: collect raw spans per card and the set of titles used.
    raw: dict[str, dict[str, list[tuple[int, int, str]]]] = {}
    titles_seen: set[str] = set()
    for i, (cid, q, a) in enumerate(cards, start=1):
        q_spans = find_spans(q, automaton, overrides) if q else []
        a_spans = find_spans(a, automaton, overrides) if a else []
        if q_spans or a_spans:
            entry: dict[str, list[tuple[int, int, str]]] = {}
            if q_spans:
                entry["q"] = q_spans
                titles_seen.update(t for _, _, t in q_spans)
            if a_spans:
                entry["a"] = a_spans
                titles_seen.update(t for _, _, t in a_spans)
            raw[cid] = entry
        if i % 1000 == 0:
            print(f"  {i:,}/{len(cards):,} cards", flush=True)

    # Second pass: build the title table and rewrite spans as [s, e, idx].
    titles_sorted = sorted(titles_seen)
    title_idx = {t: j for j, t in enumerate(titles_sorted)}
    out_cards: dict[str, dict[str, list[list[int]]]] = {}
    for cid in sorted(raw):
        entry_norm: dict[str, list[list[int]]] = {}
        for key in ("q", "a"):
            if key in raw[cid]:
                entry_norm[key] = [[s, e, title_idx[t]] for s, e, t in raw[cid][key]]
        out_cards[cid] = entry_norm

    ANNOTATIONS_FILE.write_text(
        json.dumps(
            {"titles": titles_sorted, "cards": out_cards},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    print(
        f"Done: {len(out_cards):,} annotated cards, "
        f"{len(titles_sorted):,} unique titles "
        f"in {time.time() - t0:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
