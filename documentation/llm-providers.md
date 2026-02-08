# LLM Provider System

ILET uses a provider-agnostic LLM interface defined in `savannah/src/llm.py`. All inference calls go through this abstraction, allowing the simulation to run on different backends without changing any other code.

## The LLMProvider ABC

```python
class LLMProvider(ABC):
    @abstractmethod
    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Stateless single-shot inference."""
        ...

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        """Resume a persistent session. Returns response with session_id
        for subsequent calls. Raises NotImplementedError if provider
        doesn't support resumable sessions."""
        raise NotImplementedError(...)
```

The `LLMResponse` dataclass:

```python
@dataclass
class LLMResponse:
    text: str                      # The model's response text
    session_id: str | None = None  # Session ID for resumable mode
    raw: dict | None = None        # Raw provider-specific response data
```

The `invoke()` method is required for all providers. The `invoke_resumable()` method defaults to `NotImplementedError` -- providers that support persistent sessions override it.

## Providers

### claude_code (Default)

**Mechanism**: Runs `claude -p` as an async subprocess via `asyncio.create_subprocess_exec()`.

**Cost**: $0 marginal cost with a Pro Max subscription. The practical constraint is wall-clock time, not money.

**Session modes**: Supports both `stateless` and `resumable`.

- **Stateless**: Each tick is an independent `claude -p` call. No context carries between ticks.
- **Resumable**: First tick captures a `session_id` from the response. Subsequent ticks use `claude --resume <session_id> -p` to continue the session. Context accumulates naturally in the LLM's context window.

**Model selection**: Via `--model` flag. `haiku` for tick inference (fastest), `sonnet` for compaction (stronger reasoning), `opus` for analysis only.

**Error handling**: On non-zero exit code or timeout, retries up to `retry_max` times with exponential backoff. Falls back to `LLMResponse(text="rest")` on exhausted retries -- the parser interprets this as a rest action.

```python
class ClaudeCodeProvider(LLMProvider):
    async def invoke(self, prompt: str, model: str) -> LLMResponse:
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
        return self._parse_output(stdout.decode())

    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None = None
    ) -> LLMResponse:
        cmd = ["claude"]
        if session_id:
            cmd.extend(["--resume", session_id])
        cmd.extend(["-p", prompt, "--output-format", "json", "--model", model])
        # ... subprocess execution ...
```

### anthropic_api

**Mechanism**: Direct Anthropic API via the `anthropic` Python SDK.

**Cost**: Per-token billing. Haiku is cheapest (~$0.00003/call at ~600 tokens), Sonnet ~10x more.

**Session modes**: Stateless only. Resumable would require maintaining a full conversation history and re-sending it each tick (expensive but possible as a future enhancement).

**Status**: Stub implementation. `invoke()` raises `NotImplementedError`.

### openai_api

**Mechanism**: OpenAI API for cross-model comparison experiments.

**Cost**: Per-token billing, varies by model.

**Session modes**: Stateless only.

**Status**: Stub implementation. For Phase 5 multi-model comparison.

### local_ollama

**Mechanism**: HTTP calls to a local Ollama server (`ollama serve`).

**Cost**: Free. No rate limits. Runs on local GPU.

**Session modes**: Stateless only.

**Models**: Llama 3 8B, Mistral 7B, or any model supported by Ollama.

**Use cases**:
- Rapid iteration on simulation mechanics without consuming API calls
- Offline development
- Phase 5 cross-model comparison experiments

**Status**: Stub implementation. Base URL configurable via `llm.ollama_base_url`.

## Provider Selection

The `get_provider()` factory function reads `llm.provider` from config:

```python
def get_provider(config: dict) -> LLMProvider:
    providers = {
        "claude_code": ClaudeCodeProvider,
        "anthropic_api": AnthropicAPIProvider,
        "openai_api": OpenAIAPIProvider,
        "local_ollama": OllamaProvider,
    }
    return providers[config["provider"]](config)
```

Config validation should enforce: if `llm.session_mode` is `resumable`, the provider must support `invoke_resumable()`. Currently only `claude_code` does.

## Semaphore Pattern for Concurrency

Within each tick, all agent inference calls are independent and run in parallel. The engine uses an `asyncio.Semaphore` to limit concurrent calls:

```python
class Engine:
    def __init__(self, config, data_dir):
        self.semaphore = asyncio.Semaphore(
            config["llm"].get("max_concurrent_agents", 6)
        )

    async def _dispatch_all(self):
        async def _invoke_one(agent):
            async with self.semaphore:
                prompt = agent.build_prompt(self.world, self.tick)
                return await self.provider.invoke(prompt, self.config["llm"]["model"])

        tasks = [_invoke_one(a) for a in self.alive_agents]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

The `max_concurrent_agents` config value (default 6) controls how many simultaneous `claude -p` processes run. Start at 6 and increase until throughput plateaus or errors appear. Even on Pro Max, sustained high-frequency calls may hit practical limits.

## Cost Estimates

### Claude Code (Pro Max)

$0 marginal cost. The constraint is wall-clock time:

| Configuration | Est. Time |
|--------------|-----------|
| Quick test (100 ticks, 4 agents) | ~5 min |
| Phase 1 validation (500 ticks, 8 agents) | ~30 min |
| Single condition (5000 ticks, 12 agents) | ~5 hours |
| Full factorial, 4 conditions | ~20 hours |
| Full factorial, 5 replications | ~4 days |

Assumes ~2 seconds per inference with 6-way parallelism.

### API Providers (Fallback)

| Configuration | Calls | Haiku Cost | Sonnet Cost |
|--------------|-------|-----------|------------|
| 12 agents x 5K ticks x 1 condition | 60K | ~$8 | ~$80 |
| 12 agents x 5K ticks x 4 conditions | 240K | ~$32 | ~$320 |
| Above x 5 replications | 1.2M | ~$160 | ~$1,600 |

### Local (Ollama)

$0. No rate limits. Slower inference. Useful for development iteration and Phase 5 comparison.

## Adding a New Provider

To add a new LLM backend:

1. Create a class that inherits from `LLMProvider`
2. Implement `invoke()` (required)
3. Optionally implement `invoke_resumable()` if the provider supports persistent sessions
4. Add the class to the `providers` dict in `get_provider()`
5. Add any provider-specific config keys to the `llm` section of `default.yaml`

The rest of the simulation code does not need to change.

See [Architecture](architecture.md) for how the provider fits into the overall data flow, and [Session Modes](concepts/session-modes.md) for the distinction between stateless and resumable inference.
