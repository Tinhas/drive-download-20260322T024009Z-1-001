"""
tools_reverse_eng.py
====================
Módulo de engenharia reversa ética (TDD, TRD, DDD).
Usa APIs online (Firecrawl + LLM via Gemini) para analisar repositórios
e sites em alto nível conceitual, sem precisar baixar o código (que consome RAM).
"""

from typing import Any
import server as base_server

def reverse_engineer_architecture(url: str, depth: str = "high_level") -> str:
    """Extrai e infere a arquitetura (Web, Backend, DB, Cloud) de um repo ou produto."""
    prompt = f"Faça uma análise de engenharia reversa estrutural da URL: {url}.\n"
    prompt += "Foque nos componentes arquiteturais macro (Frontend, API, Banco, Message Broker).\n"
    if depth == "detailed":
        prompt += "Tente detalhar padrões de design (ex: CQRS, Event Sourcing) se for possível inferir."
    else:
        prompt += "Dê uma visão geral de alto nível."
        
    return base_server.tool_notebook_ask(prompt, document_url=url)


def reverse_engineer_ddd(url: str) -> str:
    """Extrai o modelo de domínios (DDD) — Bounded Contexts, Aggregates, Entities."""
    prompt = f"Analise a URL {url} sob a ótica do Domain-Driven Design (DDD).\n"
    prompt += "Identifique e liste:\n"
    prompt += "1. Bounded Contexts prováveis\n"
    prompt += "2. Entidades Principais e Agregados\n"
    prompt += "3. Linguagem Ubíqua (Glossário de termos inferido)\n"
    return base_server.tool_notebook_ask(prompt, document_url=url)


def reverse_engineer_tdd(url: str) -> str:
    """Gera suítes de teste conceituais (TDD) baseados no comportamento do produto."""
    prompt = f"Analise o produto ou repo em {url}.\n"
    prompt += "Crie uma especificação de testes (TDD) para seus principais fluxos de valor.\n"
    prompt += "Estruture os casos de teste agrupando no formato Given/When/Then (BDD/TDD).\n"
    return base_server.tool_notebook_ask(prompt, document_url=url)


def reverse_engineer_trd(url: str) -> str:
    """Gera um Technical Requirements Document (TRD) a partir da URL."""
    prompt = f"Crie um Documento de Requisitos Técnicos (TRD) reverso analisando a URL: {url}.\n"
    prompt += "Inclua:\n"
    prompt += "1. Objetivo do Produto\n"
    prompt += "2. Requisitos Não Funcionais (NFRs) Inferidos (Escalabilidade, Segurança)\n"
    prompt += "3. Principais APIs/Integrações presumidas\n"
    prompt += "4. Riscos/Desafios Técnicos prováveis\n"
    return base_server.tool_notebook_ask(prompt, document_url=url)

