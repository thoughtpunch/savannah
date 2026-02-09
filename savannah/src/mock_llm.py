"""Smart mock LLM provider — plays the game without API calls.

Parses agent prompts to extract position, energy, and visible food/agents,
then makes reasonable decisions: move toward food, eat when on food,
flee when low energy and threatened, occasionally remember/signal.
"""

from __future__ import annotations

import random
import re

from .llm import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock that parses prompts and plays a simple survival strategy."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
        self._tick_count = 0

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        self._tick_count += 1
        state = _parse_prompt(prompt)
        action, working, reasoning = _decide(state, self._rng)
        text = f"ACTION: {action}\nWORKING: {working}\nREASONING: {reasoning}"
        return LLMResponse(text=text)

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        response = await self.invoke(prompt, model)
        response.session_id = session_id or "mock-session-001"
        return response


def _parse_prompt(prompt: str) -> dict:
    """Extract structured state from the agent tick prompt."""
    state: dict = {
        "name": "",
        "x": 0,
        "y": 0,
        "energy": 0.0,
        "max_energy": 100.0,
        "tick": 0,
        "food": [],
        "agents": [],
        "signals": [],
    }

    # [Tick N] You are Name.
    m = re.search(r"\[Tick (\d+)\] You are ([^.]+)\.", prompt)
    if m:
        state["tick"] = int(m.group(1))
        state["name"] = m.group(2)

    # Energy: X/Y. Position: (x,y).
    m = re.search(r"Energy:\s*(\d+\.?\d*)/(\d+\.?\d*)\.\s*Position:\s*\((\d+),(\d+)\)", prompt)
    if m:
        state["energy"] = float(m.group(1))
        state["max_energy"] = float(m.group(2))
        state["x"] = int(m.group(3))
        state["y"] = int(m.group(4))

    # Food at (x,y): N energy
    for m in re.finditer(r"Food at \((\d+),(\d+)\):\s*(\d+) energy", prompt):
        state["food"].append({
            "x": int(m.group(1)),
            "y": int(m.group(2)),
            "energy": int(m.group(3)),
        })

    # Agent Name at (x,y)
    for m in re.finditer(r"Agent (\S+) at \((\d+),(\d+)\)", prompt):
        state["agents"].append({
            "name": m.group(1),
            "x": int(m.group(2)),
            "y": int(m.group(3)),
        })

    # Signals
    if "INCOMING SIGNALS:" in prompt:
        sig_block = prompt.split("INCOMING SIGNALS:")[1].split("WORKING NOTES")[0].strip()
        if sig_block and sig_block != "None":
            state["signals"] = [s.strip() for s in sig_block.split("\n") if s.strip()]

    return state


def _decide(state: dict, rng: random.Random) -> tuple[str, str, str]:
    """Simple survival AI: eat > move-to-food > explore > rest."""
    x, y = state["x"], state["y"]
    energy = state["energy"]
    max_energy = state["max_energy"]
    food_list = state["food"]
    agents = state["agents"]
    tick = state["tick"]

    # Check if food is at our exact position
    food_here = [f for f in food_list if f["x"] == x and f["y"] == y]
    if food_here and energy < max_energy:
        return "eat", f"Eating food at my position ({x},{y})", "There is food here and I need energy"

    # If there's visible food, move toward the nearest one
    if food_list:
        # Pick the closest food (Manhattan distance, ignoring wrapping for simplicity)
        best = min(food_list, key=lambda f: abs(f["x"] - x) + abs(f["y"] - y))
        dx = best["x"] - x
        dy = best["y"] - y

        # Pick direction toward food
        if abs(dx) >= abs(dy):
            direction = "e" if dx > 0 else "w"
            reason = f"Moving {'east' if dx > 0 else 'west'} toward food at ({best['x']},{best['y']})"
        else:
            direction = "s" if dy > 0 else "n"
            reason = f"Moving {'south' if dy > 0 else 'north'} toward food at ({best['x']},{best['y']})"

        working = f"Food spotted at ({best['x']},{best['y']}) with {best['energy']} energy. Heading there."
        return f"move({direction})", working, reason

    # Low energy and no food visible — try to remember where food was
    if energy < max_energy * 0.4 and tick > 5 and rng.random() < 0.3:
        return 'recall("food location")', "Low energy, checking memory for food", "Running low on energy with no food visible, searching memory"

    # Occasionally remember things
    if rng.random() < 0.05 and tick > 1:
        notes = [
            f"No food visible from ({x},{y})",
            f"Energy at {energy:.0f}/{max_energy:.0f}",
            f"Explored area around ({x},{y})",
        ]
        note = rng.choice(notes)
        return f'remember("{note}")', f"Recording observation at tick {tick}", "Making a note for future reference"

    # Occasionally signal if other agents are nearby
    if agents and rng.random() < 0.08:
        msg = rng.choice([
            "no food here",
            "searching for food",
            f"heading {rng.choice(['north', 'south', 'east', 'west'])}",
        ])
        return f'signal("{msg}")', "Communicating with nearby agents", "Other agents are nearby, sharing information"

    # Default: explore in a random direction
    direction = rng.choice(["n", "s", "e", "w"])
    dir_names = {"n": "north", "s": "south", "e": "east", "w": "west"}
    return (
        f"move({direction})",
        f"Exploring {dir_names[direction]} from ({x},{y}). No food visible.",
        f"No food in sight, exploring {dir_names[direction]} to find resources",
    )
