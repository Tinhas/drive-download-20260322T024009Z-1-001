@echo off
REM =========================================================
REM clone_repos.bat — Clona repositórios BigTech em data\repos\
REM Usa --depth=1 para economizar espaço e banda
REM =========================================================

echo.
echo 🤖 agentes-24h-final — Clone de Repositórios BigTech
echo ======================================================
echo.

if not exist "data\repos" mkdir "data\repos"

cd data\repos

set REPOS=facebook/react vercel/next.js microsoft/vscode google/guava netflix/hystrix spotify/luigi stripe/stripe-python airbnb/javascript uber/go-torch palantir/blueprint

for %%R in (%REPOS%) do (
    set REPO=%%R
    for /f "tokens=2 delims=/" %%N in ("%%R") do set NAME=%%N
    if exist "%%N\.git" (
        echo ✅ %%N já existe — pulando
    ) else (
        echo 📥 Clonando %%R ...
        git clone --depth=1 "https://github.com/%%R.git" "%%N" 2>&1
        if errorlevel 1 (
            echo ❌ Falha ao clonar %%R
        ) else (
            echo ✅ %%N clonado com sucesso
        )
    )
    echo.
)

cd ..\..

echo.
echo 🎉 Clone concluído! Repos em: data\repos\
echo    Os agentes começarão a analisar automaticamente.
echo.
pause
