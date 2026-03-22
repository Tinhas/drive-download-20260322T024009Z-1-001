"""
skills/notebooklm.py
====================
Integração com o Google NotebookLM via API REST.

NOTA: O NotebookLM não possui uma API pública oficial estável (março/2025).
      Esta implementação usa a API interna do NotebookLM, documentada pela
      comunidade. Para uso em produção, prefira a API do Gemini com grounding.

      Alternativa mais estável: use a API do Gemini 2.5 Pro com
      file uploads para simular o comportamento do NotebookLM.

Uso:
    from skills.notebooklm import NotebookLMSkill, GeminiNotebookSkill

    # Via Gemini (recomendado – API oficial)
    skill = GeminiNotebookSkill(api_key="AIza...")
    answer = skill.ask_about_document(doc_text="...", question="Resumo?")

    # Via NotebookLM (experimental)
    skill = NotebookLMSkill(oauth_token="...")
    nb_id = skill.create_notebook("Meu Projeto")
    skill.add_source(nb_id, text="conteúdo do documento...")
    answer = skill.query(nb_id, "Quais são os pontos principais?")
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

log = logging.getLogger("skill.notebooklm")


# ===========================================================================
# Opção A: Gemini como NotebookLM substituto (API oficial, estável)
# ===========================================================================
class GeminiNotebookSkill:
    """
    Usa a API do Gemini com file context para Q&A sobre documentos.
    Equivalente funcional ao NotebookLM para agentes.
    """

    _BASE = "https://generativelanguage.googleapis.com/v1beta"
    _MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self._key or self._key.startswith("PLACEHOLDER"):
            raise ValueError("GEMINI_API_KEY não configurada.")

    def ask_about_document(
        self,
        question: str,
        doc_text: str | None = None,
        doc_url: str | None = None,
        system: str = "",
    ) -> str:
        """
        Faz uma pergunta sobre um documento (texto ou URL).
        """
        parts: list[dict] = []

        if system:
            parts.append({"text": f"Contexto: {system}\n\n"})

        if doc_url:
            # Firecrawl ou fetch básico pode ser usado externamente para obter o texto
            log.info("GeminiNotebook: carregando URL %s", doc_url)
            r = httpx.get(doc_url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            doc_text = r.text[:30000]  # limitar contexto

        if doc_text:
            parts.append({"text": f"Documento:\n{doc_text[:30000]}\n\n"})

        parts.append({"text": f"Pergunta: {question}"})

        r = httpx.post(
            f"{self._BASE}/models/{self._MODEL}:generateContent",
            params={"key": self._key},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {"maxOutputTokens": 2048},
            },
            timeout=120,
        )
        if r.status_code == 429:
            raise RuntimeError("Gemini rate limit atingido.")
        r.raise_for_status()

        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def summarize(self, text: str, language: str = "português") -> str:
        """Gera um resumo estruturado do texto."""
        prompt = (
            f"Crie um resumo estruturado do seguinte conteúdo em {language}. "
            f"Inclua: pontos principais, conclusões e insights acionáveis.\n\n{text[:30000]}"
        )
        return self.ask_about_document(question=prompt)

    def extract_insights(self, text: str) -> list[str]:
        """Extrai insights como lista de strings."""
        prompt = (
            "Extraia os insights mais valiosos do documento abaixo. "
            "Retorne APENAS uma lista JSON de strings, sem markdown:\n\n"
            f"{text[:20000]}"
        )
        response = self.ask_about_document(question=prompt)
        try:
            import json
            # Remove possíveis backticks de markdown
            clean = response.strip().strip("```json").strip("```").strip()
            return json.loads(clean)
        except Exception:
            # Fallback: divide por newline
            return [line.strip("- •*") for line in response.split("\n") if line.strip()]


# ===========================================================================
# Opção B: NotebookLM (API interna não-oficial – experimental)
# ===========================================================================
class NotebookLMSkill:
    """
    EXPERIMENTAL: Interface com a API interna do Google NotebookLM.
    Requer um token OAuth do Google com escopo adequado.
    
    ⚠️  Esta API não é oficial e pode mudar a qualquer momento.
        Use GeminiNotebookSkill para produção.
    """

    _BASE = "https://notebooklm.google.com/_/NotebooklmUi/data"

    def __init__(self, oauth_token: str):
        """
        Args:
            oauth_token: Bearer token obtido via 'opencode auth' ou OAuth2 flow.
        """
        self._token = oauth_token
        self._headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        }
        log.warning(
            "NotebookLMSkill usa API interna não-oficial. "
            "Prefira GeminiNotebookSkill para uso em produção."
        )

    def create_notebook(self, title: str) -> str:
        """Cria um novo notebook e retorna o ID."""
        log.info("NotebookLM: criando notebook '%s'", title)
        r = httpx.post(
            f"{self._BASE}/CreateNotebook",
            headers=self._headers,
            json={"title": title},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        notebook_id = data[0][1][1]  # estrutura interna – frágil
        log.info("Notebook criado: %s", notebook_id)
        return notebook_id

    def add_source(
        self,
        notebook_id: str,
        text: str | None = None,
        url: str | None = None,
        title: str = "Fonte",
    ) -> str:
        """Adiciona uma fonte ao notebook (texto ou URL)."""
        if not text and not url:
            raise ValueError("Forneça text ou url.")

        payload: dict[str, Any] = {
            "notebookId": notebook_id,
            "source": {"title": title},
        }

        if url:
            payload["source"]["url"] = url
        else:
            payload["source"]["textContent"] = text

        log.info("NotebookLM: adicionando fonte ao notebook %s", notebook_id)
        r = httpx.post(
            f"{self._BASE}/AddSource",
            headers=self._headers,
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()[0][1][1]  # source_id

    def query(self, notebook_id: str, question: str) -> str:
        """Faz uma pergunta sobre as fontes do notebook."""
        log.info("NotebookLM: query em notebook %s", notebook_id)
        r = httpx.post(
            f"{self._BASE}/Query",
            headers=self._headers,
            json={"notebookId": notebook_id, "query": question},
            timeout=120,
        )
        r.raise_for_status()
        # A resposta está em posição fixa na estrutura interna
        try:
            return r.json()[0][1][0][1]
        except (IndexError, KeyError, TypeError):
            log.error("Estrutura de resposta inesperada do NotebookLM.")
            return r.text[:2000]
