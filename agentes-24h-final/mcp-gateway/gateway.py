"""
mcp-gateway/gateway.py
======================
HTTP Gateway para o sistema agentes-24h.
Expõe todos os 50+ tools MCP como REST API + dashboard web + PWA mobile.

Endpoints:
  GET  /              Dashboard desktop
  GET  /mobile        PWA mobile-first (celular antigo, <50KB)
  GET  /health        Healthcheck
  GET  /tools         JSON com schema de todas as ferramentas
  POST /call/{tool}   Chama ferramenta diretamente
  GET  /providers     Status dos provedores de IA
  GET  /mcp/config    Retorna mcp_config.json pronto para uso

Porta padrão: 8080
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# Adiciona o mcp-server ao PYTHONPATH para re-usar os tools
# ============================================================
MCP_SERVER_DIR = Path(__file__).parent.parent / "mcp-server"
sys.path.insert(0, str(MCP_SERVER_DIR))

# Importa todas as ferramentas do mcp-server
try:
    import server as mcp_server
    TOOLS = mcp_server.TOOLS
    HAS_TOOLS = True
except Exception as e:
    TOOLS = {}
    HAS_TOOLS = False
    logging.warning("Falha ao importar tools do mcp-server: %s", e)

# ============================================================
# Configuração
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mcp-gateway] %(levelname)s %(message)s",
)
log = logging.getLogger("mcp-gateway")

GATEWAY_PORT = int(os.environ.get("MCP_GATEWAY_PORT", 8080))
KM_URL       = os.environ.get("KM_URL", "http://key-manager:8100")
KM_TOKEN     = os.environ.get("KM_AUTH_TOKEN", "")
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://ollama:11434")
REPOS_DIR    = os.environ.get("GIT_REPO_PATH", "/data/repos")
LOGS_DIR     = "/data/logs"

# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="agentes-24h Gateway",
    description="HTTP gateway para 50+ ferramentas MCP de agentes autônomos",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = Path(__file__).parent / "templates"


# ============================================================
# Helpers
# ============================================================
def _get_provider_status() -> dict:
    """Verifica quais providers de IA estão disponíveis."""
    status = {}

    # Ollama
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        status["ollama"] = {"ok": True, "models": models[:5]}
    except Exception:
        status["ollama"] = {"ok": False, "models": []}

    # Key-manager secrets
    for provider in ["openrouter_key", "groq_key", "firecrawl_key"]:
        try:
            r = httpx.get(
                f"{KM_URL}/secret/{provider}",
                headers={"Authorization": f"Bearer {KM_TOKEN}"},
                timeout=3,
            )
            val = r.json().get("value", "")
            status[provider.replace("_key", "")] = {
                "ok": bool(val) and not val.startswith("PLACEHOLDER"),
            }
        except Exception:
            status[provider.replace("_key", "")] = {"ok": False}

    # Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    status["gemini"] = {"ok": bool(gemini_key)}

    return status


def _get_tools_summary() -> list[dict]:
    """Retorna lista resumida de todos os tools."""
    return [
        {
            "name": name,
            "description": meta["description"][:120],
            "params": list(meta["inputSchema"].get("properties", {}).keys()),
            "required": meta["inputSchema"].get("required", []),
        }
        for name, meta in TOOLS.items()
    ]


# ============================================================
# Endpoints
# ============================================================

@app.get("/health")
async def health():
    return {"status": "ok", "tools": len(TOOLS), "timestamp": int(time.time())}


@app.get("/tools")
async def list_tools():
    """Lista todas as ferramentas disponíveis com seus schemas completos."""
    tools_list = [
        {
            "name": name,
            "description": meta["description"],
            "inputSchema": meta["inputSchema"],
        }
        for name, meta in TOOLS.items()
    ]
    return {"count": len(tools_list), "tools": tools_list}


@app.post("/call/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """Chama uma ferramenta pelo nome com os argumentos no body JSON."""
    if tool_name not in TOOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Ferramenta '{tool_name}' não encontrada. Use GET /tools para listar.",
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        log.info("Chamando tool: %s args=%s", tool_name, list(body.keys()))
        result = TOOLS[tool_name]["fn"](**body)
        return {"ok": True, "tool": tool_name, "result": str(result)}
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Argumentos inválidos: {e}")
    except Exception as e:
        log.error("Erro em %s: %s", tool_name, e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "tool": tool_name, "error": str(e)},
        )


@app.get("/providers")
async def provider_status():
    """Status de todos os provedores de IA."""
    return _get_provider_status()


@app.get("/mcp/config")
async def mcp_config(request: Request):
    """Retorna o mcp_config.json pronto para uso no Claude Code / OpenCode."""
    host = request.headers.get("host", "localhost:8080")
    base = f"http://{host}"
    config = {
        "mcpServers": {
            "agentes-24h-http": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-fetch", f"{base}/mcp"],
                "description": "agentes-24h via HTTP Gateway",
            }
        }
    }
    return config


@app.get("/repos")
async def list_repos():
    """Lista repositórios disponíveis em data/repos/."""
    base = Path(REPOS_DIR)
    if not base.exists():
        return {"repos": []}
    repos = [p.name for p in base.iterdir() if (p / ".git").exists()]
    return {"count": len(repos), "repos": sorted(repos)}


@app.get("/logs")
async def list_logs():
    """Lista logs e relatórios gerados pelos agentes."""
    logs_dir = Path(LOGS_DIR)
    if not logs_dir.exists():
        return {"files": []}
    files = sorted(logs_dir.iterdir(), reverse=True)[:20]
    return {
        "files": [
            {"name": f.name, "size": f.stat().st_size, "modified": int(f.stat().st_mtime)}
            for f in files
        ]
    }


# ============================================================
# Dashboard Desktop (HTML)
# ============================================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentes-24h | Dashboard</title>
<style>
  :root{--bg:#0d1117;--card:#161b22;--border:#30363d;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d29922;--text:#e6edf3;--muted:#8b949e}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:0}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:1rem 2rem;display:flex;align-items:center;gap:1rem}
  header h1{font-size:1.25rem;font-weight:600}
  header .badge{background:var(--accent);color:#000;padding:.2rem .6rem;border-radius:99px;font-size:.75rem;font-weight:700}
  .container{max-width:1400px;margin:0 auto;padding:2rem}
  .grid-4{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem;margin-bottom:2rem}
  .stat-card{background:var(--card);border:1px solid var(--border);border-radius:.75rem;padding:1.25rem}
  .stat-card h3{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem}
  .stat-card .value{font-size:2rem;font-weight:700;color:var(--accent)}
  .section{margin-bottom:2rem}
  .section h2{font-size:1rem;font-weight:600;margin-bottom:1rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .tools-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:.75rem}
  .tool-card{background:var(--card);border:1px solid var(--border);border-radius:.5rem;padding:1rem;cursor:pointer;transition:border-color .2s}
  .tool-card:hover{border-color:var(--accent)}
  .tool-card h4{font-size:.875rem;font-weight:600;color:var(--accent);margin-bottom:.25rem}
  .tool-card p{font-size:.75rem;color:var(--muted);line-height:1.4}
  .tool-card .tags{display:flex;flex-wrap:wrap;gap:.25rem;margin-top:.5rem}
  .tool-card .tag{background:#21262d;color:var(--muted);padding:.15rem .5rem;border-radius:99px;font-size:.7rem}
  .call-panel{background:var(--card);border:1px solid var(--border);border-radius:.75rem;padding:1.5rem;margin-bottom:2rem}
  .call-panel h2{font-size:1rem;font-weight:600;margin-bottom:1rem}
  .input-row{display:flex;gap:.5rem;margin-bottom:.75rem}
  input,textarea,select{background:#21262d;border:1px solid var(--border);color:var(--text);padding:.5rem .75rem;border-radius:.375rem;font-size:.875rem;outline:none;transition:border-color .2s}
  input:focus,textarea:focus,select:focus{border-color:var(--accent)}
  input{flex:1}
  button{background:var(--accent);color:#000;border:none;padding:.5rem 1.25rem;border-radius:.375rem;font-weight:600;cursor:pointer;font-size:.875rem;transition:opacity .2s}
  button:hover{opacity:.85}
  button.secondary{background:var(--card);color:var(--text);border:1px solid var(--border)}
  .result{background:#010409;border:1px solid var(--border);border-radius:.375rem;padding:1rem;margin-top:.75rem;font-family:'Cascadia Code','Fira Code',monospace;font-size:.8rem;white-space:pre-wrap;max-height:400px;overflow-y:auto;color:#7ee787}
  .provider-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5rem}
  .provider{background:var(--card);border:1px solid var(--border);border-radius:.5rem;padding:.75rem;display:flex;align-items:center;gap:.5rem}
  .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
  .dot.ok{background:var(--green)}
  .dot.fail{background:var(--red)}
  .mobile-btn{position:fixed;bottom:1.5rem;right:1.5rem;background:var(--accent);color:#000;padding:.75rem 1.5rem;border-radius:99px;font-weight:700;text-decoration:none;box-shadow:0 4px 16px rgba(88,166,255,.3)}
  @media(max-width:600px){.container{padding:1rem}.grid-4{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<header>
  <span style="font-size:1.5rem">🤖</span>
  <h1>agentes-24h</h1>
  <span class="badge" id="tool-count">...</span>
  <span style="margin-left:auto;color:var(--muted);font-size:.8rem" id="status-text">carregando...</span>
</header>
<div class="container">

  <!-- Stats -->
  <div class="grid-4" id="stats">
    <div class="stat-card"><h3>Ferramentas</h3><div class="value" id="s-tools">-</div></div>
    <div class="stat-card"><h3>Providers Ativos</h3><div class="value" id="s-providers">-</div></div>
    <div class="stat-card"><h3>Repos</h3><div class="value" id="s-repos">-</div></div>
    <div class="stat-card"><h3>Logs</h3><div class="value" id="s-logs">-</div></div>
  </div>

  <!-- Providers -->
  <div class="section">
    <h2>⚡ Provedores de IA</h2>
    <div class="provider-grid" id="providers">Carregando...</div>
  </div>

  <!-- Call Tool -->
  <div class="call-panel">
    <h2>🔧 Chamar Ferramenta</h2>
    <div class="input-row">
      <select id="tool-select" style="min-width:200px"><option>Carregando...</option></select>
      <button onclick="callTool()">▶ Executar</button>
      <button class="secondary" onclick="clearResult()">✕ Limpar</button>
    </div>
    <textarea id="tool-args" rows="3" style="width:100%;font-family:monospace" placeholder='{"param": "valor"}'>{}</textarea>
    <div class="result" id="result" style="display:none"></div>
  </div>

  <!-- Tools Grid -->
  <div class="section">
    <h2>🛠️ Todas as Ferramentas</h2>
    <div class="tools-grid" id="tools-grid">Carregando...</div>
  </div>

</div>
<a href="/mobile" class="mobile-btn">📱 Mobile</a>

<script>
const $ = id => document.getElementById(id);

async function load() {
  try {
    // Health
    const h = await fetch('/health').then(r=>r.json());
    $('s-tools').textContent = h.tools;
    $('tool-count').textContent = h.tools + ' tools';
    $('status-text').textContent = '✅ online';

    // Providers
    const prov = await fetch('/providers').then(r=>r.json());
    const okCount = Object.values(prov).filter(p=>p.ok).length;
    $('s-providers').textContent = okCount + '/' + Object.keys(prov).length;
    $('providers').innerHTML = Object.entries(prov).map(([k,v])=>
      `<div class="provider"><div class="dot ${v.ok?'ok':'fail'}"></div><span style="font-size:.8rem">${k}${v.models?.length?' ('+v.models[0]+')':''}</span></div>`
    ).join('');

    // Repos  
    const repos = await fetch('/repos').then(r=>r.json());
    $('s-repos').textContent = repos.count;

    // Logs
    const logs = await fetch('/logs').then(r=>r.json());
    $('s-logs').textContent = logs.files.length;

    // Tools
    const tools = await fetch('/tools').then(r=>r.json());
    $('tool-select').innerHTML = tools.tools.map(t=>`<option value="${t.name}">${t.name}</option>`).join('');
    $('tools-grid').innerHTML = tools.tools.map(t=>`
      <div class="tool-card" onclick="selectTool('${t.name}')">
        <h4>${t.name}</h4>
        <p>${t.description.slice(0,100)}${t.description.length>100?'...':''}</p>
        <div class="tags">${(t.required||[]).map(r=>`<span class="tag">${r}</span>`).join('')}</div>
      </div>
    `).join('');
  } catch(e) {
    $('status-text').textContent = '❌ erro: ' + e.message;
  }
}

function selectTool(name) {
  $('tool-select').value = name;
  window.scrollTo({top: document.querySelector('.call-panel').offsetTop - 20, behavior: 'smooth'});
}

async function callTool() {
  const name = $('tool-select').value;
  const args = JSON.parse($('tool-args').value || '{}');
  $('result').style.display = 'block';
  $('result').textContent = '⏳ Executando ' + name + '...';
  try {
    const r = await fetch('/call/' + name, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(args)
    }).then(r=>r.json());
    $('result').textContent = r.ok 
      ? r.result 
      : '❌ Erro: ' + r.error;
  } catch(e) {
    $('result').textContent = '❌ ' + e.message;
  }
}

function clearResult() { $('result').style.display='none'; $('result').textContent=''; }

load();
setInterval(load, 30000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Dashboard avançado desktop para acompanhar a orquestração e uso de tokens."""
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return DASHBOARD_HTML


# ============================================================
# Dashboard Mobile PWA (celular antigo, <50KB, sem frameworks)
# ============================================================
MOBILE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="theme-color" content="#0d1117">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>agentes-24h</title>
<link rel="manifest" href="/manifest.json">
<style>
  *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
  :root{--bg:#0d1117;--card:#161b22;--border:#30363d;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--text:#e6edf3;--muted:#8b949e}
  html,body{height:100%;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;font-size:16px}
  #app{display:flex;flex-direction:column;height:100%}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:.75rem 1rem;display:flex;align-items:center;gap:.5rem;flex-shrink:0}
  header h1{font-size:1rem;font-weight:700}
  header .badge{background:var(--accent);color:#000;padding:.15rem .5rem;border-radius:99px;font-size:.7rem;font-weight:700;margin-left:auto}
  #chat{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.75rem;scroll-behavior:smooth}
  .msg{max-width:90%;padding:.75rem 1rem;border-radius:1rem;line-height:1.5;font-size:.875rem;word-break:break-word}
  .msg.user{background:var(--accent);color:#000;align-self:flex-end;border-bottom-right-radius:.25rem}
  .msg.bot{background:var(--card);border:1px solid var(--border);align-self:flex-start;border-bottom-left-radius:.25rem;font-family:'Courier New',monospace;white-space:pre-wrap}
  .msg.bot.error{border-color:var(--red);color:var(--red)}
  .msg.bot.typing{color:var(--muted)}
  #input-area{background:var(--card);border-top:1px solid var(--border);padding:.75rem;display:flex;gap:.5rem;flex-shrink:0}
  #msg-input{flex:1;background:#21262d;border:1px solid var(--border);color:var(--text);padding:.75rem;border-radius:1.5rem;font-size:.875rem;outline:none;resize:none;max-height:120px;overflow-y:auto}
  #send-btn{background:var(--accent);color:#000;border:none;width:44px;height:44px;border-radius:50%;font-size:1.2rem;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center}
  .quick-btns{display:flex;gap:.5rem;overflow-x:auto;padding:.5rem .75rem;background:var(--card);border-bottom:1px solid var(--border);scrollbar-width:none;flex-shrink:0}
  .quick-btns::-webkit-scrollbar{display:none}
  .qbtn{background:#21262d;color:var(--text);border:1px solid var(--border);padding:.4rem .75rem;border-radius:99px;font-size:.75rem;white-space:nowrap;cursor:pointer}
  .qbtn:active{background:var(--border)}
  .welcome{text-align:center;padding:2rem 1rem;color:var(--muted)}
  .welcome .icon{font-size:3rem;margin-bottom:.5rem}
  .welcome p{font-size:.875rem;line-height:1.6}
</style>
</head>
<body>
<div id="app">
  <header>
    <span>🤖</span>
    <h1>agentes-24h</h1>
    <span class="badge" id="tool-count">...</span>
  </header>
  <div class="quick-btns" id="quick-btns">
    <button class="qbtn" onclick="send('status dos providers')">⚡ Providers</button>
    <button class="qbtn" onclick="send('listar repos')">📁 Repos</button>
    <button class="qbtn" onclick="send('health')">💚 Saúde</button>
    <button class="qbtn" onclick="send('ver logs')">📋 Logs</button>
    <button class="qbtn" onclick="send('executar health_check')">🔄 Health Check</button>
    <button class="qbtn" onclick="send('listar ferramentas')">🛠️ Tools</button>
  </div>
  <div id="chat">
    <div class="welcome">
      <div class="icon">🤖</div>
      <p><strong>agentes-24h</strong><br>Digite um comando ou use os botões acima.<br><br>
      Exemplos:<br>
      <em>dns_lookup google.com</em><br>
      <em>executar fix_bugs</em><br>
      <em>status</em>
      </p>
    </div>
  </div>
  <div id="input-area">
    <textarea id="msg-input" placeholder="Comando ou tool..." rows="1"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg()}"></textarea>
    <button id="send-btn" onclick="sendMsg()">➤</button>
  </div>
</div>

<script>
const chat = document.getElementById('chat');
const input = document.getElementById('msg-input');
let toolsList = [];

async function init() {
  try {
    const h = await fetch('/health').then(r=>r.json());
    document.getElementById('tool-count').textContent = h.tools + ' tools';
    const t = await fetch('/tools').then(r=>r.json());
    toolsList = t.tools.map(x=>x.name);
  } catch(e) {}
}

function addMsg(text, type='bot') {
  const el = document.createElement('div');
  el.className = 'msg ' + type;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

function send(text) {
  input.value = text;
  sendMsg();
}

async function sendMsg() {
  const text = input.value.trim();
  if(!text) return;
  input.value = '';
  addMsg(text, 'user');

  const typing = addMsg('⏳ processando...', 'bot typing');

  try {
    const result = await processCommand(text);
    typing.remove();
    const el = addMsg(result, 'bot');
    if(result.startsWith('❌')) el.classList.add('error');
  } catch(e) {
    typing.remove();
    addMsg('❌ ' + e.message, 'bot error');
  }
}

async function processCommand(text) {
  const lower = text.toLowerCase();

  // Comandos especiais
  if(lower.match(/^(saúde|saude|health|status)$/)) {
    const h = await fetch('/health').then(r=>r.json());
    return `✅ Online\n🛠️ Tools: ${h.tools}\n⏱️ ${new Date(h.timestamp*1000).toLocaleTimeString('pt-BR')}`;
  }

  if(lower.includes('provider') || lower.includes('⚡')) {
    const p = await fetch('/providers').then(r=>r.json());
    return Object.entries(p)
      .map(([k,v]) => (v.ok?'✅':'❌')+' '+k+(v.models?.[0]?' ('+v.models[0]+')':''))
      .join('\\n');
  }

  if(lower.includes('repo') || lower.includes('📁')) {
    const r = await fetch('/repos').then(r=>r.json());
    if(r.count===0) return '📁 Nenhum repo ainda. Clone com clone_repos.bat';
    return `📁 ${r.count} repositórios:\\n${r.repos.join('\\n')}`;
  }

  if(lower.includes('log') || lower.includes('📋')) {
    const l = await fetch('/logs').then(r=>r.json());
    if(!l.files.length) return '📋 Nenhum log ainda.';
    return l.files.map(f=>f.name).join('\\n');
  }

  if(lower.includes('ferramenta') || lower.includes('tool') || lower.includes('🛠️')) {
    return '🛠️ '+toolsList.length+' tools:\\n'+toolsList.slice(0,30).join(', ')+'...';
  }

  // Execução direta de task
  if(lower.includes('executar') || lower.includes('run')) {
    const tasks = ['fix_bugs','add_feature','refactor','pen_test','improve_self','health_check'];
    const task = tasks.find(t => lower.includes(t.replace('_',' ')) || lower.includes(t));
    if(task) {
      const r = await fetch('/call/run_task', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({task_name: task})
      }).then(r=>r.json());
      return r.ok ? '✅ ' + r.result : '❌ ' + r.error;
    }
  }

  // Detecta tool pelo nome
  const toolMatch = toolsList.find(t => lower.includes(t.replace('_',' ')) || lower===t);
  if(toolMatch) {
    // Extrai argumentos simples (domínio, URL, keyword)
    const args = extractArgs(text, toolMatch);
    const r = await fetch('/call/'+toolMatch, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(args)
    }).then(r=>r.json());
    if(r.ok) {
      const result = r.result.slice(0, 1500);
      return result + (r.result.length > 1500 ? '\\n... (truncado)' : '');
    }
    return '❌ ' + r.error;
  }

  return '❓ Não entendi. Tente: "dns_lookup google.com", "executar health_check", "status", "listar tools"';
}

function extractArgs(text, toolName) {
  // Extrai domínio/URL/keyword do texto
  const domainMatch = text.match(/([a-z0-9-]+\.[a-z]{2,}[^\s]*)/i);
  const urlMatch = text.match(/(https?:\/\/[^\s]+)/i);
  // Ferramentas que precisam de "domain"
  if(['dns_lookup','ssl_check','whois_rdap','subdomain_enum','security_score'].includes(toolName)) {
    const d = domainMatch?.[1]?.replace(/^https?:\/\//,'').split('/')[0];
    return d ? {domain: d} : {};
  }
  // Ferramentas que precisam de "url"
  if(['http_headers_audit','screenshot_url','html_validate','pagespeed_check',
      'broken_links_check','favicon_check','tech_stack_detect'].includes(toolName)) {
    return urlMatch ? {url: urlMatch[1]} : domainMatch ? {url:'https://'+domainMatch[1]} : {};
  }
  // Ferramentas de busca
  if(['firecrawl_search','hackernews_top'].includes(toolName)) {
    const q = text.replace(new RegExp(toolName.replace('_',' '),'gi'),'').trim();
    return q ? {query: q} : {};
  }
  return {};
}

// Auto-resize textarea
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

init();
</script>
</body>
</html>"""


@app.get("/mobile", response_class=HTMLResponse)
async def mobile():
    """PWA mobile-first para celular antigo — ultra-leve, funciona com 3G."""
    return MOBILE_HTML


@app.get("/manifest.json")
async def manifest():
    """PWA manifest para instalar como app no celular."""
    return {
        "name": "agentes-24h",
        "short_name": "Agentes",
        "description": "50+ ferramentas MCP de agentes autônomos",
        "start_url": "/mobile",
        "display": "standalone",
        "background_color": "#0d1117",
        "theme_color": "#0d1117",
        "icons": [
            {"src": "https://em-content.zobj.net/source/apple/354/robot_1f916.png",
             "sizes": "any", "type": "image/png"}
        ],
    }


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    import uvicorn
    log.info("MCP Gateway iniciando na porta %d", GATEWAY_PORT)
    log.info("Dashboard: http://localhost:%d/", GATEWAY_PORT)
    log.info("Mobile PWA: http://localhost:%d/mobile", GATEWAY_PORT)
    log.info("Tools: http://localhost:%d/tools", GATEWAY_PORT)
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT, log_level="info")
