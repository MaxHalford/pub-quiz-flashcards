"""Build an index of all episodes of France Inter's "Le jeu des 1000 euros".

The script walks every page of the show's episode listing on radiofrance.fr,
then for any episode not already indexed it fetches the episode page to extract
the audio file URL. Output is `episodes.json` next to this file.

The script is idempotent: known episodes (matched by id) are kept as-is, and
their audio URL is not re-fetched.
"""

import datetime as dt
import json
import logging
import pathlib
import re
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.radiofrance.fr"
SHOW_PATH = "/franceinter/podcasts/le-jeu-des-1000"

FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}

DATE_RE = re.compile(r"(\d+)(?:er)?\s+(\S+)\s+(\d{4})", re.IGNORECASE)


def parse_french_date(text: str) -> dt.date:
    """Parse a French date such as "Mardi 19 mai 2026" or "Mercredi 1er avril 2020"."""
    match = DATE_RE.search(text)
    assert match, f"Unparseable date: {text!r}"
    day, month_name, year = match.groups()
    return dt.date(int(year), FRENCH_MONTHS[month_name.lower()], int(day))


class SvelteKitData:
    """Resolve SvelteKit `__data.json` index references into plain Python data."""

    def __init__(self, payload: dict):
        # The radiofrance.fr page returns one entry per layout node; node 1 holds the page data.
        self.data: list = payload["nodes"][1]["data"]

    def deref(self, value, _seen: frozenset[int] = frozenset()):
        if isinstance(value, int):
            if value == -1 or value in _seen or value >= len(self.data):
                return None
            return self.deref(self.data[value], _seen | {value})
        if isinstance(value, dict):
            return {k: self.deref(v, _seen) for k, v in value.items()}
        if isinstance(value, list):
            return [self.deref(v, _seen) for v in value]
        return value

    @property
    def root(self) -> dict:
        root = self.deref(0)
        assert isinstance(root, dict), f"Expected dict root, got {type(root).__name__}"
        return root


def fetch_listing_page(session: requests.Session, page: int) -> tuple[list[dict], bool]:
    """Return (episode metadata, whether there is another page)."""
    response = session.get(
        f"{BASE_URL}{SHOW_PATH}/__data.json",
        params={"p": page} if page > 1 else None,
    )
    response.raise_for_status()
    expressions = SvelteKitData(response.json()).root["content"]["expressions"]
    return expressions["items"], expressions["next"] is not None


def fetch_audio_url(session: requests.Session, episode_path: str) -> str | None:
    """Return the audio file URL for an episode, or None if not available."""
    response = session.get(f"{BASE_URL}{episode_path}/__data.json")
    response.raise_for_status()
    raw = response.json()["nodes"][1]["data"]
    try:
        manifestation_audio_idx = raw.index("ManifestationAudio")
    except ValueError:
        return None
    for item in raw:
        if (
            isinstance(item, dict)
            and item.get("__typename") == manifestation_audio_idx
            and "url" in item
        ):
            url_ref = item["url"]
            return raw[url_ref] if isinstance(url_ref, int) else url_ref
    return None


def save(path: pathlib.Path, episodes: list[dict]) -> None:
    episodes_sorted = sorted(episodes, key=lambda e: e["date"])
    path.write_text(
        json.dumps(episodes_sorted, indent=4, sort_keys=True, ensure_ascii=False) + "\n"
    )


def run(path: pathlib.Path) -> None:
    try:
        existing = json.loads(path.read_text())
        logger.info("Loaded %d existing episodes from %s", len(existing), path)
    except FileNotFoundError:
        logger.info("No existing file at %s, starting fresh", path)
        existing = []

    by_id: dict[str, dict] = {e["id"]: e for e in existing}

    session = requests.Session()
    session.headers["User-Agent"] = "le-jeu-des-1000-euros-indexer/1.0"

    page = 1
    stop = False
    while not stop:
        logger.info("Fetching listing page %d", page)
        items, has_next = fetch_listing_page(session, page)
        if not items:
            break
        for item in items:
            ep_id = item["id"]
            # Listings are date-ordered (newest first). The first known id means
            # everything below is already indexed, so we can stop walking.
            if ep_id in by_id:
                logger.info("Reached known episode %s, stopping listing walk", ep_id)
                stop = True
                break
            by_id[ep_id] = {
                "id": ep_id,
                "date": parse_french_date(item["publishedDate"]).isoformat(),
                "title": item["titleProps"]["title"],
                "url": BASE_URL + item["titleProps"]["href"],
                "audio_url": None,
            }
        if not has_next:
            break
        # Persist metadata each page so an interrupted bootstrap can resume
        # without re-walking pages that were already fully ingested.
        save(path, list(by_id.values()))
        page += 1

    # Persist metadata before the slow audio-URL pass, so a crash doesn't lose progress.
    save(path, list(by_id.values()))

    missing = [e for e in by_id.values() if e["audio_url"] is None]
    if not missing:
        logger.info("All %d episodes already have audio URLs", len(by_id))
        return

    logger.info("Fetching audio URLs for %d episodes", len(missing))
    for i, entry in enumerate(missing, 1):
        episode_path = entry["url"].removeprefix(BASE_URL)
        audio_url = fetch_audio_url(session, episode_path)
        entry["audio_url"] = audio_url
        logger.info(
            "[%d/%d] %s | %s | audio=%s",
            i,
            len(missing),
            entry["date"],
            entry["title"],
            "yes" if audio_url else "no",
        )
        save(path, list(by_id.values()))
        time.sleep(0.2)

    logger.info("Saved %d total episodes to %s", len(by_id), path)


if __name__ == "__main__":
    here = pathlib.Path(__file__).parent
    log_dir = here.parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "le_jeu_des_1000_euros.log"),
        ],
    )
    run(here / "episodes.json")
