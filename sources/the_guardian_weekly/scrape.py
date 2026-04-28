import dataclasses
import datetime as dt
import json
import logging
from os import path
import pathlib
import typing

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

    def find_pages_to_scrape(self, last_scraped_date: dt.date) -> typing.Generator[str]:
        url = 'https://www.theguardian.com/theguardian/series/the-quiz-thomas-eaton?page=%d'
        done = False
        page_no = 0

        while not done:
            page_no += 1

            logger.info(f"Fetching index page {page_no}")
            response = requests.get(url % page_no)
            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            week_sections = soup.find_all('section', class_='fc-container')

            for ws in week_sections:
                ws_date = dt.datetime.strptime(ws.get('data-id'), '%d %B %Y').date()

                if ws_date <= last_scraped_date:
                    logger.info(f"Reached already-scraped date {ws_date}, stopping")
                    done = True
                    break

                ws_link = next(
                    link.get('href')
                    for link in ws.find_all('a')
                    if link.get('href', '').startswith('https://www.theguardian.com/lifeandstyle')
                )
                yield ws_link

    def scrape_page(self, url: str) -> QuestionSet:
        logger.info(f"Scraping {url}")
        ws_response = requests.get(url)
        ws_soup = bs4.BeautifulSoup(ws_response.text, 'html.parser')
        ws_date = dt.datetime.fromisoformat(
            ws_soup.find('meta', property='article:published_time')['content']
        ).date()
        ws_questions_h2 = ws_soup.find('h2', id='the-questions')
        ws_questions_p = ws_questions_h2.find_next_sibling('p')
        ws_questions = []
        what_links = False
        for child in ws_questions_p.children:
            if isinstance(child, bs4.element.Tag) and child.text.strip().lower() == 'what links':
                what_links = True
                continue
            if not isinstance(child, bs4.element.NavigableString):
                continue
            text = child.text.strip()
            if not text or text == ':':
                continue
            if what_links:
                text = f"What links: {text}"
            ws_questions.append(text)

        ws_answers_h2 = ws_soup.find('h2', id='the-answers')
        ws_answers_p = ws_answers_h2.find_next_sibling('p')
        ws_answers = [
            tag.text.strip().rstrip('.')
            for tag in ws_answers_p.children
            if isinstance(tag, bs4.element.NavigableString)
        ]
        ws_question_answers = dict(zip(ws_questions, ws_answers))

        question_set = QuestionSet(
            pairs=[QuestionAnswerPair(q, a) for q, a in ws_question_answers.items()],
            source_url=url,
            source_date=ws_date,
        )
        return question_set

    def run(self) -> None:

        # Load existing questions, so that we can append to them.
        try:
            questions = json.load(pathlib.Path(self.path).open())
            logger.info(f"Loaded {len(questions)} existing question sets from {self.path}")
        except FileNotFoundError:
            logger.info(f"No existing file found at {self.path}, starting fresh")
            questions = []

        # Determine the date of the most recently scraped quiz, so that we only scrape new quizzes.
        last_scraped_date = max(dt.date.fromisoformat(q['source_date']) for q in questions) if questions else dt.date.min
        logger.info(f"Last scraped date: {last_scraped_date}")

        for url in self.find_pages_to_scrape(last_scraped_date):
            question_set = self.scrape_page(url)
            questions.append(question_set)

            # Save after each scrape, so that if the script is interrupted, we don't lose progress.
            pathlib.Path(self.path).write_text(json.dumps(questions, indent=4, sort_keys=True))
            logger.info(f"Saved {len(questions)} question sets to {self.path}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    here = pathlib.Path(__file__).parent
    parser = TheGuardianParser(here / 'questions.json')
    parser.run()
