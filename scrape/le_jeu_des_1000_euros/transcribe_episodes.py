"""Transcribe France Inter's "Le jeu des 1000 euros" audio files with Whisper.

For each episode in `episodes.json` that has an audio URL, the MP3 is downloaded
to a temporary file and transcribed with MLX Whisper. The result (full text and
per-segment timestamps) is written to `transcripts/<id>.json` next to this file.

The script is idempotent: episodes whose transcript file already exists are
skipped. Pass `--id <episode-id>` to transcribe just one episode, or `--next`
to transcribe only the newest untranscribed episode.
"""

import argparse
import json
import logging
import pathlib
import tempfile

import mlx_whisper
import requests

logger = logging.getLogger(__name__)

MODEL = "mlx-community/whisper-large-v3-turbo"

# Titles containing any of these substrings are skipped — they are weekend
# promos / best-of compilations rather than real game episodes.
SKIP_TITLE_SUBSTRINGS = ("bonus",)


def is_game_episode(episode: dict) -> bool:
    title = (episode.get("title") or "").lower()
    return not any(s in title for s in SKIP_TITLE_SUBSTRINGS)


def download(session: requests.Session, url: str, dest: pathlib.Path) -> None:
    with session.get(url, stream=True) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 16):
                f.write(chunk)


def transcribe(audio_path: pathlib.Path) -> dict:
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=MODEL,
        language="fr",
    )
    return {
        "text": result["text"],
        "segments": [
            {
                "start": round(s["start"], 2),
                "end": round(s["end"], 2),
                "text": s["text"],
            }
            for s in result["segments"]
        ],
    }


def run(
    episodes_path: pathlib.Path,
    transcripts_dir: pathlib.Path,
    questions_path: pathlib.Path,
    episode_id: str | None,
    only_next: bool,
    skip: int,
) -> None:
    episodes = json.loads(episodes_path.read_text())
    if episode_id is not None:
        episodes = [e for e in episodes if e["id"] == episode_id]
        if not episodes:
            raise SystemExit(f"No episode with id {episode_id!r}")

    extracted_ids: set[str] = set()
    if questions_path.exists():
        extracted_ids = {e["id"] for e in json.loads(questions_path.read_text())}

    transcripts_dir.mkdir(exist_ok=True)
    todo = [
        e
        for e in episodes
        if e["audio_url"]
        and is_game_episode(e)
        and not (transcripts_dir / f"{e['id']}.json").exists()
        and e["id"] not in extracted_ids
    ]
    if only_next:
        # episodes.json is sorted by date ascending — last pending = newest.
        todo = todo[-1:]
    elif skip:
        todo = todo[skip:]
    if not todo:
        logger.info("Nothing to transcribe")
        return

    session = requests.Session()
    session.headers["User-Agent"] = "le-jeu-des-1000-euros-transcriber/1.0"

    for i, ep in enumerate(todo, 1):
        logger.info(
            "[%d/%d] %s | %s | %s",
            i,
            len(todo),
            ep["id"],
            ep["date"],
            ep["title"],
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
            tmp_path = pathlib.Path(tmp.name)
            download(session, ep["audio_url"], tmp_path)
            result = transcribe(tmp_path)
        out = transcripts_dir / f"{ep['id']}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        logger.info("Wrote %s (%d segments)", out, len(result["segments"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--id", help="Transcribe only the episode with this id")
    selector.add_argument(
        "--next",
        action="store_true",
        help="Transcribe only the newest untranscribed episode",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Skip the first N items of the TODO list (for parallel runs)",
    )
    args = parser.parse_args()

    here = pathlib.Path(__file__).parent
    log_dir = here.parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "le_jeu_des_1000_euros_transcribe.log"),
        ],
    )

    run(
        here / "episodes.json",
        here / "transcripts",
        here / "questions.json",
        args.id,
        args.next,
        args.skip,
    )
