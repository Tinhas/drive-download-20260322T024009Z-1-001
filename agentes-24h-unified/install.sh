#!/usr/bin/env bash
# =============================================================================
# agentes-24h – Instalador Linux/macOS
# Uso: chmod +x install.sh && ./install.sh
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error() { echo -e "${RED}[ERRO]${NC} $*"; exit 1; }
ask()   { echo -e "\n${YELLOW}$*${NC}"; }

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          agentes-24h  –  Instalador Linux/macOS         ║"
echo "║     Sistema de Agentes Autônomos com IA (24/7)          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ---------------------------------------------------------------------------
# 1. Verificar dependências
# ---------------------------------------------------------------------------
echo "==> [1/6] Verificando dependências..."

command -v docker &>/dev/null || error "Docker não encontrado. Instale: https://docs.docker.com/get-docker/"
docker compose version &>/dev/null || error "Docker Compose plugin não encontrado. Atualize o Docker."
command -v git &>/dev/null    || warn "Git não encontrado. Commits automáticos não funcionarão."
command -v python3 &>/dev/null || warn "Python3 não encontrado. Algumas funções de setup podem falhar."

info "Dependências verificadas."

# ---------------------------------------------------------------------------
# 2. Criar diretórios
# ---------------------------------------------------------------------------
echo ""
echo "==> [2/6] Criando estrutura de diretórios..."

mkdir -p secrets data/logs data/repos
touch secrets/.gitkeep data/.gitkeep

# Restringir permissões na pasta de secrets
chmod 700 secrets

info "Diretórios criados."

# ---------------------------------------------------------------------------
# 3. Coletar chaves interativamente
# ---------------------------------------------------------------------------
echo ""
echo "==> [3/6] Configuração de chaves e segredos..."
echo "    (As chaves ficam em secrets/ com permissão 600 – NUNCA as commite no Git)"

# Função auxiliar para salvar secret
save_secret() {
    local file="$1"
    local prompt="$2"
    local url="$3"
    local default="$4"

    if [[ -f "$file" ]]; then
        warn "$file já existe. Pulando."
        return
    fi

    echo ""
    echo "  $prompt"
    [[ -n "$url" ]] && echo "  Obtenha em: $url"
    read -rp "  > " value
    value="${value:-$default}"
    echo "$value" > "$file"
    chmod 600 "$file"
    info "$file salvo."
}

save_secret \
    "secrets/openrouter_key.txt" \
    "OpenRouter API Key:" \
    "https://openrouter.ai/keys" \
    "PLACEHOLDER_TROQUE_AQUI"

save_secret \
    "secrets/firecrawl_key.txt" \
    "Firecrawl API Key (Enter para pular):" \
    "https://firecrawl.dev" \
    "PLACEHOLDER_TROQUE_AQUI"

save_secret \
    "secrets/github_token.txt" \
    "GitHub Personal Access Token (escopo: repo ou contents:write):" \
    "https://github.com/settings/tokens" \
    "PLACEHOLDER_TROQUE_AQUI"

if [[ ! -f "secrets/google_oauth_token.json" ]]; then
    echo ""
    warn "google_oauth_token.json não encontrado."
    echo "  Execute 'opencode auth' ou 'gemini auth' no host e copie"
    echo "  o token gerado para secrets/google_oauth_token.json."
    echo '{"placeholder": true}' > secrets/google_oauth_token.json
    chmod 600 secrets/google_oauth_token.json
    warn "Placeholder criado. Substitua pelo token real depois."
fi

# ---------------------------------------------------------------------------
# 4. Gerar .env
# ---------------------------------------------------------------------------
echo ""
echo "==> [4/6] Gerando arquivo .env..."

if [[ -f ".env" ]]; then
    warn ".env já existe. Pulando geração automática."
else
    # Token interno seguro
    if command -v python3 &>/dev/null; then
        KM_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    else
        KM_TOKEN="km_$(date +%s)_$(( RANDOM * RANDOM ))"
    fi

    echo ""
    read -rp "  Senha para o Flower (padrão: changeme): " FLOWER_PASS
    FLOWER_PASS="${FLOWER_PASS:-changeme}"

    read -rp "  E-mail para commits Git (padrão: agente@localhost): " GIT_EMAIL
    GIT_EMAIL="${GIT_EMAIL:-agente@localhost}"

    read -rp "  Nome para commits Git (padrão: Agente Autonomo): " GIT_NAME
    GIT_NAME="${GIT_NAME:-Agente Autonomo}"

    cat > .env <<EOF
# Gerado pelo instalador em $(date)
KM_AUTH_TOKEN=${KM_TOKEN}
FLOWER_USER=admin
FLOWER_PASSWORD=${FLOWER_PASS}
GIT_USER_EMAIL=${GIT_EMAIL}
GIT_USER_NAME=${GIT_NAME}
OLLAMA_DEFAULT_MODEL=phi3:mini
TASK_FIX_BUGS_INTERVAL=3600
TASK_ADD_FEATURE_INTERVAL=7200
TASK_REFACTOR_INTERVAL=14400
TASK_PEN_TEST_INTERVAL=86400
TASK_IMPROVE_SELF_INTERVAL=43200
EOF

    chmod 600 .env
    info ".env gerado."
fi

# ---------------------------------------------------------------------------
# 5. Iniciar Docker Compose
# ---------------------------------------------------------------------------
echo ""
echo "==> [5/6] Iniciando containers (docker compose up -d --build)..."
echo "    Isso pode levar alguns minutos na primeira execução."

docker compose up -d --build

info "Containers iniciados."

# ---------------------------------------------------------------------------
# 6. Resumo
# ---------------------------------------------------------------------------
echo ""
echo "==> [6/6] Instalação concluída!"
echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│  Acesso aos serviços:                                   │"
echo "│                                                         │"
echo "│  Flower (monitoramento): http://localhost:5555          │"
echo "│  Usuário: admin  /  Senha: conforme .env               │"
echo "│                                                         │"
echo "│  Comandos úteis:                                        │"
echo "│    docker compose logs -f worker    # ver logs          │"
echo "│    docker compose ps                # status            │"
echo "│    docker compose down              # parar             │"
echo "│    docker compose restart worker    # reiniciar worker  │"
echo "│                                                         │"
echo "│  PRÓXIMOS PASSOS:                                       │"
echo "│  1. Coloque repositórios em data/repos/                 │"
echo "│  2. Edite secrets/ com suas chaves reais               │"
echo "│  3. Substitua google_oauth_token.json pelo token real  │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""
