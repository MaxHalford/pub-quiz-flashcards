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
        """Split a <p> tag's contents by <br/> and numbered items into text segments."""
        # Use HTML-based splitting for robustness against malformed HTML
        # where <br> tags might not be properly closed
        html_str = str(p_tag)
        # Remove the p tag wrapper
        html_str = re.sub(r"^<p[^>]*>|</p>$", "", html_str)
        # Split by <br> with optional / and optional attributes
        parts = re.split(r"<br\s*/?.*?>", html_str)
        # Extract text from each HTML fragment and further split on numbered items
        segments: list[str] = []
        for part in parts:
            # Split on <strong>N</strong> patterns to handle multiple numbered items
            # without explicit line breaks between them
            items = re.split(r"<strong>\d+</strong>", part)
            for item in items:
                soup = bs4.BeautifulSoup(item, "html.parser")
                text = soup.get_text().strip()
                if text:
                    # Re-add the number prefix that was stripped
                    segments.append(text)
        return segments

    @staticmethod
    def _strip_number_prefix(text: str) -> str:
        """Remove a leading number like '1 ' or '9 ' from text."""
        return re.sub(r"^\d+\s*", "", text)

    def scrape_page(self, url: str) -> list[QuestionAnswerPair]:
        logger.info(f"Scraping {url}")
        response = requests.get(url)
        soup = bs4.BeautifulSoup(response.text, "html.parser")

        # Try to find the questions h2 first (present in many formats)
        questions_h2 = soup.find("h2", id="the-questions")
        # Look for answers h2 with either id (varies by page)
        answers_h2 = soup.find("h2", id="the-answers") or soup.find("h2", id="answers")

        # If no h2 sections, look for paragraphs starting with "The questions" / "The answers"
        if not questions_h2 and not answers_h2:
            article = soup.find("article") or soup
            for p in article.find_all("p"):
                p_text = p.get_text().strip()
                if p_text.lower().startswith("the questions"):
                    questions_h2 = p
                elif p_text.lower().startswith("the answers"):
                    answers_h2 = p

        questions_p = None
        if questions_h2:
            # If questions_h2 is actually a p tag (old format), use it directly
            if questions_h2.name == "p":
                questions_p = questions_h2
            else:
                questions_p = questions_h2.find_next_sibling("p")
            assert questions_p is not None

            raw_questions = self._split_on_br(questions_p)
            # Remove "The questions" prefix from the first item if present
            if raw_questions and raw_questions[0].lower().startswith("the questions"):
                raw_questions[0] = re.sub(
                    r"^the questions\s*", "", raw_questions[0], flags=re.IGNORECASE
                )
            questions = []
            what_links = False
            for raw in raw_questions:
                text = self._strip_number_prefix(raw)
                # Skip "The questions" header or empty text
                if not text or text.lower().startswith("the questions"):
                    continue
                if text.lower().startswith("what links"):
                    what_links = True
                    rest = re.sub(r"^what links:?\s*", "", text, flags=re.IGNORECASE)
                    rest = self._strip_number_prefix(rest)
                    if rest:
                        questions.append(f"What links: {rest}")
                    continue
                if what_links:
                    text = f"What links: {text}"
                questions.append(text)

            # Look for additional "What links" paragraphs after main questions
            current = questions_p
            while current:
                current = current.find_next_sibling("p")
                if current == answers_h2 or current is None:
                    break
                p_text = current.get_text().strip()
                if p_text.lower().startswith("what links"):
                    raw_what_links = self._split_on_br(current)
                    for raw in raw_what_links:
                        text = self._strip_number_prefix(raw)
                        if text.lower().startswith("what links"):
                            text = re.sub(
                                r"^what links:?\s*",
                                "",
                                text,
                                flags=re.IGNORECASE,
                            )
                            text = self._strip_number_prefix(text)
                        if text:
                            questions.append(f"What links: {text}")
        else:
            # New format without h2 headers: look for numbered paragraphs
            questions = []
            # If answers_h2 is None, find paragraphs that start with numbers
            if answers_h2 is None:
                article = soup.find("article") or soup
                number_paras = []
                for p in article.find_all("p"):
                    p_text = p.get_text().strip()
                    if p_text and p_text[0].isdigit():
                        number_paras.append(p)
                if number_paras:
                    # First numbered paragraph is questions, second is answers
                    questions_h2 = number_paras[0]
                    answers_h2 = number_paras[1] if len(number_paras) > 1 else None

            current = answers_h2
            question_paras = []
            while current:
                current = current.find_previous_sibling("p")
                if current is None:
                    break
                p_text = current.get_text().strip()
                if (
                    p_text
                    and not p_text[0].isdigit()
                    and not p_text.lower().startswith("what links")
                ):
                    break
                question_paras.append(current)

            # Process paragraphs in reverse order (oldest to newest)
            what_links = False
            for para in reversed(question_paras):
                p_text = para.get_text().strip()
                # Check if this paragraph contains line breaks (multi-question format)
                if "<br" in str(para):
                    raw_questions = self._split_on_br(para)
                    for raw in raw_questions:
                        text = self._strip_number_prefix(raw)
                        if text.lower().startswith("what links"):
                            what_links = True
                            rest = re.sub(
                                r"^what links:?\s*",
                                "",
                                text,
                                flags=re.IGNORECASE,
                            )
                            rest = self._strip_number_prefix(rest)
                            if rest:
                                questions.append(f"What links: {rest}")
                            continue
                        if what_links:
                            text = f"What links: {text}"
                        if text:
                            questions.append(text)
                else:
                    # Single question per paragraph format
                    if p_text.lower() == "what links:":
                        what_links = True
                    else:
                        text = self._strip_number_prefix(p_text)
                        if text.lower().startswith("what links"):
                            what_links = True
                            rest = re.sub(
                                r"^what links:?\s*",
                                "",
                                text,
                                flags=re.IGNORECASE,
                            )
                            rest = self._strip_number_prefix(rest)
                            if rest:
                                questions.append(f"What links: {rest}")
                        else:
                            if what_links:
                                text = f"What links: {text}"
                            if text:
                                questions.append(text)

        answers_paragraphs = []
        if answers_h2:
            # If answers_h2 is a p tag (old format), include it as first answers paragraph
            if answers_h2.name == "p":
                answers_paragraphs.append(answers_h2)
            # Collect subsequent answer paragraphs
            for p in answers_h2.find_next_siblings("p"):
                p_text = p.get_text().strip()
                if not p_text:
                    break
                if p_text[0].isdigit():
                    answers_paragraphs.append(p)
        elif questions_h2:
            # No answers h2, but have questions h2, look for answers after it
            current = questions_p
            while current:
                current = current.find_next_sibling("p")
                if current is None:
                    break
                p_text = current.get_text().strip()
                if not p_text:
                    continue
                # Look for answers paragraph
                if p_text.lower().startswith("the answers"):
                    # Skip "The answers" header and get the actual answers
                    current = current.find_next_sibling("p")
                    if current:
                        p_text = current.get_text().strip()
                        if p_text and p_text[0].isdigit():
                            answers_paragraphs.append(current)
                    break
                # Take the first non-empty paragraph as answers
                if p_text[0].isdigit():
                    answers_paragraphs.append(current)
                    break
        assert answers_paragraphs, "No answer paragraphs found"

        raw_answers = []
        for answers_p in answers_paragraphs:
            raw_answers.extend(self._split_on_br(answers_p))
        answers = []
        for s in raw_answers:
            # Skip header-only segments like "The Answers"
            if s.lower().strip() in ("the answers", "answers"):
                continue
            # For the first real answer, strip "The Answers" prefix if present
            if not answers:
                s = re.sub(r"^the answers\s+", "", s, flags=re.IGNORECASE)
            answer = self._strip_number_prefix(s).rstrip(".")
            if answer:
                answers.append(answer)

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
