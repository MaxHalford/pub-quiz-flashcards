---
name: lejeudes1000euros
description: Extract trivia questions and answers from a transcribed episode of France Inter's "Le jeu des 1000 euros"
---

Your goal is to extract trivia Q/A pairs from one transcribed episode of "Le jeu des 1000 euros" and append them to the aggregated `scrape/le_jeu_des_1000_euros/questions.json`.

# Hard rules — read carefully

- **Do not `Read` this `SKILL.md` file.** Its content is already in your prompt via `@`.
- **Do not `cd` in `Bash` commands.** The shell's working directory persists between calls, which silently breaks subsequent relative-path commands. Always use repo-rooted paths like `scrape/le_jeu_des_1000_euros/questions.json`.
- **Do not `Read` `episodes.json`** (3000+ entries, ~1.3 MB). Use a targeted `jq` filter instead.

# Input

The episode id to process is given to you in the prompt. To get its metadata, use `jq` against `scrape/le_jeu_des_1000_euros/episodes.json` — **never `Read` that file whole** (3000+ entries, ~1.3 MB):

```bash
jq --arg id "<id>" '.[] | select(.id == $id)' scrape/le_jeu_des_1000_euros/episodes.json
```

The transcript text is at `scrape/le_jeu_des_1000_euros/transcripts/<id>.json` (top-level `"text"` field). You do not need to re-`Read` this `SKILL.md` — its content is already in your prompt via the `@` reference.

# Show format

The show is a French radio trivia quiz broadcast live on France Inter from a different town each week (currently hosted by Nicolas Stoufflet). The host poses questions to two contestants in tiers of increasing difficulty:

- **bleue** — easiest
- **blanche** — medium
- **rouge** — hard
- **banco** — high-stakes single question, played near the end
- **super-banco** — rare, highest tier

The host announces each tier explicitly ("question bleue", "à 100 euros, question blanche"). After contestants answer, the host confirms the correct answer, often with cultural context.

# What to extract

For the chosen episode, build a JSON object with these fields, matching the metadata in `episodes.json`:

- `"id"` (string): the episode id.
- `"date"` (string): the episode date.
- `"title"` (string): the episode title.
- `"url"` (string): the source URL.
- `"pairs"` (array): one object per distinct question, each with:
  - `"question"` (string, French): the question itself.
  - `"answer"` (string or null, French): the correct answer as confirmed by the host. Use `null` if no canonical answer is stated.
  - `"tier"` (string or null): one of `"bleue"`, `"blanche"`, `"rouge"`, `"banco"`, `"super-banco"`, or `null` if the tier wasn't stated.

Include questions even when the answer is missing — they can be filled in manually later.

# Rephrasing is encouraged

Whisper transcripts are noisy: disfluencies, run-on sentences, missing punctuation, occasional misrecognitions. **You may and should rephrase both questions and answers so they read as clean, standalone quiz items that can be shown to end users in a quiz game.**

- Restore punctuation and capitalization.
- Drop disfluencies ("euh", "alors", "voilà"), audience reactions, host filler, contestant interjections.
- If the host's setup spans several sentences, condense it into one well-formed question.
- For the answer, keep only the canonical fact the host confirms — drop the explanatory aside.
- Stay faithful to the transcript. Do **not** invent facts, dates, or names not present in it.
- Use the canonical spelling for proper names, even if the transcript misspells them (e.g. "George Sand", not "Georges Sand"; "Édith Piaf", not "Edith Piaf"). Whisper frequently mangles names.

The bar: a French speaker reading any single `{question, answer}` pair on its own should immediately understand it as a self-contained trivia item.

# What to skip

- Opening and closing jingles, the "France Inter" station ID, and the recurring Whisper artifact `"Sous-titrage Société Radio-Canada"`.
- Greetings, sponsor mentions, contestant introductions (where they're from, what they do), audience banter, music interludes.
- The host's elaboration after the answer (cultural context, anecdotes) — keep only the canonical answer itself.
- Transition chatter between rounds.

# Saving

Append the new episode entry to `scrape/le_jeu_des_1000_euros/questions.json`, then re-sort the array by `date` ascending. Preserve all existing entries unchanged. Write the file as pretty-printed JSON (2-space indent, `ensure_ascii=False`), with a trailing newline. Validate the result is parseable JSON before exiting.

**Do not** shell out to Python heredocs for this — use `jq` or the `Write` tool directly. One efficient pattern, given a file `/tmp/entry.json` you've written with the new episode object:

```bash
ROOT=scrape/le_jeu_des_1000_euros
jq --slurpfile new /tmp/entry.json '. + $new | sort_by(.date)' "$ROOT"/questions.json > "$ROOT"/questions.json.tmp
mv "$ROOT"/questions.json.tmp "$ROOT"/questions.json
```

When done, your final message should be a single line stating what you did (e.g. `Added 9 questions for episode <id> (<date>).`). No celebratory prose, no summary tables, no bullet lists — those just bloat the logbook.
