"""Model-agnostic LLM layer.

Two provider types cover almost everything:
  - anthropic          -> Claude via the official Anthropic SDK
  - openai_compatible  -> Ollama, LM Studio, vLLM, OpenAI, Gemini, any /v1/chat/completions server
"""

import json
import re

import requests

from .config import env, log


class LLMError(RuntimeError):
    pass


def record_usage(provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Count tokens for the dashboard's usage meters (never breaks a request)."""
    try:
        from . import db
        db.add_usage(provider, model, input_tokens, output_tokens)
    except Exception as e:
        log.debug("Could not record usage: %s", e)


def friendly_claude_error(status: int, message: str) -> str:
    low = message.lower()
    if "credit balance" in low or "billing" in low:
        return ("Your Claude account has no API credits. Add credits at "
                "https://console.anthropic.com/settings/billing (or switch the writer to a local model in Settings).")
    if status == 429:
        return "Claude rate limit reached - CreatorOS will try again on the next run."
    if status == 529 or status >= 500:
        return "Claude is temporarily overloaded - try again in a few minutes."
    return f"Claude API error {status}: {message}"


class AnthropicLLM:
    # Models that support server-side refusal fallbacks ("default" routing).
    _FALLBACK_PREFIXES = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")

    def __init__(self, model: str, api_key: str | None = None, effort: str | None = None, provider: str = "claude"):
        import anthropic

        self.provider = provider
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def complete(self, system: str, prompt: str, max_tokens: int = 32000, images: list | None = None) -> str:
        """images: list of (media_type, base64_data) tuples, e.g. ("image/png", "iVBOR...")."""
        content = prompt
        if images:
            content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}}
                       for mt, b64 in images] + [{"type": "text", "text": prompt}]
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}

        try:
            if self.model.startswith(self._FALLBACK_PREFIXES):
                stream = self.client.beta.messages.stream(
                    betas=["server-side-fallback-2026-07-01"],
                    extra_body={"fallbacks": "default"},
                    **kwargs,
                )
            else:
                stream = self.client.messages.stream(**kwargs)
            with stream as s:
                msg = s.get_final_message()
        except self._anthropic.AuthenticationError as e:
            raise LLMError("Claude API key is missing or invalid (check ANTHROPIC_API_KEY in .env)") from e
        except self._anthropic.APIStatusError as e:
            raise LLMError(friendly_claude_error(e.status_code, str(e.message))) from e
        except self._anthropic.APIConnectionError as e:
            raise LLMError("Could not reach the Claude API (network problem)") from e

        u = getattr(msg, "usage", None)
        if u is not None:
            inp = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) + \
                  (getattr(u, "cache_read_input_tokens", 0) or 0)
            record_usage(self.provider, self.model, inp, u.output_tokens or 0)
        if msg.stop_reason == "refusal":
            raise LLMError("The model declined this request")
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        if msg.stop_reason == "max_tokens":
            log.warning("Response hit max_tokens; output may be cut off")
        return text


class OpenAICompatibleLLM:
    def __init__(self, model: str, base_url: str, api_key: str | None = None, provider: str = "", **_):
        self.provider = provider or _provider_name(base_url).lower()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def complete(self, system: str, prompt: str, max_tokens: int = 8000, images: list | None = None) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        user_content = prompt
        if images:  # vision models (e.g. gemma3, llava, qwen-vl, gpt-4o)
            user_content = [{"type": "text", "text": prompt}] + [
                {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}} for mt, b64 in images
            ]
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        # OpenAI's newer models only accept max_completion_tokens; other servers expect max_tokens.
        length_key = "max_completion_tokens" if "api.openai.com" in self.base_url else "max_tokens"
        body[length_key] = max_tokens
        r = self._post(body, headers)
        if r.status_code == 400 and "max_tokens" in r.text and length_key == "max_tokens":
            body["max_completion_tokens"] = body.pop("max_tokens")
            r = self._post(body, headers)
        if r.status_code >= 400:
            raise LLMError(friendly_http_error(self.base_url, r.status_code, r.text))
        data = r.json()
        usage = data.get("usage") or {}
        record_usage(self.provider, self.model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        choice = data["choices"][0]
        text = (choice.get("message") or {}).get("content") or ""
        # Reasoning models (Qwen, DeepSeek...) may include their thinking inline.
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    def _post(self, body: dict, headers: dict) -> requests.Response:
        try:
            return requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=900)
        except requests.RequestException as e:
            raise LLMError(f"Could not reach {self.base_url} - is the server running and reachable? ({e})") from e


def _provider_name(base_url: str) -> str:
    if "openai.com" in base_url:
        return "OpenAI"
    if "googleapis.com" in base_url:
        return "Gemini"
    return base_url


def friendly_http_error(base_url: str, status: int, text: str) -> str:
    name, low = _provider_name(base_url), text.lower()
    if status in (401, 403) or "api key not valid" in low or "invalid api key" in low or "incorrect api key" in low:
        return f"{name} rejected the API key - check it was copied completely (Connections tab)."
    if "insufficient_quota" in low or "billing" in low or "credit" in low:
        return f"Your {name} account has no credits or quota left - add billing in your {name} account."
    if status == 429:
        return f"{name} rate limit or free-tier daily limit reached - try again later or upgrade your {name} plan."
    if status == 404 or "model" in low and "not found" in low:
        return f"{name} doesn't recognise that model name - pick another model on the Connections tab."
    if status >= 500:
        return f"{name} is having problems right now - try again in a few minutes."
    return f"{name} returned {status}: {text[:300]}"


CHAT_EXCLUDE = ("embed", "whisper", "tts", "dall-e", "moderation", "image", "audio", "realtime", "transcribe",
                "search", "computer-use", "aqa", "imagen", "veo", "learnlm", "babbage", "davinci", "codex")


def list_models(cfg: dict, provider: str) -> list[str]:
    """Chat models available to this account, newest-looking first."""
    prov = cfg["providers"][provider]
    key = env(prov.get("api_key_env"))
    if prov["type"] == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return [m.id for m in client.models.list()]
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    r = requests.get(prov["base_url"].rstrip("/") + "/models", headers=headers, timeout=30)
    if r.status_code >= 400:
        raise LLMError(friendly_http_error(prov["base_url"], r.status_code, r.text))
    ids = [m["id"].removeprefix("models/") for m in r.json().get("data", [])]
    ids = [i for i in ids if not any(x in i.lower() for x in CHAT_EXCLUDE)]
    return sorted(set(ids), reverse=True)


def cheapest(models: list[str]) -> str | None:
    """Pick a small/cheap model, matching whole name parts ("gemini" must not count as "mini")."""
    for hint in ("flash-lite", "nano", "mini", "flash", "haiku"):
        pattern = re.compile(rf"(^|[-_.:/]){re.escape(hint)}($|[-_.:/])")
        for m in models:
            if pattern.search(m.lower()):
                return m
    return models[0] if models else None


def get_llm(cfg: dict, role: str):
    spec = cfg["models"][role]
    provider = cfg["providers"][spec["provider"]]
    api_key = env(provider.get("api_key_env"))
    if provider["type"] == "anthropic":
        return AnthropicLLM(spec["model"], api_key=api_key, effort=spec.get("effort"), provider=spec["provider"])
    if provider["type"] == "openai_compatible":
        return OpenAICompatibleLLM(spec["model"], base_url=provider["base_url"], api_key=api_key,
                                   provider=spec["provider"])
    raise ValueError(f"Unknown provider type: {provider['type']}")


def parse_json(text: str):
    """Pull the first JSON object/array out of a model reply."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not m:
            raise LLMError(f"Model did not return JSON: {text[:200]}")
        return json.loads(m.group(1))
