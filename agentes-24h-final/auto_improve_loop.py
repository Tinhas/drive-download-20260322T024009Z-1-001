import subprocess
import os
import sys

repo_dir = r"repos\white-label mvp"
max_loops = 5

def run_cmd(cmd_list: list[str], **kwargs):
    if os.name == 'nt' and cmd_list[0] == "npx":
        return subprocess.run(["npx.cmd"] + cmd_list[1:], **kwargs)
    return subprocess.run(cmd_list, **kwargs)

print("=====================================================")
print("🤖 Cérebro Mestre: Auto-Aprimoramento do White-Label 🤖")
print("=====================================================")

if not os.path.exists(os.path.join(repo_dir, ".git")):
    run_cmd(["git", "init"], cwd=repo_dir)
    run_cmd(["git", "add", "."], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "chore: Initial state"], cwd=repo_dir)

for i in range(1, max_loops + 1):
    print(f"\n--- [ 💫 Loop de QA e Melhoria | Iteração {i}/{max_loops} ] ---")
    
    prompt = f"""
Você é o Agente Subordinado (Claude Code) convocado pelo Antigravity Orchestrator. 
Sua missão na iteração {i} de {max_loops} no repositório white-label-mvp:
1. Revise o código existente.
2. Adicione ou fortaleça testes (Q&A local) se for iteração 1. Refatore a interface HTML ou serve.py nas próximas.
3. SEMPRE rode os testes que criar para garantir estabilidade. Corrija tudo que quebrar.
Não pessa permissão, faça as edições diretamente e termine com sucesso.
"""

    print("⏳ Disparando Agente Claude Code (Background Worker)...")
    cmd = ["npx", "-y", "@anthropic-ai/claude-code", "-p", prompt]
    
    result = run_cmd(cmd, cwd=repo_dir, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ Agente concluiu a iteração {i} com sucesso.")
        
        # Commit da versão aprimorada
        run_cmd(["git", "add", "."], cwd=repo_dir)
        run_cmd(["git", "commit", "-m", f"feat(auto-improve): Melhorias da iteração {i} passadas com testes"], cwd=repo_dir)
        print(f"📦 Git commit e versionamento salvo para a Iteração {i}.")
    else:
        print(f"❌ Agente relatou falha ou não completou a iteração {i}.")
        print(f"Log de Erro:\n{result.stderr[-1000:] if result.stderr else result.stdout[-1000:]}")  # type: ignore
        print("Triturando loop para economizar recursos e evitar side effects destrutivos.")
        break

print("\n=====================================================")
print("🎯 Fim do Master Loop de Aprimoramento.")
print("=====================================================")
