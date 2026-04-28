#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-unknown}"
JSON=".claude_output.json"
LOGBOOK="LOGBOOK.md"

if ! jq empty "$JSON" 2>/dev/null; then
  echo "ERROR: $JSON is not valid JSON"
  cat "$JSON"
  exit 1
fi

# --verbose + --output-format json produces a JSON array; the result is the last element
RESULT_FILTER='if type == "array" then .[-1] else . end'

QUESTIONS="sources/${SOURCE}/questions.json"
DATE=$(jq -r '.[-1].source_date // empty' "$QUESTIONS" 2>/dev/null || date -u +"%Y-%m-%d")
COST=$(jq -r "($RESULT_FILTER) | .total_cost_usd // .cost_usd // 0" "$JSON")
TURNS=$(jq -r "($RESULT_FILTER) | .num_turns // 0" "$JSON")
INPUT_TOKENS=$(jq -r "($RESULT_FILTER) | .usage | (.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)" "$JSON")
OUTPUT_TOKENS=$(jq -r "($RESULT_FILTER) | .usage.output_tokens // 0" "$JSON")
DURATION_MS=$(jq -r "($RESULT_FILTER) | .duration_ms // 0" "$JSON")
SUMMARY=$(jq -r "($RESULT_FILTER) | .result // \"No summary available.\"" "$JSON")

COST_FMT=$(export LC_NUMERIC=C; printf '%.4f' "$COST")
DURATION_FMT=$(awk "BEGIN { printf \"%dm%02ds\", $DURATION_MS/60000, ($DURATION_MS%60000)/1000 }")

# Check if any code files were modified
CODE_CHANGED=$(git diff --name-only -- '*.py' '*.sh' | head -1)

ENTRY="## $DATE -- \`$SOURCE\`

- Cost: \$$COST_FMT
- Duration: $DURATION_FMT
- Turns: $TURNS
- Tokens: ${INPUT_TOKENS} input / ${OUTPUT_TOKENS} output

if [ -n "$CODE_CHANGED" ]; then
  ENTRY="$ENTRY
- Code changes: $SUMMARY"
fi

# Insert new entry after the "# Logbook" header (newest first)
if [ -f "$LOGBOOK" ]; then
  REST=$(tail -n +2 "$LOGBOOK")
  printf '# Logbook\n\n%s\n%s\n' "$ENTRY" "$REST" > "$LOGBOOK"
else
  printf '# Logbook\n\n%s\n' "$ENTRY" > "$LOGBOOK"
fi

echo "Logged run to $LOGBOOK"
