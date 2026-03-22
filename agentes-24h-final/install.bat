@echo off
setlocal enabledelayedexpansion
REM =========================================================
REM install.bat — Instalador do agentes-24h-final
REM Regras:
REM   - Nunca apaga código existente
REM   - Não derruba stacks Docker ativas
REM   - Free tiers only (Ollama local + Groq + OpenRouter + Gemini)
REM =========================================================

echo.
echo ==========================================
echo   agentes-24h-final -- Instalador v1.0
echo ==========================================
echo.

REM --- Verificar Docker ---
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Docker nao encontrado. Instale em: https://www.docker.com/get-started
    pause & exit /b 1
)
echo [OK] Docker encontrado

REM --- Verificar Docker rodando ---
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Docker nao esta rodando. Inicie o Docker Desktop primeiro.
    pause & exit /b 1
)
echo [OK] Docker rodando

REM --- Verificar Git ---
git --version >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Git nao encontrado. Clone de repos BigTech sera pulado.
    set HAS_GIT=0
) else (
    echo [OK] Git encontrado
    set HAS_GIT=1
)

REM --- Criar .env se nao existe ---
if not exist ".env" (
    echo.
    echo Criando .env a partir do .env.example...
    copy ".env.example" ".env" >nul

    REM Gera token seguro automaticamente
    for /f %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set KM_TOKEN=%%i
    powershell -Command "(gc .env) -replace 'TROQUE_POR_TOKEN_ALEATORIO_SEGURO', '!KM_TOKEN!' | Set-Content .env -Encoding UTF8"

    REM Gera senha do Flower
    for /f %%i in ('python -c "import secrets; print(secrets.token_urlsafe(16))"') do set FL_PASS=%%i
    powershell -Command "(gc .env) -replace 'TROQUE_POR_SENHA_FORTE', '!FL_PASS!' | Set-Content .env -Encoding UTF8"

    echo [OK] .env criado com tokens seguros auto-gerados
    echo.
    echo [IMPORTANTE] Adicione suas chaves de API no .env:
    echo   GROQ_API_KEY     = https://console.groq.com/keys (gratis)
    echo   OPENROUTER_API_KEY = https://openrouter.ai/keys (gratis)
    echo   GEMINI_API_KEY   = https://aistudio.google.com/app/apikey (gratis)
    echo.
) else (
    echo [OK] .env ja existe - mantendo configuracoes atuais
)

REM --- Criar diretórios se não existem ---
if not exist "data\repos" mkdir "data\repos"
if not exist "data\logs" mkdir "data\logs"

REM --- Clonar repos BigTech (opcional) ---
if %HAS_GIT%==1 (
    echo.
    set /p CLONE_REPOS="Clonar repositórios BigTech para data\repos\? [S/N]: "
    if /i "!CLONE_REPOS!"=="S" (
        call clone_repos.bat
    )
)

REM --- Verificar stacks ativas (NÃO derruba) ---
echo.
echo Verificando containers Docker ativos (nao serao afetados)...
docker compose ps 2>&1 | findstr "running" && (
    echo [INFO] Stacks ativas detectadas - novos containers usarao rede separada
) || echo [INFO] Nenhum container ativo detectado

REM --- Build ---
echo.
echo Construindo imagens Docker (profile: core + ui)...
docker compose --profile core --profile ui build --no-cache 2>&1
if errorlevel 1 (
    echo [ERRO] Falha no build. Verifique os logs acima.
    pause & exit /b 1
)
echo [OK] Build concluido

REM --- Subir serviços ---
echo.
echo Iniciando agentes (profile: core + ui)...
echo   - redis, key-manager, scheduler, worker x2
echo   - mcp-gateway (porta 8080), flower (porta 5555)
echo   (Ollama NOT iniciado - use: docker compose --profile llm up -d)
echo.
docker compose --profile core --profile ui up -d 2>&1
if errorlevel 1 (
    echo [ERRO] Falha ao iniciar containers.
    pause & exit /b 1
)

echo.
echo ==========================================
echo   [OK] agentes-24h-final rodando!
echo ==========================================
echo.
echo   Dashboard Desktop: http://localhost:8080
echo   Mobile PWA:        http://localhost:8080/mobile
echo   Flower (monitor):  http://localhost:5555
echo   Tools API:         http://localhost:8080/tools
echo.
echo   Para instalar Ollama local (LLM gratis):
echo     docker compose --profile llm up -d
echo.
echo   Para Claude Code com MCP:
echo     cd agentes-24h-final
echo     claude
echo.
echo   Para clonar repos BigTech:
echo     clone_repos.bat
echo.
pause
