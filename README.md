# 🤖 Antigravity Orchestrator & Agentes-24h

O **Antigravity Orchestrator** é um ecossistema autônomo e de alta performance baseado em IA, desenhado para operar 24/7 de forma responsiva. Ele atua como um supervisor Mestre (Gateway HTTP + GUI) que unifica MVPs independentes, sub-agentes e ferramentas de protocolo (MCPs).

---

## 🚀 Principais Features

- **Arquitetura Resiliente & Offline-First:** 50+ ferramentas locais gerenciadas pelo `mcp-server`, garantindo total privacidade em logs e auditorias.
- **Multiplexador de APIs (LiteLLM):** Balanceamento inteligente de tráfego entre diferentes cotas gratuitas (Groq Llama 3, Gemini Flash, OpenRouter e Ollama Local) para operação contínua 24 horas por dia sem limites.
- **Integrações de Autonomia Ética MCP:** 
  - `Sequential Thinking`: Otimiza os loops recursivos de chamadas de LLMs pensando antes de agir.
  - `Server Memory`: Graph network baseada em SQLite mantendo o contexto sempre em disco (estado constante).
  - `Puppeteer` & `Github`: Scraping visual headless local e parseamento limpo de repositórios públicos sem consumir tokens de APIs engessadas.
- **Auto-Aprimoramento via Sandbox (DEV):** Loop cíclico e programável que isoladamente reescreve, refatora e adiciona Q&A automatizado via sub-agentes autônomos como o *Claude Code*.

## 🌟 Dashboard UI / UX

A interface principal fica disponível na base do **Gateway (`http://localhost:8080/`)**. 
Criada utilizando *Glassmorphism* em Vanilla CSS, ela reflete em tempo real o console de logs dos agentes rodando em background, as barras de utilização de token limit/budget, e a Pipeline interativa dos próximos passos da máquina.

---

## 🛠️ Tecnologias

* **Stack Principal:** Python 3.10+, FastAPI (Gateway REST)
* **Containers:** Docker / Docker Compose (Profile Segregation `core` / `ui`)
* **Agentes Clientes:** Claude Code, OpenCode, VSCode Roo/Continue
* **Extensões Globais:** `@modelcontextprotocol/*` NPM packages
* **Gestão de Segredos:** `agentes-24h-final-key-manager`

## 📦 Como Usar (Ponto de Partida)

1. **Configuração de Ambiente:** Execute o `install.bat` da pasta raiz para criar suas estruturas de arquivos seguras (.env, secrets) sem riscos de vazamento.
2. **Setup do Servidor:** Use o docker para provisionar as engines pesadas de banco ou multiplexadores rodando apenas os agentes que deseja instanciar: `docker compose -f docker-compose.dev.yml --profile core up -d`
3. **Dashboards e Gateway:** `docker restart dev_agents_mcp_gateway`. Toda a árvore de operação e debug será espelhada no http://localhost:8080.
4. **Auto Aprimoramento Constante:** Rode o Cérebro Mestre Python nativamente: `python auto_improve_loop.py` e assista ao QA test automagicamento reescrever partes frágeis dos repositórios via VSCode ou Console.

---
> 💡 *Sempre verifique as restrições éticas de autonomia local no respectivo `mcp_config.json` base.*
