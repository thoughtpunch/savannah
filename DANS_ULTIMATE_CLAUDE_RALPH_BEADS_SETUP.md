# Dan's Ultimate Claude + Ralph + Beads Setup Guide

> A battle-tested autonomous AI development setup combining Claude Code, a custom Ralph loop, and Beads issue tracking. This guide documents the setup that built claudetube (40 MCP tools, provider system, scene analysis, playlist navigation) — largely through autonomous agent loops.

---

## Table of Contents

1. [Philosophy & Architecture](#philosophy--architecture)
2. [Ralph: frankbria/ralph-claude-code vs Custom Script](#ralph-frankbriaralph-claude-code-vs-custom-script)
3. [Prerequisites](#prerequisites)
4. [Project Setup (Step by Step)](#project-setup-step-by-step)
5. [Beads Configuration](#beads-configuration)
6. [The Ralph Loop Script](#the-ralph-loop-script)
7. [CLAUDE.md — Teaching Claude How to Work](#claudemd--teaching-claude-how-to-work)
8. [Ralph's CLAUDE.md — The Agent's Playbook](#ralphs-claudemd--the-agents-playbook)
9. [Claude Code Hooks](#claude-code-hooks)
10. [Permissions & Settings](#permissions--settings)
11. [Helper Scripts](#helper-scripts)
12. [Running the Loop](#running-the-loop)
13. [Monitoring & Debugging](#monitoring--debugging)
14. [Patterns That Work](#patterns-that-work)
15. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
16. [Quick-Start Checklist](#quick-start-checklist)

---

## Philosophy & Architecture

This setup rests on three pillars:

| Pillar | Tool | Role |
|--------|------|------|
| **Brain** | Claude Code (`claude --print`) | Does the actual coding, testing, committing |
| **Scheduler** | Ralph loop (bash script) | Picks the next task, feeds it to Claude, detects stuck/done |
| **Memory** | Beads (`bd`) | Persistent issue tracker with dependencies, comments, sync |

**Why this combination works:**

- **Claude Code** is stateless between invocations. It forgets everything after each call.
- **Beads** provides the persistent memory — tickets survive across sessions, carry context in comments, and track what's done vs blocked.
- **Ralph** is the glue — a simple bash loop that reads from beads, constructs a prompt, calls Claude, syncs state, and repeats.

The result: you can `./scripts/ralph/ralph-beads.sh 20` and walk away. When you come back, 15 tickets are closed, code is committed, and the progress log tells you what happened.

---

## Ralph: frankbria/ralph-claude-code vs Custom Script

### What frankbria/ralph-claude-code Offers

The [ralph-claude-code](https://github.com/frankbria/ralph-claude-code) library (v0.11.4) is a full-featured autonomous loop framework:

**Strengths:**
- Global installation (`ralph`, `ralph-monitor`, `ralph-setup`, `ralph-enable`)
- Modular library system (circuit breaker, response analyzer, date/timeout utils)
- Intelligent exit detection with dual-condition checking (completion indicators + explicit EXIT_SIGNAL)
- Session continuity across loop iterations (`--continue` flag)
- Rate limiting (configurable calls/hour with automatic reset)
- Circuit breaker pattern (no-progress, same-error, output-decline thresholds)
- 5-hour API limit handling with wait-or-exit choice
- Live monitoring via tmux integration (`ralph --monitor`)
- JSON output format parsing from Claude CLI
- `ralph-enable` wizard that auto-detects project type and imports from beads/GitHub/PRDs
- `ralph-import` to convert requirement docs into Ralph format
- `.ralphrc` per-project configuration
- 490 tests, actively maintained

**Weaknesses (for our use case):**
- **Task tracking is file-based** (`.ralph/fix_plan.md` with checkboxes) — no dependency graph, no structured metadata, no comments
- **Heavyweight** — full npm project, libraries in `~/.ralph/lib/`, global PATH additions
- **Prompt is monolithic** — PROMPT.md + RALPH_STATUS block approach requires Claude to output structured status blocks, adding prompt overhead
- **No beads integration in the loop itself** — `ralph-enable --from beads` imports tasks once, but doesn't read from beads on each iteration
- **Completion detection is heuristic** — relies on parsing natural language for "completion indicators" plus an explicit EXIT_SIGNAL block from Claude
- **Overkill for focused workflows** — circuit breaker, rate limiting, and session management add complexity that matters for long unattended runs but not for supervised 10-20 iteration bursts

### What the Custom Script Offers

The `ralph-beads.sh` script used in this project is ~365 lines of bash:

**Strengths:**
- **Beads-native** — reads `bd ready` on every iteration, picks highest-priority unblocked task
- **Simple** — no libraries, no npm, no global install, no session management
- **Dependency-aware** — respects beads dependency graph (blocked tasks are skipped)
- **Epic lifecycle** — auto-detects when all children of an epic are closed, triggers holistic review
- **Orphan cleanup** — auto-closes epics with no children when no other work remains
- **Structured comments** — approach comments before work, completion comments after, all in beads
- **Progress log** — simple append-only text file tracking what was done and when
- **Lightweight exit detection** — `<promise>COMPLETE</promise>` and `<ralph>STUCK</ralph>` signals (no heuristic parsing)
- **Works with any project** — just needs `bd` and `claude` on PATH

**Weaknesses:**
- No rate limiting (relies on Claude's own limits)
- No circuit breaker (uses a simple no-task streak counter instead)
- No session continuity (each iteration is a fresh `claude --print` call)
- No tmux monitoring (just a log file and progress.txt)
- No JSON output parsing from Claude CLI
- No automatic recovery from API limits

### Recommendation

**Use the custom `ralph-beads.sh` approach** for new projects. Here's why:

1. **Beads is the better task system** — dependencies, comments, priorities, epics, search, daemon sync. `fix_plan.md` checkboxes can't compete.
2. **Simplicity wins** — 365 lines of bash you can read in 5 minutes vs a multi-file library system you need to debug.
3. **The loop is not the hard part** — the hard part is the CLAUDE.md and ralph-specific CLAUDE.md that teach the agent how to behave. That's where the real value is.
4. **Cherry-pick from Ralph library if needed** — if you need rate limiting or circuit breaker, extract those ~100 lines from `lib/circuit_breaker.sh` and add them to your script.

You can always install `ralph-claude-code` globally alongside this setup and use `ralph-enable --from beads` as a one-time import if you want its project scaffolding.

---

## Prerequisites

Install these before starting:

```bash
# Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Beads issue tracker
# See: https://github.com/dbbring/beads (or wherever bd is distributed)
# Ensure `bd` is on your PATH

# Optional but recommended
brew install jq      # JSON processing (used in hooks and scripts)
brew install tmux    # If you want split-pane monitoring
```

Verify:
```bash
claude --version     # Should be 1.x+
bd --help            # Should show beads help
jq --version         # Should be 1.7+
```

---

## Project Setup (Step by Step)

### 1. Initialize Git Repo

```bash
mkdir my-project && cd my-project
git init
```

### 2. Initialize Beads

```bash
bd init
```

This creates `.beads/` with:
- `beads.db` — SQLite database
- `issues.jsonl` — git-syncable export
- `config.yaml` — beads configuration
- `metadata.json` — project metadata

### 3. Configure Beads Daemon

```bash
# Set the sync branch (commits beads changes to a separate branch)
bd config set sync.branch beads-sync

# Enable auto-commit and auto-push
bd config set daemon.auto-commit true
bd config set daemon.auto-push true

# Start the daemon
bd daemon start
```

The daemon watches for changes to beads data and auto-commits/pushes to the `beads-sync` branch. This means beads state survives even if you forget to sync manually.

### 4. Install Beads Git Hooks

```bash
bd hooks install
```

This installs git hooks that:
- **pre-commit**: Ensures beads data is synced before commits
- **post-merge**: Re-imports beads data after merges
- **pre-push**: Validates beads state before pushing
- **post-checkout**: Refreshes beads state after branch switches
- **prepare-commit-msg**: Can inject ticket IDs into commit messages

### 5. Create Project Directory Structure

```bash
mkdir -p scripts/ralph
mkdir -p scripts/hooks
mkdir -p .claude/hooks
```

Your project should look like:

```
my-project/
├── .beads/                    # Beads issue tracker (auto-created)
│   ├── beads.db
│   ├── issues.jsonl
│   ├── config.yaml
│   └── daemon.log
├── .claude/                   # Claude Code settings
│   ├── settings.json          # Project permissions
│   ├── settings.local.json    # Hook configuration
│   └── hooks/                 # Post-tool-use hooks
├── scripts/
│   ├── ralph/
│   │   ├── ralph-beads.sh     # The autonomous loop
│   │   ├── CLAUDE.md          # Agent-specific instructions
│   │   └── progress.txt       # Append-only progress log
│   ├── hooks/
│   │   ├── pre-task.sh        # Shows ticket context before work
│   │   └── post-task.sh       # Validates Definition of Done
│   └── extract_followups.sh   # Mines closed tickets for deferred work
├── CLAUDE.md                  # Project-level AI instructions
├── src/                       # Your code
└── tests/                     # Your tests
```

### 6. Create Initial Tickets

```bash
# Create an epic for the first milestone
bd create --title="Epic: Initial project setup" --type=epic --priority=1

# Create child tasks
bd create --title="Set up project scaffolding" --type=task --priority=1
bd create --title="Add core feature X" --type=feature --priority=2
bd create --title="Write tests for feature X" --type=task --priority=2

# Link dependencies
bd dep add <tests-id> <feature-id>   # Tests depend on feature being done first
```

---

## Beads Configuration

### .beads/config.yaml

```yaml
# Sync branch for beads commits (keeps beads changes separate from code)
sync-branch: "beads-sync"

# Role determines what bd commands are available
beads.role: maintainer

# Daemon auto-syncs changes to git
daemon.auto-commit: true
daemon.auto-push: true
```

### Key Beads Commands for AI Agents

This is the subset that matters for the Ralph loop:

| Command | Purpose |
|---------|---------|
| `bd ready` | Find unblocked tasks (what to work on next) |
| `bd ready --json --limit 50` | Same, but JSON for script parsing |
| `bd show <id>` | Full task details with dependencies |
| `bd show <id> --json` | Same, but JSON for script parsing |
| `bd update <id> --status in_progress` | Claim a task |
| `bd comments add <id> "text"` | Add approach/completion comment |
| `bd close <id> --reason "Done"` | Close a task |
| `bd close <id1> <id2> ...` | Close multiple tasks at once |
| `bd create --title="..." --type=task --priority=2` | Create follow-up work |
| `bd dep add <issue> <depends-on>` | Add dependency |
| `bd sync` | Export DB to JSONL (daemon does this automatically) |
| `bd blocked` | Show blocked issues |
| `bd stats` | Project health overview |
| `bd search "keyword"` | Find issues by text |

### Priority Scale

| Priority | Meaning |
|----------|---------|
| P0 | Critical — blocks everything |
| P1 | High — do next |
| P2 | Medium — default for new work |
| P3 | Low — nice to have |
| P4 | Backlog — someday/maybe |

**Important**: Use numeric priorities (0-4), not words like "high" or "medium". Beads doesn't understand word priorities.

---

## The Ralph Loop Script

This is the core of the autonomous system. Save as `scripts/ralph/ralph-beads.sh`:

```bash
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
        # Build epic review prompt (see full script for details)
        # ... runs Claude with review dimensions prompt ...
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
```

### Key Design Decisions

1. **`--dangerously-skip-permissions`** — Required for autonomous mode. Claude can't ask for permission when no human is watching. Set up your `.claude/settings.local.json` carefully instead.

2. **`--print` mode** — Runs Claude as a one-shot: reads prompt from stdin, outputs to stdout, exits. No interactive session.

3. **Two CLAUDE.md files** — The project CLAUDE.md teaches Claude about the codebase. The ralph-specific CLAUDE.md teaches Claude about the autonomous workflow. Both are injected into every prompt.

4. **Epic review phase** — When all children of an epic are closed, the loop auto-triggers a holistic review before moving on. This catches integration issues between subtasks.

5. **Simple exit signals** — `<promise>COMPLETE</promise>` and `<ralph>STUCK</ralph>` are wrapped in XML tags to avoid false positives from natural language.

---

## CLAUDE.md — Teaching Claude How to Work

This is the **project-level** CLAUDE.md that lives in the repo root. It teaches Claude about your codebase, architecture, and conventions. This file is automatically read by Claude Code in interactive sessions AND injected into Ralph prompts.

### Template for New Projects

```markdown
# CLAUDE.md - AI Assistant Guide for [PROJECT NAME]

## Your Role: Product Manager & Software Architect

Your default role in this project is **Product Manager and Software Architect**.
When users describe features, bugs, or improvements:

1. **Understand the requirement** — Ask clarifying questions, research the codebase
2. **Design the solution** — Consider architecture, patterns, dependencies, trade-offs
3. **Create BEADS tickets** — Every defined body of work gets tracked in `.beads/`
4. **Implement or delegate** — Execute the work or hand off to future sessions

**ALWAYS create beads tickets** for:
- New features (use `bd create --type=feature`)
- Bug fixes (use `bd create --type=bug`)
- Tasks and refactoring (use `bd create --type=task`)
- Epics with subtasks (use `bd create --type=epic`)

Use `bd ready` to find available work. Use `bd sync` to save progress.

## What is [PROJECT NAME]?

[2-3 sentences explaining the project]

## Architecture

[Key directories, modules, data flow]

## Key Files

[List the 5-10 most important files and what they do]

## Development Commands

```bash
# Run tests
pytest tests/ -q

# Lint
ruff check src/

# Build
[your build command]
```

## Conventions

- [Code style notes]
- [Naming conventions]
- [Error handling patterns]
- [Testing expectations]
```

### What Makes a Good CLAUDE.md

- **Be specific** — "Use ruff for linting" not "follow best practices"
- **Show the architecture** — Claude needs to know where things live
- **List key files** — Claude will read them before making changes
- **Include commands** — Test, lint, build, run commands Claude should use
- **State conventions** — So Claude's code matches your existing style

---

## Ralph's CLAUDE.md — The Agent's Playbook

This is the **agent-specific** CLAUDE.md that lives at `scripts/ralph/CLAUDE.md`. It teaches Claude how to behave in autonomous mode — the workflow, the signals, the comment formats.

### Template for New Projects

```markdown
# Ralph Autonomous Agent Instructions

You are Ralph, an autonomous coding agent working on **[PROJECT NAME]**.

## Workflow (Per Task)

1. **Claim**: `bd update <task-id> --status in_progress`
2. **Plan & Document**: Add approach comment (see format below)
3. **Implement** the task
4. **Test**: Run `[test command]` to verify changes
5. **Lint**: Run `[lint command]` to catch issues
6. **Commit** with ticket ID: `git commit -m "feat: <task-id> - Description"`
7. **Back-link SHA**: `bd comments add <task-id> "Commit: $(git rev-parse HEAD)"`
8. **Add completion comment** (see format below)
9. **Close**: `bd close <task-id> --reason "Done"`
10. **Sync**: `bd sync`
11. **STOP** — Do NOT output any signal. The loop handles the next task.

## Session Close Protocol

**CRITICAL**: Before stopping, complete this checklist:

```
[ ] 1. bd comments add ...     # Approach comment (if not done)
[ ] 2. git status              # Check what changed
[ ] 3. git add <files>         # Stage code changes
[ ] 4. git commit -m "..."     # Commit with ticket ID
[ ] 5. bd comments add ...     # Completion comment
[ ] 6. bd close <id>           # Close the task
[ ] 7. bd sync                 # Sync beads
```

## Approach Comment Format (BEFORE implementation)

```
bd comments add <task-id> "## Approach

**Understanding:** [1-2 sentences on what the task requires]

**Plan:**
1. [First step]
2. [Second step]

**Files to modify:** [list expected files]

**Risks/Questions:** [any concerns]"
```

## Completion Comment Format (AFTER implementation)

```
## What was done
- [specific changes]
- Files: [modified files]

## Left undone
- [deferred items, or "None"]

## Gotchas
- [surprises, edge cases, patterns discovered]
```

## After Completing a Task

**IMPORTANT**: After closing a task, just STOP. Do not output anything else.
The loop will automatically pick up the next task.

**DO NOT output `<promise>COMPLETE</promise>` after finishing a single task.**
That signal means the ENTIRE project backlog is done.

## Stop Signals (RARE)

### `<promise>COMPLETE</promise>`
**ONLY use when**: `bd ready` returns NO tasks (empty list).

### `<ralph>STUCK</ralph>`
**ONLY use when**: You've tried 3+ times and cannot proceed.

## bd Commands Reference

| Action | Command |
|--------|---------|
| Ready tasks | `bd ready` |
| Show details | `bd show <id>` |
| Claim task | `bd update <id> --status in_progress` |
| Add comment | `bd comments add <id> "text"` |
| Close task | `bd close <id> --reason "Done"` |
| Create follow-up | `bd create --title="..." --type=task --priority=2` |
| Add dependency | `bd dep add <issue> <depends-on>` |
| Sync | `bd sync` |

**Priority**: 0-4 (0=critical, 2=medium, 4=backlog). NOT "high"/"medium"/"low".

## Creating Dependent Work

When implementation reveals new work:

```bash
bd create --title="Follow-up: Handle edge case X" --type=task --priority=2
bd dep add <new-id> <current-id>
bd comments add <current-id> "Created follow-up: <new-id>"
```

## Quality Checks Before Closing

```bash
[test command]
[lint command]
git status
```

If tests fail or linter errors exist, fix them before closing the task.
```

### Critical Instructions to Get Right

1. **"Just STOP after closing"** — Without this, Claude will try to pick up the next task itself, leading to confusion about ticket state.
2. **"Do NOT output COMPLETE after a single task"** — Claude loves to be helpful and will say "all done!" after finishing one thing. The XML tags prevent accidental exits.
3. **Approach + Completion comments** — These are the audit trail. When you come back and wonder "why was this done this way?", the comments tell you.
4. **"Left undone" section** — This is gold. The `extract_followups.sh` script mines these for future work.

---

## Claude Code Hooks

### .claude/settings.json (Hook Configuration)

Hooks fire on Claude Code events and can inject context or block actions.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "tool_name_pattern",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/your-hook.sh"
          }
        ]
      }
    ]
  }
}
```

### Session Start Hook (Beads Context Injection)

The beads `bd prime` output is injected at session start via hooks. This is configured through `bd setup claude` or `bd hooks install`. When Claude Code starts, it automatically runs `bd prime` and injects the output — giving Claude the full beads workflow context without you needing to explain it every time.

This is what makes the "bd create", "bd close", "bd ready" instructions stick — Claude sees them at the start of every session.

### Example: Post-Tool-Use Hook

You can create hooks that fire after specific tool calls. For example, a hook that reminds Claude to extract video frames after processing a video:

```bash
#!/bin/bash
# .claude/hooks/post-process-reminder.sh
INPUT=$(cat)

# Parse tool output, check conditions
if echo "$INPUT" | jq -e '.some_field == true' > /dev/null 2>&1; then
    CONTEXT="Reminder: You should also do X based on the tool output."
    echo "$CONTEXT" | jq -R -s '{
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": .
        }
    }'
fi
exit 0
```

---

## Permissions & Settings

### .claude/settings.local.json

This controls what Claude Code is allowed to do without asking. For autonomous Ralph mode, you need generous permissions since no human is there to approve.

```json
{
  "permissions": {
    "allow": [
      "Bash(git:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push:*)",
      "Bash(git status:*)",
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Bash(git rev-parse:*)",
      "Bash(gh:*)",
      "Bash(bd:*)",
      "Bash(bd create:*)",
      "Bash(bd update:*)",
      "Bash(bd close:*)",
      "Bash(bd show:*)",
      "Bash(bd list:*)",
      "Bash(bd ready:*)",
      "Bash(bd comments:*)",
      "Bash(bd comments add:*)",
      "Bash(bd dep:*)",
      "Bash(bd dep add:*)",
      "Bash(bd sync:*)",
      "Bash(bd stats:*)",
      "Bash(bd blocked:*)",
      "Bash(bd search:*)",
      "Bash(bd prime:*)",
      "Bash(bd daemon:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pytest:*)",
      "Bash(ruff:*)",
      "Bash(ruff check:*)",
      "Bash(pip:*)",
      "Bash(pip install:*)",
      "Bash(make:*)",
      "Bash(ls:*)",
      "Bash(wc:*)",
      "Bash(jq:*)",
      "Bash(echo:*)",
      "Bash(cat:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(sort:*)",
      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(rm:*)",
      "Bash(touch:*)",
      "Bash(which:*)",
      "WebSearch"
    ]
  }
}
```

**Customize for your project:**
- Add your build tools (`npm`, `cargo`, `go`, etc.)
- Add your test runner (`jest`, `pytest`, `bats`, etc.)
- Add your linter (`eslint`, `ruff`, `clippy`, etc.)
- Remove anything you don't want Claude touching autonomously

**Security note**: `--dangerously-skip-permissions` in the Ralph script bypasses these entirely. The permissions file matters for interactive Claude Code sessions. For Ralph, it's the CLAUDE.md instructions that constrain behavior.

---

## Helper Scripts

### scripts/hooks/pre-task.sh — Context Before Work

Shows ticket details and related tickets before starting work. Useful for manual workflows (not called by Ralph loop automatically, but useful for `bd` hooks).

```bash
#!/usr/bin/env bash
set -euo pipefail
TICKET_ID="${1:-}"
[ -z "$TICKET_ID" ] && { echo "Usage: $0 <ticket-id>"; exit 1; }

echo "═══ PRE-TASK: $TICKET_ID ═══"
bd show "$TICKET_ID"

# Find related open tickets by keyword
TITLE=$(bd show "$TICKET_ID" --json | jq -r '.title')
KEYWORDS=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '\n' \
    | grep -E '^.{4,}$' | grep -vE '^(this|that|with|from|have|will|epic|task|feature)$' | head -3)

echo "RELATED TICKETS:"
for kw in $KEYWORDS; do
    RESULTS=$(bd search "$kw" --status open 2>/dev/null | grep -v "^$TICKET_ID" | head -3)
    [ -n "$RESULTS" ] && echo "  [$kw]: $RESULTS"
done
```

### scripts/hooks/post-task.sh — Definition of Done

Validates that work is properly documented and committed before a ticket can be closed.

```bash
#!/usr/bin/env bash
set -euo pipefail
TICKET_ID="${1:-}"
[ -z "$TICKET_ID" ] && { echo "Usage: $0 <ticket-id>"; exit 1; }

ERRORS=0

# Check 1: Has a completion comment
COMMENTS=$(bd show "$TICKET_ID" --json | jq '.comments | length')
[ "$COMMENTS" -eq 0 ] && { echo "ERROR: No completion comment"; ERRORS=$((ERRORS+1)); }

# Check 2: Commit references ticket ID
COMMITS=$(git log --oneline --all --grep="$TICKET_ID" 2>/dev/null | wc -l | tr -d ' ')
[ "$COMMITS" -eq 0 ] && { echo "ERROR: No commit references $TICKET_ID"; ERRORS=$((ERRORS+1)); }

# Check 3: Uncommitted changes
git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null || echo "WARN: Uncommitted changes"

[ $ERRORS -gt 0 ] && { echo "BLOCKED: Fix $ERRORS error(s)"; exit 1; }
echo "READY TO CLOSE"
```

### scripts/extract_followups.sh — Mine Closed Tickets

Scans all closed tickets for "Left undone" and "Gotchas" sections in completion comments. Outputs a report of potential follow-up work.

```bash
./scripts/extract_followups.sh         # Human-readable report
./scripts/extract_followups.sh --json  # JSON for programmatic use
```

This is a great periodic review tool — run it after a Ralph session to see what deferred work accumulated.

---

## Running the Loop

### Basic Usage

```bash
# Run 10 iterations (default)
./scripts/ralph/ralph-beads.sh

# Run 20 iterations
./scripts/ralph/ralph-beads.sh 20

# Debug mode (see Claude's full output)
./scripts/ralph/ralph-beads.sh --debug 5

# Dry run (see what would happen without calling Claude)
./scripts/ralph/ralph-beads.sh --dry-run

# Verbose mode (extra state info)
./scripts/ralph/ralph-beads.sh --verbose 15
```

### Recommended Workflow

1. **Create tickets** — Either manually or have Claude create them in an interactive session
2. **Review the backlog** — `bd ready` to see what's queued
3. **Start the loop** — `./scripts/ralph/ralph-beads.sh 15`
4. **Monitor** — `tail -f ralph.log` in another terminal
5. **Review results** — `cat scripts/ralph/progress.txt` to see what was done
6. **Extract follow-ups** — `./scripts/extract_followups.sh` to find deferred work
7. **Create new tickets** for follow-ups, repeat

### Split Terminal Monitoring

```bash
# Terminal 1: Run the loop
./scripts/ralph/ralph-beads.sh --verbose 20

# Terminal 2: Watch the log
tail -f ralph.log

# Terminal 3: Watch beads state
watch -n 5 'bd stats'
```

---

## Monitoring & Debugging

### Log Files

| File | Purpose |
|------|---------|
| `ralph.log` | Full loop execution log (append-only) |
| `scripts/ralph/progress.txt` | One-line-per-task summary |
| `.beads/daemon.log` | Beads daemon sync activity |

### Common Issues

**Claude exits immediately without doing work:**
- Check that `bd ready` returns tasks
- Check that tasks aren't all epics (Ralph skips epics in favor of concrete tasks)
- Check `bd blocked` for dependency issues

**Claude keeps working on the same task:**
- The task may not be getting closed — check `bd list --status=in_progress`
- Claude may be ignoring the "just STOP" instruction — strengthen the wording in `scripts/ralph/CLAUDE.md`

**"No actionable tasks" but tickets exist:**
- Tasks may be blocked by unclosed dependencies — `bd blocked`
- Tasks may all be epics — Ralph looks for non-epic tasks first
- Run `bd ready --json` to see what's actually available

**Loop exits with code 2 (STUCK):**
- 3 consecutive iterations found no actionable work
- Check `bd blocked` and resolve dependency chains
- Check if remaining tasks need human input

---

## Patterns That Work

### 1. Front-Load Ticket Creation

Before starting a Ralph session, spend 10 minutes creating well-structured tickets with:
- Clear titles (imperative: "Add X", "Fix Y", not "X should be added")
- Descriptions with acceptance criteria
- Dependencies set up (`bd dep add`)
- Priorities assigned (P0-P4)

The better your tickets, the better Ralph performs.

### 2. Use Epics for Multi-Step Features

```bash
bd create --title="Epic: Add authentication system" --type=epic --priority=1
bd create --title="Add JWT token generation" --type=task --priority=1
bd create --title="Add login endpoint" --type=feature --priority=1
bd create --title="Add auth middleware" --type=task --priority=1
bd create --title="Write auth tests" --type=task --priority=2

# Set up dependency chain
bd dep add <login-id> <jwt-id>        # Login needs JWT first
bd dep add <middleware-id> <login-id>  # Middleware needs login
bd dep add <tests-id> <middleware-id>  # Tests need everything
```

Ralph will work through these in dependency order, then auto-review the epic when all children are done.

### 3. Structured Completion Comments

The "What was done / Left undone / Gotchas" format in completion comments is not just documentation — it's a **knowledge transfer mechanism** between Ralph iterations. When `extract_followups.sh` mines these, you get:
- A list of deferred work to create new tickets from
- A list of gotchas that inform future architecture decisions

### 4. Keep the Loop Short

10-20 iterations per session. After that:
- Review what was done (`progress.txt`)
- Extract follow-ups
- Create new tickets if needed
- Start a fresh loop

This prevents drift — where Claude starts making increasingly questionable decisions because the backlog has shifted.

### 5. Interactive Session + Ralph Session

Best workflow:
1. **Interactive** — Talk to Claude, explore the codebase, design the approach
2. **Create tickets** — Turn the plan into beads tickets with dependencies
3. **Ralph** — Let the loop execute the plan autonomously
4. **Interactive** — Review results, course-correct, plan next batch

---

## Anti-Patterns to Avoid

### 1. Huge Tickets
"Implement the entire authentication system" is too big. Break it into 3-7 focused subtasks.

### 2. Missing Dependencies
If Task B needs Task A's code, set `bd dep add B A`. Without this, Ralph might try B first and get confused.

### 3. Vague Descriptions
"Fix the bug" — which bug? Claude can't read your mind. Include:
- What's broken
- How to reproduce
- What the fix should look like

### 4. Running Without Review
Don't run 100 iterations overnight. Start with 5-10, review, adjust, repeat. Trust builds gradually.

### 5. Skipping the CLAUDE.md
Without good CLAUDE.md files, Claude will:
- Use wrong test commands
- Not know your project's conventions
- Create files in wrong locations
- Skip important steps

### 6. Using `bd edit`
`bd edit` opens `$EDITOR` (vim/nano) which blocks agents. Always use `bd update --title/--description` or `bd comments add` instead.

---

## Quick-Start Checklist

For a brand new project:

```bash
# 1. Create project
mkdir my-project && cd my-project && git init

# 2. Initialize beads
bd init
bd config set sync.branch beads-sync
bd config set daemon.auto-commit true
bd config set daemon.auto-push true
bd daemon start
bd hooks install

# 3. Create directory structure
mkdir -p scripts/ralph scripts/hooks .claude/hooks

# 4. Create CLAUDE.md (project instructions)
# Edit CLAUDE.md with your project's specifics (see template above)

# 5. Create scripts/ralph/CLAUDE.md (agent instructions)
# Copy the template from the "Ralph's CLAUDE.md" section above

# 6. Create scripts/ralph/ralph-beads.sh (the loop)
# Copy from the "Ralph Loop Script" section above
chmod +x scripts/ralph/ralph-beads.sh

# 7. Create scripts/ralph/progress.txt
echo "# Ralph Progress Log" > scripts/ralph/progress.txt

# 8. Set up permissions
# Create .claude/settings.local.json (see Permissions section above)

# 9. Create initial tickets
bd create --title="Epic: Initial setup" --type=epic --priority=1
bd create --title="Set up project scaffolding" --type=task --priority=1
# ... add more tickets ...

# 10. First commit
git add -A
git commit -m "feat: initial project setup with ralph + beads"

# 11. Run the loop!
./scripts/ralph/ralph-beads.sh --verbose 5
```

---

## Appendix: Beads Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    BEADS QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FIND WORK                                                  │
│    bd ready              Show unblocked tasks               │
│    bd list --status=open All open issues                    │
│    bd blocked            Show blocked issues                │
│    bd search "keyword"   Search by text                     │
│                                                             │
│  DO WORK                                                    │
│    bd update ID --status in_progress   Claim task           │
│    bd comments add ID "text"           Add comment          │
│    bd close ID                         Complete task        │
│    bd close ID --reason "why"          Complete with reason  │
│                                                             │
│  CREATE WORK                                                │
│    bd create --title="X" --type=task --priority=2           │
│    bd create --title="X" --type=bug --priority=1            │
│    bd create --title="X" --type=feature --priority=2        │
│    bd create --title="X" --type=epic --priority=1           │
│                                                             │
│  DEPENDENCIES                                               │
│    bd dep add ISSUE DEPENDS_ON    Issue depends on other    │
│    bd dep rm ISSUE DEPENDS_ON     Remove dependency         │
│    bd show ID                     See deps in details       │
│                                                             │
│  HEALTH                                                     │
│    bd stats              Project overview                   │
│    bd doctor             Check for issues                   │
│    bd sync               Manual sync to git                 │
│    bd daemon status      Check daemon                       │
│                                                             │
│  PRIORITIES: P0=critical P1=high P2=medium P3=low P4=backlog│
│  TYPES: task, bug, feature, epic                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
