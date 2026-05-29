"""Annotate scraped questions with Wikipedia entity links.

Downloads the English and French Wikipedia article-titles dumps once, builds
an Aho-Corasick automaton over their titles, and tags every card's question
and answer with the spans that match a Wikipedia article. No online lookups
at annotation time — fully offline once the dumps are cached.

When the same surface form exists in both wikis (e.g. "Paris"), English wins —
we add titles in DUMPS order and skip duplicates.

Output (committed) at scrape/wikipedia_annotations.json:

    {
      "titles": [["en", "Pastern"], ["fr", "Les Cinq Sens"], ...],
      "cards": {
        "abc123def456": {
          "q": [[start, end, title_idx], ...],
          "a": [[start, end, title_idx], ...]
        }
      }
    }

URLs are derived at read time from (lang, title): `https://{lang}.wikipedia.org/wiki/…`.

Manual disambiguation lives in scrape/wikipedia_overrides.json. Each key is a
surface form (case-insensitive); each value is either:
    { "title": "Apple Inc.", "lang": "en" }   # redirect to a different title
    null                                      # suppress entirely (too ambiguous)
`lang` defaults to "en" if omitted.
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
OVERRIDES_FILE = SCRAPE_DIR / "wikipedia_overrides.json"
ANNOTATIONS_FILE = SCRAPE_DIR / "wikipedia_annotations.json"

USER_AGENT = "PubQuizFlashcards/1.0 (https://github.com/MaxHalford/pub-quiz-flashcards)"

# Wikipedias we ingest, in priority order — when a surface form exists in both
# (e.g. "Paris"), the first listed wins.
DUMPS: tuple[tuple[str, Path, str], ...] = (
    (
        "en",
        SCRAPE_DIR / "_enwiki_titles.gz",
        "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-all-titles-in-ns0.gz",
    ),
    (
        "fr",
        SCRAPE_DIR / "_frwiki_titles.gz",
        "https://dumps.wikimedia.org/frwiki/latest/frwiki-latest-all-titles-in-ns0.gz",
    ),
)

WIKI_HOSTS = {"en": "en.wikipedia.org", "fr": "fr.wikipedia.org"}

# Per-language meta/list title prefixes that are never useful trivia entities.
SKIP_PREFIXES_BY_LANG: dict[str, tuple[str, ...]] = {
    "en": (
        "List_of_",
        "Lists_of_",
        "Timeline_of_",
        "Timelines_of_",
        "History_of_",
        "Outline_of_",
        "Index_of_",
        "Glossary_of_",
    ),
    "fr": (
        "Liste_de_",
        "Liste_des_",
        "Liste_d'",
        "Listes_de_",
        "Listes_des_",
        "Chronologie_de_",
        "Chronologie_des_",
        "Chronologie_du_",
        "Histoire_de_",
        "Histoire_des_",
        "Histoire_du_",
        "Glossaire_de_",
        "Glossaire_des_",
    ),
}

# Small connector words allowed to be lowercase inside multi-word titles. Used
# to detect proper-noun-style English titles vs common-noun concept articles;
# for French it's just used to identify the leading content word.
TITLE_STOPWORDS_BY_LANG: dict[str, frozenset[str]] = {
    "en": frozenset(
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
    ),
    "fr": frozenset(
        {
            "le",
            "la",
            "les",
            "de",
            "du",
            "des",
            "d",
            "l",
            "un",
            "une",
            "et",
            "ou",
            "à",
            "au",
            "aux",
            "en",
            "dans",
            "sur",
            "par",
            "pour",
            "avec",
            "sans",
            "ce",
            "ces",
            "cet",
            "cette",
            "sa",
            "son",
            "ses",
            "qui",
            "que",
            "est",
            "sont",
        }
    ),
}

# Skip single-significant-word titles whose lowercase form has zipf-frequency
# >= this in any of FREQ_LANGS. 3.8 catches "fictional" (3.86), "Who is"
# (Who=6.34), "singers" (3.81) while keeping "Einstein" (3.74), "octopus"
# (3.46), "Rihanna" (3.46). Checking French too catches stopwords like "une"
# (en=3.34, fr=7.0) and "et" (en=4.66, fr=7.31) that match French quiz text.
COMMON_WORD_THRESHOLD = 3.8
FREQ_LANGS = ("en", "fr")

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


def ensure_dumps() -> None:
    """Download any missing all-titles dumps."""
    for _, path, url in DUMPS:
        if path.exists():
            continue
        print(f"Downloading {url}…", flush=True)
        with requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}) as r:
            r.raise_for_status()
            tmp = path.with_suffix(".gz.part")
            with tmp.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.rename(path)
        print(f"  saved {path.stat().st_size / 1e6:.0f} MB", flush=True)


def iter_titles():
    """Yield (lang, surface) over the filtered union of all dumps."""
    for lang, path, _ in DUMPS:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            header = f.readline()
            if not header.startswith("page_"):
                yield from _filter_line(header, lang)
            for line in f:
                yield from _filter_line(line, lang)


def _filter_line(line: str, lang: str):
    line = line.rstrip("\n")
    if not line:
        return
    # File format: "0\tTitle" — the namespace prefix is "0" for NS0 only.
    title = line.split("\t", 1)[-1]
    if not title:
        return
    if title.startswith(SKIP_PREFIXES_BY_LANG[lang]):
        return
    if "(" in title:  # disambiguation suffix like "Mercury_(planet)"
        return
    if not title[0].isupper():
        return
    if len(title) < MIN_LEN or len(title) > MAX_LEN:
        return
    if DATE_LIKE.match(title):
        return

    words = title.split("_")
    stopwords = TITLE_STOPWORDS_BY_LANG[lang]
    significant = [w for w in words if w and w.lower() not in stopwords]
    if not significant:
        return

    # Capitalisation rule. English Wikipedia title-cases every significant
    # word in proper-noun titles ("United States of America"); a title with a
    # lowercase content word is a common-noun concept article ("Pig farmer"),
    # which we drop. French Wikipedia only capitalises the first word, so we
    # rely solely on the leading-capital check already done above plus the
    # frequency filter below.
    if lang == "en" and not all(w[0].isupper() for w in significant):
        return

    # Single significant word: drop if it's common in any of FREQ_LANGS.
    if len(significant) == 1:
        word = significant[0].lower()
        if max(zipf_frequency(word, lg) for lg in FREQ_LANGS) >= COMMON_WORD_THRESHOLD:
            return

    surface = title.replace("_", " ")
    if surface in SURFACE_BLOCKLIST:
        return
    yield (lang, surface)


def title_to_url(lang: str, title: str) -> str:
    host = WIKI_HOSTS[lang]
    return f"https://{host}/wiki/{quote(title.replace(' ', '_'))}"


def _boundary_before(text: str, pos: int) -> bool:
    if pos <= 0:
        return True
    return WORD_CHAR.match(text[pos - 1]) is None


def _boundary_after(text: str, pos: int) -> bool:
    if pos >= len(text):
        return True
    return WORD_CHAR.match(text[pos]) is None


_SENTINEL: object = object()


def find_spans(
    text: str, automaton, overrides: dict
) -> list[tuple[int, int, str, str]]:
    """Non-overlapping, word-bounded, longest-match-wins entity spans.

    Returns (start, end, lang, title) tuples. URLs are reconstructed by the
    consumer via `title_to_url(lang, title)`. Matching is case-insensitive.
    """
    candidates: list[tuple[int, int, str, str]] = []
    haystack = text.lower()
    for end_idx, (match_lang, canonical) in automaton.iter(haystack):
        start = end_idx - len(canonical) + 1
        end = end_idx + 1
        if not _boundary_before(text, start):
            continue
        if not _boundary_after(text, end):
            continue
        override = overrides.get(canonical.lower(), _SENTINEL)
        if override is None:
            continue
        if override is not _SENTINEL:
            title = override["title"]
            lang = override.get("lang", "en")
        else:
            title = canonical
            lang = match_lang
        candidates.append((start, end, lang, title))

    candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
    kept: list[tuple[int, int, str, str]] = []
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
    ensure_dumps()

    raw_overrides = (
        json.loads(OVERRIDES_FILE.read_text()) if OVERRIDES_FILE.exists() else {}
    )
    overrides = {k.lower(): v for k, v in raw_overrides.items()}

    print("Building automaton…", flush=True)
    t0 = time.time()
    automaton = ahocorasick.Automaton()
    seen_keys: set[str] = set()
    counts = {lang: 0 for lang, *_ in DUMPS}
    for lang, surface in iter_titles():
        key = surface.lower()
        if key in seen_keys:
            continue  # first lang in DUMPS wins on collision
        seen_keys.add(key)
        automaton.add_word(key, (lang, surface))
        counts[lang] += 1
        total = sum(counts.values())
        if total % 500_000 == 0:
            print(f"  {total:,} surfaces loaded", flush=True)
    print(
        "  "
        + ", ".join(f"{lang}={n:,}" for lang, n in counts.items())
        + f" — {sum(counts.values()):,} total, finalising…",
        flush=True,
    )
    automaton.make_automaton()
    print(f"  done in {time.time() - t0:.1f}s", flush=True)

    cards = list(collect_cards())
    print(f"Annotating {len(cards)} cards…", flush=True)
    t0 = time.time()

    # First pass: collect raw spans per card and the set of titles used.
    raw: dict[str, dict[str, list[tuple[int, int, str, str]]]] = {}
    titles_seen: set[tuple[str, str]] = set()
    for i, (cid, q, a) in enumerate(cards, start=1):
        q_spans = find_spans(q, automaton, overrides) if q else []
        a_spans = find_spans(a, automaton, overrides) if a else []
        if q_spans or a_spans:
            entry: dict[str, list[tuple[int, int, str, str]]] = {}
            if q_spans:
                entry["q"] = q_spans
                titles_seen.update((lg, t) for _, _, lg, t in q_spans)
            if a_spans:
                entry["a"] = a_spans
                titles_seen.update((lg, t) for _, _, lg, t in a_spans)
            raw[cid] = entry
        if i % 1000 == 0:
            print(f"  {i:,}/{len(cards):,} cards", flush=True)

    # Second pass: build the title table and rewrite spans as [s, e, idx].
    titles_sorted = sorted(titles_seen)
    title_idx = {tt: j for j, tt in enumerate(titles_sorted)}
    out_cards: dict[str, dict[str, list[list[int]]]] = {}
    for cid in sorted(raw):
        entry_norm: dict[str, list[list[int]]] = {}
        for key in ("q", "a"):
            if key in raw[cid]:
                entry_norm[key] = [
                    [s, e, title_idx[(lg, t)]] for s, e, lg, t in raw[cid][key]
                ]
        out_cards[cid] = entry_norm

    titles_out = [list(tt) for tt in titles_sorted]
    ANNOTATIONS_FILE.write_text(
        json.dumps(
            {"titles": titles_out, "cards": out_cards},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    by_lang = {lg: 0 for lg, *_ in DUMPS}
    for lg, _ in titles_sorted:
        by_lang[lg] = by_lang.get(lg, 0) + 1
    print(
        f"Done: {len(out_cards):,} annotated cards, "
        f"{len(titles_sorted):,} unique titles "
        f"({', '.join(f'{lg}={n:,}' for lg, n in by_lang.items())}) "
        f"in {time.time() - t0:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
