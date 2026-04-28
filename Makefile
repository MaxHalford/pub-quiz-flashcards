run:
	set -a && . ./.env && set +a && \
	claude -p "Scrape @sources/$(filter-out $@,$(MAKECMDGOALS))/SKILL.md @sources/$(filter-out $@,$(MAKECMDGOALS))/scrape.py" \
		--bare \
		--append-system-prompt-file CLAUDE.md \
		--model haiku \
		--effort low \
		--tools "Bash,Read,Edit,Write,Grep,Glob" \
		--no-session-persistence \
		--output-format json \
		--dangerously-skip-permissions \
		--verbose \
		--max-budget-usd 5 \
		> .claude_output.json 2>.claude_stderr.log || true
	@cat .claude_stderr.log
	@bash log_usage.sh $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
