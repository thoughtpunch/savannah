"""Provider-agnostic LLM interface. Claude Code headless mode is the default."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str
    session_id: str | None = None
    raw: dict | None = None


class LLMProvider(ABC):
    """Base interface for LLM providers."""

    @abstractmethod
    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Stateless single-shot inference."""
        ...

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        """Resume a persistent session. Returns response with session_id."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support resumable sessions"
        )


class ClaudeCodeProvider(LLMProvider):
    """Uses `claude -p` CLI for inference (Pro Max, $0 marginal cost)."""

    def __init__(self, config: dict):
        self.timeout = config.get("timeout_seconds", 30)
        self.retry_max = config.get("retry_max", 3)
        self.retry_backoff = config.get("retry_backoff_base", 2)

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Run `claude -p` as a subprocess."""
        for attempt in range(self.retry_max):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "claude", "-p", prompt,
                    "--output-format", "json",
                    "--model", model,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout
                )

                if proc.returncode != 0:
                    logger.warning(
                        "claude -p returned %d: %s",
                        proc.returncode, stderr.decode()[:200],
                    )
                    if attempt < self.retry_max - 1:
                        await asyncio.sleep(self.retry_backoff ** attempt)
                        continue
                    return LLMResponse(text="rest")  # fallback

                return self._parse_output(stdout.decode())

            except asyncio.TimeoutError:
                logger.warning("claude -p timed out (attempt %d)", attempt + 1)
                if attempt < self.retry_max - 1:
                    await asyncio.sleep(self.retry_backoff ** attempt)
                    continue
                return LLMResponse(text="rest")

        return LLMResponse(text="rest")

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        """Resume a Claude Code session using --resume flag."""
        cmd = ["claude"]
        if session_id:
            cmd.extend(["--resume", session_id])
        cmd.extend(["-p", prompt, "--output-format", "json", "--model", model])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=self.timeout
        )

        if proc.returncode != 0:
            logger.warning("claude --resume failed: %s", stderr.decode()[:200])
            return LLMResponse(text="rest")

        response = self._parse_output(stdout.decode())
        return response

    def _parse_output(self, raw: str) -> LLMResponse:
        """Parse Claude Code JSON output."""
        try:
            data = json.loads(raw)
            return LLMResponse(
                text=data.get("result", raw),
                session_id=data.get("session_id"),
                raw=data,
            )
        except json.JSONDecodeError:
            # Raw text output (non-JSON mode fallback)
            return LLMResponse(text=raw.strip())


class AnthropicAPIProvider(LLMProvider):
    """Direct Anthropic API via SDK. Stateless only."""

    def __init__(self, config: dict):
        self.config = config
        # TODO: initialize anthropic client

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        raise NotImplementedError("Anthropic API provider not yet implemented")


class OpenAIAPIProvider(LLMProvider):
    """OpenAI API. Stateless only."""

    def __init__(self, config: dict):
        self.config = config

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        raise NotImplementedError("OpenAI API provider not yet implemented")


class OllamaProvider(LLMProvider):
    """Local models via ollama HTTP server. Stateless only."""

    def __init__(self, config: dict):
        self.base_url = config.get("ollama_base_url", "http://localhost:11434")

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        raise NotImplementedError("Ollama provider not yet implemented")


def get_provider(config: dict) -> LLMProvider:
    """Factory: return the configured LLM provider."""
    provider_name = config.get("provider", "claude_code")
    providers = {
        "claude_code": ClaudeCodeProvider,
        "anthropic_api": AnthropicAPIProvider,
        "openai_api": OpenAIAPIProvider,
        "local_ollama": OllamaProvider,
    }
    cls = providers.get(provider_name)
    if not cls:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
    return cls(config)
