"""
tools_repo_mgmt.py
=================
Ferramentas MCP para gerenciamento de repositórios Git.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("repo-mgmt")

REPOS_DIR = os.environ.get("GIT_REPO_PATH", "/data/repos")
KM_URL    = os.environ.get("KM_URL", "http://key-manager:8100")
KM_TOKEN  = os.environ.get("KM_AUTH_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")


def _get_secret(name: str) -> Optional[str]:
    try:
        r = httpx.get(
            f"{KM_URL}/secret/{name}",
            headers={"Authorization": f"Bearer {KM_TOKEN}"},
            timeout=10,
        )
        return r.json().get("value")
    except Exception:
        return None


def _run_git(repo_path: str, *args: str) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except FileNotFoundError:
        return -1, "", "git não encontrado"
    except Exception as e:
        return -1, "", str(e)


def tool_list_repos() -> str:
    """Lista todos os repositórios disponíveis com informações básicas."""
    base = Path(REPOS_DIR)
    if not base.exists():
        return f"Diretório {REPOS_DIR} não encontrado."

    repos = []
    for p in base.iterdir():
        git_dir = p / ".git"
        if not git_dir.exists():
            continue

        rc, head, _ = _run_git(str(p), "rev-parse", "--abbrev-ref", "HEAD")
        branch = head.strip() if rc == 0 else "unknown"

        rc, log_out, _ = _run_git(str(p), "log", "--oneline", "-1")
        last_commit = log_out.strip()[:60] if rc == 0 else "none"

        rc, status_out, _ = _run_git(str(p), "status", "--porcelain")
        has_changes = bool(status_out.strip())

        py_files = list(p.rglob("*.py")) if p.is_dir() else 0
        size_mb = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / (1024 * 1024)

        repos.append({
            "name": p.name,
            "branch": branch,
            "last_commit": last_commit,
            "has_changes": has_changes,
            "python_files": len(py_files),
            "size_mb": round(size_mb, 1),
        })

    if not repos:
        return "Nenhum repositório encontrado em " + REPOS_DIR

    lines = [f"Repos em {REPOS_DIR}:"]
    for r in sorted(repos, key=lambda x: x["name"]):
        changes = "⚠️" if r["has_changes"] else "✅"
        lines.append(f"  {changes} {r['name']} | branch: {r['branch']} | {r['python_files']} .py | {r['size_mb']}MB")
        lines.append(f"     └─ {r['last_commit']}")
    return "\n".join(lines)


def tool_repo_summary(repo_name: str) -> str:
    """Retorna um resumo estruturado de um repositório."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not repo_path.exists():
        return f"Repositório '{repo_name}' não encontrado."

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return f"'{repo_name}' não é um repositório Git."

    rc, stdout, _ = _run_git(str(repo_path), "remote", "-v")
    remotes = {}
    if rc == 0:
        for line in stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1].replace("(fetch)", "").replace("(push)", "").strip()

    rc, branches, _ = _run_git(str(repo_path), "branch", "-a", "--format=%(refname:short)")
    branch_list = [b.strip() for b in branches.strip().splitlines() if b.strip()]

    rc, log_out, _ = _run_git(str(repo_path), "log", "--oneline", "-10")
    commits = [c.strip() for c in log_out.strip().splitlines() if c.strip()]

    rc, contributors, _ = _run_git(str(repo_path), "shortlog", "-sn", "-5")
    top_contributors = [c.strip() for c in contributors.strip().splitlines() if c.strip()]

    languages = {}
    for ext in ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.html", "*.css", "*.md", "*.json"]:
        count = len(list(repo_path.rglob(ext)))
        if count:
            languages[ext.replace("*", "")] = count

    return json.dumps({
        "repo": repo_name,
        "path": str(repo_path),
        "remotes": remotes,
        "branches": branch_list[:20],
        "recent_commits": commits[:10],
        "top_contributors": top_contributors[:5],
        "files_by_language": languages,
    }, indent=2, ensure_ascii=False)


def tool_repo_branches(repo_name: str) -> str:
    """Lista todas as branches de um repositório."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not (repo_path / ".git").exists():
        return f"Repositório '{repo_name}' não encontrado."

    rc, stdout, stderr = _run_git(str(repo_path), "branch", "-a", "--format=%(refname:short)|%(objectname:short)|%(committerdate:short)")
    if rc != 0:
        return f"Erro: {stderr}"

    lines = ["Branches de " + repo_name + ":"]
    for line in stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 3:
            branch = parts[0].strip()
            sha = parts[1].strip()
            date = parts[2].strip()
            marker = "👉" if "*" in branch else "  "
            lines.append(f"  {marker} {branch} ({sha}) - {date}")
    return "\n".join(lines) if lines[-1] != lines[0] else "Nenhuma branch encontrada."


def tool_repo_diff(repo_name: str, branch_a: str = "HEAD", branch_b: str = "origin/main") -> str:
    """Mostra diferenças entre branches ou commits."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not (repo_path / ".git").exists():
        return f"Repositório '{repo_name}' não encontrado."

    rc, stdout, stderr = _run_git(str(repo_path), "diff", branch_a, branch_b, "--stat")
    if rc != 0:
        return f"Erro ao diff: {stderr}"

    return stdout.strip()[:5000] if stdout.strip() else "Sem diferenças."


def tool_repo_search(repo_name: str, pattern: str, file_type: str = "*.py") -> str:
    """Busca padrões em arquivos de um repositório."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not repo_path.exists():
        return f"Repositório '{repo_name}' não encontrado."

    matches = []
    for f in repo_path.rglob(file_type):
        if f.is_file():
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.lower() in line.lower():
                        matches.append(f"  {f.relative_to(repo_path)}:{i}  {line.strip()[:100]}")
            except Exception:
                pass

    if not matches:
        return f"Padrão '{pattern}' não encontrado em {file_type}."

    return f"Resultados ({len(matches)}):\n" + "\n".join(matches[:50])


def tool_clone_repo(url: str, folder_name: str = "") -> str:
    """Clona um repositório Git para data/repos/."""
    base = Path(REPOS_DIR)
    base.mkdir(parents=True, exist_ok=True)

    if not folder_name:
        folder_name = url.rstrip("/").split("/")[-1].replace(".git", "")

    dest = base / folder_name
    if dest.exists():
        return f"Repositório '{folder_name}' já existe em {REPOS_DIR}"

    try:
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return f"Erro ao clonar: {result.stderr}"

        rc, _, _ = _run_git(str(dest), "lfs", "install")
        return f"✅ Clonado com sucesso: {folder_name} -> {dest}\n{result.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return "Timeout ao clonar. URL inválida ou conexão lenta."
    except Exception as e:
        return f"Erro: {e}"


def tool_git_log(repo_name: str, limit: int = 10) -> str:
    """Mostra histórico de commits de um repositório."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not (repo_path / ".git").exists():
        return f"Repositório '{repo_name}' não encontrado."

    rc, stdout, stderr = _run_git(str(repo_path), "log", f"--oneline", f"-{limit}", "--format=%h|%s|%an|%ad", "--date=short")
    if rc != 0:
        return f"Erro: {stderr}"

    lines = [f"Últimos {limit} commits em {repo_name}:"]
    for line in stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 4:
            sha, msg, author, date = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
            lines.append(f"  {sha} | {date} | {author} | {msg[:70]}")
    return "\n".join(lines) if lines[-1] != lines[0] else "Sem commits."


def tool_repo_files(repo_name: str, path: str = ".", max_depth: int = 3) -> str:
    """Lista estrutura de arquivos de um repositório."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not repo_path.exists():
        return f"Repositório '{repo_name}' não encontrado."

    target = repo_path / path
    if not target.exists():
        return f"Caminho '{path}' não encontrado em {repo_name}."

    lines = [f"Estrutura de {repo_name}/{path}:"]
    for p in target.rglob("*"):
        if p.is_file() and "node_modules" not in str(p) and ".git" not in str(p):
            depth = len(p.relative_to(target).parts) - 1
            if depth < max_depth:
                indent = "  " * depth
                size = p.stat().st_size
                size_str = f"({size:,}B)" if size < 10000 else ""
                lines.append(f"  {indent}{p.name} {size_str}")
    return "\n".join(lines[:100])


def tool_ai_analyze_repo(repo_name: str) -> str:
    """Usa IA para analisar e resumir um repositório (contexto limitado)."""
    repo_path = Path(REPOS_DIR) / repo_name
    if not repo_path.exists():
        return f"Repositório '{repo_name}' não encontrado."

    summary = tool_repo_summary(repo_name)
    readme_path = None
    for rn in ["README.md", "README.rst", "readme.md"]:
        rp = repo_path / rn
        if rp.exists():
            readme_path = rp
            break

    prompt = f"""Analise este repositório Git e forneça:
1. O que este projeto faz (resumo em 3 linhas)
2. Stack tecnológico (linguagens, frameworks, banco de dados)
3. Pontos fortes e fracos arquiteturais
4. Sugestões de melhoria prioritárias

Dados do repo:
{summary}
"""
    if readme_path:
        try:
            readme_content = readme_path.read_text(encoding="utf-8", errors="ignore")[:3000]
            prompt += f"\n\nREADME:\n{readme_content}"
        except Exception:
            pass

    gemini_key = GEMINI_KEY or os.environ.get("GEMINI_API_KEY", "")
    if gemini_key and not gemini_key.startswith("PLACEHOLDER"):
        try:
            r = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": gemini_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 1500},
                },
                timeout=60,
            )
            if r.status_code == 200:
                result = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return f"Análise IA de {repo_name}:\n\n{result}"
        except Exception as e:
            return f"Análise via IA indisponível ({e}). Resumo básico:\n\n{summary}"

    return f"Análise IA indisponível (sem Gemini key). Resumo:\n\n{summary}"
