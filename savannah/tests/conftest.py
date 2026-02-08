"""Shared test fixtures for ILET simulation tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from savannah.src.agent import Agent
from savannah.src.llm import LLMProvider, LLMResponse
from savannah.src.world import World


# ── Config fixtures ─────────────────────────────────────────────


@pytest.fixture
def default_config():
    """Load the real default.yaml config."""
    config_path = Path(__file__).parent.parent / "config" / "default.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def test_config(default_config):
    """Small config for fast tests: 10x10 grid, 4 agents, 10 ticks."""
    cfg = default_config.copy()
    cfg["simulation"] = {
        **cfg["simulation"],
        "ticks": 10,
        "snapshot_every": 5,
        "seed": 42,
    }
    cfg["world"] = {
        **cfg["world"],
        "grid_size": 10,
        "food": {
            "spawn_rate": 0.03,
            "size_min": 100,
            "size_max": 300,
            "decay_rate": 0,
            "min_sources": 3,
            "max_sources": 8,
        },
    }
    cfg["agents"] = {
        **cfg["agents"],
        "count": 4,
        "energy_start": 80,
        "energy_max": 100,
    }
    cfg["llm"] = {
        **cfg["llm"],
        "provider": "mock",
        "max_concurrent_agents": 4,
    }
    cfg["perturbation"] = {
        **cfg["perturbation"],
        "enabled": False,
    }
    return cfg


# ── World fixtures ──────────────────────────────────────────────


@pytest.fixture
def small_world(test_config):
    """A 10x10 world with some food, ready for testing."""
    w = World(test_config["world"], seed=42)
    w.initialize()
    return w


# ── Agent fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_agent(tmp_path):
    """An initialized agent with files in a temp directory."""
    agent = Agent(
        name="Test-Creek",
        id="a1b2c3d4",
        x=5,
        y=5,
        energy=80.0,
        max_energy=100.0,
        vision_range=3,
        food_value=80,
        data_dir=tmp_path,
    )
    agent.initialize_files()
    return agent


@pytest.fixture
def two_agents(tmp_path):
    """Two agents for interaction tests."""
    agents = []
    for i, (name, x, y) in enumerate([("Alpha-Ash", 3, 3), ("Beta-Brook", 7, 7)]):
        agent = Agent(
            name=name,
            id=f"agent_{i:04x}",
            x=x,
            y=y,
            energy=80.0,
            max_energy=100.0,
            vision_range=3,
            food_value=80,
            data_dir=tmp_path,
        )
        agent.initialize_files()
        agents.append(agent)
    return agents


# ── Mock LLM provider ──────────────────────────────────────────


class MockLLMProvider(LLMProvider):
    """Mock LLM that returns canned responses. Tracks calls for assertions."""

    DEFAULT_RESPONSE = (
        "ACTION: rest\n"
        "WORKING: nothing to do\n"
        "REASONING: no food visible, conserving energy"
    )

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses) if responses else []
        self.call_count = 0
        self.prompts: list[str] = []
        self.models: list[str] = []

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        self.call_count += 1
        self.prompts.append(prompt)
        self.models.append(model)
        if self.responses:
            text = self.responses.pop(0)
        else:
            text = self.DEFAULT_RESPONSE
        return LLMResponse(text=text)

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        response = await self.invoke(prompt, model)
        response.session_id = session_id or "mock-session-001"
        return response


@pytest.fixture
def mock_llm():
    """A mock LLM provider with default rest responses."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_actions():
    """A mock LLM that cycles through move, eat, rest actions."""
    responses = [
        "ACTION: move(n)\nWORKING: heading north to find food\nREASONING: I see food to the north",
        "ACTION: eat\nWORKING: eating food here\nREASONING: food at my position",
        "ACTION: rest\nWORKING: resting\nREASONING: no food nearby",
        "ACTION: move(e)\nWORKING: exploring east\nREASONING: trying new direction",
        "ACTION: remember(\"Found food at (3,2)\")\nWORKING: recording food location\nREASONING: want to remember this spot",
        "ACTION: recall(\"food location\")\nWORKING: checking memory for food\nREASONING: where was that food?",
    ]
    # Repeat enough for multiple ticks * multiple agents
    return MockLLMProvider(responses * 20)


# ── Async helpers ───────────────────────────────────────────────


@pytest.fixture
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
