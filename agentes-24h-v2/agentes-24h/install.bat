@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: =============================================================================
:: agentes-24h – Instalador Windows
:: Execute como administrador se tiver problemas de permissão.
:: =============================================================================

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║           agentes-24h  –  Instalador Windows            ║
echo  ║     Sistema de Agentes Autônomos com IA (24/7)          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ---------------------------------------------------------------------------
:: 1. Verificar dependências
:: ---------------------------------------------------------------------------
echo [1/6] Verificando dependências...

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRO] Docker não encontrado. Instale Docker Desktop: https://docs.docker.com/desktop/windows/
    pause & exit /b 1
)

docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRO] Docker Compose plugin não encontrado. Atualize o Docker Desktop.
    pause & exit /b 1
)

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo  [AVISO] Git não encontrado. Commits automáticos não funcionarão.
    echo          Instale em: https://git-scm.com/download/win
    set GIT_MISSING=1
) else (
    set GIT_MISSING=0
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    where python3 >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [AVISO] Python não encontrado. Necessário para gerar tokens.
    )
)

echo  [OK] Dependências verificadas.
echo.

:: ---------------------------------------------------------------------------
:: 2. Criar diretórios necessários
:: ---------------------------------------------------------------------------
echo [2/6] Criando estrutura de diretórios...

if not exist "secrets" mkdir secrets
if not exist "data\logs" mkdir data\logs
if not exist "data\repos" mkdir data\repos

:: Arquivos placeholder para secrets (serão sobrescritos abaixo)
if not exist "secrets\.gitkeep" type nul > "secrets\.gitkeep"
if not exist "data\.gitkeep"    type nul > "data\.gitkeep"

echo  [OK] Diretórios criados.
echo.

:: ---------------------------------------------------------------------------
:: 3. Coletar chaves de forma interativa
:: ---------------------------------------------------------------------------
echo [3/6] Configuração de chaves e segredos...
echo  (As chaves ficam em secrets/ com acesso restrito - NUNCA as commite no Git)
echo.

:: OpenRouter API Key
if not exist "secrets\openrouter_key.txt" (
    echo  OpenRouter API Key (obtenha em https://openrouter.ai/keys):
    set /p OR_KEY="  > "
    if "!OR_KEY!"=="" (
        echo PLACEHOLDER_TROQUE_AQUI > secrets\openrouter_key.txt
        echo  [AVISO] Chave em branco – usando placeholder. Edite secrets\openrouter_key.txt depois.
    ) else (
        echo !OR_KEY! > secrets\openrouter_key.txt
        echo  [OK] OpenRouter key salva.
    )
) else (
    echo  [SKIP] secrets\openrouter_key.txt já existe.
)
echo.

:: Firecrawl API Key
if not exist "secrets\firecrawl_key.txt" (
    echo  Firecrawl API Key (obtenha em https://firecrawl.dev – deixe em branco para pular):
    set /p FC_KEY="  > "
    if "!FC_KEY!"=="" (
        echo PLACEHOLDER_TROQUE_AQUI > secrets\firecrawl_key.txt
    ) else (
        echo !FC_KEY! > secrets\firecrawl_key.txt
        echo  [OK] Firecrawl key salva.
    )
) else (
    echo  [SKIP] secrets\firecrawl_key.txt já existe.
)
echo.

:: GitHub Personal Access Token
if not exist "secrets\github_token.txt" (
    echo  GitHub Personal Access Token (para push de branches automáticas):
    echo  Gere em: GitHub > Settings > Developer settings > Personal access tokens
    echo  Escopo necessário: repo (ou contents:write)
    set /p GH_TOKEN="  > "
    if "!GH_TOKEN!"=="" (
        echo PLACEHOLDER_TROQUE_AQUI > secrets\github_token.txt
    ) else (
        echo !GH_TOKEN! > secrets\github_token.txt
        echo  [OK] GitHub token salvo.
    )
) else (
    echo  [SKIP] secrets\github_token.txt já existe.
)
echo.

:: Google OAuth Token (gerado externamente pelo OpenCode/Gemini CLI)
if not exist "secrets\google_oauth_token.json" (
    echo  Google OAuth Token (google_oauth_token.json):
    echo  Execute 'opencode auth' ou 'gemini auth' no host e copie o token para
    echo  secrets\google_oauth_token.json. Por enquanto, criando placeholder...
    echo {"placeholder": true} > secrets\google_oauth_token.json
    echo  [AVISO] Edite secrets\google_oauth_token.json com o token real depois.
) else (
    echo  [SKIP] secrets\google_oauth_token.json já existe.
)
echo.

:: ---------------------------------------------------------------------------
:: 4. Gerar o arquivo .env
:: ---------------------------------------------------------------------------
echo [4/6] Gerando arquivo .env...

if exist ".env" (
    echo  [SKIP] .env já existe. Pulando geração automática.
    goto :env_done
)

:: Gerar token interno aleatório (usa PowerShell se disponível)
set KM_TOKEN=TROQUE_MANUALMENTE
for /f "delims=" %%i in ('powershell -Command "[System.Web.Security.Membership]::GeneratePassword(32,4)" 2^>nul') do set KM_TOKEN=%%i
if "!KM_TOKEN!"=="TROQUE_MANUALMENTE" (
    :: Fallback: timestamp como token (menos seguro, mas funcional)
    for /f "delims=" %%i in ('powershell -Command "Get-Date -Format 'yyyyMMddHHmmss'" 2^>nul') do set KM_TOKEN=km_%%i
)

set /p FLOWER_PASS="  Senha para o Flower (monitoramento – padrão: changeme): "
if "!FLOWER_PASS!"=="" set FLOWER_PASS=changeme

set /p GIT_EMAIL="  E-mail para commits Git (padrão: agente@localhost): "
if "!GIT_EMAIL!"=="" set GIT_EMAIL=agente@localhost

set /p GIT_NAME="  Nome para commits Git (padrão: Agente Autonomo): "
if "!GIT_NAME!"=="" set GIT_NAME=Agente Autonomo

(
echo # Gerado pelo instalador em %date% %time%
echo KM_AUTH_TOKEN=!KM_TOKEN!
echo FLOWER_USER=admin
echo FLOWER_PASSWORD=!FLOWER_PASS!
echo GIT_USER_EMAIL=!GIT_EMAIL!
echo GIT_USER_NAME=!GIT_NAME!
echo OLLAMA_DEFAULT_MODEL=phi3:mini
echo TASK_FIX_BUGS_INTERVAL=3600
echo TASK_ADD_FEATURE_INTERVAL=7200
echo TASK_REFACTOR_INTERVAL=14400
echo TASK_PEN_TEST_INTERVAL=86400
echo TASK_IMPROVE_SELF_INTERVAL=43200
) > .env

echo  [OK] .env gerado.
:env_done
echo.

:: ---------------------------------------------------------------------------
:: 5. Iniciar o sistema com Docker Compose
:: ---------------------------------------------------------------------------
echo [5/6] Iniciando containers (docker compose up -d)...
echo  Isso pode levar alguns minutos na primeira execução (download de imagens).
echo.

docker compose up -d --build
if %errorlevel% neq 0 (
    echo  [ERRO] Falha ao iniciar o Docker Compose. Verifique os logs acima.
    pause & exit /b 1
)

echo  [OK] Containers iniciados.
echo.

:: ---------------------------------------------------------------------------
:: 6. Resumo final
:: ---------------------------------------------------------------------------
echo [6/6] Instalação concluída!
echo.
echo  ┌─────────────────────────────────────────────────────────┐
echo  │  Acesso aos serviços:                                   │
echo  │                                                         │
echo  │  Flower (monitoramento): http://localhost:5555          │
echo  │  Usuário: admin  /  Senha: conforme .env               │
echo  │                                                         │
echo  │  Para ver logs:                                         │
echo  │    docker compose logs -f worker                        │
echo  │                                                         │
echo  │  Para parar:                                            │
echo  │    docker compose down                                  │
echo  │                                                         │
echo  │  PRÓXIMOS PASSOS:                                       │
echo  │  1. Coloque repositórios em data\repos\                 │
echo  │  2. Edite secrets\ com suas chaves reais               │
echo  │  3. Substitua google_oauth_token.json pelo real        │
echo  └─────────────────────────────────────────────────────────┘
echo.

pause
endlocal
