"""
key_manager.py
==============
Serviço HTTP leve que expõe chaves de forma segura para os workers.

- Lê os secrets dos arquivos montados pelo Docker Secrets.
- Autentica cada requisição com um token Bearer simples (KM_AUTH_TOKEN).
- Nunca loga o valor das chaves, apenas eventos de acesso.
- Não faz rotação de chaves (respeitando os ToS dos provedores).
"""

import os
import json
import logging
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
HOST = os.environ.get("KM_HOST", "0.0.0.0")
PORT = int(os.environ.get("KM_PORT", 8100))
AUTH_TOKEN = os.environ.get("KM_AUTH_TOKEN", "")

# Mapeamento: nome_da_chave → caminho do arquivo de secret
SECRET_FILES = {
    "groq_key":          "/run/secrets/groq_key",
    "openrouter_key":    "/run/secrets/openrouter_key",
    "google_oauth_token": "/run/secrets/google_oauth_token",
    "firecrawl_key":     "/run/secrets/firecrawl_key",
    "github_token":      "/run/secrets/github_token",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [key-manager] %(levelname)s %(message)s",
)
log = logging.getLogger("key-manager")

# ---------------------------------------------------------------------------
# Cache em memória (lê do disco uma vez, não reloga o valor)
# ---------------------------------------------------------------------------
_cache: dict[str, str] = {}


def _load_secret(name: str) -> str | None:
    """Lê e cacheia um secret do arquivo Docker Secret."""
    if name in _cache:
        return _cache[name]

    path = SECRET_FILES.get(name)
    if not path:
        log.warning("Secret desconhecido solicitado: %s", name)
        return None

    try:
        value = Path(path).read_text().strip()
        _cache[name] = value
        log.info("Secret '%s' carregado (len=%d).", name, len(value))
        return value
    except FileNotFoundError:
        log.warning("Arquivo de secret não encontrado: %s", path)
        return None
    except Exception as exc:
        log.error("Erro ao ler secret '%s': %s", name, exc)
        return None


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class KeyManagerHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):  # noqa: A002
        """Redireciona logs do BaseHTTPRequestHandler para o logger padrão."""
        log.debug(format, *args)

    def _send_json(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authenticate(self) -> bool:
        """Valida o token Bearer no cabeçalho Authorization."""
        if not AUTH_TOKEN:
            log.error("KM_AUTH_TOKEN não configurado – acesso bloqueado.")
            return False
        auth_header = self.headers.get("Authorization", "")
        if auth_header != f"Bearer {AUTH_TOKEN}":
            log.warning("Tentativa de acesso não autorizado de %s.", self.client_address[0])
            return False
        return True

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        # --- /health ---
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        # --- /secret/<nome> ---
        if path.startswith("/secret/"):
            if not self._authenticate():
                self._send_json(401, {"error": "unauthorized"})
                return

            name = path[len("/secret/"):]
            value = _load_secret(name)
            if value is None:
                self._send_json(404, {"error": f"secret '{name}' não encontrado"})
            else:
                # Retorna APENAS o valor, sem logar
                self._send_json(200, {"name": name, "value": value})
            return

        # --- /list ---
        if path == "/list":
            if not self._authenticate():
                self._send_json(401, {"error": "unauthorized"})
                return
            # Lista apenas os nomes, nunca os valores
            available = [k for k in SECRET_FILES if Path(SECRET_FILES[k]).exists()]
            self._send_json(200, {"secrets": available})
            return

        self._send_json(404, {"error": "not found"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    if not AUTH_TOKEN:
        log.critical(
            "KM_AUTH_TOKEN está vazio! Defina a variável de ambiente antes de iniciar."
        )
        raise SystemExit(1)

    log.info("Key Manager iniciando em %s:%d", HOST, PORT)
    server = HTTPServer((HOST, PORT), KeyManagerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Encerrando Key Manager.")


if __name__ == "__main__":
    main()
