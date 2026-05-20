#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-unknown}"
LABEL="${2:-}"
JSON=".claude_output.json"
STDERR=".claude_stderr.log"
PAIRS_BEFORE_FILE=".pairs_before"
LOGBOOK="LOGBOOK.md"

if ! jq empty "$JSON" 2>/dev/null; then
  echo "ERROR: $JSON is not valid JSON"
  cat "$JSON"
  exit 1
fi

# --verbose + --output-format json produces a JSON array; the result is the last element.
RESULT_FILTER='if type == "array" then .[-1] else . end'

QUESTIONS_FILE="scrape/${SOURCE}/questions.json"

# Number of question pairs added by this run.
BEFORE=$(cat "$PAIRS_BEFORE_FILE" 2>/dev/null || echo 0)
AFTER=$(jq '[.[].pairs[]?] | length' "$QUESTIONS_FILE" 2>/dev/null || echo 0)
ADDED=$((AFTER - BEFORE))

# Session metrics.
MODEL=$(jq -r '[.[] | select(.type=="assistant") | .message.model] | .[0] // "unknown"' "$JSON")
COST=$(jq -r "($RESULT_FILTER) | .total_cost_usd // .cost_usd // 0" "$JSON")
TURNS=$(jq -r "($RESULT_FILTER) | .num_turns // 0" "$JSON")
INPUT_TOKENS=$(jq -r "($RESULT_FILTER) | .usage | (.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)" "$JSON")
OUTPUT_TOKENS=$(jq -r "($RESULT_FILTER) | .usage.output_tokens // 0" "$JSON")
DURATION_MS=$(jq -r "($RESULT_FILTER) | .duration_ms // 0" "$JSON")

COST_FMT=$(export LC_NUMERIC=C; printf '%.4f' "$COST")
DURATION_FMT=$(awk "BEGIN { printf \"%dm%02ds\", $DURATION_MS/60000, ($DURATION_MS%60000)/1000 }")

# Hiccups: tool-call errors, session-level error flag, non-empty stderr.
TOOL_ERRORS=$(jq '[.[] | select(.type=="user") | .message.content[]? | select(.type=="tool_result" and .is_error == true)] | length' "$JSON" 2>/dev/null || echo 0)
SESSION_ERROR=$(jq -r "($RESULT_FILTER) | .is_error // false" "$JSON")
STDERR_BYTES=$(wc -c < "$STDERR" 2>/dev/null | tr -d ' ' || echo 0)

HICCUPS=""
[ "$SESSION_ERROR" = "true" ] && HICCUPS="session ended with error"
if [ "$TOOL_ERRORS" -gt 0 ]; then
  [ -n "$HICCUPS" ] && HICCUPS="$HICCUPS; "
  HICCUPS="${HICCUPS}${TOOL_ERRORS} tool error(s)"
fi
if [ "$STDERR_BYTES" -gt 0 ]; then
  [ -n "$HICCUPS" ] && HICCUPS="$HICCUPS; "
  HICCUPS="${HICCUPS}stderr non-empty"
fi

[ -z "$LABEL" ] && LABEL=$(date -u +"%Y-%m-%d %H:%MZ")

ENTRY="## $LABEL -- \`$SOURCE\`

- Model: $MODEL
- Questions added: $ADDED
- Duration: $DURATION_FMT
- Cost: \$$COST_FMT
- Turns: $TURNS
- Tokens: ${INPUT_TOKENS} input / ${OUTPUT_TOKENS} output"

[ -n "$HICCUPS" ] && ENTRY="$ENTRY
- Hiccups: $HICCUPS"

# Insert new entry after the "# Logbook" header (newest first).
if [ -f "$LOGBOOK" ]; then
  REST=$(tail -n +2 "$LOGBOOK")
  printf '# Logbook\n\n%s\n%s\n' "$ENTRY" "$REST" > "$LOGBOOK"
else
  printf '# Logbook\n\n%s\n' "$ENTRY" > "$LOGBOOK"
fi

echo "Logged run to $LOGBOOK"
