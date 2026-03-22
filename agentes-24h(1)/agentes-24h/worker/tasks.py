"""
tasks.py
========
Tarefas Celery executadas pelos agentes autônomos.

Tarefas disponíveis:
  - fix_bugs         : analisa código, gera patch via IA, testa e commita
  - add_feature      : implementa feature descrita em ticket
  - refactor         : melhora qualidade do código
  - pen_test         : busca vulnerabilidades comuns
  - improve_self     : melhora o próprio código dos agentes
  - health_check     : verifica saúde de todos os provedores

Cada tarefa:
  1. Seleciona um repositório de data/repos/
  2. Cria uma branch separada
  3. Aplica mudanças via IA
  4. Commita e (opcionalmente) faz push
  5. Nunca altera main/master diretamente
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from celery import Celery
from celery.utils.log import get_task_logger

import git_utils
from key_client import KeyClient
from providers import ProviderOrchestrator

# ---------------------------------------------------------------------------
# App Celery
# ---------------------------------------------------------------------------
BROKER_URL  = os.environ.get("CELERY_BROKER_URL",  "redis://redis:6379/0")
BACKEND_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

app = Celery("agents", broker=BROKER_URL, backend=BACKEND_URL)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

log: logging.Logger = get_task_logger(__name__)

REPOS_DIR = os.environ.get("GIT_REPO_PATH", "/data/repos")

# ---------------------------------------------------------------------------
# Singletons (inicializados no worker, não no broker)
# ---------------------------------------------------------------------------
_key_client: Optional[KeyClient] = None
_orchestrator: Optional[ProviderOrchestrator] = None


def get_orchestrator() -> ProviderOrchestrator:
    global _key_client, _orchestrator
    if _orchestrator is None:
        _key_client = KeyClient()
        _orchestrator = ProviderOrchestrator(_key_client)
    return _orchestrator


def get_github_token() -> str:
    try:
        return get_orchestrator()._key_client.get_secret("github_token")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------
def _pick_repo() -> Optional[Path]:
    """Escolhe um repositório aleatório de data/repos/."""
    repos = git_utils.list_repos(REPOS_DIR)
    if not repos:
        log.warning("Nenhum repositório encontrado em %s.", REPOS_DIR)
        return None
    return random.choice(repos)


def _read_code_sample(repo: Path, max_chars: int = 8000) -> tuple[str, list[str]]:
    """
    Lê uma amostra de arquivos de código do repositório.
    Retorna (texto_concatenado, lista_de_arquivos).
    """
    extensions = {".py", ".js", ".ts", ".go", ".java", ".rs", ".rb", ".php"}
    files_found: list[Path] = []
    for ext in extensions:
        files_found.extend(repo.rglob(f"*{ext}"))

    # Exclui diretórios desnecessários
    files_found = [
        f for f in files_found
        if not any(part in str(f) for part in [".git", "node_modules", "__pycache__", "venv", ".venv"])
    ]

    if not files_found:
        return "", []

    # Amostra aleatória de até 5 arquivos
    sample = random.sample(files_found, min(5, len(files_found)))
    combined = ""
    names = []
    for f in sample:
        try:
            content = f.read_text(errors="replace")
            combined += f"\n\n# === {f.relative_to(repo)} ===\n{content}"
            names.append(str(f))
            if len(combined) > max_chars:
                combined = combined[:max_chars] + "\n# ... (truncado)"
                break
        except Exception:
            pass

    return combined, names


def _apply_patch(repo: Path, patch_text: str, files: list[str]) -> bool:
    """
    Aplica um patch de texto simples.
    A IA deve retornar o arquivo completo entre marcadores:
      === ARQUIVO: path/relativo ===
      <conteúdo>
      === FIM ===
    """
    import re

    pattern = re.compile(r"=== ARQUIVO: (.+?) ===\n(.*?)\n=== FIM ===", re.DOTALL)
    matches = pattern.findall(patch_text)

    if not matches:
        log.warning("Nenhum bloco ARQUIVO encontrado na resposta da IA.")
        return False

    applied = 0
    for rel_path, content in matches:
        target = repo / rel_path.strip()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            log.info("Arquivo atualizado: %s", target)
            applied += 1
        except Exception as exc:
            log.error("Falha ao escrever %s: %s", target, exc)

    return applied > 0


def _run_tests(repo: Path) -> tuple[bool, str]:
    """Executa testes no repositório e retorna (passou, output)."""
    test_runners = [
        (["python", "-m", "pytest", "--tb=short", "-q"], "pytest.ini", "setup.cfg", "pyproject.toml"),
        (["npm", "test", "--", "--watchAll=false"], "package.json"),
        (["go", "test", "./..."], "go.mod"),
    ]
    for runner_cmd, *markers in test_runners:
        if any((repo / m).exists() for m in markers):
            try:
                result = subprocess.run(
                    runner_cmd, cwd=str(repo), capture_output=True, text=True, timeout=120
                )
                passed = result.returncode == 0
                output = (result.stdout + result.stderr)[:3000]
                return passed, output
            except Exception as exc:
                return False, str(exc)
    return True, "Nenhum runner de testes encontrado – assumindo OK."


# ===========================================================================
# TAREFA: fix_bugs
# ===========================================================================
@app.task(name="tasks.fix_bugs", bind=True, max_retries=2)
def fix_bugs(self):
    """Analisa código em busca de bugs e aplica correções via IA."""
    log.info("==> Iniciando fix_bugs")

    repo = _pick_repo()
    if not repo:
        return {"status": "skipped", "reason": "sem repositórios"}

    code, files = _read_code_sample(repo)
    if not code:
        return {"status": "skipped", "reason": "sem código"}

    system = (
        "Você é um engenheiro de software sênior especialista em encontrar e corrigir bugs. "
        "Analise o código fornecido, identifique bugs reais (não apenas estilo) e corrija-os. "
        "Para cada arquivo modificado, retorne o arquivo COMPLETO no formato:\n"
        "=== ARQUIVO: <caminho/relativo> ===\n<conteúdo completo>\n=== FIM ===\n"
        "Se não houver bugs, responda apenas: NENHUM_BUG_ENCONTRADO"
    )

    prompt = f"Repositório: {repo.name}\n\nCódigo para análise:\n{code}"

    try:
        response, provider_used = get_orchestrator().complete(prompt, system=system, max_tokens=4096)
    except RuntimeError as exc:
        log.error("fix_bugs: todos os provedores falharam: %s", exc)
        return {"status": "error", "reason": str(exc)}

    if "NENHUM_BUG_ENCONTRADO" in response:
        log.info("fix_bugs: nenhum bug identificado pela IA.")
        return {"status": "ok", "result": "no_bugs", "provider": provider_used}

    # Criar branch e aplicar patch
    branch = git_utils.create_branch(str(repo), prefix="fix")
    applied = _apply_patch(repo, response, files)

    if not applied:
        return {"status": "error", "reason": "patch inválido"}

    # Testes antes de commitar
    passed, test_output = _run_tests(repo)
    if not passed:
        log.warning("fix_bugs: testes falharam após patch:\n%s", test_output[:500])
        # Revertemos a branch
        subprocess.run(["git", "checkout", "."], cwd=str(repo), check=False)
        return {"status": "error", "reason": "testes falharam", "test_output": test_output[:500]}

    committed = git_utils.commit_changes(
        str(repo),
        f"fix: correção automática de bugs via {provider_used}",
    )

    if committed:
        gh_token = get_github_token()
        if gh_token and not gh_token.startswith("PLACEHOLDER"):
            git_utils.push_branch(str(repo), branch, gh_token)

    return {
        "status": "ok",
        "branch": branch,
        "provider": provider_used,
        "committed": committed,
    }


# ===========================================================================
# TAREFA: add_feature
# ===========================================================================
@app.task(name="tasks.add_feature", bind=True, max_retries=2)
def add_feature(self, feature_description: str = ""):
    """Implementa uma feature descrita em texto."""
    log.info("==> Iniciando add_feature: %s", feature_description[:80])

    repo = _pick_repo()
    if not repo:
        return {"status": "skipped", "reason": "sem repositórios"}

    if not feature_description:
        feature_description = (
            "Adicione docstrings faltando às funções públicas e "
            "melhore as mensagens de log para facilitar debugging."
        )

    code, files = _read_code_sample(repo)

    system = (
        "Você é um desenvolvedor sênior. Implemente a feature descrita no código fornecido. "
        "Retorne os arquivos modificados/criados COMPLETOS no formato:\n"
        "=== ARQUIVO: <caminho/relativo> ===\n<conteúdo>\n=== FIM ===\n"
        "Seja conservador: implemente apenas o necessário, sem refatorações não relacionadas."
    )

    prompt = (
        f"Repositório: {repo.name}\n"
        f"Feature a implementar: {feature_description}\n\n"
        f"Código atual:\n{code}"
    )

    try:
        response, provider_used = get_orchestrator().complete(prompt, system=system, max_tokens=4096)
    except RuntimeError as exc:
        return {"status": "error", "reason": str(exc)}

    branch = git_utils.create_branch(str(repo), prefix="feat")
    applied = _apply_patch(repo, response, files)

    if not applied:
        return {"status": "error", "reason": "patch inválido"}

    passed, test_output = _run_tests(repo)
    committed = False
    if passed:
        committed = git_utils.commit_changes(
            str(repo),
            f"feat: {feature_description[:72]} (via {provider_used})",
        )
        if committed:
            gh_token = get_github_token()
            if gh_token and not gh_token.startswith("PLACEHOLDER"):
                git_utils.push_branch(str(repo), branch, gh_token)

    return {
        "status": "ok" if passed else "tests_failed",
        "branch": branch,
        "provider": provider_used,
        "committed": committed,
    }


# ===========================================================================
# TAREFA: refactor
# ===========================================================================
@app.task(name="tasks.refactor", bind=True, max_retries=2)
def refactor(self):
    """Refatora código para melhorar qualidade sem mudar comportamento."""
    log.info("==> Iniciando refactor")

    repo = _pick_repo()
    if not repo:
        return {"status": "skipped"}

    code, files = _read_code_sample(repo)
    if not code:
        return {"status": "skipped", "reason": "sem código"}

    system = (
        "Você é um engenheiro especialista em qualidade de código. "
        "Refatore o código para melhorar legibilidade, remover duplicação e seguir boas práticas. "
        "NÃO mude o comportamento externo das funções. "
        "Retorne APENAS os arquivos alterados no formato:\n"
        "=== ARQUIVO: <caminho/relativo> ===\n<conteúdo>\n=== FIM ===\n"
        "Se o código já estiver bom, responda: CODIGO_JA_OTIMIZADO"
    )

    prompt = f"Repositório: {repo.name}\n\nCódigo:\n{code}"

    try:
        response, provider_used = get_orchestrator().complete(
            prompt, system=system, max_tokens=4096, prefer="ollama"
        )
    except RuntimeError as exc:
        return {"status": "error", "reason": str(exc)}

    if "CODIGO_JA_OTIMIZADO" in response:
        return {"status": "ok", "result": "already_good"}

    branch = git_utils.create_branch(str(repo), prefix="refactor")
    applied = _apply_patch(repo, response, files)

    if not applied:
        return {"status": "error", "reason": "patch inválido"}

    passed, _ = _run_tests(repo)
    committed = False
    if passed:
        committed = git_utils.commit_changes(
            str(repo),
            f"refactor: melhoria automática de qualidade (via {provider_used})",
        )

    return {"status": "ok", "branch": branch, "committed": committed}


# ===========================================================================
# TAREFA: pen_test
# ===========================================================================
@app.task(name="tasks.pen_test", bind=True, max_retries=1)
def pen_test(self):
    """Analisa código em busca de vulnerabilidades comuns (OWASP Top 10)."""
    log.info("==> Iniciando pen_test")

    repo = _pick_repo()
    if not repo:
        return {"status": "skipped"}

    code, _ = _read_code_sample(repo)
    if not code:
        return {"status": "skipped"}

    system = (
        "Você é um especialista em segurança de aplicações. "
        "Analise o código em busca de vulnerabilidades comuns: "
        "SQL injection, XSS, CSRF, secrets hardcoded, dependências desatualizadas, "
        "execução arbitrária de código, path traversal, etc. "
        "Retorne um relatório estruturado em JSON com a chave 'vulnerabilities': "
        "lista de {severity, type, file, line, description, recommendation}. "
        "Se não houver vulnerabilidades, retorne {\"vulnerabilities\": []}."
    )

    prompt = f"Repositório: {repo.name}\n\nCódigo:\n{code}"

    try:
        response, provider_used = get_orchestrator().complete(
            prompt, system=system, max_tokens=3000
        )
    except RuntimeError as exc:
        return {"status": "error", "reason": str(exc)}

    # Salvar relatório em arquivo de log
    report_path = Path("/data/logs") / f"pentest_{repo.name}_{int(time.time())}.json"
    try:
        report_path.write_text(response)
        log.info("Relatório de segurança salvo: %s", report_path)
    except Exception:
        pass

    return {
        "status": "ok",
        "provider": provider_used,
        "report_file": str(report_path),
    }


# ===========================================================================
# TAREFA: improve_self
# ===========================================================================
@app.task(name="tasks.improve_self", bind=True, max_retries=1)
def improve_self(self):
    """
    O agente analisa seu próprio código e sugere melhorias.
    Por segurança, as mudanças são commitadas em branch separada
    e NÃO são aplicadas automaticamente (requer revisão humana).
    """
    log.info("==> Iniciando improve_self")

    # Lê o próprio código dos workers
    self_dir = Path(__file__).parent
    own_files = list(self_dir.glob("*.py"))[:5]

    combined = ""
    for f in own_files:
        combined += f"\n\n# === {f.name} ===\n{f.read_text()}"

    if len(combined) > 10000:
        combined = combined[:10000] + "\n# ... (truncado)"

    system = (
        "Você é um engenheiro especialista em sistemas distribuídos e agentes autônomos. "
        "Analise o código do próprio sistema de agentes e sugira melhorias de:"
        " resiliência, performance, segurança e novas funcionalidades. "
        "Retorne os arquivos melhorados no formato:\n"
        "=== ARQUIVO: <nome_do_arquivo.py> ===\n<conteúdo>\n=== FIM ===\n"
        "IMPORTANTE: seja conservador. Não quebre funcionalidades existentes."
    )

    prompt = f"Código do sistema de agentes:\n{combined}"

    try:
        response, provider_used = get_orchestrator().complete(
            prompt, system=system, max_tokens=4096
        )
    except RuntimeError as exc:
        return {"status": "error", "reason": str(exc)}

    # Salvar sugestão como patch (NÃO aplicar automaticamente)
    patch_path = Path("/data/logs") / f"self_improve_{int(time.time())}.patch"
    patch_path.write_text(response)

    log.info(
        "Sugestão de melhoria salva em %s (requer revisão humana antes de aplicar).",
        patch_path,
    )

    return {
        "status": "ok",
        "provider": provider_used,
        "patch_file": str(patch_path),
        "note": "Revisão humana necessária antes de aplicar.",
    }


# ===========================================================================
# TAREFA: health_check
# ===========================================================================
@app.task(name="tasks.health_check")
def health_check():
    """Verifica disponibilidade de todos os provedores e retorna status."""
    log.info("==> health_check")
    orch = get_orchestrator()
    results = {}
    for provider in orch._providers:
        results[provider.name] = provider.is_available()
    log.info("Status dos provedores: %s", results)
    return results
