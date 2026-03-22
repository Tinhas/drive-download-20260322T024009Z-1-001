"""
key_client.py
=============
Cliente HTTP simples para buscar secrets do Key Manager.
Cacheia valores em memória para evitar chamadas repetidas.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("key-client")

_cache: dict[str, str] = {}


class KeyClient:
    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
    ):
        self._base_url = (base_url or os.environ.get("KM_URL", "http://key-manager:8100")).rstrip("/")
        self._token = auth_token or os.environ.get("KM_AUTH_TOKEN", "")

    def get_secret(self, name: str) -> str:
        """Retorna o valor do secret, com cache em memória."""
        if name in _cache:
            return _cache[name]

        try:
            r = httpx.get(
                f"{self._base_url}/secret/{name}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10,
            )
            r.raise_for_status()
            value = r.json()["value"]
            _cache[name] = value
            log.debug("Secret '%s' obtido do Key Manager.", name)
            return value
        except Exception as exc:
            log.error("Falha ao obter secret '%s': %s", name, exc)
            raise
