run:
	claude -p "Scrape @sources/$(filter-out $@,$(MAKECMDGOALS))" \
		--output-format json \
		--dangerously-skip-permissions \
		--verbose \
		--max-turns 20 \
		--max-budget-usd 5 \
		> .claude_output.json 2>.claude_stderr.log || true
	@cat .claude_stderr.log
	@bash log_usage.sh $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
