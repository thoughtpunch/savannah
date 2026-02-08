#!/usr/bin/env bash
#
# ralph-beads.sh - Autonomous agent loop with beads integration
#
# Usage: ./scripts/ralph/ralph-beads.sh [options] [max_iterations]
#
# Options:
#   --debug, -d     Enable debug output (show Claude's full response)
#   --verbose, -v   Show additional loop state info
#   --dry-run       Show what would be done without running Claude
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# ── Parse arguments ──────────────────────────────────────────────
DEBUG=false
VERBOSE=false
DRY_RUN=false
MAX_ITERATIONS=10

while [[ $# -gt 0 ]]; do
    case $1 in
        --debug|-d)  DEBUG=true; shift ;;
        --verbose|-v) VERBOSE=true; shift ;;
        --dry-run)   DRY_RUN=true; shift ;;
        -*)          echo "Unknown option: $1"; exit 1 ;;
        *)           MAX_ITERATIONS=$1; shift ;;
    esac
done

LOG_FILE="ralph.log"
PROGRESS_FILE="scripts/ralph/progress.txt"

# ── Logging ──────────────────────────────────────────────────────
log()     { echo "$@" | tee -a "$LOG_FILE"; }
debug()   { $DEBUG && echo "[DEBUG] $@" | tee -a "$LOG_FILE"; }
verbose() { ($VERBOSE || $DEBUG) && echo "[INFO] $@" | tee -a "$LOG_FILE"; }

# ── Run Claude ───────────────────────────────────────────────────
run_claude() {
    local prompt="$1" output_var="$2" temp_file
    temp_file=$(mktemp)

    if $DRY_RUN; then
        log "[DRY-RUN] Would run Claude with prompt (${#prompt} chars)"
        echo "DRY_RUN_OUTPUT" > "$temp_file"
    elif $DEBUG; then
        log "─── Claude output (streaming) ───"
        echo "$prompt" | claude --dangerously-skip-permissions --print 2>&1 \
            | tee -a "$LOG_FILE" "$temp_file"
        log "─── End Claude output ───"
    else
        log -n "Running Claude"
        echo "$prompt" | claude --dangerously-skip-permissions --print \
            > "$temp_file" 2>&1 &
        local pid=$!
        while kill -0 "$pid" 2>/dev/null; do
            echo -n "." | tee -a "$LOG_FILE"; sleep 5
        done
        wait "$pid" || true
        log ""
    fi

    eval "$output_var"'=$(cat "$temp_file")'
    rm -f "$temp_file"
}

# ── Main loop ────────────────────────────────────────────────────
log ""
log "══════════════════════════════════════════"
log "  RALPH LOOP — $(basename $(pwd))"
log "  Max: $MAX_ITERATIONS iterations"
log "  Started: $(date '+%Y-%m-%d %H:%M:%S')"
log "══════════════════════════════════════════"

iteration=0
no_task_streak=0
MAX_NO_TASK_STREAK=3

while [ $iteration -lt $MAX_ITERATIONS ]; do
    ((++iteration))
    log ""
    log "━━━ Iteration $iteration / $MAX_ITERATIONS ━━━"

    # Phase 1: Check for epics needing review (all children closed)
    OPEN_EPICS=$(bd list --status open --json 2>/dev/null \
        | jq -r '[.[] | select(.issue_type == "epic") | .id] | .[]' 2>/dev/null || true)

    REVIEW_EPIC=""
    for epic_id in $OPEN_EPICS; do
        ALL_CLOSED=$(bd show "$epic_id" --json 2>/dev/null | jq -r '
            .[0].dependents // []
            | [.[] | select(.dependency_type == "parent-child")]
            | if length == 0 then "no_children"
              elif all(.status == "closed") then "all_closed"
              else "has_open" end
        ' 2>/dev/null || echo "error")
        if [ "$ALL_CLOSED" = "all_closed" ]; then
            REVIEW_EPIC="$epic_id"; break
        fi
    done

    if [ -n "$REVIEW_EPIC" ]; then
        log "Epic review: $REVIEW_EPIC (all children closed)"
        EPIC_DETAILS=$(bd show "$REVIEW_EPIC" 2>/dev/null)
        RALPH_CLAUDE=$(cat scripts/ralph/CLAUDE.md 2>/dev/null || echo "")
        PROJECT_CLAUDE=$(cat CLAUDE.md 2>/dev/null || echo "")

        PROMPT="## AUTONOMOUS MODE — EPIC REVIEW

$PROJECT_CLAUDE

---

$RALPH_CLAUDE

---

## EPIC REVIEW: $REVIEW_EPIC

$EPIC_DETAILS

---

All child tasks are closed. Review this epic holistically:
1. Check that all pieces integrate correctly
2. Run tests to verify nothing is broken
3. If everything is good, close the epic
4. If issues found, create follow-up tasks

Begin."

        run_claude "$PROMPT" OUTPUT
        bd sync 2>/dev/null || true
        continue
    fi

    # Phase 2: Find actionable task (non-epic, highest priority)
    READY_JSON=$(bd ready --json --limit 50 2>/dev/null || echo "[]")
    TASK=$(echo "$READY_JSON" | jq -r '
        [.[] | select(.issue_type == "epic" | not)
             | select((.title | startswith("Epic:")) | not)]
        | sort_by(.priority // 99) | .[0] // empty
    ')

    # Phase 3: Handle no-task state
    if [ -z "$TASK" ] || [ "$TASK" = "null" ]; then
        ((++no_task_streak))
        TOTAL=$(bd list --status open --json 2>/dev/null | jq 'length' || echo "0")
        if [ "$TOTAL" -eq 0 ]; then
            log "All tasks closed."; exit 0
        fi
        if [ "$no_task_streak" -ge "$MAX_NO_TASK_STREAK" ]; then
            log "Stuck: no actionable tasks after ${MAX_NO_TASK_STREAK} checks."
            exit 2
        fi
        sleep 2; continue
    fi

    # Phase 4: Execute task
    no_task_streak=0
    TASK_ID=$(echo "$TASK" | jq -r '.id')
    TITLE=$(echo "$TASK" | jq -r '.title')

    log "Task: $TASK_ID - $TITLE"
    echo "- $(date '+%Y-%m-%d %H:%M') | $TASK_ID | $TITLE" >> "$PROGRESS_FILE"

    TASK_DETAILS=$(bd show "$TASK_ID" 2>/dev/null)
    RALPH_CLAUDE=$(cat scripts/ralph/CLAUDE.md 2>/dev/null || echo "")
    PROJECT_CLAUDE=$(cat CLAUDE.md 2>/dev/null || echo "")

    PROMPT="## AUTONOMOUS MODE

$PROJECT_CLAUDE

---

$RALPH_CLAUDE

---

## TASK: $TASK_ID

$TASK_DETAILS

---

Begin. Follow the workflow."

    run_claude "$PROMPT" OUTPUT

    # Check exit signals
    if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
        log "All tasks complete!"; exit 0
    fi
    if echo "$OUTPUT" | grep -q "<ralph>STUCK</ralph>"; then
        log "Agent stuck. Human needed."; exit 2
    fi

    bd sync 2>/dev/null || true
    sleep 2
done

log "Max iterations reached."
exit 1
