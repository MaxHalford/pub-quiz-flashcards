import dataclasses
import datetime as dt
import json
import logging
import pathlib
import re

import bs4
import requests

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class QuestionAnswerPair:
    question: str
    answer: str


@dataclasses.dataclass
class QuestionSet:
    pairs: list[QuestionAnswerPair]
    source_url: str
    source_date: dt.date


class TheGuardianParser:
    def __init__(self, path: pathlib.Path):
        self.path = path

    def get_next_page(self, last_scraped_date: dt.date) -> tuple[dt.date, str] | None:
        """Return the oldest unscraped page, or None if everything is up to date."""
        url_template = "https://www.theguardian.com/theguardian/series/the-quiz-thomas-eaton?page=%d"
        candidates: list[tuple[dt.date, str]] = []
        seen_urls: set[str] = set()
        page_no = 0
        done = False

        while not done:
            page_no += 1

            response = requests.get(url_template % page_no)
            soup = bs4.BeautifulSoup(response.text, "html.parser")

            quiz_links = []
            for link in soup.find_all("a"):
                href = str(link.get("href", ""))
                if (
                    href.startswith("/lifeandstyle/")
                    and "quiz" in href
                    and "#" not in href
                ):
                    full_url = "https://www.theguardian.com" + href
                    if full_url not in seen_urls:
                        quiz_links.append(full_url)
                        seen_urls.add(full_url)

            if not quiz_links:
                logger.info(f"No quiz links found on page {page_no}, stopping")
                break

            for link in quiz_links:
                parts = link.split("/")
                # Some older URLs have /article/ before the date segments
                date_start = 5 if "article" in parts else 4
                year = int(parts[date_start])
                month = dt.datetime.strptime(parts[date_start + 1], "%b").month
                day = int(parts[date_start + 2])
                link_date = dt.date(year, month, day)

                if link_date <= last_scraped_date:
                    logger.info(f"Reached already-scraped date {link_date}, stopping")
                    done = True
                    break

                candidates.append((link_date, link))

        if not candidates:
            return None
        return min(candidates, key=lambda x: x[0])

    @staticmethod
    def _split_on_br(p_tag: bs4.element.Tag) -> list[str]:
        """Split a <p> tag's contents by <br/> into text segments."""
        segments: list[str] = []
        current: list[str] = []
        for child in p_tag.children:
            if isinstance(child, bs4.element.Tag) and child.name == "br":
                segments.append("".join(current).strip())
                current = []
            else:
                current.append(child.get_text())
        segments.append("".join(current).strip())
        return [s for s in segments if s]

    @staticmethod
    def _strip_number_prefix(text: str) -> str:
        """Remove a leading number like '1 ' or '9 ' from text."""
        return re.sub(r"^\d+\s+", "", text)

    def scrape_page(self, url: str) -> list[QuestionAnswerPair]:
        logger.info(f"Scraping {url}")
        response = requests.get(url)
        soup = bs4.BeautifulSoup(response.text, "html.parser")

        questions_h2 = soup.find("h2", id="the-questions")
        assert questions_h2 is not None
        questions_p = questions_h2.find_next_sibling("p")
        assert questions_p is not None

        raw_questions = self._split_on_br(questions_p)
        questions = []
        what_links = False
        for raw in raw_questions:
            text = self._strip_number_prefix(raw)
            if text.lower().startswith("what links"):
                what_links = True
                # The number for the first "what links" question may be on the
                # same line (e.g. "What links:\n  9 ...") or the next segment.
                rest = re.sub(r"^what links:?\s*", "", text, flags=re.IGNORECASE)
                rest = self._strip_number_prefix(rest)
                if rest:
                    questions.append(f"What links: {rest}")
                continue
            if what_links:
                text = f"What links: {text}"
            questions.append(text)

        answers_h2 = soup.find("h2", id="the-answers")
        assert answers_h2 is not None
        answers_p = answers_h2.find_next_sibling("p")
        assert answers_p is not None

        answers = [
            self._strip_number_prefix(s).rstrip(".")
            for s in self._split_on_br(answers_p)
        ]

        assert len(questions) == len(answers), (
            f"Mismatch: {len(questions)} questions vs {len(answers)} answers"
        )
        return [QuestionAnswerPair(q, a) for q, a in zip(questions, answers)]

    def run(self) -> None:

        # Load existing questions, so that we can append to them.
        try:
            questions = json.load(pathlib.Path(self.path).open())
            logger.info(
                f"Loaded {len(questions)} existing question sets from {self.path}"
            )
        except FileNotFoundError:
            logger.info(f"No existing file found at {self.path}, starting fresh")
            questions = []

        # Determine the date of the most recently scraped quiz, so that we only scrape new quizzes.
        last_scraped_date = (
            max(dt.date.fromisoformat(q["source_date"]) for q in questions)
            if questions
            else dt.date.min
        )
        logger.info(f"Last scraped date: {last_scraped_date}")

        result = self.get_next_page(last_scraped_date)
        if result is None:
            logger.info("Nothing new to scrape")
            return

        source_date, source_url = result
        question_answers = self.scrape_page(source_url)
        question_set = QuestionSet(
            pairs=question_answers,
            source_url=source_url,
            source_date=source_date,
        )
        questions.append(dataclasses.asdict(question_set))

        pathlib.Path(self.path).write_text(
            json.dumps(questions, indent=4, sort_keys=True, default=str)
        )
        logger.info(f"Saved {len(questions)} question sets to {self.path}")


if __name__ == "__main__":
    here = pathlib.Path(__file__).parent
    log_dir = here.parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "the_guardian_weekly.log"),
        ],
    )

    parser = TheGuardianParser(here / "questions.json")
    parser.run()
