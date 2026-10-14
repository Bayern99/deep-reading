#!/usr/bin/env python3
"""WSJ 深读 · Model-Agnostic Generation Provider Interface (`model_provider.py`).

Decouples Editorial Planning & Generative Composition from any specific LLM vendor.
Core modules (`canonical_builder`, `editorial_compiler`, `artifact_store`, `editorial_studio`)
never hardcode model names; they interact strictly through `ModelProvider`, `GenerationConfig`,
and `GenerationResult`.

Supported adapters & features:
- Automatic discovery of configured models from `~/.pi/agent/models.json` (Magpie gateway, oMLX, etc.)
  and environment variables (`WSJ_LLM_*`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
- `OpenAICompatibleProvider`: works with Magpie (`http://127.0.0.1:3425/v1/chat/completions`),
  Gemini OpenAI-compatible endpoints, OpenAI, oMLX, OpenRouter, or vLLM.
- `AnthropicProvider`: works with Claude Messages API (`https://api.anthropic.com/v1/messages`).
- `CallableModelProvider`: wraps an injected callable (e.g., deterministic test mock or host bridge).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


DEFAULT_EDITORIAL_MODEL_ID = "google-vertex/gemini-4-argon"


@dataclass
class GenerationConfig:
    provider: str = "magpie"
    model_id: str = DEFAULT_EDITORIAL_MODEL_ID
    endpoint: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = 32000
    context_limit: int = 200000
    timeout_seconds: int = 300
    system_prompt: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass
class UsageMetadata:
    prompt_chars: int = 0
    completion_chars: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    content: str
    config: GenerationConfig
    usage: UsageMetadata
    raw_response: dict[str, Any] | None = None


class ModelProviderError(RuntimeError):
    pass


class ModelProvider:
    """Abstract base interface for all Editorial Generation model providers."""

    def generate(self, prompt: str, config: GenerationConfig | None = None) -> GenerationResult:
        raise NotImplementedError


def load_local_provider_registry() -> dict[str, Any]:
    """Load configured providers and models from ~/.pi/agent/models.json if available."""
    for p in (
        os.path.expanduser("~/.pi/agent/models.json"),
        os.path.expanduser("~/.omp/agent/models.json"),
    ):
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f).get("providers") or {}
            except Exception:
                pass
    return {}


def list_configured_models() -> list[dict[str, Any]]:
    """Return curated list of configured models available for Editorial Generation in the UI."""
    providers = load_local_provider_registry()
    curated_models: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Priority order for editorial layout generation
    preferred_ids = [
        "google-vertex/gemini-4-argon",
        "google-vertex/gemini-3.8-flash",
        "kimi-code-cn/k3",
        "kimi-code-cn/kimi-for-coding-highspeed",
        "cursor/claude-sonnet-5-thinking",
        "cursor/grok-4.7",
        "codex/gpt-6.1-sol",
        "omlx/Qwen3.8-27B-oQ4e-mtp",
    ]

    magpie = providers.get("magpie") or {}
    magpie_models = {
        (m["id"] if isinstance(m, dict) else str(m)): m
        for m in (magpie.get("models") or [])
    }

    for mid in preferred_ids:
        if mid in magpie_models:
            m_info = magpie_models[mid]
            curated_models.append({
                "provider": "magpie",
                "model_id": mid,
                "label": f"{mid} ({m_info.get('name', mid) if isinstance(m_info, dict) else mid})",
                "context_window": m_info.get("contextWindow", 200000) if isinstance(m_info, dict) else 200000,
                "max_tokens": m_info.get("maxTokens", 32000) if isinstance(m_info, dict) else 32000,
                "recommended": mid == DEFAULT_EDITORIAL_MODEL_ID,
            })
            seen.add(f"magpie:{mid}")

    # Append remaining configured models from local providers
    for prov_name, prov_data in providers.items():
        for m in prov_data.get("models") or []:
            mid = m["id"] if isinstance(m, dict) else str(m)
            key = f"{prov_name}:{mid}"
            if key in seen:
                continue
            curated_models.append({
                "provider": prov_name,
                "model_id": mid,
                "label": f"{prov_name}/{mid}",
                "context_window": m.get("contextWindow", 128000) if isinstance(m, dict) else 128000,
                "max_tokens": m.get("maxTokens", 16384) if isinstance(m, dict) else 16384,
                "recommended": False,
            })
            seen.add(key)

    if not curated_models:
        curated_models.append({
            "provider": os.environ.get("WSJ_PROVIDER", "openai-compatible"),
            "model_id": os.environ.get("WSJ_LLM_MODEL", DEFAULT_EDITORIAL_MODEL_ID),
            "label": f"{os.environ.get('WSJ_LLM_MODEL', DEFAULT_EDITORIAL_MODEL_ID)} (Default)",
            "context_window": 200000,
            "max_tokens": 32000,
            "recommended": True,
        })

    return curated_models


class CallableModelProvider(ModelProvider):
    """Provider backed by a host callable (e.g. deterministic test stub or custom bridge)."""

    def __init__(self, fn: Callable[[str, GenerationConfig], str], default_config: GenerationConfig | None = None):
        self._fn = fn
        self.default_config = default_config or GenerationConfig(
            provider="host-bridge", model_id=DEFAULT_EDITORIAL_MODEL_ID
        )

    def generate(self, prompt: str, config: GenerationConfig | None = None) -> GenerationResult:
        cfg = config or self.default_config
        t0 = time.time()
        try:
            text = self._fn(prompt, cfg)
        except Exception as e:
            raise ModelProviderError(f"Provider '{cfg.provider}/{cfg.model_id}' failed: {e}") from e
        elapsed = round(time.time() - t0, 3)
        usage = UsageMetadata(
            prompt_chars=len(prompt),
            completion_chars=len(text or ""),
            input_tokens=len(prompt) // 4,
            output_tokens=len(text or "") // 4,
            total_tokens=(len(prompt) + len(text or "")) // 4,
            latency_seconds=elapsed,
        )
        return GenerationResult(content=text, config=cfg, usage=usage)


class OpenAICompatibleProvider(ModelProvider):
    """Adapter for OpenAI-compatible `/v1/chat/completions` endpoints (Magpie gateway, Gemini, OpenAI, oMLX)."""

    def __init__(self, default_config: GenerationConfig | None = None):
        providers = load_local_provider_registry()
        default_prov = "magpie" if "magpie" in providers else "openai-compatible"
        base_url = providers.get(default_prov, {}).get("baseUrl")
        default_endpoint = os.environ.get("WSJ_LLM_ENDPOINT") or (
            f"{base_url.rstrip('/')}/chat/completions"
            if base_url
            else "http://127.0.0.1:3425/v1/chat/completions"
        )
        self.default_config = default_config or GenerationConfig(
            provider=default_prov,
            model_id=os.environ.get("WSJ_LLM_MODEL", DEFAULT_EDITORIAL_MODEL_ID),
            endpoint=default_endpoint,
            api_key_env="WSJ_LLM_API_KEY",
        )

    def _resolve_endpoint_and_key(self, cfg: GenerationConfig) -> tuple[str, str]:
        providers = load_local_provider_registry()
        prov_entry = providers.get(cfg.provider) or providers.get("magpie") or {}

        endpoint = cfg.endpoint or os.environ.get("WSJ_LLM_ENDPOINT")
        if not endpoint:
            base_url = prov_entry.get("baseUrl")
            if base_url:
                endpoint = f"{base_url.rstrip('/')}/chat/completions"
            else:
                endpoint = self.default_config.endpoint or "http://127.0.0.1:3425/v1/chat/completions"

        api_key = ""
        if cfg.api_key_env and os.environ.get(cfg.api_key_env):
            api_key = os.environ[cfg.api_key_env]
        elif os.environ.get("WSJ_LLM_API_KEY"):
            api_key = os.environ["WSJ_LLM_API_KEY"]
        elif prov_entry.get("apiKey"):
            api_key = prov_entry["apiKey"]
        else:
            for env_name in ("WSJ_LLM_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
                if os.environ.get(env_name):
                    api_key = os.environ[env_name]
                    break

        return endpoint, api_key

    def generate(self, prompt: str, config: GenerationConfig | None = None) -> GenerationResult:
        cfg = config or self.default_config
        endpoint, api_key = self._resolve_endpoint_and_key(cfg)
        if not endpoint:
            raise ModelProviderError("OpenAICompatibleProvider requires an endpoint URL")

        messages = []
        if cfg.system_prompt:
            messages.append({"role": "system", "content": cfg.system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": cfg.model_id,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_output_tokens,
            **cfg.extra_params,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            err_body = ""
            try:
                err_body = he.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            raise ModelProviderError(
                f"HTTP {he.code} from {endpoint} ({cfg.model_id}): {err_body or he.reason}"
            ) from he
        except Exception as e:
            raise ModelProviderError(f"Request to {endpoint} ({cfg.model_id}) failed: {e}") from e

        elapsed = round(time.time() - t0, 3)
        choices = resp_data.get("choices") or []
        if not choices or not choices[0].get("message"):
            raise ModelProviderError(f"Malformed response from {cfg.model_id}: {str(resp_data)[:300]}")
        content = choices[0]["message"].get("content") or ""
        if not content.strip():
            raise ModelProviderError(f"Empty generation content returned by {cfg.model_id}")

        u = resp_data.get("usage") or {}
        usage = UsageMetadata(
            prompt_chars=len(prompt),
            completion_chars=len(content),
            input_tokens=u.get("prompt_tokens"),
            output_tokens=u.get("completion_tokens"),
            total_tokens=u.get("total_tokens"),
            latency_seconds=elapsed,
        )
        return GenerationResult(content=content, config=cfg, usage=usage, raw_response=resp_data)


class AnthropicProvider(ModelProvider):
    """Adapter for Anthropic Messages API (`/v1/messages`)."""

    def __init__(self, default_config: GenerationConfig | None = None):
        self.default_config = default_config or GenerationConfig(
            provider="anthropic",
            model_id=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            endpoint="https://api.anthropic.com/v1/messages",
            api_key_env="ANTHROPIC_API_KEY",
        )

    def generate(self, prompt: str, config: GenerationConfig | None = None) -> GenerationResult:
        cfg = config or self.default_config
        api_key = os.environ.get(cfg.api_key_env or "ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ModelProviderError("AnthropicProvider requires ANTHROPIC_API_KEY")

        payload: dict[str, Any] = {
            "model": cfg.model_id,
            "max_tokens": cfg.max_output_tokens,
            "temperature": cfg.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if cfg.system_prompt:
            payload["system"] = cfg.system_prompt

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            cfg.endpoint or "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ModelProviderError(f"Anthropic request ({cfg.model_id}) failed: {e}") from e

        elapsed = round(time.time() - t0, 3)
        blocks = resp_data.get("content") or []
        content = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        u = resp_data.get("usage") or {}
        in_tok = u.get("input_tokens")
        out_tok = u.get("output_tokens")
        usage = UsageMetadata(
            prompt_chars=len(prompt),
            completion_chars=len(content),
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=(in_tok or 0) + (out_tok or 0) if (in_tok is not None or out_tok is not None) else None,
            latency_seconds=elapsed,
        )
        return GenerationResult(content=content, config=cfg, usage=usage, raw_response=resp_data)


def create_provider_for_model(
    provider_name: str = "magpie",
    model_id: str = DEFAULT_EDITORIAL_MODEL_ID,
    temperature: float = 0.2,
    max_output_tokens: int = 32000,
) -> tuple[ModelProvider, GenerationConfig]:
    """Create a (ModelProvider, GenerationConfig) pair for the selected model."""
    cfg = GenerationConfig(
        provider=provider_name,
        model_id=model_id,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    if provider_name == "anthropic":
        return AnthropicProvider(cfg), cfg
    return OpenAICompatibleProvider(cfg), cfg


def create_provider_from_env() -> ModelProvider:
    provider_name = os.environ.get("WSJ_PROVIDER", "magpie").lower()
    if provider_name == "anthropic":
        return AnthropicProvider()
    return OpenAICompatibleProvider()
