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


class AnthropicLLM:
    # Models that support server-side refusal fallbacks ("default" routing).
    _FALLBACK_PREFIXES = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")

    def __init__(self, model: str, api_key: str | None = None, effort: str | None = None):
        import anthropic

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
            raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMError("Could not reach the Claude API (network problem)") from e

        if msg.stop_reason == "refusal":
            raise LLMError("The model declined this request")
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        if msg.stop_reason == "max_tokens":
            log.warning("Response hit max_tokens; output may be cut off")
        return text


class OpenAICompatibleLLM:
    def __init__(self, model: str, base_url: str, api_key: str | None = None, **_):
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
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=900)
        except requests.RequestException as e:
            raise LLMError(f"Could not reach {self.base_url}: {e}") from e
        if r.status_code >= 400:
            raise LLMError(f"{self.base_url} returned {r.status_code}: {r.text[:300]}")
        text = r.json()["choices"][0]["message"]["content"] or ""
        # Reasoning models (Qwen, DeepSeek...) may include their thinking inline.
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def get_llm(cfg: dict, role: str):
    spec = cfg["models"][role]
    provider = cfg["providers"][spec["provider"]]
    api_key = env(provider.get("api_key_env"))
    if provider["type"] == "anthropic":
        return AnthropicLLM(spec["model"], api_key=api_key, effort=spec.get("effort"))
    if provider["type"] == "openai_compatible":
        return OpenAICompatibleLLM(spec["model"], base_url=provider["base_url"], api_key=api_key)
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
