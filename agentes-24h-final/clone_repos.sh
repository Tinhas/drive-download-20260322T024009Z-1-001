#!/usr/bin/env bash
# =========================================================
# clone_repos.sh — Clona repositórios BigTech em data/repos/
# Usa --depth=1 para economizar espaço e banda
# =========================================================

set -euo pipefail

echo ""
echo "🤖 agentes-24h-final — Clone de Repositórios BigTech"
echo "======================================================"
echo ""

mkdir -p data/repos
cd data/repos

REPOS=(
  "facebook/react"
  "vercel/next.js"
  "microsoft/vscode"
  "google/guava"
  "netflix/hystrix"
  "spotify/luigi"
  "stripe/stripe-python"
  "airbnb/javascript"
  "uber/go-torch"
  "palantir/blueprint"
)

for REPO in "${REPOS[@]}"; do
  NAME="${REPO##*/}"
  if [ -d "${NAME}/.git" ]; then
    echo "✅ ${NAME} já existe — pulando"
  else
    echo "📥 Clonando ${REPO} ..."
    if git clone --depth=1 "https://github.com/${REPO}.git" "${NAME}" 2>&1; then
      echo "✅ ${NAME} clonado"
    else
      echo "❌ Falha ao clonar ${REPO}"
    fi
  fi
  echo ""
done

cd ../..

echo ""
echo "🎉 Clone concluído! Repos em: data/repos/"
echo "   Os agentes começarão a analisar automaticamente."
echo ""
