.PHONY: the_guardian_weekly le_jeu_des_1000_euros wiki-entities wiki-topics wiki-card-topics annotate

CLAUDE_FLAGS = --append-system-prompt-file CLAUDE.md \
	--effort medium \
	--tools "Bash,Read,Edit,Write,Grep,Glob" \
	--no-session-persistence \
	--output-format json \
	--dangerously-skip-permissions \
	--verbose \
	--max-budget-usd 5

the_guardian_weekly:
	@jq '[.[].pairs[]?] | length' scrape/the_guardian_weekly/questions.json 2>/dev/null > .pairs_before || echo 0 > .pairs_before
	if [ -f .env ]; then set -a && . ./.env && set +a; fi && \
	claude -p "Scrape @scrape/the_guardian_weekly/SKILL.md @scrape/the_guardian_weekly/scrape.py" \
		--model haiku $(CLAUDE_FLAGS) \
		> .claude_output.json 2>.claude_stderr.log || true
	@cat .claude_stderr.log
	@LABEL=$$(jq -r '.[-1].source_date // ""' scrape/the_guardian_weekly/questions.json 2>/dev/null); \
	bash log_usage.sh the_guardian_weekly "$$LABEL"
	@rm -f .pairs_before

le_jeu_des_1000_euros:
	@set -e; \
	ROOT=scrape/le_jeu_des_1000_euros; \
	ID=$$(jq -r --slurpfile q "$$ROOT/questions.json" '($$q[0] | map(.id)) as $$ex | .[] | select(.id as $$i | $$ex | index($$i) | not) | select((.title // "") | ascii_downcase | contains("bonus") | not) | .id' "$$ROOT/episodes.json" \
		| while read id; do [ -f "$$ROOT/transcripts/$$id.json" ] && echo "$$id"; done | tail -1); \
	if [ -z "$$ID" ]; then echo "No pending transcript to extract"; exit 0; fi; \
	echo "Extracting episode $$ID..."; \
	jq '[.[].pairs[]?] | length' "$$ROOT/questions.json" 2>/dev/null > .pairs_before || echo 0 > .pairs_before; \
	if [ -f .env ]; then set -a && . ./.env && set +a; fi; \
	claude -p "Extract questions for episode $$ID. Follow @scrape/le_jeu_des_1000_euros/SKILL.md. The transcript is at scrape/le_jeu_des_1000_euros/transcripts/$$ID.json. Episode metadata (id, date, title, url) is in scrape/le_jeu_des_1000_euros/episodes.json — fetch it with jq, do not Read the whole file." \
		--model sonnet $(CLAUDE_FLAGS) \
		> .claude_output.json 2>.claude_stderr.log || true; \
	cat .claude_stderr.log; \
	LABEL=$$(jq -r --arg id "$$ID" '.[] | select(.id == $$id) | "\(.date) — \(.title)"' "$$ROOT/questions.json"); \
	bash log_usage.sh le_jeu_des_1000_euros "$$LABEL"; \
	rm -f .pairs_before

# Annotation pipeline (run in this order; each step's output is the next's input):
#   1. wiki-entities     — match question text against Wikipedia titles
#                          (writes scrape/wikipedia_annotations.json)
#   2. wiki-topics       — fetch ORES articletopic scores for every linked
#                          title (writes scrape/wikipedia_topics.json; hits
#                          LiftWing, incremental: only new titles are fetched)
#   3. wiki-card-topics  — collapse per-entity scores into one editorial topic
#                          per card (writes scrape/wikipedia_card_topics.json)
# Use `make annotate` to run the whole chain.

wiki-entities:
	uv run python scrape/build_entities.py

wiki-topics:
	uv run python scrape/build_topics.py

wiki-card-topics:
	uv run python scrape/aggregate_topics.py

annotate: wiki-entities wiki-topics wiki-card-topics
