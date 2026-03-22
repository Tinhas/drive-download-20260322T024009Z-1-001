"""
providers.py
============
Camada de abstração para múltiplos provedores de IA.

Ordem de preferência padrão:
  1. Ollama     – local, sem custo, sem rate-limit externo
  2. OpenRouter – modelos gratuitos (GLM-4-Air, DeepSeek-R1, etc.)
  3. Gemini CLI – 1 000 req/dia via subprocess (gemini CLI no host não disponível
                  dentro do container; usa a API REST diretamente com a key)
  4. Claude     – via OpenRouter (claude-3-haiku é gratuito no tier free)

ÉTICA: uma única conta por provedor; sem rotação de contas para burlar limites.
Se o limite de um provedor for atingido, fallback para o próximo.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Optional

import httpx

from key_client import KeyClient

log = logging.getLogger("providers")

# ---------------------------------------------------------------------------
# Modelos OpenRouter gratuitos (atualizar conforme disponibilidade)
# https://openrouter.ai/models?q=free
# ---------------------------------------------------------------------------
OPENROUTER_FREE_MODELS = [
    "thudm/glm-4-5-air:free",
    "deepseek/deepseek-r1:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-4b-it:free",
]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


# ---------------------------------------------------------------------------
# Utilitário de retry simples
# ---------------------------------------------------------------------------
def _retry(fn, retries=3, delay=2.0):
    """Tenta chamar fn até `retries` vezes com backoff linear."""
    last_exc = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            log.warning("Tentativa %d/%d falhou: %s", attempt + 1, retries, exc)
            time.sleep(delay * (attempt + 1))
    raise last_exc


# ===========================================================================
# Provedor base
# ===========================================================================
class BaseProvider:
    name: str = "base"

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


# ===========================================================================
# Ollama (local)
# ===========================================================================
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


# ===========================================================================
# OpenRouter (modelos gratuitos)
# ===========================================================================
class OpenRouterProvider(BaseProvider):
    name = "openrouter"

    def __init__(self, key_client: KeyClient):
        self._key_client = key_client
        self._model_index = 0  # rotação entre modelos gratuitos

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
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            if r.status_code == 429:
                raise RuntimeError("OpenRouter rate limit atingido.")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

        return _retry(_call)


# ===========================================================================
# Gemini (via REST direto com API Key do Gemini Studio)
# ===========================================================================
class GeminiProvider(BaseProvider):
    name = "gemini"
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    _MODEL = "gemini-2.0-flash"  # 1 000 req/dia no tier gratuito

    def __init__(self, api_key: Optional[str] = None):
        # A key pode vir de variável de ambiente ou ser passada diretamente
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
                raise RuntimeError("Gemini rate limit atingido.")
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

        return _retry(_call)


# ===========================================================================
# Orquestrador de provedores (fallback automático)
# ===========================================================================
class ProviderOrchestrator:
    """
    Tenta cada provedor na ordem de preferência.
    Se um falhar (indisponível ou rate-limited), passa para o próximo.
    """

    def __init__(self, key_client: KeyClient):
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self._providers: list[BaseProvider] = [
            OllamaProvider(),
            OpenRouterProvider(key_client),
            GeminiProvider(api_key=gemini_key),
        ]

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        prefer: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Retorna (resposta, nome_do_provedor).

        Args:
            prefer: nome do provedor preferido ("ollama", "openrouter", "gemini").
                    Se não disponível, faz fallback normalmente.
        """
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
