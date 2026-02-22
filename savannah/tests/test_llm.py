"""Tests for the LLM module — provider factory, response dataclass, parsing."""

from __future__ import annotations

import importlib
import json
from unittest.mock import patch

import pytest

from savannah.src.llm import (
    AGENT_SYSTEM_PROMPT,
    ANTHROPIC_MODEL_MAP,
    AnthropicAPIProvider,
    ClaudeCodeProvider,
    LiteLLMProvider,
    LLMResponse,
    TeamModeProvider,
    get_provider,
)
from savannah.tests.conftest import MockLLMProvider


def _has_module(name: str) -> bool:
    """Check if an optional dependency is installed."""
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False

# ── LLMResponse dataclass ────────────────────────────────────────


class TestLLMResponse:
    def test_text_only(self):
        r = LLMResponse(text="hello")
        assert r.text == "hello"
        assert r.session_id is None
        assert r.raw is None

    def test_with_session_id(self):
        r = LLMResponse(text="hello", session_id="sess-42")
        assert r.text == "hello"
        assert r.session_id == "sess-42"
        assert r.raw is None

    def test_with_raw_dict(self):
        raw = {"result": "hello", "session_id": "sess-42", "extra": True}
        r = LLMResponse(text="hello", session_id="sess-42", raw=raw)
        assert r.text == "hello"
        assert r.session_id == "sess-42"
        assert r.raw is raw
        assert r.raw["extra"] is True


# ── MockLLMProvider behaviour ────────────────────────────────────


class TestMockLLMProvider:
    @pytest.mark.asyncio
    async def test_default_response(self):
        provider = MockLLMProvider()
        r = await provider.invoke("test prompt", "test-model")
        assert r.text == MockLLMProvider.DEFAULT_RESPONSE

    @pytest.mark.asyncio
    async def test_queued_responses_in_order(self):
        provider = MockLLMProvider(responses=["first", "second", "third"])
        r1 = await provider.invoke("p1", "m")
        r2 = await provider.invoke("p2", "m")
        r3 = await provider.invoke("p3", "m")
        assert r1.text == "first"
        assert r2.text == "second"
        assert r3.text == "third"

    @pytest.mark.asyncio
    async def test_fallback_to_default_after_queue_exhausts(self):
        provider = MockLLMProvider(responses=["only-one"])
        r1 = await provider.invoke("p1", "m")
        r2 = await provider.invoke("p2", "m")
        assert r1.text == "only-one"
        assert r2.text == MockLLMProvider.DEFAULT_RESPONSE

    @pytest.mark.asyncio
    async def test_tracks_call_count(self):
        provider = MockLLMProvider()
        assert provider.call_count == 0
        await provider.invoke("a", "m")
        await provider.invoke("b", "m")
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_tracks_prompts_and_models(self):
        provider = MockLLMProvider()
        await provider.invoke("prompt-A", "model-X")
        await provider.invoke("prompt-B", "model-Y")
        assert provider.prompts == ["prompt-A", "prompt-B"]
        assert provider.models == ["model-X", "model-Y"]

    @pytest.mark.asyncio
    async def test_invoke_resumable_returns_session_id(self):
        provider = MockLLMProvider()
        r = await provider.invoke_resumable("p", "m", session_id=None)
        assert r.session_id == "mock-session-001"

    @pytest.mark.asyncio
    async def test_invoke_resumable_preserves_given_session_id(self):
        provider = MockLLMProvider()
        r = await provider.invoke_resumable("p", "m", session_id="my-sess")
        assert r.session_id == "my-sess"


# ── get_provider factory ─────────────────────────────────────────


class TestGetProvider:
    def test_claude_code_provider(self):
        provider = get_provider({"provider": "claude_code"})
        assert isinstance(provider, ClaudeCodeProvider)

    @pytest.mark.skipif(
        not _has_module("anthropic"), reason="anthropic SDK not installed"
    )
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_anthropic_api_provider(self):
        provider = get_provider({"provider": "anthropic_api"})
        assert isinstance(provider, AnthropicAPIProvider)

    @pytest.mark.skipif(
        not _has_module("litellm"), reason="litellm not installed"
    )
    def test_litellm_provider(self):
        provider = get_provider({"provider": "litellm"})
        assert isinstance(provider, LiteLLMProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider({"provider": "nonexistent"})


# ── ClaudeCodeProvider ───────────────────────────────────────────


class TestClaudeCodeProvider:
    def _make_provider(self, **overrides):
        config = {"lean_mode": True}
        config.update(overrides)
        return ClaudeCodeProvider(config=config)

    def test_parse_valid_json(self):
        provider = self._make_provider()
        data = {"result": "move(n)", "session_id": "sess-99"}
        raw = json.dumps(data)
        r = provider._parse_output(raw)
        assert r.text == "move(n)"
        assert r.session_id == "sess-99"
        assert r.raw == data

    def test_parse_non_json_returns_raw_text(self):
        provider = self._make_provider()
        raw = "ACTION: rest\nWORKING: nothing"
        r = provider._parse_output(raw)
        assert r.text == raw.strip()
        assert r.session_id is None
        assert r.raw is None

    def test_parse_empty_json_object(self):
        """Empty JSON {} has no 'result' key, so text falls back to the raw string."""
        provider = self._make_provider()
        raw = "{}"
        r = provider._parse_output(raw)
        assert r.text == raw
        assert r.session_id is None
        assert r.raw == {}

    def test_lean_mode_builds_stripped_command(self):
        provider = self._make_provider(lean_mode=True)
        cmd = provider._build_cmd("haiku")
        assert "--tools" in cmd
        assert "" in cmd  # empty string for --tools
        assert "--strict-mcp-config" in cmd
        assert "--system-prompt" in cmd
        assert "--disable-slash-commands" in cmd
        assert "--no-session-persistence" in cmd

    def test_non_lean_mode_builds_minimal_command(self):
        provider = self._make_provider(lean_mode=False)
        cmd = provider._build_cmd("haiku")
        assert "--tools" not in cmd
        assert "--strict-mcp-config" not in cmd

    def test_default_system_prompt(self):
        provider = self._make_provider()
        assert provider.system_prompt == AGENT_SYSTEM_PROMPT

    def test_custom_system_prompt(self):
        provider = self._make_provider(system_prompt="custom prompt")
        assert provider.system_prompt == "custom prompt"


# ── AnthropicAPIProvider ─────────────────────────────────────────


@pytest.mark.skipif(not _has_module("anthropic"), reason="anthropic SDK not installed")
class TestAnthropicAPIProvider:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_resolve_model_aliases(self):
        provider = AnthropicAPIProvider(config={})
        for alias, expected in ANTHROPIC_MODEL_MAP.items():
            assert provider._resolve_model(alias) == expected

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_resolve_model_passthrough(self):
        provider = AnthropicAPIProvider(config={})
        assert provider._resolve_model("claude-3-opus-20240229") == "claude-3-opus-20240229"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_config_defaults(self):
        provider = AnthropicAPIProvider(config={})
        assert provider.temperature == 0.3
        assert provider.max_tokens == 400
        assert provider.system_prompt == AGENT_SYSTEM_PROMPT

    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True), pytest.raises(
            ValueError, match="ANTHROPIC_API_KEY"
        ):
            AnthropicAPIProvider(config={})


# ── LiteLLMProvider ──────────────────────────────────────────────


@pytest.mark.skipif(not _has_module("litellm"), reason="litellm not installed")
class TestLiteLLMProvider:
    def test_resolve_model_aliases(self):
        provider = LiteLLMProvider(config={})
        assert provider._resolve_model("haiku") == "anthropic/claude-haiku-4-5-20251001"
        assert provider._resolve_model("sonnet") == "anthropic/claude-sonnet-4-5-20250929"
        assert provider._resolve_model("opus") == "anthropic/claude-opus-4-6"

    def test_resolve_model_passthrough(self):
        provider = LiteLLMProvider(config={})
        assert provider._resolve_model("gpt-4o") == "gpt-4o"
        assert provider._resolve_model("ollama/llama3") == "ollama/llama3"

    def test_config_defaults(self):
        provider = LiteLLMProvider(config={})
        assert provider.temperature == 0.3
        assert provider.max_tokens == 400
        assert provider.system_prompt == AGENT_SYSTEM_PROMPT
        assert provider.api_base is None

    def test_custom_api_base(self):
        provider = LiteLLMProvider(config={"api_base": "http://localhost:11434"})
        assert provider.api_base == "http://localhost:11434"


# ── TeamModeProvider ──────────────────────────────────────────────


class TestTeamModeProvider:
    def test_team_mode_provider_registered(self):
        """get_provider with 'team' should return a TeamModeProvider."""
        provider = get_provider({"provider": "team"})
        assert isinstance(provider, TeamModeProvider)

    @pytest.mark.asyncio
    async def test_team_mode_provider_invoke_raises(self):
        """TeamModeProvider.invoke() should raise NotImplementedError."""
        provider = TeamModeProvider({})
        with pytest.raises(NotImplementedError, match="Team mode"):
            await provider.invoke("test", "haiku")
