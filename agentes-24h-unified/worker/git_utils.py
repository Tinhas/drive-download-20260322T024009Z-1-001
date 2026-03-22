"""
git_utils.py
============
Utilitários Git para os agentes criarem branches e commitarem mudanças.

Política de branches:
  - NUNCA commitar diretamente em main/master.
  - Criar branches descritivas: feat/auto-<timestamp>, fix/auto-<timestamp>, etc.
  - Deixar merge para aprovação humana (ou CI/CD).
  - Não apagar branches antigas (histórico preservado).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("git-utils")

GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "agente@localhost")
GIT_USER_NAME  = os.environ.get("GIT_USER_NAME",  "Agente Autonomo")


def _run(args: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Executa comando git com logging."""
    log.debug("git %s  (cwd=%s)", " ".join(args[1:] if args[0] == "git" else args), cwd)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def configure_git(repo_path: str):
    """Configura identidade Git no repositório."""
    _run(["git", "config", "user.email", GIT_USER_EMAIL], cwd=repo_path)
    _run(["git", "config", "user.name",  GIT_USER_NAME],  cwd=repo_path)


def current_branch(repo_path: str) -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    return result.stdout.strip()


def create_branch(repo_path: str, prefix: str = "feat") -> str:
    """
    Cria e faz checkout em uma nova branch descritiva.
    Retorna o nome da branch criada.
    """
    timestamp = int(time.time())
    branch_name = f"{prefix}/auto-{timestamp}"
    configure_git(repo_path)

    # Garante que estamos em cima da branch padrão atualizada
    _run(["git", "fetch", "--quiet"], cwd=repo_path, check=False)
    _run(["git", "checkout", "-b", branch_name], cwd=repo_path)
    log.info("Branch criada: %s", branch_name)
    return branch_name


def commit_changes(
    repo_path: str,
    message: str,
    files: Optional[list[str]] = None,
) -> bool:
    """
    Adiciona arquivos e cria um commit.

    Args:
        repo_path: caminho do repositório.
        message: mensagem de commit.
        files: lista de arquivos para adicionar. Se None, usa `git add -A`.

    Retorna True se o commit foi criado, False se não havia mudanças.
    """
    configure_git(repo_path)

    if files:
        _run(["git", "add", "--"] + files, cwd=repo_path)
    else:
        _run(["git", "add", "-A"], cwd=repo_path)

    # Verificar se há mudanças staged
    result = _run(["git", "diff", "--cached", "--quiet"], cwd=repo_path, check=False)
    if result.returncode == 0:
        log.info("Nenhuma mudança para commitar.")
        return False

    full_message = f"[agente] {message}"
    _run(["git", "commit", "-m", full_message], cwd=repo_path)
    log.info("Commit criado: %s", full_message)
    return True


def push_branch(repo_path: str, branch: str, github_token: str) -> bool:
    """
    Faz push da branch para o remote, injetando o token no URL.
    Funciona com repositórios GitHub HTTPS.
    """
    try:
        # Obtém o URL remoto atual
        result = _run(["git", "remote", "get-url", "origin"], cwd=repo_path)
        remote_url = result.stdout.strip()

        # Injeta token no URL (apenas se for GitHub HTTPS)
        if "github.com" in remote_url and remote_url.startswith("https://"):
            auth_url = remote_url.replace(
                "https://", f"https://{github_token}@"
            )
        else:
            auth_url = remote_url  # SSH ou outro provider

        _run(
            ["git", "push", auth_url, f"{branch}:{branch}", "--set-upstream"],
            cwd=repo_path,
        )
        log.info("Branch '%s' enviada para o remote.", branch)
        return True
    except subprocess.CalledProcessError as exc:
        log.error("Falha ao fazer push: %s", exc.stderr)
        return False


def list_repos(repos_dir: str) -> list[Path]:
    """Lista todos os repositórios Git em repos_dir."""
    base = Path(repos_dir)
    return [p for p in base.iterdir() if (p / ".git").exists()]
