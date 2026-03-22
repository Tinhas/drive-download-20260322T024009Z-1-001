"""
tools_llm_connectors.py
=======================
Extensões (connectors) MCP nativas para o Antigravity (e Claude Code/OpenCode).
Permite que o agente principal delegue tarefas secundárias (sub-agents) 
usando OpenRouter, Groq, ou Ollama local, sem consumir cotas principais.
"""

import os
import httpx
import json

def ask_openrouter(prompt: str, model: str = "openrouter/auto", max_tokens: int = 1000) -> str:
    """Conector para delegar um prompt para o OpenRouter (balanceamento grátis)."""
    # Se o LiteLLM router estiver online, usamos ele para poupar requests diretas
    litellm_url = "http://litellm:4000/v1/chat/completions"
    try:
        r = httpx.post(
            litellm_url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            },
            timeout=60
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        pass # Fallback direto
    
    # Fallback tráfego direto para OpenRouter se o LiteLLM falhar
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key or key.startswith("PLACEHOLDER"):
        return "Erro: OPENROUTER_API_KEY não configurada no .env ou key-manager."
        
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "http://localhost", "X-Title": "Agentes-24h"},
        json={
            "model": model if model != "openrouter/auto" else "google/gemini-2.8-flash:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        },
        timeout=60
    )
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"]
    return f"Erro OpenRouter: {r.status_code} - {r.text}"


def ask_groq(prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
    """Conector rápido do Groq para inferência Llama 3 ultra rápida."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key or key.startswith("PLACEHOLDER"):
        return "Erro: GROQ_API_KEY não configurada no .env."
        
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30
    )
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"]
    return f"Erro Groq: {r.status_code} - {r.text}"


def ask_ollama_local(prompt: str, model: str = "phi3:mini") -> str:
    """Conector para delegar uma tarefa ao proxy LLM (Ollama) rodando local 24/7."""
    url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
    r = httpx.post(
        f"{url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    if r.status_code == 200:
        return r.json().get("response", "")
    return f"Erro Ollama Local: {r.status_code} - Certifique-se de que o container 'ollama' está rodando (profile llm)."
