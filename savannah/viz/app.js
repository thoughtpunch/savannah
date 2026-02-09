/**
 * AI Savannah Savannah Viewer — Canvas-based grid renderer + timeline control.
 * Reads tick snapshot JSON files and renders the world state.
 *
 * URL params:
 *   ?data=path/to/experiment   — set data base path
 */

// ── DOM refs ─────────────────────────────────────────────────────

const canvas = document.getElementById('grid');
const ctx = canvas.getContext('2d');
const slider = document.getElementById('tick-slider');
const tickLabel = document.getElementById('tick-label');
const playBtn = document.getElementById('play-btn');
const inspectorTitle = document.getElementById('inspector-title');
const inspectorContent = document.getElementById('inspector-content');
const showTrails = document.getElementById('show-trails');
const showNames = document.getElementById('show-names');
const showDead = document.getElementById('show-dead');
const statusEl = document.getElementById('status');
const gridInfoEl = document.getElementById('grid-info');
const tooltipEl = document.getElementById('tooltip');
const perturbationMarkersEl = document.getElementById('perturbation-markers');

// ── State ────────────────────────────────────────────────────────

let currentTick = 0;
let maxTick = 0;
let playing = false;
let playInterval = null;
let playSpeed = 1.0;        // multiplier
let snapshotCache = {};
let dataBasePath = '../data/';
let gridSize = 30;
let selectedAgent = null;
let perturbationTicks = [];  // list of tick numbers with perturbation events
let perturbations = [];      // full perturbation data
let trailHistory = [];       // recent positions per agent for trail rendering

// Agent color palette
const AGENT_COLORS = [
    '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6',
    '#8b5cf6', '#ec4899', '#f43f5e', '#14b8a6', '#a855f7', '#6366f1',
];

// ── URL param parsing ────────────────────────────────────────────

function parseParams() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('data')) {
        dataBasePath = params.get('data');
        if (!dataBasePath.endsWith('/')) dataBasePath += '/';
    }
}

// ── Data loading ─────────────────────────────────────────────────

async function loadSnapshot(tick) {
    const key = tick.toString().padStart(6, '0');
    if (snapshotCache[key]) return snapshotCache[key];

    try {
        const resp = await fetch(`${dataBasePath}logs/ticks/${key}.json`);
        if (!resp.ok) return null;
        const data = await resp.json();
        snapshotCache[key] = data;

        // Keep cache manageable (sliding window of 100)
        const keys = Object.keys(snapshotCache);
        if (keys.length > 100) {
            delete snapshotCache[keys[0]];
        }
        return data;
    } catch (e) {
        console.warn(`Failed to load tick ${tick}:`, e);
        return null;
    }
}

async function loadPerturbations() {
    try {
        const resp = await fetch(`${dataBasePath}logs/perturbations.jsonl`);
        if (!resp.ok) return;
        const text = await resp.text();
        perturbations = text.trim().split('\n')
            .filter(line => line.trim())
            .map(line => JSON.parse(line));
        perturbationTicks = [...new Set(perturbations.map(p => p.tick))];
    } catch (e) {
        console.warn('No perturbation log found:', e);
    }
}

async function discoverMaxTick() {
    // Try loading the index file first, then binary search
    try {
        const resp = await fetch(`${dataBasePath}logs/ticks/`);
        if (resp.ok) {
            const text = await resp.text();
            const matches = text.match(/(\d{6})\.json/g);
            if (matches && matches.length > 0) {
                const ticks = matches.map(m => parseInt(m.replace('.json', '')));
                maxTick = Math.max(...ticks);
                slider.max = maxTick;
                return;
            }
        }
    } catch (e) {
        // fall through to binary search
    }

    // Binary search for max tick
    let lo = 0, hi = 10000;
    while (lo < hi) {
        const mid = Math.floor((lo + hi + 1) / 2);
        const snap = await loadSnapshot(mid);
        if (snap) {
            lo = mid;
        } else {
            hi = mid - 1;
        }
    }
    maxTick = lo;
    slider.max = maxTick;
}

// ── Trail tracking ───────────────────────────────────────────────

function updateTrails(snapshot) {
    if (!snapshot || !snapshot.agents) return;

    // Store current positions
    const entry = { tick: snapshot.tick, positions: {} };
    for (const agent of snapshot.agents) {
        entry.positions[agent.name] = {
            x: agent.position[0],
            y: agent.position[1],
            alive: agent.alive,
        };
    }
    trailHistory.push(entry);

    // Keep last 20 entries
    if (trailHistory.length > 20) {
        trailHistory.shift();
    }
}

// ── Rendering ────────────────────────────────────────────────────

function render(snapshot) {
    if (!snapshot) return;

    const cellSize = canvas.width / gridSize;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Grid background
    ctx.fillStyle = '#0d1b2a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Grid lines
    ctx.strokeStyle = '#1b2838';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= gridSize; i++) {
        ctx.beginPath();
        ctx.moveTo(i * cellSize, 0);
        ctx.lineTo(i * cellSize, canvas.height);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, i * cellSize);
        ctx.lineTo(canvas.width, i * cellSize);
        ctx.stroke();
    }

    // Food sources (green circles sized by energy)
    for (const food of snapshot.world.food_sources || []) {
        const cx = food.x * cellSize + cellSize / 2;
        const cy = food.y * cellSize + cellSize / 2;
        const energyFrac = food.energy / (food.max_energy || 1);
        const radius = cellSize * 0.15 + cellSize * 0.3 * energyFrac;

        // Glow
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34, 197, 94, ${0.1 * energyFrac})`;
        ctx.fill();

        // Circle
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34, 197, 94, ${0.3 + 0.7 * energyFrac})`;
        ctx.fill();
    }

    // Trails
    if (showTrails.checked && trailHistory.length > 1) {
        for (let i = 0; i < (snapshot.agents || []).length; i++) {
            const agent = snapshot.agents[i];
            const color = AGENT_COLORS[i % AGENT_COLORS.length];

            ctx.beginPath();
            let started = false;
            for (let h = 0; h < trailHistory.length; h++) {
                const pos = trailHistory[h].positions[agent.name];
                if (!pos) continue;
                const px = pos.x * cellSize + cellSize / 2;
                const py = pos.y * cellSize + cellSize / 2;
                if (!started) {
                    ctx.moveTo(px, py);
                    started = true;
                } else {
                    ctx.lineTo(px, py);
                }
            }
            ctx.strokeStyle = color;
            ctx.globalAlpha = 0.25;
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.globalAlpha = 1.0;
        }
    }

    // Dead agents (gray X marks)
    if (showDead.checked) {
        for (const agent of snapshot.agents || []) {
            if (agent.alive) continue;
            const [x, y] = agent.position;
            const cx = x * cellSize + cellSize / 2;
            const cy = y * cellSize + cellSize / 2;
            const size = cellSize * 0.25;

            ctx.strokeStyle = '#555';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(cx - size, cy - size);
            ctx.lineTo(cx + size, cy + size);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(cx + size, cy - size);
            ctx.lineTo(cx - size, cy + size);
            ctx.stroke();
        }
    }

    // Alive agents (colored dots with energy rings)
    for (let i = 0; i < (snapshot.agents || []).length; i++) {
        const agent = snapshot.agents[i];
        if (!agent.alive) continue;

        const [x, y] = agent.position;
        const color = AGENT_COLORS[i % AGENT_COLORS.length];
        const cx = x * cellSize + cellSize / 2;
        const cy = y * cellSize + cellSize / 2;
        const radius = cellSize * 0.35;

        // Selection highlight
        if (selectedAgent && selectedAgent === agent.name) {
            ctx.beginPath();
            ctx.arc(cx, cy, radius + 6, 0, Math.PI * 2);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // Agent dot
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // Energy ring
        const energyFrac = Math.max(0, agent.energy / agent.max_energy);
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 2, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * energyFrac);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Name label
        if (showNames.checked) {
            ctx.fillStyle = '#ddd';
            ctx.font = '9px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(agent.name, cx, cy - radius - 5);
        }
    }

    // Update grid info
    const aliveCount = (snapshot.agents || []).filter(a => a.alive).length;
    const foodCount = (snapshot.world.food_sources || []).length;
    gridInfoEl.textContent =
        `Tick ${snapshot.tick} | Alive: ${aliveCount} | Food: ${foodCount}`;
}

// ── Perturbation markers on timeline ─────────────────────────────

function renderPerturbationMarkers() {
    perturbationMarkersEl.innerHTML = '';
    if (maxTick <= 0) return;

    for (const tick of perturbationTicks) {
        const pct = (tick / maxTick) * 100;
        const marker = document.createElement('div');
        marker.className = 'perturbation-tick';
        marker.style.left = `${pct}%`;
        marker.title = `Perturbation at tick ${tick}`;
        perturbationMarkersEl.appendChild(marker);
    }
}

// ── Tooltip ──────────────────────────────────────────────────────

function showTooltip(e, snapshot) {
    if (!snapshot) return;

    const rect = canvas.getBoundingClientRect();
    const cellSize = canvas.width / gridSize;
    const mouseX = Math.floor((e.clientX - rect.left) / cellSize);
    const mouseY = Math.floor((e.clientY - rect.top) / cellSize);

    // Check agents at position
    const agentHere = (snapshot.agents || []).find(a => {
        const [ax, ay] = a.position;
        return ax === mouseX && ay === mouseY;
    });

    // Check food at position
    const foodHere = (snapshot.world.food_sources || []).find(f =>
        f.x === mouseX && f.y === mouseY
    );

    if (!agentHere && !foodHere) {
        tooltipEl.classList.add('hidden');
        return;
    }

    let html = '';
    if (agentHere) {
        const status = agentHere.alive ? 'Alive' : 'Dead';
        html += `<div class="tooltip-title">${agentHere.name}</div>`;
        html += `<div class="tooltip-row">Energy: ${agentHere.energy.toFixed(1)} / ${agentHere.max_energy}</div>`;
        html += `<div class="tooltip-row">Position: (${agentHere.position[0]}, ${agentHere.position[1]})</div>`;
        html += `<div class="tooltip-row">Status: ${status} | Age: ${agentHere.age}</div>`;
        if (agentHere.times_perturbed > 0) {
            html += `<div class="tooltip-row">Perturbed: ${agentHere.times_perturbed}x</div>`;
        }
    }
    if (foodHere) {
        if (html) html += '<hr style="border-color:#0f3460;margin:4px 0">';
        html += `<div class="tooltip-title">Food Source</div>`;
        html += `<div class="tooltip-row">Energy: ${foodHere.energy.toFixed(0)} / ${foodHere.max_energy.toFixed(0)}</div>`;
        html += `<div class="tooltip-row">Position: (${foodHere.x}, ${foodHere.y})</div>`;
    }

    tooltipEl.innerHTML = html;
    tooltipEl.classList.remove('hidden');

    // Position tooltip near cursor
    const container = document.getElementById('grid-container');
    const containerRect = container.getBoundingClientRect();
    tooltipEl.style.left = (e.clientX - containerRect.left + 15) + 'px';
    tooltipEl.style.top = (e.clientY - containerRect.top + 15) + 'px';
}

// ── Agent detail panel ───────────────────────────────────────────

async function showAgentDetails(agent) {
    if (!agent) return;
    selectedAgent = agent.name;
    inspectorTitle.textContent = agent.name;

    const energyPct = Math.max(0, (agent.energy / agent.max_energy) * 100);
    let energyClass = 'energy-high';
    if (energyPct < 30) energyClass = 'energy-low';
    else if (energyPct < 60) energyClass = 'energy-mid';

    let html = '';

    // Status section
    html += '<div class="agent-detail-section">';
    html += '<h3>Status</h3>';
    html += `<div class="energy-bar"><div class="energy-bar-fill ${energyClass}" style="width:${energyPct}%"></div></div>`;
    html += `<div class="detail-row"><span class="detail-label">Energy</span><span class="detail-value">${agent.energy.toFixed(1)} / ${agent.max_energy}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Position</span><span class="detail-value">(${agent.position[0]}, ${agent.position[1]})</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Age</span><span class="detail-value">${agent.age} ticks</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Alive</span><span class="detail-value">${agent.alive ? 'Yes' : 'No'}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Kills</span><span class="detail-value">${agent.kills}</span></div>`;
    html += `<div class="detail-row"><span class="detail-label">Perturbed</span><span class="detail-value">${agent.times_perturbed}x</span></div>`;
    html += '</div>';

    // Perturbation events for this agent
    const agentPerturbations = perturbations.filter(p => p.agent === agent.name);
    if (agentPerturbations.length > 0) {
        html += '<div class="agent-detail-section">';
        html += '<h3>Perturbations</h3>';
        for (const p of agentPerturbations.slice(-5)) {
            html += `<div class="detail-row"><span class="detail-label">Tick ${p.tick}</span><span class="detail-value">${p.type} (${p.transform})</span></div>`;
        }
        html += '</div>';
    }

    // Memory file previews (load from agent directory)
    html += '<div class="agent-detail-section">';
    html += '<h3>Memory Files</h3>';
    for (const memFile of ['episodic', 'semantic', 'self', 'social']) {
        const content = await loadMemoryFile(agent.name, memFile);
        html += `<div class="memory-label">${memFile}.md</div>`;
        html += `<div class="memory-preview">${escapeHtml(content || '(empty)')}</div>`;
    }
    html += '</div>';

    // Working notes
    const working = await loadMemoryFile(agent.name, 'working', false);
    html += '<div class="agent-detail-section">';
    html += '<h3>Working Notes</h3>';
    html += `<div class="memory-preview">${escapeHtml(working || '(empty)')}</div>`;
    html += '</div>';

    inspectorContent.innerHTML = html;
}

async function loadMemoryFile(agentName, fileName, isMemory = true) {
    try {
        const subPath = isMemory
            ? `agents/${agentName}/memory/${fileName}.md`
            : `agents/${agentName}/${fileName}.md`;
        const resp = await fetch(`${dataBasePath}${subPath}`);
        if (!resp.ok) return null;
        const text = await resp.text();
        // Truncate for preview
        return text.length > 500 ? text.substring(0, 500) + '...' : text;
    } catch (e) {
        return null;
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Controls ─────────────────────────────────────────────────────

slider.addEventListener('input', async () => {
    currentTick = parseInt(slider.value);
    tickLabel.textContent = `Tick ${currentTick}`;
    const snapshot = await loadSnapshot(currentTick);
    if (snapshot) {
        updateTrails(snapshot);
        render(snapshot);
        // Update selected agent details if one is selected
        if (selectedAgent) {
            const agent = (snapshot.agents || []).find(a => a.name === selectedAgent);
            if (agent) showAgentDetails(agent);
        }
    }
});

playBtn.addEventListener('click', () => {
    playing = !playing;
    playBtn.textContent = playing ? 'Pause' : 'Play';
    playBtn.classList.toggle('playing', playing);

    if (playing) {
        const intervalMs = 500 / playSpeed;
        playInterval = setInterval(async () => {
            if (currentTick >= maxTick) {
                playing = false;
                playBtn.textContent = 'Play';
                playBtn.classList.remove('playing');
                clearInterval(playInterval);
                return;
            }
            currentTick++;
            slider.value = currentTick;
            tickLabel.textContent = `Tick ${currentTick}`;
            const snapshot = await loadSnapshot(currentTick);
            if (snapshot) {
                updateTrails(snapshot);
                render(snapshot);
                if (selectedAgent) {
                    const agent = (snapshot.agents || []).find(a => a.name === selectedAgent);
                    if (agent) showAgentDetails(agent);
                }
            }
        }, intervalMs);
    } else {
        clearInterval(playInterval);
    }
});

// Speed controls
document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        playSpeed = parseFloat(btn.dataset.speed);

        // If currently playing, restart interval with new speed
        if (playing) {
            clearInterval(playInterval);
            const intervalMs = 500 / playSpeed;
            playInterval = setInterval(async () => {
                if (currentTick >= maxTick) {
                    playing = false;
                    playBtn.textContent = 'Play';
                    playBtn.classList.remove('playing');
                    clearInterval(playInterval);
                    return;
                }
                currentTick++;
                slider.value = currentTick;
                tickLabel.textContent = `Tick ${currentTick}`;
                const snapshot = await loadSnapshot(currentTick);
                if (snapshot) {
                    updateTrails(snapshot);
                    render(snapshot);
                }
            }, intervalMs);
        }
    });
});

// Canvas click — select agent
canvas.addEventListener('click', async (e) => {
    const snapshot = await loadSnapshot(currentTick);
    if (!snapshot) return;

    const rect = canvas.getBoundingClientRect();
    const cellSize = canvas.width / gridSize;
    const clickX = Math.floor((e.clientX - rect.left) / cellSize);
    const clickY = Math.floor((e.clientY - rect.top) / cellSize);

    // Find agent at clicked position
    const agent = (snapshot.agents || []).find(a => {
        const [ax, ay] = a.position;
        return ax === clickX && ay === clickY;
    });

    if (agent) {
        showAgentDetails(agent);
        render(snapshot);  // re-render to show selection highlight
    } else {
        // Deselect
        selectedAgent = null;
        inspectorTitle.textContent = 'Click an agent to inspect';
        inspectorContent.innerHTML = '';
        render(snapshot);
    }
});

// Canvas hover — tooltip
canvas.addEventListener('mousemove', async (e) => {
    const snapshot = snapshotCache[currentTick.toString().padStart(6, '0')];
    showTooltip(e, snapshot);
});

canvas.addEventListener('mouseleave', () => {
    tooltipEl.classList.add('hidden');
});

// Checkbox changes trigger re-render
showTrails.addEventListener('change', async () => {
    const snapshot = await loadSnapshot(currentTick);
    render(snapshot);
});
showNames.addEventListener('change', async () => {
    const snapshot = await loadSnapshot(currentTick);
    render(snapshot);
});
showDead.addEventListener('change', async () => {
    const snapshot = await loadSnapshot(currentTick);
    render(snapshot);
});

// ── Keyboard shortcuts ───────────────────────────────────────────

document.addEventListener('keydown', async (e) => {
    if (e.target.tagName === 'INPUT') return;

    if (e.key === ' ' || e.key === 'k') {
        e.preventDefault();
        playBtn.click();
    } else if (e.key === 'ArrowRight' || e.key === 'l') {
        if (currentTick < maxTick) {
            currentTick++;
            slider.value = currentTick;
            tickLabel.textContent = `Tick ${currentTick}`;
            const snapshot = await loadSnapshot(currentTick);
            if (snapshot) {
                updateTrails(snapshot);
                render(snapshot);
            }
        }
    } else if (e.key === 'ArrowLeft' || e.key === 'j') {
        if (currentTick > 0) {
            currentTick--;
            slider.value = currentTick;
            tickLabel.textContent = `Tick ${currentTick}`;
            const snapshot = await loadSnapshot(currentTick);
            if (snapshot) {
                updateTrails(snapshot);
                render(snapshot);
            }
        }
    }
});

// ── Initialization ───────────────────────────────────────────────

async function init() {
    parseParams();
    statusEl.textContent = `Loading from ${dataBasePath}...`;

    await loadPerturbations();
    await discoverMaxTick();

    if (maxTick > 0) {
        statusEl.textContent = `Loaded: ${maxTick} ticks`;
        renderPerturbationMarkers();

        // Detect grid size from first snapshot
        const first = await loadSnapshot(0);
        if (first && first.world && first.world.grid_size) {
            gridSize = first.world.grid_size;
        }

        const snapshot = await loadSnapshot(0);
        if (snapshot) {
            updateTrails(snapshot);
            render(snapshot);
        }
    } else {
        statusEl.textContent =
            'No data found. Set ?data=path/to/experiment in URL, or use: python run.py --replay <dir> --viz';
    }
}

init();
