"""
tools_delegation.py
===================
Ferramentas de delegação para o Antigravity (Orquestrador).
Permite que o Antigravity dispare tarefas complexas para Claude Code 
ou OpenCode AI como sub-agentes, recebendo o resultado quando terminarem.
"""

import subprocess
import os

def _tail(text: str | None, chars: int) -> str:
    if not text:
        return ""
    if len(text) <= chars:
        return text
    start = len(text) - chars
    end = len(text)
    return text[start:end]  # type: ignore

def delegate_to_claude(prompt: str, cwd: str = ".") -> str:
    """
    Delega uma tarefa complexa de codificação para o agente Claude Code.
    O Anthropic Claude Code vai rodar no terminal, resolver o prompt interagindo com o sistema,
    e retornar o sucesso. (Requer claude instalado globalmente).
    """
    try:
        # A flag --print garante que ele execute e cuspa a saída, sem UI interativa travando
        cmd = ["npx", "-y", "@anthropic-ai/claude-code", "-p", prompt]
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600  # Até 10 minutos para concluir a sub-tarefa
        )
        if result.returncode == 0:
            return f"✅ Tarefa concluída pelo Claude Code subordinado.\n\nOutput:\n{_tail(result.stdout, 2000)}"
        else:
            return f"❌ Claude Code reportou erro (Return Code {result.returncode}).\n\nErro:\n{_tail(result.stderr, 2000)}\n\nOutput:\n{_tail(result.stdout, 1000)}"
    except subprocess.TimeoutExpired:
        return "⚠️ O Claude Code estourou o timeout de 10 minutos, mas pode ter feito progresso parcial."
    except Exception as e:
        return f"❌ Erro ao invocar Claude Code: {e}"


def delegate_to_opencode(prompt: str, cwd: str = ".") -> str:
    """
    Delega uma tarefa para o OpenCode AI. 
    Perfeito para tarefas de varredura ou edições em massa que você (Antigravity) queira terceirizar.
    """
    try:
        # OpenCode CLI. Depende da interface específica, geralmente passamos prompts via stdin ou flags.
        # Vamos usar um comando bash simples injetando o prompt
        cmd = ["npx", "-y", "opencode-ai", "-m", prompt]
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode == 0:
            return f"✅ Tarefa concluída pelo OpenCode subordinado.\n\nOutput:\n{_tail(result.stdout, 2000)}"
        else:
            return f"❌ OpenCode reportou erro (Return Code {result.returncode}).\n\nErro:\n{_tail(result.stderr, 2000)}"
    except subprocess.TimeoutExpired:
        return "⚠️ O OpenCode estourou o timeout de 10 minutos."
    except Exception as e:
        return f"❌ Erro ao invocar OpenCode: {e}"
