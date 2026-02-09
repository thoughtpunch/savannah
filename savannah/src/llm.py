"""Provider-agnostic LLM interface. Claude Code headless mode is the default."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Model alias → Anthropic API model ID
ANTHROPIC_MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-6",
}

# Minimal system prompt for agents — no tools, no Claude Code overhead.
# ~30 tokens vs 74K for claude -p.
AGENT_SYSTEM_PROMPT = (
    "You are an agent in a survival simulation. "
    "Choose actions to find food and survive. "
    "Respond in the exact format specified in the prompt."
)


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
    """Uses `claude -p` CLI for inference (Pro Max, $0 marginal cost).

    Runs in "lean mode" by default: strips all tools, MCP servers, skills,
    and the default system prompt — reducing overhead from ~74K tokens to ~1-2K.
    """

    def __init__(self, config: dict):
        self.timeout = config.get("timeout_seconds", 120)
        self.retry_max = config.get("retry_max", 3)
        self.retry_backoff = config.get("retry_backoff_base", 2)
        self.system_prompt = config.get("system_prompt", AGENT_SYSTEM_PROMPT)
        self.lean = config.get("lean_mode", True)

    def _build_cmd(self, model: str) -> list[str]:
        """Build the claude -p command with lean-mode flags."""
        cmd = ["claude", "-p", "--output-format", "json", "--model", model]
        if self.lean:
            # Strip all tools (~20K tokens saved)
            cmd.extend(["--tools", ""])
            # Strip all MCP servers (~30K tokens saved)
            cmd.append("--strict-mcp-config")
            # Replace default system prompt (~15K → ~30 tokens)
            cmd.extend(["--system-prompt", self.system_prompt])
            # Strip skills
            cmd.append("--disable-slash-commands")
            # Don't persist session files to disk
            cmd.append("--no-session-persistence")
        return cmd

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Run `claude -p` as a subprocess, piping prompt via stdin."""
        cmd = self._build_cmd(model)

        for attempt in range(self.retry_max):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode()), timeout=self.timeout
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

            except TimeoutError:
                logger.warning("claude -p timed out (attempt %d)", attempt + 1)
                if attempt < self.retry_max - 1:
                    await asyncio.sleep(self.retry_backoff ** attempt)
                    continue
                return LLMResponse(text="rest")

        return LLMResponse(text="rest")

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        """Resume a Claude Code session using --resume flag.

        Note: resumable mode disables lean mode since sessions need full context.
        """
        cmd = ["claude"]
        if session_id:
            cmd.extend(["--resume", session_id])
        cmd.extend(["-p", "--output-format", "json", "--model", model])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()), timeout=self.timeout
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
    """Direct Anthropic API via SDK — ~30 token system prompt vs 74K for claude -p.

    Requires: pip install anthropic
    Config keys:
        anthropic_api_key: API key or "env:VAR_NAME" (default: env:ANTHROPIC_API_KEY)
        temperature: float (default: 0.3)
        max_output_tokens: int (default: 400)
        timeout_seconds: int (default: 120)
        retry_max: int (default: 3)
        retry_backoff_base: int (default: 2)
        system_prompt: str (optional override for the default agent system prompt)
    """

    def __init__(self, config: dict):
        self.config = config
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_output_tokens", 400)
        self.timeout = config.get("timeout_seconds", 120)
        self.retry_max = config.get("retry_max", 3)
        self.retry_backoff = config.get("retry_backoff_base", 2)
        self.system_prompt = config.get("system_prompt", AGENT_SYSTEM_PROMPT)

        api_key = self._resolve_api_key(config)
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=api_key,
                timeout=self.timeout,
            )
        except ImportError as exc:
            raise ImportError(
                "anthropic package required for AnthropicAPIProvider. "
                "Install with: pip install anthropic"
            ) from exc

    def _resolve_api_key(self, config: dict) -> str:
        """Resolve API key from config or environment."""
        raw = config.get("anthropic_api_key", "env:ANTHROPIC_API_KEY")
        if isinstance(raw, str) and raw.startswith("env:"):
            var_name = raw[4:]
            key = os.environ.get(var_name)
            if not key:
                raise ValueError(
                    f"Environment variable {var_name} not set. "
                    f"Set it or provide anthropic_api_key in config."
                )
            return key
        return raw

    def _resolve_model(self, alias: str) -> str:
        """Map model alias to Anthropic API model ID."""
        return ANTHROPIC_MODEL_MAP.get(alias, alias)

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Single-shot inference via Anthropic Messages API."""
        model_id = self._resolve_model(model)

        for attempt in range(self.retry_max):
            try:
                response = await self._client.messages.create(
                    model=model_id,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                return LLMResponse(
                    text=text,
                    raw={
                        "model": response.model,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                        },
                        "stop_reason": response.stop_reason,
                    },
                )

            except Exception as e:
                logger.warning(
                    "Anthropic API error (attempt %d/%d): %s",
                    attempt + 1, self.retry_max, e,
                )
                if attempt < self.retry_max - 1:
                    await asyncio.sleep(self.retry_backoff ** attempt)
                    continue
                return LLMResponse(text="rest")  # safe fallback

        return LLMResponse(text="rest")


class LiteLLMProvider(LLMProvider):
    """Universal provider via litellm — supports Anthropic, OpenAI, Google,
    Ollama, Groq, Together, and 100+ other providers through one interface.

    Requires: pip install litellm

    Model format examples:
        "anthropic/claude-haiku-4-5-20251001"  (explicit provider prefix)
        "gpt-4o"                               (OpenAI auto-detected)
        "ollama/llama3"                        (local Ollama)
        "groq/llama3-70b-8192"                 (Groq cloud)
        "together_ai/meta-llama/Llama-3-70b"   (Together AI)

    Aliases (haiku/sonnet/opus) are expanded to anthropic/ prefixed model IDs.

    Config keys:
        model: str — model name or alias
        temperature: float (default: 0.3)
        max_output_tokens: int (default: 400)
        timeout_seconds: int (default: 120)
        retry_max: int (default: 3)
        retry_backoff_base: int (default: 2)
        system_prompt: str (optional override)
        api_base: str (optional — for custom endpoints like Ollama)
    """

    # Alias → litellm model string (provider-prefixed)
    MODEL_ALIASES = {
        "haiku": "anthropic/claude-haiku-4-5-20251001",
        "sonnet": "anthropic/claude-sonnet-4-5-20250929",
        "opus": "anthropic/claude-opus-4-6",
    }

    def __init__(self, config: dict):
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_output_tokens", 400)
        self.timeout = config.get("timeout_seconds", 120)
        self.retry_max = config.get("retry_max", 3)
        self.retry_backoff = config.get("retry_backoff_base", 2)
        self.system_prompt = config.get("system_prompt", AGENT_SYSTEM_PROMPT)
        self.api_base = config.get("api_base")

        try:
            import litellm
            self._litellm = litellm
            # Suppress litellm's verbose logging
            litellm.suppress_debug_info = True
        except ImportError as exc:
            raise ImportError(
                "litellm package required for LiteLLMProvider. "
                "Install with: pip install litellm"
            ) from exc

    def _resolve_model(self, alias: str) -> str:
        """Map alias to litellm model string, or pass through as-is."""
        return self.MODEL_ALIASES.get(alias, alias)

    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Single-shot inference via litellm.acompletion (OpenAI-compatible)."""
        model_id = self._resolve_model(model)

        kwargs: dict = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base

        for attempt in range(self.retry_max):
            try:
                response = await self._litellm.acompletion(**kwargs)
                text = response.choices[0].message.content
                usage = response.usage
                return LLMResponse(
                    text=text,
                    raw={
                        "model": response.model,
                        "usage": {
                            "input_tokens": usage.prompt_tokens,
                            "output_tokens": usage.completion_tokens,
                        },
                        "finish_reason": response.choices[0].finish_reason,
                        "provider": "litellm",
                    },
                )

            except Exception as e:
                logger.warning(
                    "litellm error (attempt %d/%d, model=%s): %s",
                    attempt + 1, self.retry_max, model_id, e,
                )
                if attempt < self.retry_max - 1:
                    await asyncio.sleep(self.retry_backoff ** attempt)
                    continue
                return LLMResponse(text="rest")

        return LLMResponse(text="rest")


def get_provider(config: dict) -> LLMProvider:
    """Factory: return the configured LLM provider.

    Providers:
        "claude_code"    — claude -p subprocess ($0 with Pro Max, lean mode)
        "anthropic_api"  — direct Anthropic SDK (fast, needs API key)
        "litellm"        — any provider via litellm (Anthropic, OpenAI, Ollama, etc.)
    """
    provider_name = config.get("provider", "claude_code")
    providers = {
        "claude_code": ClaudeCodeProvider,
        "anthropic_api": AnthropicAPIProvider,
        "litellm": LiteLLMProvider,
    }
    cls = providers.get(provider_name)
    if not cls:
        raise ValueError(
            f"Unknown LLM provider: {provider_name!r}. "
            f"Available: {', '.join(providers)}"
        )
    return cls(config)
