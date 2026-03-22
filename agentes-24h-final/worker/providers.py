"""
providers.py
===========
Camada de abstração para múltiplos provedores de IA.

Ordem de preferência padrão:
  1. Ollama      – local, sem custo, sem rate-limit externo
  2. Groq        – free tier com Llama/Gemma (alta velocidade)
  3. OpenRouter  – modelos gratuitos (GLM-4-Air, DeepSeek-R1, etc.)
  4. TogetherAI  – modelos gratuitos (Qwen, Mistral)
  5. FireworksAI – modelos gratuitos (Mixtral)
  6. Gemini      – 1.000 req/dia via API REST

ÉTICA: uma única conta por provedor; sem rotação de contas para burlar limites.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

from key_client import KeyClient

log = logging.getLogger("providers")

GROQ_FREE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

OPENROUTER_FREE_MODELS = [
    "thudm/glm-4-5-air:free",
    "deepseek/deepseek-r1:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-4b-it:free",
]

TOGETHERAI_FREE_MODELS = [
    "meta-llama/Llama-3-8B-Instruct-Turbo",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "Qwen/Qwen2.5-14B-Instruct-Turbo",
]

FIREWORKSAI_FREE_MODELS = [
    "accounts/fireworks/models/mixtral-8x7b-instruct",
    "accounts/fireworks/models/llama-v3p1-8b-instruct",
]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
TOGETHERAI_BASE_URL = "https://api.together.ai/v1"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/v1"


def _retry(fn, retries=3, delay=2.0):
    last_exc = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            log.warning("Tentativa %d/%d falhou: %s", attempt + 1, retries, exc)
            time.sleep(delay * (2 ** attempt))
    raise last_exc


class BaseProvider:
    name: str = "base"

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
        self.model = os.environ.get("OLLAMA_DEFAULT_MODEL", "phi3:mini")

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        def _call():
            r = httpx.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

        return _retry(_call)


class GroqProvider(BaseProvider):
    name = "groq"

    def __init__(self, key_client: KeyClient):
        self._key_client = key_client
        self._model_index = 0

    def _get_key(self) -> str:
        return self._key_client.get_secret("groq_key")

    def _next_model(self) -> str:
        model = GROQ_FREE_MODELS[self._model_index % len(GROQ_FREE_MODELS)]
        self._model_index += 1
        return model

    def is_available(self) -> bool:
        try:
            key = self._get_key()
            return bool(key) and not key.startswith("PLACEHOLDER")
        except Exception:
            return False

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        key = self._get_key()
        model = self._next_model()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log.info("Groq: usando modelo %s", model)

        def _call():
            r = httpx.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=60,
            )
            if r.status_code == 429:
                raise RuntimeError("Groq rate limit.")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].lstrip("\ufeff")

        return _retry(_call)


class OpenRouterProvider(BaseProvider):
    name = "openrouter"

    def __init__(self, key_client: KeyClient):
        self._key_client = key_client
        self._model_index = 0

    def _get_key(self) -> str:
        return self._key_client.get_secret("openrouter_key")

    def _next_model(self) -> str:
        model = OPENROUTER_FREE_MODELS[self._model_index % len(OPENROUTER_FREE_MODELS)]
        self._model_index += 1
        return model

    def is_available(self) -> bool:
        try:
            key = self._get_key()
            return bool(key) and not key.startswith("PLACEHOLDER")
        except Exception:
            return False

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        key = self._get_key()
        model = self._next_model()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log.info("OpenRouter: usando modelo %s", model)

        def _call():
            r = httpx.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "https://github.com/agentes-24h",
                    "X-Title": "agentes-24h",
                },
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=120,
            )
            if r.status_code == 429:
                raise RuntimeError("OpenRouter rate limit.")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].lstrip("\ufeff")

        return _retry(_call)


class TogetherAIProvider(BaseProvider):
    name = "togetherai"

    def __init__(self, key_client: KeyClient):
        self._key_client = key_client
        self._model_index = 0

    def _get_key(self) -> str:
        return self._key_client.get_secret("togetherai_key")

    def _next_model(self) -> str:
        model = TOGETHERAI_FREE_MODELS[self._model_index % len(TOGETHERAI_FREE_MODELS)]
        self._model_index += 1
        return model

    def is_available(self) -> bool:
        try:
            key = self._get_key()
            return bool(key) and not key.startswith("PLACEHOLDER")
        except Exception:
            return False

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        key = self._get_key()
        model = self._next_model()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log.info("TogetherAI: usando modelo %s", model)

        def _call():
            r = httpx.post(
                f"{TOGETHERAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=120,
            )
            if r.status_code == 429:
                raise RuntimeError("TogetherAI rate limit.")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].lstrip("\ufeff")

        return _retry(_call)


class FireworksAIProvider(BaseProvider):
    name = "fireworksai"

    def __init__(self, key_client: KeyClient):
        self._key_client = key_client
        self._model_index = 0

    def _get_key(self) -> str:
        return self._key_client.get_secret("fireworksai_key")

    def _next_model(self) -> str:
        model = FIREWORKSAI_FREE_MODELS[self._model_index % len(FIREWORKSAI_FREE_MODELS)]
        self._model_index += 1
        return model

    def is_available(self) -> bool:
        try:
            key = self._get_key()
            return bool(key) and not key.startswith("PLACEHOLDER")
        except Exception:
            return False

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        key = self._get_key()
        model = self._next_model()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log.info("FireworksAI: usando modelo %s", model)

        def _call():
            r = httpx.post(
                f"{FIREWORKS_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=120,
            )
            if r.status_code == 429:
                raise RuntimeError("FireworksAI rate limit.")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].lstrip("\ufeff")

        return _retry(_call)


class GeminiProvider(BaseProvider):
    name = "gemini"
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    _MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self._api_key) and not self._api_key.startswith("PLACEHOLDER")

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        def _call():
            r = httpx.post(
                f"{self._BASE}/{self._MODEL}:generateContent",
                params={"key": self._api_key},
                json={
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens},
                },
                timeout=120,
            )
            if r.status_code == 429:
                raise RuntimeError("Gemini rate limit.")
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].lstrip("\ufeff")

        return _retry(_call)


class ProviderOrchestrator:
    def __init__(self, key_client: KeyClient):
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self._providers: list[BaseProvider] = [
            OllamaProvider(),
            GroqProvider(key_client),
            OpenRouterProvider(key_client),
            TogetherAIProvider(key_client),
            FireworksAIProvider(key_client),
            GeminiProvider(api_key=gemini_key),
        ]

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        prefer: Optional[str] = None,
    ) -> tuple[str, str]:
        ordered = self._providers.copy()
        if prefer:
            preferred = [p for p in ordered if p.name == prefer]
            rest = [p for p in ordered if p.name != prefer]
            ordered = preferred + rest

        for provider in ordered:
            if not provider.is_available():
                log.info("Provedor '%s' indisponível, pulando.", provider.name)
                continue
            try:
                log.info("Usando provedor: %s", provider.name)
                result = provider.complete(prompt, system=system, max_tokens=max_tokens)
                return result, provider.name
            except Exception as exc:
                log.warning("Provedor '%s' falhou: %s. Tentando próximo.", provider.name, exc)

        raise RuntimeError("Todos os provedores de IA falharam.")
