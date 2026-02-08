#!/usr/bin/env bash
set -euo pipefail
TICKET_ID="${1:-}"
[ -z "$TICKET_ID" ] && { echo "Usage: $0 <ticket-id>"; exit 1; }

ERRORS=0

# Check 1: Has a completion comment
COMMENTS=$(bd show "$TICKET_ID" --json | jq '.[0].comments // [] | length')
[ "$COMMENTS" -eq 0 ] && { echo "ERROR: No completion comment"; ERRORS=$((ERRORS+1)); }

# Check 2: Commit references ticket ID
COMMITS=$(git log --oneline --all --grep="$TICKET_ID" 2>/dev/null | wc -l | tr -d ' ')
[ "$COMMITS" -eq 0 ] && { echo "ERROR: No commit references $TICKET_ID"; ERRORS=$((ERRORS+1)); }

# Check 3: Uncommitted changes
git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null || echo "WARN: Uncommitted changes"

[ $ERRORS -gt 0 ] && { echo "BLOCKED: Fix $ERRORS error(s)"; exit 1; }
echo "READY TO CLOSE"
