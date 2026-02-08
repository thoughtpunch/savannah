/**
 * ILET Savannah Viewer — Canvas-based grid renderer + timeline control.
 * Reads tick snapshot JSON files and renders the world state.
 */

const canvas = document.getElementById('grid');
const ctx = canvas.getContext('2d');
const slider = document.getElementById('tick-slider');
const tickLabel = document.getElementById('tick-label');
const playBtn = document.getElementById('play-btn');
const inspectorTitle = document.getElementById('inspector-title');
const inspectorContent = document.getElementById('inspector-content');
const showTrails = document.getElementById('show-trails');
const showNames = document.getElementById('show-names');

let currentTick = 0;
let maxTick = 0;
let playing = false;
let playInterval = null;
let snapshotCache = {};
let dataBasePath = '';
let gridSize = 30;

// ── Data loading ──────────────────────────────────────────────────

async function loadSnapshot(tick) {
    const key = tick.toString().padStart(6, '0');
    if (snapshotCache[key]) return snapshotCache[key];

    try {
        const resp = await fetch(`${dataBasePath}/logs/ticks/${key}.json`);
        if (!resp.ok) return null;
        const data = await resp.json();
        snapshotCache[key] = data;

        // Keep cache manageable (sliding window of 50)
        const keys = Object.keys(snapshotCache);
        if (keys.length > 50) {
            delete snapshotCache[keys[0]];
        }
        return data;
    } catch (e) {
        console.warn(`Failed to load tick ${tick}:`, e);
        return null;
    }
}

// ── Rendering ─────────────────────────────────────────────────────

function render(snapshot) {
    if (!snapshot) return;

    const cellSize = canvas.width / gridSize;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Grid background
    ctx.fillStyle = '#2a2a1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Grid lines
    ctx.strokeStyle = '#3a3a2a';
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

    // Food sources (green, opacity = energy/max)
    for (const food of snapshot.world.food_sources || []) {
        const opacity = Math.max(0.2, food.energy / food.max_energy);
        ctx.fillStyle = `rgba(34, 197, 94, ${opacity})`;
        ctx.fillRect(food.x * cellSize + 1, food.y * cellSize + 1, cellSize - 2, cellSize - 2);
    }

    // Agents (colored dots)
    const colors = [
        '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6',
        '#8b5cf6', '#ec4899', '#f43f5e', '#14b8a6', '#a855f7', '#6366f1',
    ];

    for (let i = 0; i < (snapshot.agents || []).length; i++) {
        const agent = snapshot.agents[i];
        if (!agent.alive) continue;

        const [x, y] = agent.position;
        const color = colors[i % colors.length];
        const cx = x * cellSize + cellSize / 2;
        const cy = y * cellSize + cellSize / 2;
        const radius = cellSize * 0.35;

        // Agent dot
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // Energy ring
        const energyFrac = agent.energy / agent.max_energy;
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 2, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * energyFrac);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Name label
        if (showNames.checked) {
            ctx.fillStyle = '#fff';
            ctx.font = '9px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(agent.name, cx, cy - radius - 4);
        }
    }
}

// ── Controls ──────────────────────────────────────────────────────

slider.addEventListener('input', async () => {
    currentTick = parseInt(slider.value);
    tickLabel.textContent = `Tick ${currentTick}`;
    const snapshot = await loadSnapshot(currentTick);
    render(snapshot);
});

playBtn.addEventListener('click', () => {
    playing = !playing;
    playBtn.textContent = playing ? 'Pause' : 'Play';

    if (playing) {
        playInterval = setInterval(async () => {
            if (currentTick >= maxTick) {
                playing = false;
                playBtn.textContent = 'Play';
                clearInterval(playInterval);
                return;
            }
            currentTick++;
            slider.value = currentTick;
            tickLabel.textContent = `Tick ${currentTick}`;
            const snapshot = await loadSnapshot(currentTick);
            render(snapshot);
        }, 200);
    } else {
        clearInterval(playInterval);
    }
});

canvas.addEventListener('click', async (e) => {
    const snapshot = await loadSnapshot(currentTick);
    if (!snapshot) return;

    const cellSize = canvas.width / gridSize;
    const clickX = Math.floor(e.offsetX / cellSize);
    const clickY = Math.floor(e.offsetY / cellSize);

    // Find agent at clicked position
    const agent = (snapshot.agents || []).find(a => {
        const [ax, ay] = a.position;
        return ax === clickX && ay === clickY && a.alive;
    });

    if (agent) {
        inspectorTitle.textContent = agent.name;
        inspectorContent.innerHTML = `
            <div><strong>Energy:</strong> ${agent.energy.toFixed(1)} / ${agent.max_energy}</div>
            <div><strong>Position:</strong> (${agent.position[0]}, ${agent.position[1]})</div>
            <div><strong>Age:</strong> ${agent.age} ticks</div>
            <div><strong>Kills:</strong> ${agent.kills}</div>
            <div><strong>Perturbed:</strong> ${agent.times_perturbed}x</div>
        `;
    }
});

// ── Initialization ────────────────────────────────────────────────

document.getElementById('status').textContent =
    'Set dataBasePath in app.js or use the CLI: python run.py --replay <dir> --viz';
