# Ralph & Beads Workflow

Ralph is the autonomous agent loop that develops ILET. It combines Claude Code for coding, Beads for persistent issue tracking, and a bash script for orchestration.

## Architecture

| Component | Tool | Role |
|-----------|------|------|
| Brain | Claude Code (`claude --print`) | Does the coding, testing, committing |
| Scheduler | Ralph loop (`ralph-beads.sh`) | Picks next task, feeds to Claude, detects done/stuck |
| Memory | Beads (`bd`) | Persistent tickets with dependencies, comments, sync |

Claude Code is stateless between invocations -- it forgets everything after each call. Beads provides the persistent memory. Ralph is the glue that reads from Beads, constructs a prompt, calls Claude, syncs state, and repeats.

## How It Works

### The Loop

The `scripts/ralph/ralph-beads.sh` script runs a loop:

1. **Check for epic reviews**: If an epic has all children closed, trigger a holistic review
2. **Find actionable task**: `bd ready --json` picks the highest-priority non-epic, non-blocked task
3. **Handle no-task state**: If no tasks available, increment a streak counter. After 3 consecutive no-task iterations, exit
4. **Execute task**: Build a prompt from project CLAUDE.md + ralph CLAUDE.md + task details, pipe to `claude --print`
5. **Check exit signals**: Look for `<promise>COMPLETE</promise>` (all done) or `<ralph>STUCK</ralph>` (needs human)
6. **Sync and repeat**: `bd sync`, wait 2 seconds, next iteration

### Beads for Ticket Management

Beads (`bd`) is the issue tracker. Key commands:

| Command | Purpose |
|---------|---------|
| `bd ready` | Find unblocked tasks (what to work on next) |
| `bd show <id>` | Full task details with dependencies |
| `bd update <id> --status in_progress` | Claim a task |
| `bd comments add <id> "text"` | Add approach/completion comment |
| `bd close <id> --reason "Done"` | Close a task |
| `bd create --title="..." --type=task --priority=2` | Create follow-up work |
| `bd dep add <issue> <depends-on>` | Add dependency |
| `bd sync` | Export state to git |

Priorities are numeric: P0 (critical) through P4 (backlog). Types: task, bug, feature, epic.

### ralph-beads.sh

The script lives at `scripts/ralph/ralph-beads.sh`. Usage:

```bash
# Run 10 iterations (default)
./scripts/ralph/ralph-beads.sh

# Run 20 iterations
./scripts/ralph/ralph-beads.sh 20

# Debug mode (see Claude's full output)
./scripts/ralph/ralph-beads.sh --debug 5

# Dry run
./scripts/ralph/ralph-beads.sh --dry-run
```

### Progress Tracking

The `scripts/ralph/progress.txt` file is an append-only log. Each completed task gets a one-line entry:

```
- 2026-02-08 14:30 | TASK-42 | Implement BM25 recall in memory.py
- 2026-02-08 14:45 | TASK-43 | Add perturbation logging to JSONL
```

Review this after a Ralph session to see what was done.

### Epic Reviews

When all children of an epic are closed, Ralph auto-triggers a holistic review. This catches integration issues between subtasks that might be missed when each subtask is completed in isolation.

## Per-Task Workflow

When Ralph picks up a task, the Claude instance follows this workflow (defined in `scripts/ralph/CLAUDE.md`):

1. **Claim**: `bd update <task-id> --status in_progress`
2. **Plan**: Add an approach comment with understanding, plan, files to modify, risks
3. **Implement**: Write the code
4. **Test**: `pytest savannah/tests/ -q`
5. **Lint**: `ruff check savannah/`
6. **Commit**: `git commit -m "feat: <task-id> - Description"`
7. **Back-link**: `bd comments add <task-id> "Commit: $(git rev-parse HEAD)"`
8. **Completion comment**: What was done, what was left undone, gotchas
9. **Close**: `bd close <task-id> --reason "Done"`
10. **Sync**: `bd sync`
11. **Stop**: Do not pick up the next task. The loop handles that.

## CLAUDE.md Files

Two CLAUDE.md files teach Claude how to behave:

### Project CLAUDE.md (root)

Located at `/Users/danielbarrett/sites/savannah/CLAUDE.md`. Teaches Claude about:
- The project (what ILET is, key constraints)
- Architecture (directory layout, key modules)
- Development commands (test, lint, run)
- Conventions (Python 3.12, asyncio, YAML config, anti-contamination)

### Ralph CLAUDE.md

Located at `scripts/ralph/CLAUDE.md`. Teaches Claude about:
- The autonomous workflow (claim, plan, implement, test, commit, close)
- Comment formats (approach before, completion after)
- Stop signals (`<promise>COMPLETE</promise>` and `<ralph>STUCK</ralph>`)
- Beads commands reference
- Quality checks before closing

Both files are injected into every Ralph prompt. The project CLAUDE.md provides codebase knowledge; the Ralph CLAUDE.md provides workflow knowledge.

## Recommended Workflow for Humans

1. **Interactive session**: Talk to Claude, explore the codebase, design the approach
2. **Create tickets**: Turn the plan into Beads tickets with dependencies
3. **Ralph session**: `./scripts/ralph/ralph-beads.sh --verbose 15`
4. **Monitor**: `tail -f ralph.log` in another terminal
5. **Review**: `cat scripts/ralph/progress.txt` to see what was done
6. **Extract follow-ups**: Check closed tickets for deferred work
7. **Course-correct**: Create new tickets, adjust priorities, repeat

### Monitoring

| File | Purpose |
|------|---------|
| `ralph.log` | Full loop execution log |
| `scripts/ralph/progress.txt` | One-line-per-task summary |
| `.beads/daemon.log` | Beads sync activity |

Split terminal setup:

```bash
# Terminal 1: Run the loop
./scripts/ralph/ralph-beads.sh --verbose 20

# Terminal 2: Watch the log
tail -f ralph.log

# Terminal 3: Watch beads state
watch -n 5 'bd stats'
```

## Tips

- **Keep loops short**: 10-20 iterations per session. Review, adjust, restart.
- **Front-load ticket creation**: Well-structured tickets with clear titles and dependencies produce better Ralph output.
- **Use epics**: Multi-step features should be an epic with child tasks. Ralph respects dependency order.
- **Never use `bd edit`**: It opens `$EDITOR` (vim/nano) which blocks agents. Use `bd update` or `bd comments add`.

See [Getting Started](getting-started.md) for initial setup, and [Architecture](architecture.md) for how the codebase is structured.
