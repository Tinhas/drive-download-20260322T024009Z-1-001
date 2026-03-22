"""
tools_cybersec.py
=================
Ferramentas de CYBERSEGURANÇA — todas gratuitas, sem chave de API
(exceto HIBP que tem tier gratuito com chave).

Ferramentas:
  - dns_lookup          : registros DNS via Cloudflare DoH (sem chave)
  - ssl_check           : detalhes do certificado TLS
  - http_headers_audit  : auditoria de cabeçalhos de segurança HTTP
  - ip_info             : geolocalização e ASN de um IP (ip-api.com)
  - wayback_lookup      : histórico de snapshots no Wayback Machine
  - cve_search          : busca CVEs no banco NVD/NIST (sem chave)
  - subdomain_enum      : enumeração passiva via crt.sh (sem chave)
  - url_reputation      : reputação de URL via URLScan.io público
  - whois_rdap          : WHOIS moderno via protocolo RDAP (sem chave)
  - open_ports_common   : verifica portas comuns abertas
  - email_breach_check  : verifica breach via HIBP (requer chave gratuita)
  - tech_stack_detect   : detecta tecnologias de um site
  - security_score      : score consolidado de segurança de um domínio
"""

from __future__ import annotations

import logging
import socket
import ssl
import time
import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx

log = logging.getLogger("tools.cybersec")

# ---------------------------------------------------------------------------
# DNS Lookup via Cloudflare DNS over HTTPS (1.1.1.1) — sem chave
# ---------------------------------------------------------------------------

DNS_TYPES = {
    "A": 1, "AAAA": 28, "MX": 15, "TXT": 16,
    "NS": 2, "CNAME": 5, "SOA": 6, "CAA": 257,
}

def dns_lookup(domain: str, record_type: str = "A") -> str:
    """
    Consulta registros DNS via Cloudflare DoH (DNS over HTTPS).
    record_type: A | AAAA | MX | TXT | NS | CNAME | SOA | CAA
    """
    record_type = record_type.upper()
    if record_type not in DNS_TYPES:
        return f"Tipo de registro inválido. Válidos: {', '.join(DNS_TYPES.keys())}"

    r = httpx.get(
        "https://cloudflare-dns.com/dns-query",
        params={"name": domain, "type": record_type},
        headers={"Accept": "application/dns-json"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()

    status_map = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN"}
    status = status_map.get(data.get("Status", -1), f"Código {data.get('Status')}")

    if data.get("Status") == 3:
        return f"DNS: domínio '{domain}' não encontrado (NXDOMAIN)."

    answers = data.get("Answer", [])
    if not answers:
        return f"Nenhum registro {record_type} encontrado para '{domain}'. Status: {status}"

    lines = [f"# DNS {record_type} – {domain}\nStatus: {status}\n"]
    for ans in answers:
        ttl  = ans.get("TTL", "?")
        data_val = ans.get("data", "?")
        lines.append(f"  {ans.get('name', domain)} — TTL {ttl}s — **{data_val}**")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SSL Certificate Check
# ---------------------------------------------------------------------------

def ssl_check(domain: str, port: int = 443) -> str:
    """
    Verifica o certificado TLS/SSL de um domínio.
    Retorna emissor, validade, SANs e alertas de segurança.
    """
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.create_connection((domain, port), timeout=10),
            server_hostname=domain,
        ) as ssock:
            cert = ssock.getpeercert()
            cipher = ssock.cipher()
            version = ssock.version()
    except ssl.SSLCertVerificationError as e:
        return f"❌ Erro de verificação SSL: {e}"
    except Exception as e:
        return f"❌ Falha na conexão SSL: {e}"

    # Datas
    not_before_str = cert.get("notBefore", "")
    not_after_str  = cert.get("notAfter", "")

    def parse_cert_date(s: str) -> datetime:
        return datetime.strptime(s, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    try:
        expires = parse_cert_date(not_after_str)
        days_left = (expires - now).days
        exp_status = "✅" if days_left > 30 else ("⚠️" if days_left > 7 else "🔴 CRÍTICO")
    except Exception:
        days_left = "?"
        exp_status = "⚠️"

    # SANs
    sans = []
    for san_type, san_val in cert.get("subjectAltName", []):
        if san_type == "DNS":
            sans.append(san_val)

    # Sujeito
    subject = dict(x[0] for x in cert.get("subject", []))
    issuer  = dict(x[0] for x in cert.get("issuer", []))

    # Alertas
    alerts = []
    if days_left != "?" and days_left < 30:
        alerts.append(f"⚠️ Certificado expira em {days_left} dias!")
    if version in ("TLSv1", "TLSv1.1"):
        alerts.append(f"🔴 Protocolo obsoleto: {version}")
    if len(sans) == 0:
        alerts.append("⚠️ Sem Subject Alternative Names")

    output = [
        f"# SSL/TLS – {domain}:{port}\n",
        f"**Sujeito:** {subject.get('commonName', '?')}",
        f"**Emissor:** {issuer.get('organizationName', '?')} ({issuer.get('commonName', '?')})",
        f"**Protocolo:** {version} | **Cipher:** {cipher[0] if cipher else '?'}",
        f"**Válido até:** {not_after_str} ({days_left} dias) {exp_status}",
        f"**SANs ({len(sans)}):** {', '.join(sans[:8])}{'...' if len(sans) > 8 else ''}",
    ]
    if alerts:
        output.append("\n**⚠️ Alertas:**\n" + "\n".join(f"  {a}" for a in alerts))

    return "\n".join(output)


# ---------------------------------------------------------------------------
# HTTP Security Headers Audit
# ---------------------------------------------------------------------------

SECURITY_HEADERS = {
    "strict-transport-security": ("HSTS",          "✅", "🔴 CRÍTICO – vulnerável a downgrade"),
    "content-security-policy":   ("CSP",           "✅", "🔴 CRÍTICO – vulnerável a XSS"),
    "x-frame-options":           ("X-Frame",       "✅", "⚠️ Vulnerável a Clickjacking"),
    "x-content-type-options":    ("X-Content-Type","✅", "⚠️ MIME sniffing habilitado"),
    "referrer-policy":           ("Referrer-Policy","✅","⚠️ Vazamento de URL"),
    "permissions-policy":        ("Permissions",   "✅", "ℹ️ Sem restrição de features"),
    "cache-control":             ("Cache-Control", "✅", "ℹ️ Cache não configurado"),
    "x-xss-protection":          ("X-XSS",         "ℹ️", "ℹ️ Cabeçalho legado"),
}

def http_headers_audit(url: str) -> str:
    """
    Audita cabeçalhos de segurança HTTP de uma URL.
    Compara com OWASP Secure Headers Project.
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        r = httpx.head(url, follow_redirects=True, timeout=15)
    except Exception:
        try:
            r = httpx.get(url, follow_redirects=True, timeout=15)
        except Exception as e:
            return f"❌ Falha ao conectar: {e}"

    headers = {k.lower(): v for k, v in r.headers.items()}
    final_url = str(r.url)

    results = []
    score = 0
    max_score = 0

    for h_key, (label, present_icon, absent_msg) in SECURITY_HEADERS.items():
        max_score += 1
        if h_key in headers:
            results.append(f"  {present_icon} **{label}:** `{headers[h_key][:80]}`")
            score += 1
        else:
            results.append(f"  ❌ **{label}:** {absent_msg}")

    # Cookie flags
    cookie_issues = []
    for h_key, h_val in headers.items():
        if "set-cookie" in h_key:
            if "secure" not in h_val.lower():
                cookie_issues.append("⚠️ Cookie sem flag Secure")
            if "httponly" not in h_val.lower():
                cookie_issues.append("⚠️ Cookie sem flag HttpOnly")
            if "samesite" not in h_val.lower():
                cookie_issues.append("⚠️ Cookie sem SameSite")

    grade_map = [(90, "A+"), (80, "A"), (70, "B"), (55, "C"), (40, "D")]
    pct = int(score / max_score * 100)
    grade = next((g for threshold, g in grade_map if pct >= threshold), "F")

    output = [
        f"# Auditoria de Headers HTTP\n",
        f"**URL:** {final_url}",
        f"**Status:** {r.status_code} | **Score:** {score}/{max_score} ({pct}%) | **Nota:** {grade}\n",
    ] + results

    if cookie_issues:
        output.append("\n**Cookies:**\n" + "\n".join(f"  {i}" for i in cookie_issues))

    # Informações que não deveriam vazar
    leak_headers = ["server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version"]
    leaks = [(h, headers[h]) for h in leak_headers if h in headers]
    if leaks:
        output.append("\n**⚠️ Informações expostas:**")
        for h, v in leaks:
            output.append(f"  🔍 `{h}: {v}`")

    return "\n".join(output)


# ---------------------------------------------------------------------------
# IP Info (ip-api.com — 45 req/min gratuito, sem chave)
# ---------------------------------------------------------------------------

def ip_info(ip_or_domain: str) -> str:
    """
    Geolocalização, ASN, ISP e informações de rede de um IP ou domínio.
    Usa ip-api.com (45 req/min gratuito, sem chave de API).
    """
    fields = "status,message,continent,country,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy,hosting,query"
    r = httpx.get(
        f"http://ip-api.com/json/{ip_or_domain}",
        params={"fields": fields},
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()

    if d.get("status") != "success":
        return f"Erro: {d.get('message', 'IP/domínio inválido ou privado.')}"

    flags = []
    if d.get("proxy"):   flags.append("🔷 Proxy/VPN detectado")
    if d.get("hosting"): flags.append("🖥️ Hosting/Datacenter")

    return (
        f"# IP Info – {d['query']}\n\n"
        f"**País:** {d.get('country', '?')} ({d.get('continent', '?')})\n"
        f"**Região/Cidade:** {d.get('regionName', '?')} / {d.get('city', '?')} {d.get('zip', '')}\n"
        f"**Coordenadas:** {d.get('lat', '?')}, {d.get('lon', '?')}\n"
        f"**Timezone:** {d.get('timezone', '?')}\n"
        f"**ISP:** {d.get('isp', '?')}\n"
        f"**Org:** {d.get('org', '?')}\n"
        f"**ASN:** {d.get('as', '?')}\n"
        + ("\n".join(flags) if flags else "✅ Sem proxy/VPN detectado")
    )


# ---------------------------------------------------------------------------
# Wayback Machine
# ---------------------------------------------------------------------------

def wayback_lookup(url: str, limit: int = 5) -> str:
    """
    Verifica snapshots disponíveis no Wayback Machine para uma URL.
    Útil para OSINT, verificar versões antigas de sites.
    """
    # CDX API — sem chave
    r = httpx.get(
        "http://web.archive.org/cdx/search/cdx",
        params={
            "url": url,
            "output": "json",
            "limit": limit,
            "fl": "timestamp,statuscode,mimetype,length",
            "filter": "statuscode:200",
            "from": "20150101",
        },
        timeout=20,
    )
    r.raise_for_status()
    rows = r.json()

    if len(rows) <= 1:
        return f"Nenhum snapshot encontrado no Wayback Machine para: {url}"

    header, *records = rows
    lines = [f"# Wayback Machine – {url}\n"]
    for rec in records:
        ts = rec[0]
        size_kb = int(rec[3]) // 1024 if rec[3].isdigit() else "?"
        archive_url = f"https://web.archive.org/web/{ts}/{url}"
        formatted = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}"
        lines.append(f"  📸 [{formatted}]({archive_url}) — {size_kb} KB")

    # Disponibilidade atual
    avail_r = httpx.get(
        f"https://archive.org/wayback/available?url={url}",
        timeout=10,
    )
    if avail_r.status_code == 200:
        closest = avail_r.json().get("archived_snapshots", {}).get("closest", {})
        if closest.get("available"):
            lines.append(f"\n**Snapshot mais recente disponível:**\n  🔗 {closest['url']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CVE Search via NVD (NIST) — sem chave para consultas básicas
# ---------------------------------------------------------------------------

def cve_search(keyword: str = "", cve_id: str = "", limit: int = 5) -> str:
    """
    Busca CVEs no banco NVD/NIST.
    Use keyword para buscar por produto/tecnologia, ou cve_id para busca direta.
    Exemplos: keyword="wordpress", cve_id="CVE-2024-1234"
    """
    params: dict[str, Any] = {"resultsPerPage": limit}

    if cve_id:
        params["cveId"] = cve_id.upper()
    elif keyword:
        params["keywordSearch"] = keyword
    else:
        return "Forneça keyword ou cve_id."

    r = httpx.get(
        "https://services.nvd.nist.gov/rest/json/cves/2.0",
        params=params,
        timeout=30,
        headers={"User-Agent": "agentes-24h/1.0"},
    )
    r.raise_for_status()
    data = r.json()

    vulns = data.get("vulnerabilities", [])
    if not vulns:
        return f"Nenhum CVE encontrado para '{keyword or cve_id}'."

    total = data.get("totalResults", len(vulns))
    lines = [f"# CVE Search: '{keyword or cve_id}' — {total} resultados\n"]

    for item in vulns:
        cve  = item["cve"]
        cid  = cve["id"]
        desc = next(
            (d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"),
            "Sem descrição."
        )

        # CVSS score
        metrics = cve.get("metrics", {})
        score_str = "N/A"
        severity_str = ""
        for metric_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metric_key in metrics:
                m = metrics[metric_key][0].get("cvssData", {})
                score_str = str(m.get("baseScore", "?"))
                severity_str = m.get("baseSeverity", "")
                break

        severity_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity_str, "⚪")
        published = cve.get("published", "")[:10]

        lines.append(
            f"**{cid}** {severity_icon} CVSS {score_str} ({severity_str})\n"
            f"  📅 {published}\n"
            f"  {desc[:300]}{'...' if len(desc) > 300 else ''}\n"
            f"  🔗 https://nvd.nist.gov/vuln/detail/{cid}"
        )

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Subdomain Enumeration via crt.sh (Certificate Transparency)
# ---------------------------------------------------------------------------

def subdomain_enum(domain: str, limit: int = 30) -> str:
    """
    Enumeração passiva de subdomínios via crt.sh (Certificate Transparency Logs).
    Não envia nenhum tráfego para o alvo — 100% passivo.
    """
    r = httpx.get(
        "https://crt.sh/",
        params={"q": f"%.{domain}", "output": "json"},
        timeout=30,
        headers={"User-Agent": "agentes-24h/1.0"},
    )
    r.raise_for_status()
    certs = r.json()

    # Extrai subdomínios únicos
    subs: set[str] = set()
    for cert in certs:
        for name in cert.get("name_value", "").split("\n"):
            name = name.strip().lower().lstrip("*.")
            if name.endswith(f".{domain}") or name == domain:
                subs.add(name)

    if not subs:
        return f"Nenhum subdomínio encontrado para '{domain}' via crt.sh."

    sorted_subs = sorted(subs)[:limit]
    lines = [
        f"# Subdomínios – {domain}\n",
        f"Encontrados via Certificate Transparency (passivo, {len(subs)} total):\n",
    ]
    for sub in sorted_subs:
        lines.append(f"  • {sub}")

    if len(subs) > limit:
        lines.append(f"\n  ... e mais {len(subs) - limit} subdomínios.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WHOIS via RDAP (protocolo moderno, sem chave)
# ---------------------------------------------------------------------------

def whois_rdap(domain: str) -> str:
    """
    Consulta WHOIS moderno via RDAP (Registration Data Access Protocol).
    Sem chave de API, padrão IETF RFC 7483.
    """
    # Tenta o bootstrap RDAP
    try:
        r = httpx.get(
            f"https://rdap.org/domain/{domain}",
            timeout=20,
            follow_redirects=True,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Erro RDAP: {e}"

    # Extrai campos relevantes
    def _get_event(events: list, action: str) -> str:
        for ev in events:
            if ev.get("eventAction") == action:
                return ev.get("eventDate", "")[:10]
        return "?"

    events = data.get("events", [])
    created  = _get_event(events, "registration")
    updated  = _get_event(events, "last changed")
    expires  = _get_event(events, "expiration")

    status = ", ".join(data.get("status", [])) or "?"
    nameservers = [ns.get("ldhName", "") for ns in data.get("nameservers", [])]

    # Entidades (registrant, registrar)
    registrar = "?"
    for entity in data.get("entities", []):
        roles = entity.get("roles", [])
        if "registrar" in roles:
            registrar = entity.get("handle") or entity.get("fn") or "?"

    # Verificação de expiração
    exp_warning = ""
    if expires != "?":
        try:
            exp_date = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days = (exp_date - datetime.now(timezone.utc)).days
            if days < 30:
                exp_warning = f" 🔴 EXPIRA EM {days} DIAS!"
        except Exception:
            pass

    return (
        f"# WHOIS/RDAP – {domain}\n\n"
        f"**Registrado em:** {created}\n"
        f"**Atualizado em:** {updated}\n"
        f"**Expira em:**     {expires}{exp_warning}\n"
        f"**Status:** {status}\n"
        f"**Registrar:** {registrar}\n"
        f"**Nameservers:** {', '.join(nameservers) or '?'}\n"
        f"**Handle:** {data.get('handle', '?')}\n"
        f"🔗 https://rdap.org/domain/{domain}"
    )


# ---------------------------------------------------------------------------
# Open Ports (portas comuns via socket — sem ferramentas externas)
# ---------------------------------------------------------------------------

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
    443: "HTTPS", 445: "SMB", 587: "SMTP/TLS",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    27017: "MongoDB",
}

def open_ports_common(host: str, timeout: float = 1.5) -> str:
    """
    Verifica quais portas comuns estão abertas em um host.
    ⚠️ Use SOMENTE em hosts que você tem permissão para escanear.
    """
    lines = [f"# Port Scan – {host}\n⚠️ Use apenas em hosts autorizados.\n"]
    open_list  = []
    closed_list = []

    for port, service in COMMON_PORTS.items():
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            open_list.append(f"  🟢 **{port}/{service}** — ABERTA")
        except (ConnectionRefusedError, OSError):
            closed_list.append(f"  🔴 {port}/{service} — fechada/filtrada")
        except Exception:
            closed_list.append(f"  ⚪ {port}/{service} — timeout")

    lines += open_list or ["  Nenhuma porta aberta detectada."]
    lines.append(f"\n*{len(closed_list)} portas fechadas/filtradas*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tech Stack Detect
# ---------------------------------------------------------------------------

def tech_stack_detect(url: str) -> str:
    """
    Detecta tecnologias usadas em um site analisando headers, cookies e HTML.
    Sem API externa — análise local das respostas HTTP.
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        r = httpx.get(url, follow_redirects=True, timeout=15,
                       headers={"User-Agent": "Mozilla/5.0 (compatible; agentes-24h/1.0)"})
    except Exception as e:
        return f"❌ Erro: {e}"

    headers = {k.lower(): v.lower() for k, v in r.headers.items()}
    body = r.text[:50000].lower()
    detected: dict[str, list[str]] = {}

    def add(category: str, tech: str):
        detected.setdefault(category, [])
        if tech not in detected[category]:
            detected[category].append(tech)

    # Servidor
    server = headers.get("server", "")
    if "nginx"   in server: add("Servidor", "Nginx")
    if "apache"  in server: add("Servidor", "Apache")
    if "caddy"   in server: add("Servidor", "Caddy")
    if "iis"     in server: add("Servidor", "IIS (Microsoft)")
    if "cloudflare" in headers.get("cf-ray", ""): add("CDN", "Cloudflare")

    # CMS
    if "wp-content" in body or "wp-json" in body: add("CMS", "WordPress")
    if "drupal"     in body:                       add("CMS", "Drupal")
    if "joomla"     in body:                       add("CMS", "Joomla")
    if "shopify"    in body or "myshopify" in body: add("CMS", "Shopify")
    if "squarespace" in body:                      add("CMS", "Squarespace")
    if "ghost"       in body:                      add("CMS", "Ghost")
    if "wix.com"     in body:                      add("CMS", "Wix")

    # Frameworks JS
    if "react"        in body or "__next" in body: add("Frontend", "React/Next.js")
    if "vue"          in body or "nuxt"   in body: add("Frontend", "Vue/Nuxt")
    if "angular"      in body:                     add("Frontend", "Angular")
    if "svelte"       in body:                     add("Frontend", "Svelte")
    if "jquery"       in body:                     add("Frontend", "jQuery")
    if "bootstrap"    in body:                     add("Frontend", "Bootstrap")
    if "tailwind"     in body:                     add("Frontend", "Tailwind CSS")

    # Analytics
    if "google-analytics" in body or "gtag" in body: add("Analytics", "Google Analytics")
    if "gtm.js"        in body:                       add("Analytics", "Google Tag Manager")
    if "plausible"     in body:                       add("Analytics", "Plausible")
    if "hotjar"        in body:                       add("Analytics", "Hotjar")

    # Backend (dicas nos headers)
    powered = headers.get("x-powered-by", "")
    if "php"     in powered: add("Backend", f"PHP ({powered})")
    if "asp.net" in powered: add("Backend", "ASP.NET")
    if "express" in powered: add("Backend", "Node.js/Express")

    # Segurança
    if headers.get("strict-transport-security"): add("Segurança", "HSTS ✅")
    if headers.get("content-security-policy"):   add("Segurança", "CSP ✅")
    if "cloudflare" in body:                     add("Segurança", "Cloudflare WAF")

    if not detected:
        return f"Nenhuma tecnologia detectada em {url} (site pode usar técnicas de ofuscação)."

    lines = [f"# Tech Stack – {url}\n"]
    for category, techs in detected.items():
        lines.append(f"**{category}:** {', '.join(techs)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Security Score Consolidado
# ---------------------------------------------------------------------------

def security_score(domain: str) -> str:
    """
    Score de segurança consolidado de um domínio.
    Agrega: SSL, headers HTTP, DNS, WHOIS e subdomínios.
    """
    lines = [f"# 🛡️ Security Score – {domain}\n"]
    total = 0
    max_pts = 0

    def check(name: str, fn, *args, points: int = 10):
        nonlocal total, max_pts
        max_pts += points
        try:
            result = fn(*args)
            lines.append(f"\n## {name}\n{result}")
            # Heurística de pontuação baseada em ausência de ícones de erro
            score = points - result.count("🔴") * 3 - result.count("❌") * 2 - result.count("⚠️") * 1
            total += max(0, score)
        except Exception as e:
            lines.append(f"\n## {name}\n❌ Erro: {e}")

    check("🔒 SSL/TLS",          ssl_check,          domain,        points=25)
    check("📋 Headers HTTP",     http_headers_audit, f"https://{domain}", points=30)
    check("🌐 DNS",              dns_lookup,         domain, "A",   points=10)
    check("📅 WHOIS/RDAP",      whois_rdap,         domain,        points=10)
    check("🔍 Subdomínios",     subdomain_enum,     domain, 10,    points=10)

    pct = int(total / max_pts * 100) if max_pts else 0
    grade = next((g for t, g in [(85,"A"),(70,"B"),(55,"C"),(40,"D")] if pct >= t), "F")
    lines.insert(1, f"**Score: {total}/{max_pts} ({pct}%) — Nota: {grade}**\n")

    return "\n".join(lines)
