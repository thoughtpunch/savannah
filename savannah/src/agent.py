"""Agent state management, file I/O, and prompt construction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .world import World

PROMPT_TEMPLATE = """[Tick {tick}] You are {name}.
Energy: {energy}/{max_energy}. Position: ({x},{y}).

VISIBLE ({vision_range}-cell radius):
{grid_description}

INCOMING SIGNALS:
{messages}

WORKING NOTES (your scratch space from last tick):
{working}

{recall_results}

ACTIONS (pick exactly one):
move(n|s|e|w) | eat | recall("query") | remember("text")
compact | signal("msg") | observe | attack(name) | flee(n|s|e|w) | rest

Respond in this exact format:
ACTION: {{your action}}
WORKING: {{updated scratch notes, max 500 tokens}}
REASONING: {{brief}}"""


@dataclass
class Agent:
    """A single simulated agent with state and file-based memory."""

    name: str
    id: str
    x: int
    y: int
    energy: float
    max_energy: float
    age: int = 0
    alive: bool = True
    food_value: int = 80
    vision_range: int = 3
    kills: int = 0
    times_perturbed: int = 0
    last_perturbation_tick: int = 0
    data_dir: Path = field(default_factory=lambda: Path("."))
    pending_signals: list[str] = field(default_factory=list)
    pending_recall_results: list[str] = field(default_factory=list)
    session_id: str | None = None

    # ── File paths ──────────────────────────────────────────────

    @property
    def agent_dir(self) -> Path:
        return self.data_dir / "agents" / self.name

    @property
    def memory_dir(self) -> Path:
        return self.agent_dir / "memory"

    @property
    def working_path(self) -> Path:
        return self.agent_dir / "working.md"

    @property
    def state_path(self) -> Path:
        return self.agent_dir / "state.json"

    @property
    def session_path(self) -> Path:
        return self.agent_dir / "session.json"

    # ── Lifecycle ───────────────────────────────────────────────

    def initialize_files(self) -> None:
        """Create initial agent files. All agents start identical."""
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)

        self.working_path.write_text("")
        (self.memory_dir / "episodic.md").write_text("")
        (self.memory_dir / "semantic.md").write_text(
            f"I am {self.name}. I need food to maintain energy."
        )
        (self.memory_dir / "self.md").write_text(f"I am {self.name}.")
        (self.memory_dir / "social.md").write_text("")

        self.save_state()

    def drain(self, amount: float) -> None:
        """Apply passive energy drain. Kill if energy <= 0."""
        self.energy -= amount
        if self.energy <= 0:
            self.energy = 0
            self.alive = False

    # ── Prompt construction ─────────────────────────────────────

    def build_prompt(self, world: World, tick: int) -> str:
        """Construct the tick prompt from current state + files."""
        working = self._read_file(self.working_path)
        visible = world.visible_from(self.x, self.y, self.vision_range)
        grid_desc = self._format_visible(visible)
        messages = "\n".join(self.pending_signals) if self.pending_signals else "None"
        recall = ""
        if self.pending_recall_results:
            recall = "RECALL RESULTS:\n" + "\n".join(self.pending_recall_results)

        prompt = PROMPT_TEMPLATE.format(
            tick=tick,
            name=self.name,
            energy=f"{self.energy:.1f}",
            max_energy=f"{self.max_energy:.1f}",
            x=self.x,
            y=self.y,
            vision_range=self.vision_range,
            grid_description=grid_desc,
            messages=messages,
            working=working or "(empty)",
            recall_results=recall,
        )

        # Clear pending after inclusion in prompt
        self.pending_signals = []
        self.pending_recall_results = []
        return prompt

    # ── Serialization ───────────────────────────────────────────

    def save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.to_dict(), indent=2))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "id": self.id,
            "position": [self.x, self.y],
            "energy": self.energy,
            "max_energy": self.max_energy,
            "age": self.age,
            "alive": self.alive,
            "food_value": self.food_value,
            "vision_range": self.vision_range,
            "kills": self.kills,
            "times_perturbed": self.times_perturbed,
            "last_perturbation_tick": self.last_perturbation_tick,
        }

    # ── Private helpers ─────────────────────────────────────────

    def _read_file(self, path: Path) -> str:
        try:
            return path.read_text().strip()
        except FileNotFoundError:
            return ""

    def _format_visible(self, visible: dict) -> str:
        parts = []
        for food in visible.get("food", []):
            parts.append(
                f"  Food at ({food['x']},{food['y']}): {food['energy']:.0f} energy"
            )
        for agent in visible.get("agents", []):
            parts.append(
                f"  Agent {agent['name']} at ({agent['x']},{agent['y']})"
            )
        return "\n".join(parts) if parts else "  Nothing visible."
