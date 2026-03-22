# agentes-24h 🤖

Sistema de agentes autônomos que rodam 24/7, orquestrados com Docker Compose.  
Os agentes analisam repositórios Git, corrigem bugs, adicionam features, fazem refatoração e pentests — tudo de forma automática, ética e dentro dos ToS dos provedores.

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
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                     │
│                                                     │
│  ┌──────────┐   ┌─────────────┐   ┌─────────────┐  │
│  │ scheduler│──▶│   redis     │◀──│   workers   │  │
│  │(Beat)    │   │  (broker)   │   │  (x2)       │  │
│  └──────────┘   └─────────────┘   └──────┬──────┘  │
│                                          │          │
│  ┌─────────────┐   ┌─────────────────────▼──────┐  │
│  │ key-manager │◀──│  providers.py              │  │
│  │ (secrets)   │   │  Ollama → OpenRouter →     │  │
│  └─────────────┘   │  Gemini (fallback chain)   │  │
│                    └────────────────────────────┘  │
│  ┌──────────┐   ┌──────────┐                       │
│  │  ollama  │   │  flower  │ :5555                  │
│  │ (local)  │   │(monitor) │                        │
│  └──────────┘   └──────────┘                       │
└─────────────────────────────────────────────────────┘
```

### Provedores de IA (em ordem de fallback)

| Provedor | Custo | Limite | Uso |
|---|---|---|---|
| **Ollama** (local) | Grátis | CPU/RAM | Tarefas simples, fallback |
| **OpenRouter** | Grátis | Por modelo | Modelos como GLM-4-Air, DeepSeek-R1 |
| **Gemini** | Grátis | 1.000 req/dia | Tarefas complexas |

> **Ética:** uma única conta por provedor. Sem rotação de contas para burlar limites.

---

## 📁 Estrutura de diretórios

```
agentes-24h/
├── docker-compose.yml        # Orquestração principal
├── .env.example              # Template de variáveis
├── install.bat / install.sh  # Instaladores
├── key-manager/              # Gerenciador de secrets
├── worker/                   # Workers Celery + providers + skills
│   └── skills/
│       ├── firecrawl.py      # Raspagem web
│       └── notebooklm.py    # Integração com Google NotebookLM
├── scheduler/                # Celery Beat (tarefas recorrentes)
├── secrets/                  # Chaves (gitignored, permissão 600)
└── data/
    ├── logs/                 # Logs e relatórios de pentest
    └── repos/                # Repositórios a serem melhorados
```

---

## 🔧 Tarefas automáticas

| Tarefa | Intervalo padrão | Descrição |
|---|---|---|
| `fix_bugs` | 1h | Analisa código, gera patch, testa e commita |
| `add_feature` | 2h | Implementa features em tickets |
| `refactor` | 4h | Melhora qualidade sem mudar comportamento |
| `pen_test` | 24h (3h AM) | Busca vulnerabilidades OWASP Top 10 |
| `improve_self` | 12h | Sugere melhorias no próprio sistema |
| `health_check` | 5min | Verifica disponibilidade dos provedores |

---

## 📋 Próximos passos após instalação

1. **Adicione repositórios** em `data/repos/` (git clone dentro da pasta)
2. **Configure as chaves reais** em `secrets/` (edite os arquivos `.txt`)
3. **Autentique o Google OAuth:**
   ```bash
   # No host (não no container)
   opencode auth   # ou: gemini auth
   # Copie o token gerado para secrets/google_oauth_token.json
   ```
4. **Acesse o Flower** em http://localhost:5555 para monitorar as tarefas

---

## 🌿 Política de branches Git

- Os agentes **nunca** commitam diretamente em `main` ou `master`
- Cada mudança gera uma branch descritiva: `fix/auto-1234567890`, `feat/auto-...`
- Merges para `main` requerem **aprovação humana**
- Histórico de branches é preservado (nada é deletado)

---

## ⚙️ Ajustar intervalos das tarefas

Edite o `.env` e reinicie o scheduler:

```bash
# .env
TASK_FIX_BUGS_INTERVAL=7200   # a cada 2h em vez de 1h

docker compose restart scheduler
```

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
| **Total** | **~3,3 GB** |

---

## 🛑 Comandos úteis

```bash
docker compose ps                    # status dos containers
docker compose logs -f worker        # logs dos workers
docker compose restart worker        # reiniciar workers
docker compose down                  # parar tudo
docker compose down -v               # parar e apagar volumes
```
