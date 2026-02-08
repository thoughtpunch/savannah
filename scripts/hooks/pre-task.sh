#!/usr/bin/env bash
set -euo pipefail
TICKET_ID="${1:-}"
[ -z "$TICKET_ID" ] && { echo "Usage: $0 <ticket-id>"; exit 1; }

echo "═══ PRE-TASK: $TICKET_ID ═══"
bd show "$TICKET_ID"

# Find related open tickets by keyword
TITLE=$(bd show "$TICKET_ID" --json | jq -r '.[0].title // .title // ""')
KEYWORDS=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '\n' \
    | grep -E '^.{4,}$' | grep -vE '^(this|that|with|from|have|will|epic|task|feature)$' | head -3)

echo "RELATED TICKETS:"
for kw in $KEYWORDS; do
    RESULTS=$(bd search "$kw" --status open 2>/dev/null | grep -v "^$TICKET_ID" | head -3)
    [ -n "$RESULTS" ] && echo "  [$kw]: $RESULTS"
done
