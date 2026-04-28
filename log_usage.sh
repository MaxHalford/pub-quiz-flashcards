#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-unknown}"
JSON=".claude_output.json"
README="README.md"

if ! jq empty "$JSON" 2>/dev/null; then
  echo "ERROR: $JSON is not valid JSON"
  cat "$JSON"
  exit 1
fi

DATE=$(date -u +"%Y-%m-%d")
COST=$(jq -r '.cost_usd // 0' "$JSON")
TURNS=$(jq -r '.num_turns // 0' "$JSON")
DURATION_MS=$(jq -r '.duration_ms // 0' "$JSON")
IS_ERROR=$(jq -r '.is_error // false' "$JSON")

COST_FMT=$(printf '%.4f' "$COST")
DURATION_S=$(awk "BEGIN {printf \"%.1f\", $DURATION_MS / 1000}")

if [ "$IS_ERROR" = "true" ]; then
  STATUS="fail"
else
  STATUS="ok"
fi

ROW="| $DATE | $SOURCE | \$$COST_FMT | $TURNS | ${DURATION_S}s | $STATUS |"

if grep -q "<!-- TOKEN_USAGE_TABLE_END -->" "$README"; then
  sed -i.bak "/<!-- TOKEN_USAGE_TABLE_END -->/i\\
$ROW" "$README"
  rm -f README.md.bak
else
  echo "ERROR: Missing <!-- TOKEN_USAGE_TABLE_END --> marker in $README"
  exit 1
fi

echo "Logged: $ROW"
