"""
tools_content.py
================
Ferramentas de CONTEÚDO & COPY — todas gratuitas, sem chave de API.

Ferramentas:
  - hackernews_top        : top stories do Hacker News agora
  - wikipedia_search      : busca + extrai artigo da Wikipedia
  - rss_fetch             : lê qualquer feed RSS/Atom
  - seo_analyze           : análise local de SEO e legibilidade
  - trending_github       : repositórios em alta no GitHub
  - reddit_top            : posts em alta de um subreddit (JSON API)
  - dictionary_lookup     : definição + sinônimos (Free Dictionary API)
  - generate_copy         : gera copy (headline, CTA, body) via IA local
  - extract_keywords      : extrai palavras-chave de um texto
  - lorem_ipsum           : gera placeholder text via API gratuita
"""

from __future__ import annotations

import html
import logging
import math
import re
from typing import Any

import httpx

log = logging.getLogger("tools.content")

# ---------------------------------------------------------------------------
# Hacker News
# ---------------------------------------------------------------------------

def hackernews_top(limit: int = 10, story_type: str = "top") -> str:
    """
    Retorna os top stories do Hacker News.
    story_type: top | new | best | ask | show
    """
    valid = {"top", "new", "best", "ask", "show"}
    if story_type not in valid:
        story_type = "top"

    ids_r = httpx.get(
        f"https://hacker-news.firebaseio.com/v0/{story_type}stories.json",
        timeout=15,
    )
    ids_r.raise_for_status()
    ids = ids_r.json()[: min(limit, 30)]

    items = []
    for item_id in ids:
        try:
            r = httpx.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=10,
            )
            item = r.json()
            score = item.get("score", 0)
            comments = item.get("descendants", 0)
            url = item.get("url", f"https://news.ycombinator.com/item?id={item_id}")
            items.append(
                f"**{item.get('title', 'sem título')}**\n"
                f"  ▲ {score} pontos | 💬 {comments} comentários\n"
                f"  🔗 {url}"
            )
        except Exception:
            pass

    return f"# Hacker News – {story_type.title()} Stories\n\n" + "\n\n".join(items)


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------

def wikipedia_search(query: str, lang: str = "pt", sentences: int = 10) -> str:
    """
    Busca e retorna resumo de artigo da Wikipedia.
    lang: código do idioma (pt, en, es, fr, de...)
    """
    # Busca o título exato
    search_r = httpx.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
        },
        timeout=15,
    )
    search_r.raise_for_status()
    results = search_r.json().get("query", {}).get("search", [])
    if not results:
        return f"Nenhum artigo encontrado para '{query}'."

    title = results[0]["title"]

    # Extrai o conteúdo
    content_r = httpx.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "exsentences": sentences,
            "exintro": True,
            "explaintext": True,
            "format": "json",
        },
        timeout=15,
    )
    content_r.raise_for_status()
    pages = content_r.json()["query"]["pages"]
    page = next(iter(pages.values()))
    extract = page.get("extract", "Sem conteúdo disponível.")
    url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"

    return f"# {title}\n🔗 {url}\n\n{extract}"


# ---------------------------------------------------------------------------
# RSS / Atom Feed Reader
# ---------------------------------------------------------------------------

def rss_fetch(feed_url: str, limit: int = 10) -> str:
    """
    Lê qualquer feed RSS ou Atom e retorna os artigos mais recentes.
    Exemplos de feeds úteis (gratuitos):
      - https://feeds.feedburner.com/TechCrunch
      - https://hnrss.org/frontpage
      - https://www.reddit.com/r/cybersecurity/.rss
    """
    r = httpx.get(
        feed_url,
        headers={"User-Agent": "agentes-24h/1.0 RSS Reader"},
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    xml = r.text

    # Parser simples sem dependências externas
    def _extract(tag: str, text: str) -> str:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
        if m:
            raw = m.group(1).strip()
            raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.DOTALL)
            return html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        return ""

    # Título do feed
    feed_title = _extract("title", xml) or feed_url

    # Encontra itens/entries
    items_raw = re.findall(r"<(?:item|entry)[^>]*>(.*?)</(?:item|entry)>", xml, re.DOTALL)
    items_raw = items_raw[:limit]

    if not items_raw:
        return f"Feed '{feed_url}' não contém itens ou formato não reconhecido."

    output = [f"# {feed_title}\n"]
    for raw in items_raw:
        title   = _extract("title",   raw) or "Sem título"
        link    = _extract("link",    raw) or _extract("guid", raw)
        summary = _extract("summary", raw) or _extract("description", raw)
        summary = summary[:300] + "..." if len(summary) > 300 else summary
        output.append(f"**{title}**\n🔗 {link}\n{summary}")

    return "\n\n---\n\n".join(output)


# ---------------------------------------------------------------------------
# SEO & Legibilidade
# ---------------------------------------------------------------------------

def seo_analyze(text: str, keyword: str = "", title: str = "") -> str:
    """
    Análise local de SEO e legibilidade (sem API externa).

    Verifica:
      - Contagem de palavras
      - Densidade de keyword
      - Índice de Flesch (legibilidade)
      - Comprimento do título
      - Parágrafos longos
      - Sugestões práticas
    """
    word_count = len(text.split())
    char_count = len(text)
    sentences  = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    n_sentences = max(len(sentences), 1)

    # Sílabas (aproximação para português/inglês)
    def _syllables(word: str) -> int:
        word = word.lower()
        count = len(re.findall(r"[aeiouáéíóúâêîôûãõàèìòùäëïöü]", word))
        return max(count, 1)

    words = text.split()
    total_syllables = sum(_syllables(w) for w in words)

    # Flesch Reading Ease (adaptado)
    if word_count > 0 and n_sentences > 0:
        flesch = 206.835 - 1.015 * (word_count / n_sentences) - 84.6 * (total_syllables / word_count)
        flesch = round(max(0, min(100, flesch)), 1)
    else:
        flesch = 0

    if flesch >= 70:
        readability = "Fácil ✅"
    elif flesch >= 50:
        readability = "Médio ⚠️"
    else:
        readability = "Difícil ❌"

    # Density de keyword
    kw_info = ""
    if keyword:
        kw_count = text.lower().count(keyword.lower())
        density = round((kw_count / word_count) * 100, 2) if word_count else 0
        status = "✅" if 1 <= density <= 3 else ("⚠️ baixo" if density < 1 else "⚠️ alto")
        kw_info = f"\n**Keyword '{keyword}':** {kw_count}× | densidade {density}% {status}"

    # Título
    title_info = ""
    if title:
        tlen = len(title)
        tstatus = "✅" if 50 <= tlen <= 60 else f"⚠️ {'curto' if tlen < 50 else 'longo'}"
        title_info = f"\n**Título:** {tlen} chars {tstatus} (ideal: 50-60)"

    # Parágrafos longos
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    long_paras = sum(1 for p in paragraphs if len(p.split()) > 150)

    # Sugestões
    suggestions = []
    if word_count < 300:
        suggestions.append("🔴 Texto muito curto para SEO (mín. 300 palavras)")
    elif word_count < 600:
        suggestions.append("🟡 Considere expandir para 600+ palavras")
    else:
        suggestions.append("✅ Volume de texto adequado para SEO")

    if long_paras > 2:
        suggestions.append(f"⚠️ {long_paras} parágrafos com +150 palavras – quebre-os")

    if flesch < 50:
        suggestions.append("⚠️ Texto complexo – use frases mais curtas")

    return (
        f"# Análise SEO\n\n"
        f"**Palavras:** {word_count} | **Frases:** {n_sentences} | **Chars:** {char_count}\n"
        f"**Legibilidade Flesch:** {flesch} – {readability}"
        f"{kw_info}{title_info}\n\n"
        f"**Sugestões:**\n" + "\n".join(f"  {s}" for s in suggestions)
    )


# ---------------------------------------------------------------------------
# GitHub Trending
# ---------------------------------------------------------------------------

def trending_github(language: str = "", since: str = "daily", limit: int = 10) -> str:
    """
    Repositórios em alta no GitHub via API não-oficial do ghtrending.
    since: daily | weekly | monthly
    language: python, javascript, go, rust, etc. (vazio = todos)
    """
    params: dict[str, str] = {"since": since}
    if language:
        params["language"] = language

    try:
        r = httpx.get(
            "https://gh-trending-api.deno.dev/repositories",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        repos = r.json()[:limit]
    except Exception:
        # Fallback: scrape via GitHub diretamente (sem parse de HTML)
        return "API de trending indisponível no momento. Tente: https://github.com/trending"

    lines = [f"# GitHub Trending – {since.title()} ({language or 'all languages'})\n"]
    for repo in repos:
        name  = repo.get("fullname") or repo.get("name", "?")
        desc  = repo.get("description", "") or ""
        stars = repo.get("stars") or repo.get("totalStars", "?")
        gained= repo.get("todayStars") or repo.get("gainedStars", "")
        url   = repo.get("url") or f"https://github.com/{name}"
        lang  = repo.get("language", "")
        gained_str = f" (+{gained} hoje)" if gained else ""
        lines.append(
            f"**{name}** ⭐ {stars}{gained_str} {f'[{lang}]' if lang else ''}\n"
            f"  {desc[:120]}\n  🔗 {url}"
        )

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Reddit Top Posts
# ---------------------------------------------------------------------------

def reddit_top(subreddit: str, limit: int = 10, time_filter: str = "day") -> str:
    """
    Posts em alta de um subreddit via Reddit JSON API (sem chave).
    time_filter: hour | day | week | month | year | all
    """
    url = f"https://www.reddit.com/r/{subreddit}/top.json"
    r = httpx.get(
        url,
        params={"limit": limit, "t": time_filter},
        headers={"User-Agent": "agentes-24h/1.0"},
        timeout=20,
    )
    r.raise_for_status()
    posts = r.json()["data"]["children"]

    if not posts:
        return f"Nenhum post encontrado em r/{subreddit}."

    lines = [f"# r/{subreddit} – Top {time_filter.title()}\n"]
    for post in posts:
        d = post["data"]
        lines.append(
            f"**{d['title']}**\n"
            f"  ▲ {d['score']} | 💬 {d['num_comments']} | por u/{d['author']}\n"
            f"  🔗 https://reddit.com{d['permalink']}"
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Free Dictionary API
# ---------------------------------------------------------------------------

def dictionary_lookup(word: str, lang: str = "en") -> str:
    """
    Definição, exemplos e sinônimos via Free Dictionary API.
    lang: en (inglês) | es | fr | de | it | pt (limitado)
    """
    r = httpx.get(
        f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}",
        timeout=15,
    )
    if r.status_code == 404:
        return f"Palavra '{word}' não encontrada no idioma '{lang}'."
    r.raise_for_status()
    data = r.json()[0]

    phonetic = data.get("phonetic", "")
    output = [f"# {word} {phonetic}\n"]

    for meaning in data.get("meanings", [])[:3]:
        pos = meaning.get("partOfSpeech", "")
        output.append(f"**{pos}**")
        for defn in meaning.get("definitions", [])[:3]:
            output.append(f"  • {defn['definition']}")
            if defn.get("example"):
                output.append(f"    *\"{defn['example']}\"*")
        synonyms = meaning.get("synonyms", [])[:6]
        if synonyms:
            output.append(f"  Sinônimos: {', '.join(synonyms)}")

    return "\n".join(output)


# ---------------------------------------------------------------------------
# Extração de Keywords
# ---------------------------------------------------------------------------

def extract_keywords(text: str, top_n: int = 15) -> str:
    """
    Extrai palavras-chave de um texto usando TF simplificado (sem API).
    Funciona para qualquer idioma.
    """
    # Stopwords básicas (PT + EN)
    stopwords = {
        "de","da","do","em","para","por","com","que","uma","um","é","se","na",
        "no","ao","os","as","isso","este","esta","esse","essa","tem","são",
        "the","a","an","and","or","but","in","on","at","to","for","of","is",
        "it","be","as","was","are","with","he","she","they","we","you","that",
        "this","have","from","by","not","but","what","all","were","when","there",
    }

    words = re.findall(r"\b[a-záéíóúâêîôûãõàèìòùäëïöü]{4,}\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1

    sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]

    lines = ["# Palavras-chave extraídas\n"]
    for word, count in sorted_kw:
        bar = "█" * min(count, 20)
        lines.append(f"  `{word}` — {count}× {bar}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lorem Ipsum / Placeholder Text
# ---------------------------------------------------------------------------

def lorem_ipsum(paragraphs: int = 3, lo_type: str = "paras") -> str:
    """
    Gera texto placeholder via loripsum.net (gratuito).
    lo_type: short | medium | long | verylong
    """
    lo_type = lo_type if lo_type in ("short", "medium", "long", "verylong") else "medium"
    r = httpx.get(
        f"https://loripsum.net/api/{paragraphs}/{lo_type}/plaintext",
        timeout=15,
    )
    r.raise_for_status()
    return r.text.strip()


# ---------------------------------------------------------------------------
# Gerador de Copy via IA (usa providers locais)
# ---------------------------------------------------------------------------

def generate_copy(
    product: str,
    audience: str,
    tone: str = "profissional",
    copy_type: str = "headline+body+cta",
) -> dict[str, str]:
    """
    Gera copy de marketing usando o orquestrador de IA local.
    Retorna dict com as partes solicitadas.

    copy_type: qualquer combinação de headline, body, cta, subject, meta_description
    """
    # Import lazy para não criar dependência circular
    try:
        from providers import ProviderOrchestrator
        from key_client import KeyClient
        orch = ProviderOrchestrator(KeyClient())
    except ImportError:
        return {"error": "providers não disponível neste contexto"}

    system = (
        "Você é um copywriter especialista em conversão. "
        "Responda APENAS com JSON válido, sem markdown, no formato solicitado."
    )

    parts = [p.strip() for p in copy_type.split("+")]
    schema = {p: f"<{p} aqui>" for p in parts}

    prompt = (
        f"Produto/Serviço: {product}\n"
        f"Público-alvo: {audience}\n"
        f"Tom: {tone}\n\n"
        f"Gere copy em português para: {', '.join(parts)}.\n"
        f"Retorne SOMENTE este JSON: {schema}"
    )

    try:
        response, _ = orch.complete(prompt, system=system, max_tokens=1024)
        import json
        clean = response.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except Exception as e:
        return {"error": str(e), "raw": response if "response" in dir() else ""}
