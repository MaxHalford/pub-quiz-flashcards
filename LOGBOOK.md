# Logbook

## 2015-11-07 -- `the_guardian_weekly`

- Cost: $0.0484
- Duration: 0m22s
- Turns: 4
- Tokens: 31828 input / 352 output
- Added: 90 questions
- Code changes: The scrape ran successfully. The latest entry is from **7 November 2015** — 15 questions with properly paired Q&A, including "What links" questions grouped correctly. Everything looks good!

## 2015-10-31 -- `the_guardian_weekly`

- Cost: $0.0520
- Duration: 0m33s
- Turns: 5
- Tokens: 32773 input / 555 output
- Changes: The scrape worked perfectly. The new entry is from **2015-10-31** and contains 15 well-formed question/answer pairs:

- 8 standard questions (e.g. *"Which Communist leader was once a chef on the Newhaven-Dieppe ferry?"* → Ho Chi Minh)
- 7 "What links" questions (e.g. Pantone colours of the year, bridges over the Liffey, wine bottle sizes, etc.)

All questions and answers are correctly paired and make sense. ✅

## 2015-10-24 -- `the_guardian_weekly`

- Cost: $0.0998
- Turns: 3
- Tokens: 63113 input / 304 output
- Changes: Looks good — 15 questions and answers, all properly paired and sensible. Date is 2015-10-24, one week after the last scraped date.

## 2015-10-17 -- `the_guardian_weekly`

- Cost: $0.1445
- Turns: 6
- Tokens: 106976 input / 782 output
- Changes: Looks good — 15 Q/A pairs, all properly paired and sensible. Date is 2015-10-17, one week after the last scraped quiz.

## 2015-10-03 -- `the_guardian_weekly`

- Changes made: Fixed scrape.py parser to split on `<br/>` tags and extract full text (including `<em>` content) instead of only collecting `NavigableString` children. This fixed misaligned Q&A pairs caused by inline tags like `<em>Carcharodon carcharias</em>` being dropped. Scraped 1 quiz (2015-10-03, the oldest) from a fresh start since questions.json was deleted.
