#!/usr/bin/env bash
#
# extract_followups.sh — Mine closed tickets for deferred work
#
# Usage:
#   ./scripts/extract_followups.sh         # Human-readable report
#   ./scripts/extract_followups.sh --json  # JSON output
#
set -euo pipefail

JSON_MODE=false
[ "${1:-}" = "--json" ] && JSON_MODE=true

CLOSED=$(bd list --status closed --json 2>/dev/null || echo "[]")
COUNT=$(echo "$CLOSED" | jq 'length')

if [ "$COUNT" -eq 0 ]; then
    echo "No closed tickets found."
    exit 0
fi

if $JSON_MODE; then
    echo "$CLOSED" | jq '[.[] | {
        id: .id,
        title: .title,
        comments: [.comments[]? | select(
            (.body | test("Left undone"; "i")) or
            (.body | test("Gotchas"; "i"))
        ) | .body]
    } | select(.comments | length > 0)]'
else
    echo "═══ FOLLOW-UP WORK FROM CLOSED TICKETS ═══"
    echo ""

    echo "$CLOSED" | jq -r '.[] | "\(.id)\t\(.title)"' | while IFS=$'\t' read -r id title; do
        DETAILS=$(bd show "$id" --json 2>/dev/null || echo "[]")
        FOLLOWUPS=$(echo "$DETAILS" | jq -r '
            .[0].comments // [] | .[] | .body // ""
            | select(test("Left undone|Gotchas"; "i"))
        ' 2>/dev/null || true)

        if [ -n "$FOLLOWUPS" ]; then
            echo "── $id: $title ──"
            echo "$FOLLOWUPS"
            echo ""
        fi
    done
fi
