# Pub quiz flashcards

This project scrapes trivia questions from popular quiz websites. For instance I started with Thomas Eaton's [weekly quiz](https://www.theguardian.com/theguardian/series/the-quiz-thomas-eaton) in The Guardian. The aim is to provide flash cards and an interactive website to explore general knowledge.

## How it works

### Parsing

Data is scraped once a week. Each source has its own parsing script. The scripts are run with Claude Code in [headless mode](https://code.claude.com/docs/en/headless). Claude Code automatically repairs scripts when they break, or when they work but the output doesn't look correct. A pull request is open after a successful parsing, which provides an additional level of quality assurance.
