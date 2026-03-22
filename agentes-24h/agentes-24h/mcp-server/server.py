"""
mcp-server/server.py
====================
Servidor MCP (Model Context Protocol) que expõe as skills dos agentes
como ferramentas para qualquer cliente compatível (Claude Desktop,
OpenCode, Continue.dev, etc.).

Ferramentas disponíveis:
  - firecrawl_scrape      : extrai conteúdo de uma URL
  - firecrawl_search      : busca na web e retorna markdown
  - firecrawl_crawl       : rastreia site inteiro
  - notebook_ask          : pergunta sobre um documento (via Gemini)
  - notebook_summarize    : resume um texto longo
  - run_task              : dispara qualquer tarefa Celery manualmente
  - list_repos            : lista repositórios disponíveis
  - read_pentest_reports  : lê relatórios de segurança gerados
  - provider_status       : verifica quais provedores de IA estão ativos

Protocolo: JSON-RPC 2.0 sobre stdio (padrão MCP).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Ferramentas extras (content, cybersec, web)
try:
    import tools_content as tc
    import tools_cybersec as ts
    import tools_web as tw
    import tools_neuro_design as tnd
    import tools_presentations as tp
    import tools_niche_intel as tni
    _EXTRA_TOOLS = True
except ImportError:
    _EXTRA_TOOLS = False

# ---------------------------------------------------------------------------
# Logging para stderr (stdout é reservado para o protocolo MCP)
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [mcp-server] %(levelname)s %(message)s",
)
log = logging.getLogger("mcp-server")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
CELERY_BROKER = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
KM_URL        = os.environ.get("KM_URL", "http://key-manager:8100")
KM_TOKEN      = os.environ.get("KM_AUTH_TOKEN", "")
REPOS_DIR     = os.environ.get("GIT_REPO_PATH", "/data/repos")
LOGS_DIR      = "/data/logs"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_secret(name: str) -> str:
    """Busca secret no key-manager."""
    r = httpx.get(
        f"{KM_URL}/secret/{name}",
        headers={"Authorization": f"Bearer {KM_TOKEN}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["value"]


def _firecrawl_headers() -> dict:
    key = _get_secret("firecrawl_key")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _gemini_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "")


# ===========================================================================
# Implementações das ferramentas
# ===========================================================================

def tool_firecrawl_scrape(url: str, only_main_content: bool = True) -> str:
    """Extrai conteúdo em Markdown de uma URL."""
    r = httpx.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers=_firecrawl_headers(),
        json={"url": url, "formats": ["markdown"], "onlyMainContent": only_main_content},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        return f"Erro: {data.get('error')}"
    return data["data"].get("markdown", "(sem conteúdo)")


def tool_firecrawl_search(query: str, limit: int = 5) -> str:
    """Busca na web e retorna resultados em Markdown."""
    r = httpx.post(
        "https://api.firecrawl.dev/v1/search",
        headers=_firecrawl_headers(),
        json={"query": query, "limit": limit, "scrapeOptions": {"formats": ["markdown"]}},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        return f"Erro: {data.get('error')}"
    results = []
    for item in data.get("data", []):
        results.append(f"### {item.get('metadata', {}).get('title', 'Sem título')}\n"
                       f"URL: {item.get('url', '')}\n\n{item.get('markdown', '')[:2000]}")
    return "\n\n---\n\n".join(results) or "Nenhum resultado."


def tool_firecrawl_crawl(url: str, max_pages: int = 5) -> str:
    """Rastreia um site e retorna conteúdo de todas as páginas."""
    # Inicia job
    r = httpx.post(
        "https://api.firecrawl.dev/v1/crawl",
        headers=_firecrawl_headers(),
        json={"url": url, "limit": max_pages, "scrapeOptions": {"formats": ["markdown"]}},
        timeout=30,
    )
    r.raise_for_status()
    job = r.json()
    if not job.get("success"):
        return f"Erro ao iniciar crawl: {job.get('error')}"

    job_id = job["id"]
    import time
    for _ in range(30):
        time.sleep(4)
        status_r = httpx.get(
            f"https://api.firecrawl.dev/v1/crawl/{job_id}",
            headers=_firecrawl_headers(),
            timeout=15,
        )
        status_r.raise_for_status()
        status = status_r.json()
        if status.get("status") == "completed":
            pages = status.get("data", [])
            out = []
            for p in pages:
                out.append(f"## {p.get('metadata', {}).get('title', p.get('url', ''))}\n"
                           f"{p.get('markdown', '')[:3000]}")
            return "\n\n---\n\n".join(out) or "Nenhuma página rastreada."
        if status.get("status") in ("failed", "cancelled"):
            return f"Crawl falhou: {status}"
    return "Timeout aguardando crawl."


def tool_notebook_ask(question: str, document_text: str = "", document_url: str = "") -> str:
    """Faz uma pergunta sobre um documento usando o Gemini como NotebookLM."""
    key = _gemini_key()
    if not key:
        return "GEMINI_API_KEY não configurada."

    parts: list[dict] = []
    if document_url:
        try:
            resp = httpx.get(document_url, timeout=30, follow_redirects=True)
            document_text = resp.text[:25000]
        except Exception as e:
            return f"Erro ao buscar URL: {e}"

    if document_text:
        parts.append({"text": f"Documento:\n{document_text[:25000]}\n\n"})

    parts.append({"text": f"Pergunta: {question}"})

    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": key},
        json={"contents": [{"parts": parts}], "generationConfig": {"maxOutputTokens": 2048}},
        timeout=120,
    )
    if r.status_code == 429:
        return "Limite do Gemini atingido. Tente novamente mais tarde."
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def tool_notebook_summarize(text: str) -> str:
    """Resume um texto longo."""
    return tool_notebook_ask(
        question=(
            "Crie um resumo estruturado em português com: "
            "pontos principais, conclusões e insights acionáveis."
        ),
        document_text=text,
    )


def tool_run_task(task_name: str, kwargs: dict | None = None) -> str:
    """
    Dispara uma tarefa Celery manualmente.
    Tarefas disponíveis: fix_bugs, add_feature, refactor, pen_test,
                         improve_self, health_check
    """
    try:
        from celery import Celery
        app = Celery(broker=CELERY_BROKER)
        result = app.send_task(f"tasks.{task_name}", kwargs=kwargs or {})
        return f"Tarefa '{task_name}' enviada. ID: {result.id}"
    except Exception as e:
        return f"Erro ao disparar tarefa: {e}"


def tool_list_repos() -> str:
    """Lista repositórios Git disponíveis em data/repos/."""
    base = Path(REPOS_DIR)
    if not base.exists():
        return "Diretório data/repos/ não encontrado."
    repos = [p.name for p in base.iterdir() if (p / ".git").exists()]
    if not repos:
        return "Nenhum repositório Git encontrado em data/repos/."
    return "Repositórios disponíveis:\n" + "\n".join(f"  - {r}" for r in sorted(repos))


def tool_read_pentest_reports(limit: int = 5) -> str:
    """Lê os relatórios de segurança mais recentes."""
    logs = Path(LOGS_DIR)
    if not logs.exists():
        return "Diretório de logs não encontrado."
    reports = sorted(logs.glob("pentest_*.json"), reverse=True)[:limit]
    if not reports:
        return "Nenhum relatório de pentest encontrado ainda."
    out = []
    for r in reports:
        out.append(f"### {r.name}\n{r.read_text()[:3000]}")
    return "\n\n---\n\n".join(out)


def tool_provider_status() -> str:
    """Verifica quais provedores de IA estão disponíveis."""
    status = {}

    # Ollama
    try:
        r = httpx.get(
            os.environ.get("OLLAMA_URL", "http://ollama:11434") + "/api/tags",
            timeout=5,
        )
        status["ollama"] = "✅ disponível" if r.status_code == 200 else "❌ erro"
    except Exception:
        status["ollama"] = "❌ inacessível"

    # OpenRouter
    try:
        key = _get_secret("openrouter_key")
        status["openrouter"] = "✅ chave configurada" if key and not key.startswith("PLACEHOLDER") else "⚠️  placeholder"
    except Exception:
        status["openrouter"] = "❌ erro ao buscar chave"

    # Gemini
    key = _gemini_key()
    status["gemini"] = "✅ chave configurada" if key else "⚠️  GEMINI_API_KEY não definida"

    # Firecrawl
    try:
        fc_key = _get_secret("firecrawl_key")
        status["firecrawl"] = "✅ chave configurada" if fc_key and not fc_key.startswith("PLACEHOLDER") else "⚠️  placeholder"
    except Exception:
        status["firecrawl"] = "❌ erro ao buscar chave"

    lines = [f"  {k}: {v}" for k, v in status.items()]
    return "Status dos provedores:\n" + "\n".join(lines)


# ===========================================================================
# Registro de ferramentas (name → função + schema)
# ===========================================================================
TOOLS: dict[str, dict] = {
    "firecrawl_scrape": {
        "fn": tool_firecrawl_scrape,
        "description": "Extrai o conteúdo de uma URL em formato Markdown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL a ser raspada"},
                "only_main_content": {"type": "boolean", "default": True},
            },
            "required": ["url"],
        },
    },
    "firecrawl_search": {
        "fn": tool_firecrawl_search,
        "description": "Busca na web e retorna resultados em Markdown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termos de busca"},
                "limit": {"type": "integer", "default": 5, "description": "Nº de resultados"},
            },
            "required": ["query"],
        },
    },
    "firecrawl_crawl": {
        "fn": tool_firecrawl_crawl,
        "description": "Rastreia um site inteiro e retorna o conteúdo de todas as páginas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL raiz do site"},
                "max_pages": {"type": "integer", "default": 5},
            },
            "required": ["url"],
        },
    },
    "notebook_ask": {
        "fn": tool_notebook_ask,
        "description": "Faz uma pergunta sobre um documento (texto ou URL). Usa Gemini como backend.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Pergunta a fazer"},
                "document_text": {"type": "string", "description": "Texto do documento (opcional)"},
                "document_url": {"type": "string", "description": "URL do documento (opcional)"},
            },
            "required": ["question"],
        },
    },
    "notebook_summarize": {
        "fn": tool_notebook_summarize,
        "description": "Resume um texto longo em pontos principais e insights.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a resumir"},
            },
            "required": ["text"],
        },
    },
    "run_task": {
        "fn": tool_run_task,
        "description": "Dispara uma tarefa dos agentes manualmente (fix_bugs, add_feature, refactor, pen_test, improve_self, health_check).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_name": {
                    "type": "string",
                    "enum": ["fix_bugs", "add_feature", "refactor", "pen_test", "improve_self", "health_check"],
                },
                "kwargs": {"type": "object", "description": "Argumentos opcionais da tarefa"},
            },
            "required": ["task_name"],
        },
    },
    "list_repos": {
        "fn": tool_list_repos,
        "description": "Lista os repositórios Git disponíveis para os agentes processarem.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "read_pentest_reports": {
        "fn": tool_read_pentest_reports,
        "description": "Lê os relatórios de segurança mais recentes gerados pelos agentes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 5, "description": "Nº de relatórios"},
            },
        },
    },
    "provider_status": {
        "fn": tool_provider_status,
        "description": "Verifica quais provedores de IA e skills estão disponíveis.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}

# ---------------------------------------------------------------------------
# Registro dinâmico das ferramentas extras (content, cybersec, web)
# ---------------------------------------------------------------------------
if _EXTRA_TOOLS:
    _EXTRA: dict[str, dict] = {

        # ── CONTENT & COPY ────────────────────────────────────────────────
        "hackernews_top": {
            "fn": tc.hackernews_top,
            "description": "Retorna os top stories do Hacker News agora (tech, startups, IA).",
            "inputSchema": {"type": "object", "properties": {
                "limit":      {"type": "integer", "default": 10},
                "story_type": {"type": "string",  "default": "top",
                               "enum": ["top","new","best","ask","show"]},
            }},
        },
        "wikipedia_search": {
            "fn": tc.wikipedia_search,
            "description": "Busca e retorna resumo de artigo da Wikipedia em qualquer idioma.",
            "inputSchema": {"type": "object", "properties": {
                "query":     {"type": "string"},
                "lang":      {"type": "string", "default": "pt"},
                "sentences": {"type": "integer", "default": 10},
            }, "required": ["query"]},
        },
        "rss_fetch": {
            "fn": tc.rss_fetch,
            "description": "Lê qualquer feed RSS/Atom e retorna os artigos mais recentes.",
            "inputSchema": {"type": "object", "properties": {
                "feed_url": {"type": "string", "description": "URL do feed RSS/Atom"},
                "limit":    {"type": "integer", "default": 10},
            }, "required": ["feed_url"]},
        },
        "seo_analyze": {
            "fn": tc.seo_analyze,
            "description": "Análise local de SEO: legibilidade Flesch, densidade de keyword, sugestões.",
            "inputSchema": {"type": "object", "properties": {
                "text":    {"type": "string"},
                "keyword": {"type": "string", "default": ""},
                "title":   {"type": "string", "default": ""},
            }, "required": ["text"]},
        },
        "trending_github": {
            "fn": tc.trending_github,
            "description": "Repositórios em alta no GitHub (daily/weekly/monthly).",
            "inputSchema": {"type": "object", "properties": {
                "language": {"type": "string", "default": ""},
                "since":    {"type": "string", "default": "daily",
                             "enum": ["daily","weekly","monthly"]},
                "limit":    {"type": "integer", "default": 10},
            }},
        },
        "reddit_top": {
            "fn": tc.reddit_top,
            "description": "Posts em alta de qualquer subreddit via Reddit JSON API (sem chave).",
            "inputSchema": {"type": "object", "properties": {
                "subreddit":   {"type": "string"},
                "limit":       {"type": "integer", "default": 10},
                "time_filter": {"type": "string", "default": "day",
                                "enum": ["hour","day","week","month","year","all"]},
            }, "required": ["subreddit"]},
        },
        "dictionary_lookup": {
            "fn": tc.dictionary_lookup,
            "description": "Definição, exemplos e sinônimos de uma palavra via Free Dictionary API.",
            "inputSchema": {"type": "object", "properties": {
                "word": {"type": "string"},
                "lang": {"type": "string", "default": "en"},
            }, "required": ["word"]},
        },
        "extract_keywords": {
            "fn": tc.extract_keywords,
            "description": "Extrai palavras-chave de um texto usando TF local (sem API).",
            "inputSchema": {"type": "object", "properties": {
                "text":  {"type": "string"},
                "top_n": {"type": "integer", "default": 15},
            }, "required": ["text"]},
        },
        "generate_copy": {
            "fn": tc.generate_copy,
            "description": "Gera copy de marketing (headline, body, CTA, subject, meta_description) via IA local.",
            "inputSchema": {"type": "object", "properties": {
                "product":   {"type": "string"},
                "audience":  {"type": "string"},
                "tone":      {"type": "string", "default": "profissional"},
                "copy_type": {"type": "string", "default": "headline+body+cta"},
            }, "required": ["product","audience"]},
        },
        "lorem_ipsum": {
            "fn": tc.lorem_ipsum,
            "description": "Gera texto placeholder Lorem Ipsum via loripsum.net.",
            "inputSchema": {"type": "object", "properties": {
                "paragraphs": {"type": "integer", "default": 3},
                "lo_type":    {"type": "string",  "default": "medium",
                               "enum": ["short","medium","long","verylong"]},
            }},
        },

        # ── CYBERSEGURANÇA ────────────────────────────────────────────────
        "dns_lookup": {
            "fn": ts.dns_lookup,
            "description": "Consulta registros DNS via Cloudflare DoH (A, AAAA, MX, TXT, NS, CNAME, SOA, CAA).",
            "inputSchema": {"type": "object", "properties": {
                "domain":      {"type": "string"},
                "record_type": {"type": "string", "default": "A",
                                "enum": ["A","AAAA","MX","TXT","NS","CNAME","SOA","CAA"]},
            }, "required": ["domain"]},
        },
        "ssl_check": {
            "fn": ts.ssl_check,
            "description": "Verifica certificado TLS/SSL: emissor, validade, SANs, protocolo e alertas.",
            "inputSchema": {"type": "object", "properties": {
                "domain": {"type": "string"},
                "port":   {"type": "integer", "default": 443},
            }, "required": ["domain"]},
        },
        "http_headers_audit": {
            "fn": ts.http_headers_audit,
            "description": "Auditoria de cabeçalhos de segurança HTTP (HSTS, CSP, X-Frame, etc.) com nota A-F.",
            "inputSchema": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
        "ip_info": {
            "fn": ts.ip_info,
            "description": "Geolocalização, ASN, ISP e detecção de proxy/VPN de um IP ou domínio.",
            "inputSchema": {"type": "object", "properties": {
                "ip_or_domain": {"type": "string"},
            }, "required": ["ip_or_domain"]},
        },
        "wayback_lookup": {
            "fn": ts.wayback_lookup,
            "description": "Verifica snapshots históricos no Wayback Machine (OSINT, auditoria).",
            "inputSchema": {"type": "object", "properties": {
                "url":   {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            }, "required": ["url"]},
        },
        "cve_search": {
            "fn": ts.cve_search,
            "description": "Busca CVEs no banco NVD/NIST por keyword (ex: 'wordpress') ou ID (ex: 'CVE-2024-1234').",
            "inputSchema": {"type": "object", "properties": {
                "keyword": {"type": "string", "default": ""},
                "cve_id":  {"type": "string", "default": ""},
                "limit":   {"type": "integer", "default": 5},
            }},
        },
        "subdomain_enum": {
            "fn": ts.subdomain_enum,
            "description": "Enumeração passiva de subdomínios via Certificate Transparency (crt.sh). Sem tráfego para o alvo.",
            "inputSchema": {"type": "object", "properties": {
                "domain": {"type": "string"},
                "limit":  {"type": "integer", "default": 30},
            }, "required": ["domain"]},
        },
        "whois_rdap": {
            "fn": ts.whois_rdap,
            "description": "WHOIS moderno via RDAP (RFC 7483): datas, registrar, nameservers, expiração.",
            "inputSchema": {"type": "object", "properties": {
                "domain": {"type": "string"},
            }, "required": ["domain"]},
        },
        "open_ports_common": {
            "fn": ts.open_ports_common,
            "description": "Verifica portas comuns abertas em um host. ⚠️ Use apenas em hosts autorizados.",
            "inputSchema": {"type": "object", "properties": {
                "host":    {"type": "string"},
                "timeout": {"type": "number", "default": 1.5},
            }, "required": ["host"]},
        },
        "tech_stack_detect": {
            "fn": ts.tech_stack_detect,
            "description": "Detecta tecnologias de um site: CMS, framework JS, analytics, CDN, backend.",
            "inputSchema": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
        "security_score": {
            "fn": ts.security_score,
            "description": "Score consolidado de segurança de um domínio: SSL + headers + DNS + WHOIS + subdomínios.",
            "inputSchema": {"type": "object", "properties": {
                "domain": {"type": "string"},
            }, "required": ["domain"]},
        },

        # ── WEB & SITES ───────────────────────────────────────────────────
        "screenshot_url": {
            "fn": tw.screenshot_url,
            "description": "Captura screenshot de qualquer URL via Microlink.io (gratuito). Retorna URL da imagem.",
            "inputSchema": {"type": "object", "properties": {
                "url":    {"type": "string"},
                "width":  {"type": "integer", "default": 1280},
                "height": {"type": "integer", "default": 800},
            }, "required": ["url"]},
        },
        "html_validate": {
            "fn": tw.html_validate,
            "description": "Valida HTML via W3C Validator. Aceita URL ou código HTML diretamente.",
            "inputSchema": {"type": "object", "properties": {
                "url_or_html": {"type": "string"},
            }, "required": ["url_or_html"]},
        },
        "pagespeed_check": {
            "fn": tw.pagespeed_check,
            "description": "Auditoria PageSpeed + Core Web Vitals (FCP, LCP, CLS, TBT) via Google.",
            "inputSchema": {"type": "object", "properties": {
                "url":      {"type": "string"},
                "strategy": {"type": "string", "default": "mobile",
                             "enum": ["mobile","desktop"]},
            }, "required": ["url"]},
        },
        "url_shorten": {
            "fn": tw.url_shorten,
            "description": "Encurta URL via is.gd (gratuito, sem chave, slug customizável).",
            "inputSchema": {"type": "object", "properties": {
                "url":         {"type": "string"},
                "custom_slug": {"type": "string", "default": ""},
            }, "required": ["url"]},
        },
        "qr_generate": {
            "fn": tw.qr_generate,
            "description": "Gera QR Code para qualquer texto/URL. Retorna URL da imagem (PNG, SVG, PDF).",
            "inputSchema": {"type": "object", "properties": {
                "content":  {"type": "string"},
                "size":     {"type": "integer", "default": 200},
                "color":    {"type": "string",  "default": "000000"},
                "bg_color": {"type": "string",  "default": "ffffff"},
                "format":   {"type": "string",  "default": "png",
                             "enum": ["png","svg","eps","pdf"]},
            }, "required": ["content"]},
        },
        "deploy_github_pages": {
            "fn": tw.deploy_github_pages,
            "description": "Publica HTML no GitHub Pages via API. Requer GitHub token com escopo repo.",
            "inputSchema": {"type": "object", "properties": {
                "repo":           {"type": "string", "description": "usuario/repositorio"},
                "html_content":   {"type": "string"},
                "github_token":   {"type": "string"},
                "commit_message": {"type": "string", "default": "Deploy automático"},
                "branch":         {"type": "string", "default": "gh-pages"},
            }, "required": ["repo","html_content","github_token"]},
        },
        "generate_landing_page": {
            "fn": tw.generate_landing_page,
            "description": "Gera HTML completo de landing page responsiva via IA local (Tailwind CSS).",
            "inputSchema": {"type": "object", "properties": {
                "product":       {"type": "string"},
                "audience":      {"type": "string"},
                "color_primary": {"type": "string", "default": "#6366f1"},
                "sections":      {"type": "string", "default": "hero,features,testimonials,cta"},
            }, "required": ["product","audience"]},
        },
        "meta_tags_generator": {
            "fn": tw.meta_tags_generator,
            "description": "Gera meta tags completas: SEO, Open Graph (Facebook) e Twitter Card.",
            "inputSchema": {"type": "object", "properties": {
                "title":       {"type": "string"},
                "description": {"type": "string"},
                "url":         {"type": "string"},
                "image_url":   {"type": "string", "default": ""},
                "site_name":   {"type": "string", "default": ""},
                "author":      {"type": "string", "default": ""},
                "keywords":    {"type": "string", "default": ""},
                "locale":      {"type": "string", "default": "pt_BR"},
            }, "required": ["title","description","url"]},
        },
        "generate_robots_txt": {
            "fn": tw.generate_robots_txt,
            "description": "Gera robots.txt otimizado para SEO com bloqueio de bots de AI.",
            "inputSchema": {"type": "object", "properties": {
                "site_url":        {"type": "string"},
                "allow_all":       {"type": "boolean", "default": True},
                "disallow_paths":  {"type": "array", "items": {"type": "string"}, "default": []},
            }, "required": ["site_url"]},
        },
        "generate_sitemap": {
            "fn": tw.generate_sitemap,
            "description": "Gera sitemap.xml a partir de lista de URLs.",
            "inputSchema": {"type": "object", "properties": {
                "urls":        {"type": "array", "items": {"type": "string"}},
                "base_url":    {"type": "string", "default": ""},
                "changefreq":  {"type": "string", "default": "weekly"},
            }, "required": ["urls"]},
        },
        "broken_links_check": {
            "fn": tw.broken_links_check,
            "description": "Verifica links quebrados em uma página (404, timeout, redirects).",
            "inputSchema": {"type": "object", "properties": {
                "url":       {"type": "string"},
                "max_links": {"type": "integer", "default": 30},
            }, "required": ["url"]},
        },
        "favicon_check": {
            "fn": tw.favicon_check,
            "description": "Verifica favicon, apple-touch-icon, manifest.json e ícones PWA de um site.",
            "inputSchema": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    }
    TOOLS.update(_EXTRA)

    # ── NEURO DESIGN & BIGTECH ────────────────────────────────────────
    _NEURO: dict[str, dict] = {
        "design_system_generate": {
            "fn": tnd.design_system_generate,
            "description": "Gera design system completo (CSS variables, escala tipográfica, spacing, sombras) inspirado em Stripe/Linear/Apple/Vercel/Figma.",
            "inputSchema": {"type": "object", "properties": {
                "brand_name":    {"type": "string"},
                "niche":         {"type": "string"},
                "personality":   {"type": "string", "default": "moderno e confiável"},
                "inspired_by":   {"type": "string", "default": "stripe",
                                  "enum": ["stripe","linear","vercel","apple","figma","notion"]},
                "primary_color": {"type": "string", "default": ""},
            }, "required": ["brand_name","niche"]},
        },
        "bigtech_site_generate": {
            "fn": tnd.bigtech_site_generate,
            "description": "Gera site vitrine completo nível Stripe/Linear/Apple via IA — neurociência aplicada, CRO, acessibilidade, SEO.",
            "inputSchema": {"type": "object", "properties": {
                "product":       {"type": "string"},
                "niche":         {"type": "string"},
                "audience":      {"type": "string"},
                "style":         {"type": "string", "default": "stripe",
                                  "enum": ["stripe","linear","vercel","apple","figma","notion"]},
                "unique_value":  {"type": "string", "default": ""},
                "social_proof":  {"type": "string", "default": ""},
            }, "required": ["product","niche","audience"]},
        },
        "neuro_copy_optimize": {
            "fn": tnd.neuro_copy_optimize,
            "description": "Reescreve copy aplicando neurociência: loss aversion, especificidade, F-pattern, cognitive fluency, power words.",
            "inputSchema": {"type": "object", "properties": {
                "original_copy": {"type": "string"},
                "product":       {"type": "string"},
                "audience":      {"type": "string"},
                "goal":          {"type": "string", "default": "conversão"},
                "framework":     {"type": "string", "default": "PAS",
                                  "enum": ["AIDA","PAS","StoryBrand","4Ps"]},
            }, "required": ["original_copy","product","audience"]},
        },
        "above_fold_blueprint": {
            "fn": tnd.above_fold_blueprint,
            "description": "Blueprint científico pixel-a-pixel do hero section com checklist de neurociência, eye-tracking e CRO.",
            "inputSchema": {"type": "object", "properties": {
                "product":  {"type": "string"},
                "niche":    {"type": "string"},
                "audience": {"type": "string"},
                "device":   {"type": "string", "default": "desktop", "enum": ["desktop","mobile"]},
            }, "required": ["product","niche","audience"]},
        },
        "color_psychology": {
            "fn": tnd.color_psychology,
            "description": "Paleta de cores baseada em psicologia, neurociência e diferenciação competitiva por nicho.",
            "inputSchema": {"type": "object", "properties": {
                "niche":               {"type": "string"},
                "desired_emotion":     {"type": "string", "default": "confiança"},
                "audience_age":        {"type": "string", "default": "adulto"},
                "competitors_colors":  {"type": "string", "default": ""},
            }, "required": ["niche"]},
        },
        "typography_scale": {
            "fn": tnd.typography_scale,
            "description": "Sistema tipográfico completo com escala modular, combinações de fontes e uso semântico — padrão BigTech.",
            "inputSchema": {"type": "object", "properties": {
                "brand_personality": {"type": "string", "default": "moderno e direto"},
                "context":           {"type": "string", "default": "web"},
                "base_size":         {"type": "integer", "default": 16},
            }},
        },
        "persuasion_framework": {
            "fn": tnd.persuasion_framework,
            "description": "Aplica framework de persuasão completo (AIDA/PAS/StoryBrand/4Ps) com neurociência e roteiro de copy.",
            "inputSchema": {"type": "object", "properties": {
                "framework":    {"type": "string", "enum": ["AIDA","PAS","StoryBrand","4Ps"]},
                "product":      {"type": "string"},
                "audience":     {"type": "string"},
                "main_pain":    {"type": "string"},
                "main_benefit": {"type": "string"},
            }, "required": ["framework","product","audience","main_pain","main_benefit"]},
        },
        "ux_laws_audit": {
            "fn": tnd.ux_laws_audit,
            "description": "Audita uma URL ou produto contra as 10 leis fundamentais de UX (Fitts, Hick, Miller, Von Restorff...).",
            "inputSchema": {"type": "object", "properties": {
                "url_or_description": {"type": "string"},
            }, "required": ["url_or_description"]},
        },
        "attention_heatmap_predict": {
            "fn": tnd.attention_heatmap_predict,
            "description": "Prediz heatmap de atenção (F/Z-pattern) baseado em pesquisas de eye-tracking do Nielsen Norman Group.",
            "inputSchema": {"type": "object", "properties": {
                "page_type": {"type": "string", "default": "landing",
                              "enum": ["landing","artigo","ecommerce"]},
                "layout":    {"type": "string", "default": "hero-left"},
            }},
        },

        # ── APRESENTAÇÕES ─────────────────────────────────────────────────
        "presentation_from_doc": {
            "fn": tp.presentation_from_doc,
            "description": "Cria apresentação profissional completa a partir de um documento. Replica o NotebookLM com output de slides navegáveis em HTML.",
            "inputSchema": {"type": "object", "properties": {
                "document_text":       {"type": "string"},
                "presentation_goal":   {"type": "string", "default": "informar",
                                        "enum": ["informar","persuadir","vender","treinar","reportar"]},
                "audience":            {"type": "string", "default": "profissional"},
                "slide_count":         {"type": "integer", "default": 12},
                "style":               {"type": "string", "default": "corporativo",
                                        "enum": ["corporativo","startup","dark","minimalista","criativo"]},
            }, "required": ["document_text"]},
        },
        "presentation_from_topic": {
            "fn": tp.presentation_from_topic,
            "description": "Cria apresentação completa sobre qualquer tema do zero. Slides HTML interativos com navegação por teclado, fullscreen e notas do apresentador.",
            "inputSchema": {"type": "object", "properties": {
                "topic":       {"type": "string"},
                "depth":       {"type": "string", "default": "intermediário",
                                "enum": ["básico","intermediário","avançado","executivo"]},
                "audience":    {"type": "string", "default": "profissional"},
                "slide_count": {"type": "integer", "default": 15},
                "style":       {"type": "string", "default": "startup",
                                "enum": ["corporativo","startup","dark","minimalista","criativo"]},
                "include_data":{"type": "boolean", "default": True},
            }, "required": ["topic"]},
        },
        "pitch_deck_generate": {
            "fn": tp.pitch_deck_generate,
            "description": "Gera pitch deck completo para investidores no formato Sequoia Capital (12 slides: Problem→Solution→Market→Traction→Team→Ask).",
            "inputSchema": {"type": "object", "properties": {
                "company_name": {"type": "string"},
                "product":      {"type": "string"},
                "problem":      {"type": "string"},
                "solution":     {"type": "string"},
                "market_size":  {"type": "string"},
                "traction":     {"type": "string", "default": ""},
                "ask":          {"type": "string", "default": ""},
                "style":        {"type": "string", "default": "dark"},
            }, "required": ["company_name","product","problem","solution","market_size"]},
        },
        "executive_summary_slide": {
            "fn": tp.executive_summary_slide,
            "description": "Gera slide único de resumo executivo estilo McKinsey (Pirâmide de Minto: Situation→Complication→Resolution).",
            "inputSchema": {"type": "object", "properties": {
                "topic":          {"type": "string"},
                "context":        {"type": "string"},
                "key_findings":   {"type": "array", "items": {"type": "string"}, "default": []},
                "recommendation": {"type": "string", "default": ""},
            }, "required": ["topic","context"]},
        },
        "slide_outline_generate": {
            "fn": tp.slide_outline_generate,
            "description": "Gera outline da apresentação para aprovação antes de criar os slides completos.",
            "inputSchema": {"type": "object", "properties": {
                "topic":       {"type": "string"},
                "slide_count": {"type": "integer", "default": 10},
                "goal":        {"type": "string", "default": "informar"},
            }, "required": ["topic"]},
        },

        # ── INTELIGÊNCIA DE NICHO ─────────────────────────────────────────
        "niche_top_sites": {
            "fn": tni.niche_top_sites,
            "description": "Encontra os sites/produtos líderes de qualquer nicho com análise de por que são líderes e o que aprender com eles.",
            "inputSchema": {"type": "object", "properties": {
                "niche":   {"type": "string"},
                "country": {"type": "string", "default": "BR"},
                "limit":   {"type": "integer", "default": 10},
            }, "required": ["niche"]},
        },
        "site_reverse_engineer": {
            "fn": tni.site_reverse_engineer,
            "description": "Engenharia reversa completa de um site concorrente: copy, design, funil, SEO, trust signals, pricing.",
            "inputSchema": {"type": "object", "properties": {
                "url":   {"type": "string"},
                "focus": {"type": "string", "default": "tudo",
                          "enum": ["tudo","copy","design","funil","seo","pricing","trust"]},
            }, "required": ["url"]},
        },
        "niche_copy_patterns": {
            "fn": tni.niche_copy_patterns,
            "description": "Extrai padrões de copy dos líderes do nicho (headlines, CTAs, taglines, value props, email subjects).",
            "inputSchema": {"type": "object", "properties": {
                "niche":        {"type": "string"},
                "copy_element": {"type": "string", "default": "headlines",
                                 "enum": ["headlines","ctas","taglines","value_props","email_subjects"]},
            }, "required": ["niche"]},
        },
        "serp_analyze": {
            "fn": tni.serp_analyze,
            "description": "Analisa intenção de busca, estratégia de conteúdo e oportunidades SEO para uma keyword.",
            "inputSchema": {"type": "object", "properties": {
                "keyword": {"type": "string"},
                "intent":  {"type": "string", "default": "auto"},
            }, "required": ["keyword"]},
        },
        "content_gap_finder": {
            "fn": tni.content_gap_finder,
            "description": "Encontra lacunas de conteúdo inexploradas no nicho — oportunidades de SEO e autoridade que os líderes ignoram.",
            "inputSchema": {"type": "object", "properties": {
                "niche":       {"type": "string"},
                "your_topics": {"type": "array", "items": {"type": "string"}, "default": []},
            }, "required": ["niche"]},
        },
        "niche_vocabulary": {
            "fn": tni.niche_vocabulary,
            "description": "Extrai vocabulário, jargões, metáforas e frases-chave do nicho para copy que soa como insider.",
            "inputSchema": {"type": "object", "properties": {
                "niche":         {"type": "string"},
                "output_format": {"type": "string", "default": "completo",
                                  "enum": ["completo","csv","glossario"]},
            }, "required": ["niche"]},
        },
        "trust_signals_audit": {
            "fn": tni.trust_signals_audit,
            "description": "Mapeia todos os sinais de confiança usados pelos líderes do nicho com score de impacto na conversão.",
            "inputSchema": {"type": "object", "properties": {
                "url":   {"type": "string", "default": ""},
                "niche": {"type": "string", "default": ""},
            }},
        },
        "pricing_intelligence": {
            "fn": tni.pricing_intelligence,
            "description": "Mapeia modelos, faixas, psicologia de preço e estratégias de conversão do nicho.",
            "inputSchema": {"type": "object", "properties": {
                "niche":        {"type": "string"},
                "product_type": {"type": "string", "default": "saas",
                                 "enum": ["saas","ecommerce","servicos","infoproduto","consultoria"]},
            }, "required": ["niche"]},
        },
        "winning_headline_patterns": {
            "fn": tni.winning_headline_patterns,
            "description": "Lista os 20 templates de headline com maior taxa de conversão histórica para o nicho.",
            "inputSchema": {"type": "object", "properties": {
                "niche": {"type": "string"},
                "goal":  {"type": "string", "default": "conversão"},
            }, "required": ["niche"]},
        },
    }
    TOOLS.update(_NEURO)


# ===========================================================================
# Loop principal MCP (JSON-RPC 2.0 sobre stdio)
# ===========================================================================

def _respond(msg: dict):
    """Escreve uma resposta JSON-RPC para stdout."""
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _error_response(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_request(req: dict) -> dict | None:
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    # ----- initialize -----
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentes-24h-mcp", "version": "1.0.0"},
            },
        }

    # ----- tools/list -----
    if method == "tools/list":
        tools_list = []
        for name, meta in TOOLS.items():
            tools_list.append({
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["inputSchema"],
            })
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    # ----- tools/call -----
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments  = params.get("arguments", {})

        if tool_name not in TOOLS:
            return _error_response(req_id, -32601, f"Ferramenta '{tool_name}' não encontrada.")

        try:
            log.info("Chamando ferramenta: %s %s", tool_name, list(arguments.keys()))
            result_text = TOOLS[tool_name]["fn"](**arguments)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(result_text)}],
                    "isError": False,
                },
            }
        except Exception as exc:
            log.error("Erro em '%s': %s", tool_name, exc, exc_info=True)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Erro: {exc}"}],
                    "isError": True,
                },
            }

    # ----- notifications (sem resposta) -----
    if method.startswith("notifications/"):
        return None

    return _error_response(req_id, -32601, f"Método '{method}' não suportado.")


def main():
    log.info("MCP Server iniciado. Aguardando requisições via stdin...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _respond({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        response = handle_request(req)
        if response is not None:
            _respond(response)


if __name__ == "__main__":
    main()
