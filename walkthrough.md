# agentes-24h-final — Walkthrough Completo 🤖

## O que foi feito

Sistema de agentes 24/7 completamente configurado e rodando, integrado aos MVPs JustBee e SovereignStack.

---

## ✅ Ferramentas Instaladas

| Ferramenta | Status | Versão |
|---|---|---|
| Claude Code (`@anthropic-ai/claude-code`) | ✅ Instalado global | npm `@anthropic-ai/claude-code` 2 pacotes |
| Node.js | ✅ | v24.11.1 |
| Git | ✅ | 2.51.0 |
| Docker | ✅ | 29.2.1 |
| Python | ✅ | 3.14.0 |

> **OpenCode e Ollama**: instale conforme abaixo quando necessário (são opcionais, não consomem recursos quando parados).

---

## ✅ Docker Stack Rodando

**Localização:** `C:\Users\pc\Downloads\drive-download-20260322T024009Z-1-001\agentes-24h-final\`

```
docker compose --profile core --profile ui up -d
```

| Container | Status | Porta |
|---|---|---|
| `agents_redis` | ✅ healthy | — |
| `agents_key_manager` | ✅ healthy | 8100 (interno) |
| `agents_scheduler` | ✅ running | — |
| `agents_worker` (×2) | ✅ running | — |
| `agents_mcp` | ✅ running | — |
| `agents_mcp_gateway` | ✅ running | **8080** |
| `agents_flower` | ✅ running | **5555** |

**RAM usada:** ~1.7GB (profile core + ui, sem Ollama)

---

## 🌐 Como Acessar

| Interface | URL | Para quem |
|---|---|---|
| **Dashboard Desktop** | http://localhost:8080 | PC / notebook |
| **📱 Mobile PWA** | http://localhost:8080/mobile | Celular antigo, instala como app |
| **API REST** | http://localhost:8080/tools | Integração / scripts |
| **Flower** | http://localhost:5555 | Monitorar tasks Celery |

> No celular: use `http://SEU_IP_LOCAL:8080/mobile`  
> (Ex: `http://192.168.1.100:8080/mobile`)

---

## 🔧 Como Usar o Claude Code com MCP

```bash
# Entrar na pasta do projeto e iniciar Claude Code
cd C:\Users\pc\Downloads\drive-download-20260322T024009Z-1-001\agentes-24h-final
claude
```

Claude Code vai ler o `CLAUDE.md` automaticamente e ter acesso a 50+ tools MCP.

**`mcp_config.json`** configurado em: `C:\Users\pc\.gemini\antigravity\mcp_config.json`

---

## 🌿 Branches dos MVPs

| Projeto | Branch criada | CLAUDE.md |
|---|---|---|
| `platform-v2/justbee/mvp` | `feature/agents-integration` | `agents/CLAUDE.md` |
| `white-label mvp` | `feature/agents-integration` | `agents/CLAUDE.md` |

> Original (`main`) intacto — nunca apagado.

---

## 📱 Versão Mobile PWA (Celular Antigo)

- **URL:** `http://SEU_IP:8080/mobile`
- **<50KB** total — sem frameworks, HTML/CSS puro
- Interface de **chat** — digita comando, retorna resultado
- **Instala como app** no Android/iOS (manifesto PWA)
- Funcional com **3G** rede lenta
- Comandos reconhecidos: `dns_lookup google.com`, `executar health_check`, `status`, `listar tools`, etc.

---

## 📦 Clone de Repos BigTech

```bat
cd agentes-24h-final
clone_repos.bat
```

Clona `--depth=1` (sem histórico, economiza ~95% de espaço):
- `facebook/react`, `vercel/next.js`, `microsoft/vscode`
- `google/guava`, `netflix/hystrix`, `spotify/luigi`
- `stripe/stripe-python`, `airbnb/javascript`, `uber/go-torch`, `palantir/blueprint`

---

## ⚡ Budget Free Tier (24/7)

| Provider | Limite | Como o sistema usa |
|---|---|---|
| **Ollama** (local) | ∞ | `docker compose --profile llm up -d` |
| **Groq** | ~14.400 req/dia gratuito | fix_bugs, add_feature |
| **OpenRouter** | free credits mensais | pen_test, análises |
| **Gemini Flash** | 1.000 req/dia gratuito | resumos, notebooks |

---

## 🔑 Preencher API Keys (GRÁTIS)

Edite `agentes-24h-final/.env`:

```bash
GROQ_API_KEY=       # https://console.groq.com/keys
OPENROUTER_API_KEY= # https://openrouter.ai/keys
GEMINI_API_KEY=     # https://aistudio.google.com/app/apikey
FIRECRAWL_API_KEY=  # https://firecrawl.dev (free tier)
```

Após editar: `docker compose --profile core --profile ui restart`

---

## 🚀 Comandos Principais

```bash
# Iniciar (recomendado -- sem Ollama)
docker compose --profile core --profile ui up -d

# Adicionar Ollama (LLM local grátis, +1.5GB RAM)
docker compose --profile llm up -d

# Parar tudo
docker compose --profile core --profile ui --profile llm down

# Logs em tempo real
docker compose logs -f mcp-gateway

# Chamar tool via CLI
curl -X POST http://localhost:8080/call/dns_lookup -d '{"domain":"google.com"}'

# Usar Claude Code
cd agentes-24h-final && claude

# Clonar BigTech repos
.\clone_repos.bat
```

---

## 📁 Estrutura Final

```
agentes-24h-final/
├── .env                    ← tokens auto-gerados ✅
├── .env.example            ← template
├── CLAUDE.md               ← instruções Claude Code
├── docker-compose.yml      ← profiles core/llm/ui/full
├── install.bat             ← instalador completo Windows
├── clone_repos.bat/sh      ← 10 repos BigTech --depth=1
├── key-manager/            ← gestão segura de API keys
├── scheduler/              ← Celery Beat (tarefas recorrentes)
├── worker/                 ← 6 tasks autônomas (Celery)
├── mcp-server/             ← 50+ tools MCP via stdio
├── mcp-gateway/            ← HTTP REST + dashboard + PWA
├── secrets/                ← placeholders (preencher)
└── data/
    ├── repos/              ← repos clonados para análise
    └── logs/               ← relatórios dos agentes
```
