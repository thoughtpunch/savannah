# Live Visualization

Real-time browser UI for watching AI Savannah simulations as they run.

## Starting the Live Server

```bash
python -m savannah.run --live [--mock] [--port 8765] [--config path.yaml] [--ticks N]
```

| Flag | Description |
|------|-------------|
| `--live` | Required. Starts the WebSocket server and serves the browser UI. |
| `--mock` | Use the mock LLM provider (instant responses, no API calls). Useful for testing and demos. |
| `--port` | Server port. Default: `8765`. |
| `--config` | Path to experiment config YAML. If provided, the simulation starts immediately. If omitted, the browser shows a lobby screen. |
| `--ticks` | Override the tick count from config. |

After starting, open `http://localhost:8765` in your browser (or the port you specified).

## Lobby Mode vs Immediate Start

### Lobby mode (no `--config`)

```bash
python -m savannah.run --live --mock
```

The browser shows a lobby screen with:

- **Preset experiment cards**: Baseline, Perturbation, Social Pressure, Full Pressure. Click any card to start that experiment.
- **Options bar**: Toggle "Mock LLM (no API)" and set tick count before starting.
- **View Past Runs** button: Opens the history tab to browse and replay completed experiments.

The server waits in lobby mode until you select a preset from the browser. After a simulation completes, it returns to the lobby.

### Immediate start (with `--config`)

```bash
python -m savannah.run --live --mock --config savannah/config/experiments/perturbation.yaml
```

The simulation begins as soon as the server starts. The browser connects and immediately shows the running simulation.

## Preset Experiments

Four preset configs are available in the lobby:

| Preset | Config file | Description |
|--------|------------|-------------|
| Baseline | `baseline.yaml` | No perturbation, no social pressure. Control condition. |
| Perturbation | `perturbation.yaml` | Memory corruption active after tick 100. Observe self-correction. |
| Social Pressure | `social.yaml` | Deceptive agents inject false signals. Trust dynamics. |
| Full Pressure | `full_pressure.yaml` | Both perturbation and social pressure active simultaneously. |

## Browser UI Layout

The interface has four main areas when a simulation is running:

### Top Bar

- **Tick counter**: Shows current tick and total (e.g., "Tick 142 / 500")
- **Status badge**: Color-coded indicator -- lobby (gray), running (green), thinking (blue, pulsing), paused (orange), stopped (red), complete (blue)
- **Inference time**: Milliseconds for the last tick's LLM calls
- **Playback controls**: Pause, Step, Stop buttons
- **Speed selector**: 0.5x (slow, 500ms delay), 1x (normal, 200ms), 3x (fast, 50ms), Max (0ms delay)

### Thought Stream (main panel, left)

A scrolling feed showing what happened each tick:

- **Tick header**: Tick number and inference time
- **Perturbation entries** (if any): Red-highlighted rows showing which agent was corrupted, the corruption type, and a before/after diff
- **Agent entries**: Each alive agent's row shows:
  - Agent name (color-coded)
  - Action taken (color-coded by type: green for eat, red for attack, orange for flee, purple for signal, blue for memory actions)
  - Reasoning excerpt (truncated)
  - Energy bar

When following an agent (see Agent Interaction below), only that agent's entries are shown.

### Sidebar (right)

From top to bottom:

1. **Minimap**: Canvas-rendered top-down view of the grid. Shows agent dots (color-coded), food sources (green circles scaled by energy), dead agents (X marks). Followed agents have a white ring. Perturbed agents flash a red halo. Signal actions show a purple ripple.

2. **Sparkline charts**: Three mini time-series charts:
   - Population (alive agent count)
   - Average energy
   - Food source count

3. **Agent list**: All agents sorted by energy (alive first, then dead). Each card shows the agent's color dot, name, energy percentage, and perturbation count. Click to follow, double-click for profile.

4. **Stats panel**: Grid of summary stats -- Alive, Dead, Food, Perturbations, Total kills, Avg energy.

### Event Toasts

Notification toasts appear in the top-right when notable events occur:

- **Death**: An agent has died (red border)
- **Kill**: An agent killed another (red border)
- **Low energy**: An agent dropped below 15 energy (yellow border)
- **Perturbation**: A memory corruption event occurred (orange border)

Toasts auto-dismiss after 3.5 seconds.

## Controls

### Buttons

| Button | Action |
|--------|--------|
| Pause | Pause the simulation. Toggles to Resume when paused. |
| Step | Advance exactly one tick (only available while paused). |
| Stop | End the simulation. |
| 0.5x / 1x / 3x / Max | Set simulation speed (inter-tick delay). |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Toggle pause/resume |
| `.` (period) | Step one tick (while paused) |
| `Escape` | Close profile modal, or stop the simulation |
| `T` | Toggle movement trails on the minimap |
| `F` | Unfollow the currently followed agent |

### Timeline Scrubber

When paused, a timeline slider appears below the top bar. Drag it to scrub through recent tick history (up to 500 ticks are buffered). The minimap, agent list, and stats update to reflect the selected tick.

## Agent Interaction

### Click: Follow mode

Click an agent's name in the thought stream or their card in the sidebar agent list to enter follow mode. In follow mode:

- The thought stream filters to show only that agent's actions
- The agent is highlighted with a white ring on the minimap

Click the same agent again to unfollow and return to the full view.

### Double-click: Profile modal

Double-click an agent anywhere to open their profile modal. The profile shows:

- **Vitals**: Current energy (large display), position, age in ticks, kill count, times perturbed, alive/dead status
- **Personality (Emergent)**: Traits inferred from action distribution -- Explorer (>50% move), Forager (>20% eat), Conservative (>30% rest), Communicator (>10% signal), Aggressive (>5% attack), Cautious (>10% flee), Reflective (>10% remember), Strategic (>10% recall), Organized (>5% compact). Shows the full action percentage breakdown.
- **Recent Actions**: Last 20 actions with tick number, action, and reasoning

Close the modal by clicking the X, clicking outside the modal, or pressing Escape.

### Minimap interaction

- **Trails toggle**: Click "Trails" in the minimap header (or press `T`) to overlay movement trails on the minimap. Each agent's recent path (up to 30 positions) is drawn as a colored line. Trails do not draw across toroidal wrap boundaries.

## History and Replay

### Viewing past runs

From the lobby, click "View Past Runs" to see a list of all experiments in the `data/` directory. Each run card shows:

- Run name (timestamp-based, e.g., `exp_20250115_143022`)
- Number of completed ticks
- Agent count
- Whether perturbation was enabled

### Replaying a run

Click a run card to enter replay mode. The replay view provides:

- **Back button**: Return to the run list
- **Play/Pause button**: Auto-advance through ticks at 100ms intervals
- **Timeline slider**: Drag to jump to any tick. Tick data is loaded on demand from the server's REST API.
- **Minimap**: Shows agent positions and food at the selected tick
- **Agent list**: Shows all agents with energy percentages at the selected tick

The replay view loads tick snapshots from `data/{run_name}/logs/ticks/` via the server's API endpoints:

- `GET /api/runs` -- list all past runs
- `GET /api/runs/{name}/tick/{n}` -- get a specific tick snapshot
- `GET /api/runs/{name}/config` -- get the run's config

## Mock Mode

The `--mock` flag uses a `MockLLMProvider` that returns instant deterministic responses without making any API calls. This is useful for:

- **First-time setup verification**: Confirm the system works before configuring LLM credentials
- **UI development and testing**: Fast iteration on visualization features
- **Demonstrations**: Show the system's capabilities without incurring API costs
- **Load testing**: Run many ticks quickly to test performance

Mock agents still produce valid actions (move, eat, rest, etc.) and follow the same simulation rules, but their reasoning is simplified.

## Troubleshooting

**Browser shows blank page**: Check that `savannah/viz/live.html` exists. The server logs `Live server running at http://localhost:8765` on successful start.

**WebSocket disconnects**: The browser auto-reconnects after 2 seconds. Check the browser console for error details.

**Port in use**: Use `--port <number>` to pick a different port.

**No past runs in history**: Runs are stored in the `data/` directory relative to your working directory. Make sure you are running from the project root.
