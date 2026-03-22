# agentes-24h-final — Instruções para Claude Code

## Contexto do Projeto

Sistema de agentes autônomos 24/7 com 50+ ferramentas MCP, múltiplos provedores de IA
com fallback automático (Ollama → Groq → OpenRouter → TogetherAI → FireworksAI → Gemini).

## Regras Inegociáveis

1. **NUNCA apagar código** — apenas criar branches descritivas
2. **NUNCA commitar em `main` ou `master`** — sempre em branches `fix/`, `feat/`, `refactor/`
3. **NUNCA burlar limites de API** — uma conta por provedor, respeitar rate limits
4. **NUNCA derrubar stacks Docker ativas** — verificar antes com `docker compose ps`
5. **Sempre testar antes de commitar** — rodar pytest/npm test se disponível

## Ferramentas MCP Disponíveis (50+)

### Agentes Autônomos
- `run_task` — dispara fix_bugs, add_feature, refactor, pen_test, improve_self
- `list_repos` — lista repos em data/repos/
- `read_pentest_reports` — lê relatórios de segurança
- `provider_status` — status dos 6 providers de IA

### Web Scraping
- `firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`

### Cybersegurança
- `dns_lookup`, `ssl_check`, `http_headers_audit`, `ip_info`
- `cve_search`, `subdomain_enum`, `whois_rdap`, `open_ports_common`
- `tech_stack_detect`, `security_score`

### Conteúdo
- `hackernews_top`, `wikipedia_search`, `rss_fetch`, `reddit_top`
- `seo_analyze`, `trending_github`, `extract_keywords`, `generate_copy`

### Web & Sites
- `screenshot_url`, `html_validate`, `pagespeed_check`
- `generate_landing_page`, `meta_tags_generator`, `generate_sitemap`

### Neuro Design & BigTech
- `design_system_generate`, `bigtech_site_generate`, `neuro_copy_optimize`
- `above_fold_blueprint`, `color_psychology`, `typography_scale`
- `persuasion_framework`, `ux_laws_audit`

### Apresentações
- `presentation_from_doc`, `presentation_from_topic`
- `pitch_deck_generate`, `executive_summary_slide`

### Inteligência de Nicho
- `niche_top_sites`, `site_reverse_engineer`, `niche_copy_patterns`
- `serp_analyze`, `content_gap_finder`, `niche_vocabulary`
- `trust_signals_audit`, `pricing_intelligence`

## Fluxo de Auto-melhoria

### Para repositórios em data/repos/
1. `run_task fix_bugs` — a cada 1h
2. `run_task add_feature` — a cada 2h
3. `run_task refactor` — a cada 4h
4. `run_task pen_test` — 1x/dia às 3h AM

### Para o próprio sistema
1. `run_task improve_self` — 2x/dia (patches salvos em data/logs/ para revisão)
2. `run_task health_check` — a cada 5min

## Budget Free Tier

| Provider | Limite | Uso |
|---|---|---|
| Ollama (local) | ∞ | refactor, tarefas simples |
| Groq | 14.400 req/dia | fix_bugs, features |
| OpenRouter | varia | pen_test, análises |
| Gemini Flash | 1.000 req/dia | notebooks, resumos |

## Comandos Úteis

```bash
# Status dos containers (não derruba nada)
docker compose ps

# Logs em tempo real
docker compose logs -f worker

# Disparar tarefa manualmente
curl -X POST http://localhost:8080/call/run_task \
  -H "Content-Type: application/json" \
  -d '{"task_name": "health_check"}'

# MCP Gateway (desktop)
open http://localhost:8080

# MCP Gateway (mobile/celular antigo)
open http://SEU_IP:8080/mobile

# Flower (monitor Celery)
open http://localhost:5555
```

## Estrutura de Diretórios

```
agentes-24h-final/
├── worker/tasks.py          # 6 tarefas Celery
├── worker/providers.py      # 6 providers de IA com fallback
├── mcp-server/server.py     # 50+ tools MCP via stdio
├── mcp-gateway/gateway.py   # HTTP REST + PWA mobile
├── key-manager/             # gerenciador de secrets
├── scheduler/               # Celery Beat (tarefas recorrentes)
├── data/repos/              # repos BigTech para análise
└── data/logs/               # relatórios e patches
```
