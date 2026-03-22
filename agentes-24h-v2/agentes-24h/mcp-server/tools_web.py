"""
tools_web.py
============
Ferramentas WEB & CRIAÇÃO DE SITES — todas gratuitas, sem chave de API.

Ferramentas:
  - screenshot_url        : screenshot de site via microlink.io (gratuito)
  - html_validate         : valida HTML via W3C Validator API
  - pagespeed_check       : auditoria PageSpeed via Google (sem chave p/ básico)
  - url_shorten           : encurta URL via is.gd (gratuito, sem chave)
  - qr_generate           : gera QR code como URL de imagem (goqr.me, gratuito)
  - deploy_github_pages   : publica site estático no GitHub Pages via API
  - generate_landing_page : gera HTML completo de landing page via IA local
  - generate_robots_txt   : gera robots.txt otimizado
  - generate_sitemap      : gera sitemap.xml a partir de lista de URLs
  - meta_tags_generator   : gera meta tags SEO + Open Graph + Twitter Card
  - color_palette         : gera paleta de cores para um nicho/marca
  - favicon_check         : verifica favicon e PWA icons de um site
  - broken_links_check    : verifica links quebrados em uma página
  - accessibility_hints   : dicas de acessibilidade baseadas no HTML
"""

from __future__ import annotations

import html as html_module
import json
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

log = logging.getLogger("tools.web")


# ---------------------------------------------------------------------------
# Screenshot via Microlink.io (gratuito, sem chave, 100 req/dia)
# ---------------------------------------------------------------------------

def screenshot_url(url: str, width: int = 1280, height: int = 800) -> str:
    """
    Captura screenshot de uma URL via Microlink.io (gratuito).
    Retorna a URL da imagem gerada.
    """
    r = httpx.get(
        "https://api.microlink.io/",
        params={
            "url": url,
            "screenshot": "true",
            "meta": "false",
            "embed": "screenshot.url",
            "viewport.width": width,
            "viewport.height": height,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if data.get("status") != "success":
        return f"Erro ao gerar screenshot: {data.get('message', 'desconhecido')}"

    img_url = data.get("data", {}).get("screenshot", {}).get("url", "")
    meta = data.get("data", {})

    return (
        f"# Screenshot – {url}\n\n"
        f"**Imagem:** {img_url}\n"
        f"**Título:** {meta.get('title', '?')}\n"
        f"**Descrição:** {meta.get('description', '?')}\n\n"
        f"*Visualize a imagem acessando o link acima.*"
    )


# ---------------------------------------------------------------------------
# HTML Validator via W3C
# ---------------------------------------------------------------------------

def html_validate(url_or_html: str) -> str:
    """
    Valida HTML via W3C Validator API (gratuita).
    Aceita uma URL ou código HTML diretamente.
    """
    is_url = url_or_html.strip().startswith("http")

    try:
        if is_url:
            r = httpx.get(
                "https://validator.w3.org/nu/",
                params={"doc": url_or_html, "out": "json"},
                headers={"User-Agent": "agentes-24h/1.0 W3C Validator"},
                timeout=30,
            )
        else:
            r = httpx.post(
                "https://validator.w3.org/nu/?out=json",
                content=url_or_html.encode("utf-8"),
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "User-Agent": "agentes-24h/1.0 W3C Validator",
                },
                timeout=30,
            )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Erro ao conectar ao W3C Validator: {e}"

    messages = data.get("messages", [])
    errors   = [m for m in messages if m.get("type") == "error"]
    warnings = [m for m in messages if m.get("type") == "info" and m.get("subType") == "warning"]

    if not messages:
        return "✅ HTML válido! Nenhum erro ou aviso encontrado."

    lines = [
        f"# Validação HTML\n",
        f"**Erros:** {len(errors)} | **Avisos:** {len(warnings)}\n",
    ]

    for e in errors[:10]:
        line = e.get("lastLine", "?")
        lines.append(f"  🔴 Linha {line}: {e.get('message', '')}")

    for w in warnings[:5]:
        line = w.get("lastLine", "?")
        lines.append(f"  ⚠️ Linha {line}: {w.get('message', '')}")

    if len(errors) > 10:
        lines.append(f"  ... e mais {len(errors) - 10} erros.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PageSpeed / Core Web Vitals (Google API, sem chave p/ uso básico)
# ---------------------------------------------------------------------------

def pagespeed_check(url: str, strategy: str = "mobile") -> str:
    """
    Auditoria de performance via Google PageSpeed Insights.
    strategy: mobile | desktop
    Sem chave de API para uso básico (limite generoso).
    """
    strategy = strategy if strategy in ("mobile", "desktop") else "mobile"

    r = httpx.get(
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        params={"url": url, "strategy": strategy},
        timeout=60,
    )
    if r.status_code == 429:
        return "Limite do PageSpeed API atingido. Tente novamente em alguns minutos."
    r.raise_for_status()
    data = r.json()

    cats = data.get("lighthouseResult", {}).get("categories", {})
    audits = data.get("lighthouseResult", {}).get("audits", {})

    def score_icon(s: float) -> str:
        if s >= 0.9: return "🟢"
        if s >= 0.5: return "🟡"
        return "🔴"

    lines = [f"# PageSpeed – {url} ({strategy.title()})\n"]

    # Scores principais
    for key, label in [("performance","Performance"), ("accessibility","Acessibilidade"),
                        ("best-practices","Boas Práticas"), ("seo","SEO")]:
        cat = cats.get(key, {})
        s = cat.get("score", 0) or 0
        pct = int(s * 100)
        lines.append(f"  {score_icon(s)} **{label}:** {pct}/100")

    # Core Web Vitals
    cwv = {
        "first-contentful-paint": "FCP",
        "largest-contentful-paint": "LCP",
        "total-blocking-time": "TBT",
        "cumulative-layout-shift": "CLS",
        "speed-index": "Speed Index",
        "interactive": "TTI",
    }
    lines.append("\n**Core Web Vitals:**")
    for audit_id, label in cwv.items():
        audit = audits.get(audit_id, {})
        display = audit.get("displayValue", "?")
        score_val = audit.get("score") or 0
        lines.append(f"  {score_icon(score_val)} {label}: {display}")

    # Oportunidades de melhoria
    opportunities = [
        a for a in audits.values()
        if a.get("details", {}).get("type") == "opportunity"
        and (a.get("score") or 1) < 0.9
    ]
    if opportunities:
        lines.append("\n**⚡ Oportunidades de melhoria:**")
        for opp in sorted(opportunities, key=lambda x: x.get("score", 1))[:5]:
            lines.append(f"  • {opp.get('title', '?')}: {opp.get('displayValue', '')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# URL Shortener (is.gd — gratuito, sem chave)
# ---------------------------------------------------------------------------

def url_shorten(url: str, custom_slug: str = "") -> str:
    """
    Encurta uma URL via is.gd (gratuito, sem chave de API).
    """
    params: dict[str, str] = {"format": "simple", "url": url}
    if custom_slug:
        params["shorturl"] = custom_slug

    r = httpx.get(
        "https://is.gd/create.php",
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    short = r.text.strip()

    if short.startswith("Error:"):
        return f"Erro: {short}"

    return f"✅ URL encurtada: **{short}**\n(Original: {url})"


# ---------------------------------------------------------------------------
# QR Code Generator (goqr.me — gratuito, sem chave)
# ---------------------------------------------------------------------------

def qr_generate(
    content: str,
    size: int = 200,
    color: str = "000000",
    bg_color: str = "ffffff",
    format: str = "png",
) -> str:
    """
    Gera um QR Code via goqr.me (gratuito, sem chave).
    Retorna a URL da imagem do QR code.

    size: tamanho em pixels (50-1000)
    color: cor de frente em hex (sem #)
    bg_color: cor de fundo em hex (sem #)
    format: png | svg | eps | pdf
    """
    size = max(50, min(1000, size))
    encoded = urllib.parse.quote(content)
    qr_url = (
        f"https://api.qrserver.com/v1/create-qr-code/"
        f"?size={size}x{size}&data={encoded}"
        f"&color={color.lstrip('#')}&bgcolor={bg_color.lstrip('#')}"
        f"&format={format}"
    )
    return (
        f"# QR Code Gerado\n\n"
        f"**Conteúdo:** {content[:80]}\n"
        f"**URL da imagem:** {qr_url}\n\n"
        f"*Acesse o link para baixar/visualizar o QR code.*"
    )


# ---------------------------------------------------------------------------
# Deploy GitHub Pages
# ---------------------------------------------------------------------------

def deploy_github_pages(
    repo: str,
    html_content: str,
    github_token: str,
    commit_message: str = "Deploy automático via agentes-24h",
    branch: str = "gh-pages",
) -> str:
    """
    Publica um arquivo index.html no GitHub Pages via GitHub API.

    Args:
        repo: formato "usuario/repositorio"
        html_content: conteúdo HTML completo do site
        github_token: Personal Access Token (escopo repo)
        branch: branch de deploy (padrão: gh-pages)
    """
    import base64

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_url = f"https://api.github.com/repos/{repo}"

    # Verifica se já existe o arquivo
    get_r = httpx.get(
        f"{base_url}/contents/index.html",
        params={"ref": branch},
        headers=headers,
        timeout=15,
    )
    sha = get_r.json().get("sha") if get_r.status_code == 200 else None

    # Encode conteúdo
    encoded = base64.b64encode(html_content.encode("utf-8")).decode()

    payload: dict[str, Any] = {
        "message": commit_message,
        "content": encoded,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_r = httpx.put(
        f"{base_url}/contents/index.html",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if put_r.status_code in (200, 201):
        user = repo.split("/")[0]
        repo_name = repo.split("/")[1]
        pages_url = f"https://{user}.github.io/{repo_name}/"
        return (
            f"✅ Deploy realizado com sucesso!\n\n"
            f"**Repositório:** https://github.com/{repo}/tree/{branch}\n"
            f"**Site:** {pages_url}\n"
            f"*(O GitHub Pages pode levar 1-2 minutos para refletir as mudanças)*"
        )
    else:
        return f"❌ Erro no deploy: {put_r.status_code} – {put_r.text[:500]}"


# ---------------------------------------------------------------------------
# Landing Page Generator (via IA local)
# ---------------------------------------------------------------------------

def generate_landing_page(
    product: str,
    audience: str,
    color_primary: str = "#6366f1",
    sections: str = "hero,features,testimonials,cta",
) -> str:
    """
    Gera HTML completo de uma landing page via IA local.
    Retorna o código HTML pronto para deploy.
    """
    try:
        from providers import ProviderOrchestrator
        from key_client import KeyClient
        orch = ProviderOrchestrator(KeyClient())
    except ImportError:
        return "Providers não disponíveis neste contexto."

    system = (
        "Você é um desenvolvedor frontend especialista em landing pages de alta conversão. "
        "Gere HTML completo, moderno e responsivo com Tailwind CSS via CDN. "
        "Retorne APENAS o código HTML, sem markdown, sem explicações."
    )

    prompt = (
        f"Crie uma landing page completa em HTML para:\n"
        f"Produto/Serviço: {product}\n"
        f"Público-alvo: {audience}\n"
        f"Cor primária: {color_primary}\n"
        f"Seções obrigatórias: {sections}\n\n"
        f"Requisitos:\n"
        f"- Tailwind CSS via CDN\n"
        f"- 100% responsivo (mobile-first)\n"
        f"- CTA claro e persuasivo\n"
        f"- Meta tags SEO completas\n"
        f"- Schema.org markup\n"
        f"- Sem imagens externas (use gradientes e SVG inline)\n"
        f"- Português brasileiro\n"
        f"Retorne APENAS o HTML completo."
    )

    try:
        response, provider = orch.complete(prompt, system=system, max_tokens=4096)
        # Limpar possível markdown
        html_clean = re.sub(r"```html\n?|```\n?", "", response).strip()
        return html_clean
    except Exception as e:
        return f"Erro ao gerar landing page: {e}"


# ---------------------------------------------------------------------------
# Meta Tags Generator
# ---------------------------------------------------------------------------

def meta_tags_generator(
    title: str,
    description: str,
    url: str,
    image_url: str = "",
    site_name: str = "",
    author: str = "",
    keywords: str = "",
    locale: str = "pt_BR",
) -> str:
    """
    Gera meta tags completas: SEO, Open Graph e Twitter Card.
    """
    og_image = image_url or "https://via.placeholder.com/1200x630"
    site = site_name or title

    tags = f"""<!-- SEO Meta Tags -->
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_module.escape(title)}</title>
<meta name="description" content="{html_module.escape(description[:160])}">
{"<meta name='keywords' content='" + html_module.escape(keywords) + "'>" if keywords else ""}
{"<meta name='author' content='" + html_module.escape(author) + "'>" if author else ""}
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{html_module.escape(title)}">
<meta property="og:description" content="{html_module.escape(description[:200])}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:site_name" content="{html_module.escape(site)}">
<meta property="og:locale" content="{locale}">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:url" content="{url}">
<meta name="twitter:title" content="{html_module.escape(title)}">
<meta name="twitter:description" content="{html_module.escape(description[:200])}">
<meta name="twitter:image" content="{og_image}">

<!-- Schema.org -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "{title}",
  "description": "{description[:200]}",
  "url": "{url}",
  "inLanguage": "pt-BR"
  {(',"author": {"@type": "Person", "name": "' + author + '"}') if author else ""}
}}
</script>"""

    char_title = len(title)
    char_desc  = len(description)
    warnings = []
    if char_title > 60:   warnings.append(f"⚠️ Título muito longo ({char_title}/60 chars)")
    if char_title < 30:   warnings.append(f"⚠️ Título muito curto ({char_title}/30 chars)")
    if char_desc  > 160:  warnings.append(f"⚠️ Descrição muito longa ({char_desc}/160 chars)")
    if char_desc  < 70:   warnings.append(f"⚠️ Descrição muito curta ({char_desc}/70 chars)")
    if not image_url:     warnings.append("⚠️ Sem imagem OG – use uma imagem 1200x630px real")

    result = f"# Meta Tags Geradas\n\n```html\n{tags}\n```"
    if warnings:
        result += "\n\n**Alertas:**\n" + "\n".join(f"  {w}" for w in warnings)
    return result


# ---------------------------------------------------------------------------
# Robots.txt Generator
# ---------------------------------------------------------------------------

def generate_robots_txt(
    site_url: str,
    allow_all: bool = True,
    disallow_paths: list[str] | None = None,
    custom_rules: dict[str, list[str]] | None = None,
) -> str:
    """
    Gera um robots.txt otimizado para SEO.

    Args:
        site_url: URL base do site (para o Sitemap)
        allow_all: se True, permite tudo para todos os bots
        disallow_paths: caminhos a bloquear (ex: ["/admin", "/api"])
        custom_rules: regras por user-agent {"Googlebot": ["/private"]}
    """
    disallow_paths = disallow_paths or []
    custom_rules   = custom_rules or {}

    lines = ["# robots.txt gerado por agentes-24h", f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", ""]

    # Regra geral
    lines.append("User-agent: *")
    if allow_all and not disallow_paths:
        lines.append("Allow: /")
    else:
        lines.append("Allow: /")
        for path in disallow_paths:
            lines.append(f"Disallow: {path}")

    lines.append("")

    # Bloqueio de bots de AI scraping (opcional, mas recomendado)
    ai_bots = ["GPTBot", "ChatGPT-User", "CCBot", "anthropic-ai", "Claude-Web", "Omgilibot"]
    lines.append("# Bots de AI (opcional — remova se quiser indexação)")
    for bot in ai_bots:
        lines.append(f"User-agent: {bot}")
        lines.append("Disallow: /")
        lines.append("")

    # Regras customizadas
    for user_agent, paths in custom_rules.items():
        lines.append(f"User-agent: {user_agent}")
        for path in paths:
            lines.append(f"Disallow: {path}")
        lines.append("")

    # Sitemap
    base = site_url.rstrip("/")
    lines.append(f"Sitemap: {base}/sitemap.xml")

    content = "\n".join(lines)
    return f"# robots.txt\n\n```\n{content}\n```\n\n*Salve como `robots.txt` na raiz do seu site.*"


# ---------------------------------------------------------------------------
# Sitemap Generator
# ---------------------------------------------------------------------------

def generate_sitemap(
    urls: list[str],
    base_url: str = "",
    changefreq: str = "weekly",
    priority_home: float = 1.0,
) -> str:
    """
    Gera um sitemap.xml a partir de uma lista de URLs.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    freq_valid = {"always", "hourly", "daily", "weekly", "monthly", "yearly", "never"}
    if changefreq not in freq_valid:
        changefreq = "weekly"

    entries = []
    for i, url in enumerate(urls):
        full_url = url if url.startswith("http") else f"{base_url.rstrip('/')}/{url.lstrip('/')}"
        priority = priority_home if i == 0 else round(priority_home * 0.8, 1)
        entries.append(
            f"""  <url>
    <loc>{html_module.escape(full_url)}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>"""
        )

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(entries)}
</urlset>"""

    return (
        f"# sitemap.xml ({len(urls)} URLs)\n\n"
        f"```xml\n{sitemap}\n```\n\n"
        f"*Salve como `sitemap.xml` na raiz do site e adicione ao Google Search Console.*"
    )


# ---------------------------------------------------------------------------
# Broken Links Checker
# ---------------------------------------------------------------------------

def broken_links_check(url: str, max_links: int = 30) -> str:
    """
    Verifica links quebrados em uma página.
    """
    try:
        r = httpx.get(url, follow_redirects=True, timeout=20,
                       headers={"User-Agent": "agentes-24h/1.0 LinkChecker"})
        r.raise_for_status()
        html_content = r.text
        base_url = str(r.url)
    except Exception as e:
        return f"❌ Erro ao carregar a página: {e}"

    # Extrai links
    raw_links = re.findall(r'href=["\']([^"\'#\s]+)["\']', html_content)
    links: list[str] = []
    for link in raw_links:
        if link.startswith("http"):
            links.append(link)
        elif link.startswith("/"):
            from urllib.parse import urljoin
            links.append(urljoin(base_url, link))

    links = list(dict.fromkeys(links))[:max_links]  # dedup + limit

    ok_list, broken_list, redirect_list = [], [], []

    for link in links:
        try:
            lr = httpx.head(link, follow_redirects=False, timeout=8,
                            headers={"User-Agent": "agentes-24h/1.0"})
            if lr.status_code in (301, 302, 307, 308):
                redirect_list.append(f"  🔀 {lr.status_code} → {lr.headers.get('location', '?')[:60]}\n     {link}")
            elif lr.status_code >= 400:
                broken_list.append(f"  🔴 {lr.status_code} — {link}")
            else:
                ok_list.append(f"  ✅ {lr.status_code} — {link}")
        except Exception:
            broken_list.append(f"  ❌ TIMEOUT/ERRO — {link}")

    lines = [
        f"# Links – {url}\n",
        f"✅ OK: {len(ok_list)} | 🔀 Redirects: {len(redirect_list)} | 🔴 Quebrados: {len(broken_list)}\n",
    ]
    if broken_list:
        lines.append("## Links Quebrados:")
        lines += broken_list
    if redirect_list:
        lines.append("\n## Redirects:")
        lines += redirect_list

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Favicon & PWA Icons Check
# ---------------------------------------------------------------------------

def favicon_check(url: str) -> str:
    """
    Verifica se um site tem favicon e ícones PWA configurados corretamente.
    """
    if not url.startswith("http"):
        url = "https://" + url

    from urllib.parse import urljoin

    try:
        r = httpx.get(url, follow_redirects=True, timeout=15)
        html_content = r.text
        base = str(r.url)
    except Exception as e:
        return f"❌ Erro: {e}"

    checks = {
        "favicon.ico (raiz)":  urljoin(base, "/favicon.ico"),
        "apple-touch-icon":    "",
        "manifest.json":       "",
        "icon 192px":          "",
        "icon 512px":          "",
    }

    # Extrai do HTML
    for m in re.finditer(r'<link[^>]+rel=["\']([^"\']+)["\'][^>]+href=["\']([^"\']+)["\']', html_content):
        rel, href = m.group(1).lower(), m.group(2)
        full = urljoin(base, href)
        if "apple-touch-icon" in rel:
            checks["apple-touch-icon"] = full
        if "manifest" in rel or href.endswith(".webmanifest"):
            checks["manifest.json"] = full

    # Verifica manifest para ícones PWA
    if checks["manifest.json"]:
        try:
            mf = httpx.get(checks["manifest.json"], timeout=10).json()
            for icon in mf.get("icons", []):
                if "192" in icon.get("sizes", ""):
                    checks["icon 192px"] = urljoin(base, icon["src"])
                if "512" in icon.get("sizes", ""):
                    checks["icon 512px"] = urljoin(base, icon["src"])
        except Exception:
            pass

    lines = [f"# Favicon & PWA Icons – {url}\n"]
    score = 0
    for label, check_url in checks.items():
        if not check_url:
            lines.append(f"  ⚠️ **{label}:** não encontrado no HTML")
            continue
        try:
            cr = httpx.head(check_url, timeout=8, follow_redirects=True)
            if cr.status_code == 200:
                lines.append(f"  ✅ **{label}:** {check_url}")
                score += 1
            else:
                lines.append(f"  🔴 **{label}:** {cr.status_code} — {check_url}")
        except Exception:
            lines.append(f"  ❌ **{label}:** erro ao verificar")

    lines.append(f"\n**Score:** {score}/{len(checks)}")
    if score < 3:
        lines.append("⚠️ Configure seus ícones para melhor experiência PWA e compartilhamento em redes sociais.")

    return "\n".join(lines)
