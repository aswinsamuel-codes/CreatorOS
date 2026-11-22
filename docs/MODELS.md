# Models: cloud and local

CreatorOS uses two model roles:

| Role | Job | Needs |
|---|---|---|
| `writer` | Writes and revises posts | Strong writing; long output |
| `scout` | Picks the day's story from ~100 headlines | Fast and cheap; reliable JSON |

```yaml
models:
  writer: { provider: claude, model: claude-opus-5-5, effort: medium }
  scout:  { provider: claude, model: claude-haiku-5-5, effort: low }
```

`effort` (`low`, `medium`, `high`, `xhigh`, `max`) only applies to Claude. Higher effort
means more careful output and more tokens.

## Switching AI without editing files

Dashboard → **Connections** → click Claude, Gemini or OpenAI → paste the key → **Test** →
pick a model under **Use this AI** → **Use for writing** / **Use for picking stories**.
Each AI tile also shows a monthly token usage meter.

## When a model is busy

Popular new models are sometimes overloaded ("high demand"). CreatorOS retries temporary
errors, then switches to the provider's backup models:

```yaml
providers:
  gemini:
    fallback_models: [gemini-2.5-flash, gemini-flash-lite-latest]
    timeout: 180          # seconds per attempt
```

The log shows "Used backup model …" when that happens.

## Claude (default)

```yaml
providers:
  claude: { type: anthropic, api_key_env: ANTHROPIC_API_KEY }
```

Put your key in `.env` as `ANTHROPIC_API_KEY`. Get one at https://console.anthropic.com.

## Local models: Ollama (e.g. your lab cluster)

1. On the machine with the GPU: install Ollama and pull a model:
   `ollama pull gemma3:27b` (or `llama3.3`, `qwen3`, `mistral-small`...).
2. Let other machines reach it: set `OLLAMA_HOST=0.0.0.0` before `ollama serve`.
3. In CreatorOS (dashboard → Settings → Models, or YAML):

```yaml
providers:
  ollama:
    type: openai_compatible
    base_url: http://192.168.1.50:11434/v1
    api_key_env: ""
models:
  writer: { provider: ollama, model: gemma3:27b }
  scout:  { provider: ollama, model: gemma3:12b }
```

Suggestions: use the biggest model you can run for `writer` (around 27B and up writes
noticeably better), and a small, fast one for `scout`. Mixing works too: Claude writer +
local scout keeps costs low.

## Other providers

Any server with an OpenAI-style `/v1/chat/completions` endpoint works:

| Provider | base_url | Key in .env |
|---|---|---|
| LM Studio | `http://localhost:1234/v1` | none |
| vLLM | `http://<host>:8000/v1` | optional |
| llama.cpp server | `http://<host>:8080/v1` | none |
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` |
| OpenRouter | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |

Add one under `providers:` with `type: openai_compatible`, a `base_url` and the name of the
env variable that holds its key in `api_key_env`.

## Adding a new provider type

Implement a class with `complete(self, system: str, prompt: str, max_tokens: int) -> str`
in `creatoros/llm.py` and register it in `get_llm()`. Raise `LLMError` with a clear message
on failure.
