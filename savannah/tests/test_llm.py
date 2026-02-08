"""Tests for the LLM module — provider factory, response dataclass, parsing."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio

from savannah.src.llm import (
    AnthropicAPIProvider,
    ClaudeCodeProvider,
    LLMResponse,
    get_provider,
)
from savannah.tests.conftest import MockLLMProvider


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

    def test_anthropic_api_provider(self):
        provider = get_provider({"provider": "anthropic_api"})
        assert isinstance(provider, AnthropicAPIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider({"provider": "nonexistent"})


# ── ClaudeCodeProvider._parse_output ─────────────────────────────


class TestClaudeCodeProvider:
    def _make_provider(self):
        return ClaudeCodeProvider(config={})

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
        # json.loads succeeds, data.get("result", raw) returns raw since no "result" key
        assert r.text == raw
        assert r.session_id is None
        assert r.raw == {}
