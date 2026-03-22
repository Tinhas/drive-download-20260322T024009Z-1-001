#!/usr/bin/env bash
# =========================================================
# install.sh — Instalador do agentes-24h-final (Linux/Mac)
# Regras:
#   - Nunca apaga código existente
#   - Não derruba stacks Docker ativas
#   - Free tiers only
# =========================================================
set -euo pipefail

log()  { echo "  $*"; }
ok()   { echo "  ✅ $*"; }
warn() { echo "  ⚠️  $*"; }
fail() { echo "  ❌ $*"; exit 1; }

echo ""
echo "=========================================="
echo "  agentes-24h-final -- Instalador v1.0"
echo "    Linux / macOS"
echo "=========================================="
echo ""

# --- Docker ---
if ! command -v docker &>/dev/null; then
  fail "Docker não encontrado. Instale em: https://www.docker.com/get-started"
fi
ok "Docker encontrado: $(docker --version | cut -d' ' -f3 | tr -d ',')"

if ! docker info &>/dev/null; then
  fail "Docker não está rodando. Inicie o Docker primeiro."
fi
ok "Docker rodando"

# --- Git ---
if command -v git &>/dev/null; then
  ok "Git encontrado: $(git --version)"
  HAS_GIT=1
else
  warn "Git não encontrado. Clone de repos será pulado."
  HAS_GIT=0
fi

# --- Python ---
if command -v python3 &>/dev/null; then
  ok "Python encontrado: $(python3 --version)"
  PYTHON=python3
elif command -v python &>/dev/null; then
  ok "Python encontrado: $(python --version)"
  PYTHON=python
else
  warn "Python não encontrado. Tokens serão gerados com openssl."
  PYTHON=""
fi

# --- Criar .env se não existe ---
if [ ! -f ".env" ]; then
  echo ""
  log "Criando .env a partir de .env.example..."
  cp .env.example .env

  # Gerar tokens seguros
  if [ -n "$PYTHON" ]; then
    KM_TOKEN=$($PYTHON -c "import secrets; print(secrets.token_hex(32))")
    FL_PASS=$($PYTHON  -c "import secrets; print(secrets.token_urlsafe(16))")
  else
    KM_TOKEN=$(openssl rand -hex 32)
    FL_PASS=$(openssl rand -hex 16)
  fi

  sed -i.bak "s/TROQUE_POR_TOKEN_ALEATORIO_SEGURO/${KM_TOKEN}/g" .env
  sed -i.bak "s/TROQUE_POR_SENHA_FORTE/${FL_PASS}/g" .env
  rm -f .env.bak

  ok ".env criado com tokens seguros auto-gerados"
  echo ""
  echo "  📝 Adicione suas chaves de API no .env:"
  echo "     GROQ_API_KEY     → https://console.groq.com/keys  (grátis)"
  echo "     OPENROUTER_API_KEY → https://openrouter.ai/keys    (grátis)"
  echo "     GEMINI_API_KEY   → https://aistudio.google.com     (grátis)"
  echo ""
else
  ok ".env já existe — mantendo configurações atuais"
fi

# --- Criar diretórios ---
mkdir -p data/repos data/logs
ok "Diretórios data/repos e data/logs criados"

# --- Clone repos BigTech (opcional) ---
if [ "$HAS_GIT" = "1" ]; then
  echo ""
  read -rp "  Clonar repositórios BigTech para data/repos/? [S/n]: " CLONE_REPOS
  if [[ "${CLONE_REPOS,,}" != "n" ]]; then
    chmod +x clone_repos.sh
    ./clone_repos.sh
  fi
fi

# --- Verificar containers ativos (NÃO derruba) ---
echo ""
log "Verificando containers Docker ativos (não serão afetados)..."
ACTIVE=$(docker ps --filter status=running --format '{{.Names}}' | grep -v "agents_" | wc -l)
if [ "$ACTIVE" -gt 0 ]; then
  ok "Stacks ativas detectadas ($ACTIVE containers) — novos usarão rede separada"
fi

# --- Build ---
echo ""
log "Construindo imagens Docker (profile: core + ui)..."
docker compose --profile core --profile ui build --no-cache
ok "Build concluído"

# --- Subir serviços ---
echo ""
log "Iniciando agentes (profile: core + ui)..."
log "  - redis, key-manager, scheduler, worker ×2"  
log "  - mcp-gateway (porta 8080), flower (porta 5555)"
echo ""
docker compose --profile core --profile ui up -d

echo ""
echo "=========================================="
echo "  ✅ agentes-24h-final rodando!"
echo "=========================================="
echo ""
echo "  Dashboard Desktop: http://localhost:8080"
echo "  Mobile PWA:        http://localhost:8080/mobile"
echo "  Flower (monitor):  http://localhost:5555"
echo "  Tools API:         http://localhost:8080/tools"
echo ""
echo "  Adicionar Ollama local (LLM grátis):"
echo "    docker compose --profile llm up -d"
echo ""
echo "  Claude Code com MCP:"
echo "    cd agentes-24h-final && claude"
echo ""
echo "  Clonar repos BigTech:"
echo "    ./clone_repos.sh"
echo ""
