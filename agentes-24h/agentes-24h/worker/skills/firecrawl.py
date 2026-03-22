"""
skills/firecrawl.py
===================
Skill de raspagem web usando a API do Firecrawl.
https://docs.firecrawl.dev

Uso:
    from skills.firecrawl import FirecrawlSkill

    skill = FirecrawlSkill(api_key="fc-...")
    result = skill.scrape("https://exemplo.com")
    pages  = skill.crawl("https://exemplo.com", max_pages=10)
    docs   = skill.search("melhores práticas Python 2024")
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

log = logging.getLogger("skill.firecrawl")

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"


class FirecrawlSkill:

    def __init__(self, api_key: str):
        if not api_key or api_key.startswith("PLACEHOLDER"):
            raise ValueError("Firecrawl API key inválida ou não configurada.")
        self._key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    def scrape(
        self,
        url: str,
        formats: list[str] | None = None,
        only_main_content: bool = True,
    ) -> dict:
        """
        Extrai conteúdo de uma única página.

        Returns:
            dict com chaves: markdown, html, metadata, links
        """
        formats = formats or ["markdown"]
        log.info("Firecrawl scrape: %s", url)

        r = httpx.post(
            f"{FIRECRAWL_BASE}/scrape",
            headers=self._headers,
            json={
                "url": url,
                "formats": formats,
                "onlyMainContent": only_main_content,
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            raise RuntimeError(f"Firecrawl scrape falhou: {data.get('error')}")

        return data.get("data", {})

    # ------------------------------------------------------------------
    def crawl(
        self,
        url: str,
        max_pages: int = 10,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> list[dict]:
        """
        Rastreia um site inteiro (async job).

        Returns:
            Lista de documentos com markdown + metadata.
        """
        log.info("Firecrawl crawl: %s (max=%d)", url, max_pages)

        payload: dict = {
            "url": url,
            "limit": max_pages,
            "scrapeOptions": {"formats": ["markdown"]},
        }
        if include_paths:
            payload["includePaths"] = include_paths
        if exclude_paths:
            payload["excludePaths"] = exclude_paths

        # Iniciar job
        r = httpx.post(f"{FIRECRAWL_BASE}/crawl", headers=self._headers, json=payload, timeout=30)
        r.raise_for_status()
        job = r.json()

        if not job.get("success"):
            raise RuntimeError(f"Falha ao iniciar crawl: {job.get('error')}")

        job_id = job["id"]
        log.info("Crawl job iniciado: %s", job_id)

        # Polling
        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_r = httpx.get(
                f"{FIRECRAWL_BASE}/crawl/{job_id}",
                headers=self._headers,
                timeout=30,
            )
            status_r.raise_for_status()
            status = status_r.json()

            log.debug("Crawl status: %s (%d/%d)",
                      status.get("status"), status.get("completed", 0), status.get("total", 0))

            if status.get("status") == "completed":
                return status.get("data", [])

            if status.get("status") in ("failed", "cancelled"):
                raise RuntimeError(f"Crawl falhou: {status}")

        raise TimeoutError(f"Crawl job {job_id} excedeu timeout de {timeout}s.")

    # ------------------------------------------------------------------
    def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        Busca e extrai conteúdo de resultados de pesquisa.

        Returns:
            Lista de resultados com url, markdown, metadata.
        """
        log.info("Firecrawl search: %s", query)

        r = httpx.post(
            f"{FIRECRAWL_BASE}/search",
            headers=self._headers,
            json={"query": query, "limit": limit, "scrapeOptions": {"formats": ["markdown"]}},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            raise RuntimeError(f"Firecrawl search falhou: {data.get('error')}")

        return data.get("data", [])

    # ------------------------------------------------------------------
    def extract_structured(self, url: str, schema: dict, prompt: str = "") -> dict:
        """
        Extrai dados estruturados de uma página usando LLM do Firecrawl.

        Args:
            url: URL a ser processada.
            schema: JSON Schema do objeto esperado.
            prompt: instrução adicional para o LLM.
        """
        log.info("Firecrawl extract: %s", url)

        payload = {
            "url": url,
            "formats": ["extract"],
            "extract": {"schema": schema},
        }
        if prompt:
            payload["extract"]["prompt"] = prompt

        r = httpx.post(
            f"{FIRECRAWL_BASE}/scrape",
            headers=self._headers,
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            raise RuntimeError(f"Firecrawl extract falhou: {data.get('error')}")

        return data.get("data", {}).get("extract", {})
