# agentes-24h-unified 🤖

Sistema de agentes autônomos que rodam 24/7, orquestrados com Docker Compose.
Os agentes analisam repositórios Git, corrigem bugs, adicionam features, fazem refatoração e pentests — tudo de forma automática, ética e dentro dos ToS dos provedores.

**Versão unificada com múltiplos provedores de IA: Ollama, Groq, OpenRouter, TogetherAI, FireworksAI, Gemini.**

---

## ⚡ Instalação com um clique

**Windows:**
```bat
install.bat
```

**Linux / macOS:**
```bash
chmod +x install.sh && ./install.sh
```

O instalador verifica dependências, pede suas chaves interativamente, gera o `.env` e sobe todos os containers.

---

## 🏗️ Arquitetura

```
┌────────────────────────────────────────────────────────────────┐
│                     Docker Compose                              │
│                                                                │
│  ┌──────────┐   ┌─────────────┐   ┌─────────────────────┐     │
│  │ scheduler│──▶│   redis     │◀──│      workers        │     │
│  │  (Beat)   │   │  (broker)   │   │  (x2) + MCP Server │     │
│  └──────────┘   └─────────────┘   └──────────┬──────────┘     │
│                                               │                 │
│  ┌─────────────┐   ┌─────────────────────────▼──────────────┐  │
│  │ key-manager │◀──│     ProviderOrchestrator (fallback)   │  │
│  │  (secrets) │   │  Ollama → Groq → OpenRouter →        │  │
│  └─────────────┘   │  TogetherAI → FireworksAI → Gemini   │  │
│                    └───────────────────────────────────────┘  │
│  ┌──────────┐   ┌──────────┐   ┌─────────────┐              │
│  │  ollama  │   │  flower  │   │ mcp-server  │ :5555        │
│  │  (local) │   │(monitor) │   │  (stdio)    │              │
│  └──────────┘   └──────────┘   └─────────────┘              │
└────────────────────────────────────────────────────────────────┘
```

### Provedores de IA (fallback automático)

| Provedor | Custo | Limite | Modelos |
|---|---|---|---|
| **Ollama** (local) | Grátis | CPU/RAM | phi3:mini, tinyllama, mistral |
| **Groq** | Grátis | 30 req/min | Llama-3.3-70B, Mixtral-8x7B, Gemma2-9B |
| **OpenRouter** | Grátis | Por modelo | GLM-4-Air, DeepSeek-R1, Mistral-7B, Gemma-3-4B |
| **TogetherAI** | Grátis | Variável | Llama-3-8B, Mistral-7B, Qwen-2.5-14B |
| **FireworksAI** | Grátis | Variável | Mixtral-8x7B, Llama-3.1-8B |
| **Gemini** | Grátis | 1.000 req/dia | gemini-2.0-flash |

> **Ética:** uma única conta por provedor. Sem rotação de contas para burlar limites.

---

## 📁 Estrutura de diretórios

```
agentes-24h-unified/
├── docker-compose.yml        # Orquestração principal
├── .env.example              # Template de variáveis
├── install.bat / install.sh  # Instaladores
├── README.md                 # Este arquivo
├── key-manager/              # Gerenciador de secrets
├── mcp-server/               # Servidor MCP (Model Context Protocol)
│   ├── server.py             # Core do servidor MCP
│   └── tools_*.py            # Ferramentas especializadas
├── scheduler/                # Celery Beat (tarefas recorrentes)
├── worker/                   # Workers Celery + providers
│   ├── tasks.py              # Tarefas: fix_bugs, add_feature, etc.
│   ├── providers.py          # Orquestrador de IA (6 provedores)
│   └── skills/               # Skills extras
│       ├── firecrawl.py      # Raspagem web avançada
│       └── notebooklm.py     # Integração Gemini
├── secrets/                  # Chaves (gitignored)
│   ├── groq_key.txt
│   ├── openrouter_key.txt
│   ├── togetherai_key.txt
│   ├── fireworksai_key.txt
│   └── ...
└── data/
    ├── logs/                 # Logs e relatórios de pentest
    └── repos/                # Repositórios a processar
```

---

## 🔧 Tarefas automáticas

| Tarefa | Intervalo | Descrição |
|---|---|---|
| `fix_bugs` | 1h | Analisa código, gera patch, testa e commita |
| `add_feature` | 2h | Implementa features automaticamente |
| `refactor` | 4h | Melhora qualidade sem mudar comportamento |
| `pen_test` | 24h (3h AM) | Busca vulnerabilidades OWASP Top 10 |
| `improve_self` | 12h | Sugere melhorias no próprio sistema |
| `health_check` | 5min | Verifica disponibilidade dos provedores |

---

## 🛠️ Ferramentas MCP (40+ ferramentas)

### Web & SEO
- `firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`
- `screenshot_url`, `pagespeed_check`, `html_validate`
- `url_shorten`, `qr_generate`, `broken_links_check`

### Cibersegurança
- `dns_lookup`, `ssl_check`, `http_headers_audit`
- `ip_info`, `wayback_lookup`, `cve_search`
- `subdomain_enum`, `whois_rdap`, `tech_stack_detect`
- `security_score`

### Conteúdo & Marketing
- `hackernews_top`, `wikipedia_search`, `rss_fetch`
- `trending_github`, `reddit_top`, `dictionary_lookup`
- `seo_analyze`, `extract_keywords`, `generate_copy`

### Neuro Design & BigTech
- `design_system_generate`, `bigtech_site_generate`
- `neuro_copy_optimize`, `above_fold_blueprint`
- `color_psychology`, `typography_scale`
- `persuasion_framework`, `ux_laws_audit`

### Apresentações
- `presentation_from_doc`, `presentation_from_topic`
- `pitch_deck_generate`, `executive_summary_slide`

### Inteligência de Nicho
- `niche_top_sites`, `site_reverse_engineer`
- `serp_analyze`, `content_gap_finder`
- `pricing_intelligence`, `winning_headline_patterns`

### Notebook & Docs
- `notebook_ask`, `notebook_summarize`
- `read_pentest_reports`, `list_repos`
- `run_task`, `provider_status`

---

## 🔑 Como obter as chaves gratuitas

1. **Groq**: https://console.groq.com/keys
2. **OpenRouter**: https://openrouter.ai/keys
3. **TogetherAI**: https://api.together.ai/settings/api-keys
4. **FireworksAI**: https://fireworks.ai/settings/api-keys
5. **Gemini**: https://aistudio.google.com/app/apikey
6. **Firecrawl**: https://www.firecrawl.dev/
7. **GitHub Token**: https://github.com/settings/tokens (escopo `repo`)

Coloque cada chave em `secrets/<nome>_key.txt`

---

## 🌿 Política de branches Git

- Os agentes **nunca** commitam diretamente em `main` ou `master`
- Cada mudança gera uma branch: `fix/auto-1234567890`, `feat/auto-...`
- Merges para `main` requerem **aprovação humana**

---

## 💾 Limites de RAM

| Serviço | Limite |
|---|---|
| redis | 256 MB |
| key-manager | 128 MB |
| scheduler | 256 MB |
| worker × 2 | 512 MB cada |
| ollama | 1.536 MB |
| flower | 128 MB |
| mcp-server | 128 MB |
| **Total** | **~3,5 GB** |

---

## 🛑 Comandos úteis

```bash
docker compose ps                     # status dos containers
docker compose logs -f worker         # logs dos workers
docker compose restart worker         # reiniciar workers
docker compose up -d                 # subir tudo
docker compose down                  # parar tudo
docker compose down -v               # parar e apagar volumes
```

---

## 🔗 Conexão MCP

Para usar as ferramentas MCP com Claude Desktop, OpenCode, etc.:

```json
{
  "mcpServers": {
    "agentes-24h": {
      "command": "docker",
      "args": ["compose", "-f", "docker-compose.yml", "run", "--rm", "-i", "mcp-server"]
    }
  }
}
```
