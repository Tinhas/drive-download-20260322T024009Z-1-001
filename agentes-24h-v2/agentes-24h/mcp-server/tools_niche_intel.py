"""
tools_niche_intel.py
====================
Inteligência de nicho — engenharia reversa dos sites de maior sucesso.

A ideia: antes de criar qualquer site ou copy, entenda o que JÁ FUNCIONA
no nicho. Raspe os líderes, extraia padrões, aplique o que funciona.

Ferramentas:
  - niche_top_sites         : encontra os top sites de um nicho
  - site_reverse_engineer   : destrói um site concorrente: copy, design, CTA, estrutura
  - niche_copy_patterns     : extrai padrões de copy dos líderes do nicho
  - serp_analyze            : analisa os resultados do Google para uma keyword
  - content_gap_finder      : encontra lacunas de conteúdo que o nicho não cobre
  - niche_vocabulary        : extrai o vocabulário, jargões e frases do nicho
  - trust_signals_audit     : mapeia todos os sinais de confiança usados no nicho
  - pricing_intelligence    : mapeia estratégias de pricing do nicho
  - social_proof_patterns   : padrões de prova social mais usados no nicho
  - winning_headline_patterns: os padrões de headline que mais aparecem nos líderes
"""

from __future__ import annotations

import logging
import re
import os
from typing import Any

import httpx

log = logging.getLogger("tools.niche_intel")


def _fetch_html(url: str) -> str:
    """Baixa HTML de uma URL com fallback."""
    r = httpx.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    return r.text


def _extract_text(html: str, max_chars: int = 8000) -> str:
    """Extrai texto limpo de HTML."""
    # Remove scripts, styles, nav, footer
    clean = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_chars]


def _ai(prompt: str, system: str = "", max_tokens: int = 3000) -> str:
    """Usa orquestrador de IA."""
    try:
        from providers import ProviderOrchestrator
        from key_client import KeyClient
        orch = ProviderOrchestrator(KeyClient())
        result, _ = orch.complete(prompt, system=system, max_tokens=max_tokens)
        return result
    except ImportError:
        # Fallback: Gemini direto
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            return "Nenhum provedor de IA disponível."
        r = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": (system + "\n\n" if system else "") + prompt}]}],
                  "generationConfig": {"maxOutputTokens": max_tokens}},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


# ===========================================================================
# 1. Encontrar Top Sites do Nicho
# ===========================================================================

def niche_top_sites(niche: str, country: str = "BR", limit: int = 10) -> str:
    """
    Encontra os sites líderes de um nicho via múltiplas fontes públicas.
    Usa SimilarWeb (dados públicos) + Hacker News + Reddit + Product Hunt.
    """
    results = {}

    # Product Hunt — via API pública GraphQL
    ph_query = f"""{{
      posts(first: {min(limit, 20)}, order: VOTES, after: null) {{
        edges {{ node {{ name tagline website url votesCount }} }}
      }}
    }}"""
    # (Product Hunt requer auth para resultados por nicho, então usamos pesquisa alternativa)

    # GitHub Awesome Lists — fonte confiável de top produtos por nicho
    awesome_map = {
        "saas": "awesome-saas-services", "fintech": "awesome-fintech",
        "ecommerce": "awesome-ecommerce", "marketing": "awesome-marketing",
        "seo": "awesome-seo", "ai": "awesome-ai", "devtools": "awesome-devtools",
        "nocode": "awesome-nocode", "analytics": "awesome-analytics",
    }

    # Usamos a pesquisa DuckDuckGo instantânea (sem chave)
    duckduck_url = f"https://api.duckduckgo.com/?q=top+{niche}+sites+tools&format=json&no_redirect=1"
    try:
        r = httpx.get(duckduck_url, timeout=15)
        dd_data = r.json()
        related = dd_data.get("RelatedTopics", [])
        results["duckduckgo"] = [t.get("Text", "")[:100] for t in related[:5] if t.get("Text")]
    except Exception:
        results["duckduckgo"] = []

    # Reddit — buscar posts sobre top ferramentas do nicho
    try:
        reddit_url = f"https://www.reddit.com/r/{niche}/top.json?limit=5&t=year"
        rr = httpx.get(reddit_url, headers={"User-Agent": "agentes-24h/1.0"}, timeout=15)
        if rr.status_code == 200:
            posts = rr.json()["data"]["children"]
            results["reddit"] = [p["data"]["title"][:80] for p in posts[:5]]
    except Exception:
        pass

    # Product Hunt (scrape público)
    try:
        ph_url = f"https://www.producthunt.com/search?q={niche}"
        ph_r = httpx.get(ph_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        ph_names = re.findall(r'"name":"([^"]{3,60})"', ph_r.text)[:8]
        results["producthunt"] = list(dict.fromkeys(ph_names))
    except Exception:
        results["producthunt"] = []

    # Usa IA para sintetizar e adicionar conhecimento
    system = "Você é analista de mercado especialista em benchmarking digital. Seja específico e factual."
    prompt = f"""Nicho: {niche} | País foco: {country}

Dados coletados de fontes públicas:
- DuckDuckGo: {results.get('duckduckgo', [])}
- Reddit r/{niche}: {results.get('reddit', [])}
- Product Hunt: {results.get('producthunt', [])}

Com base nisto E no seu conhecimento, liste os {limit} sites/produtos LÍDERES REAIS do nicho "{niche}".

Para cada um:
1. Nome + URL
2. Por que é líder (modelo, diferencial, tráfego estimado)
3. Pontos fortes a estudar (design, copy, pricing, funil)
4. Score de referência 1-10 para benchmarking

Formato: lista markdown detalhada e acionável."""

    ai_result = _ai(prompt, system=system, max_tokens=2000)
    return f"# Top Sites — Nicho: {niche}\n\n{ai_result}"


# ===========================================================================
# 2. Engenharia Reversa de Site Concorrente
# ===========================================================================

def site_reverse_engineer(url: str, focus: str = "tudo") -> str:
    """
    Destrói um site concorrente e extrai todos os padrões reutilizáveis.
    focus: tudo | copy | design | funil | seo | pricing | trust
    """
    log.info("Reverse engineering: %s (foco: %s)", url, focus)

    try:
        html = _fetch_html(url)
    except Exception as e:
        return f"❌ Erro ao carregar {url}: {e}"

    text = _extract_text(html)

    # Extrai dados estruturais do HTML
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE)
    title_text = title.group(1).strip() if title else "?"

    description = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
    desc_text = description.group(1).strip() if description else "?"

    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    h1s = [re.sub(r"<[^>]+>", "", h).strip() for h in h1s[:3]]

    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.IGNORECASE | re.DOTALL)
    h2s = [re.sub(r"<[^>]+>", "", h).strip() for h in h2s[:8] if len(h) < 200]

    ctaMatches = re.findall(r'(?:href|onclick)[^>]*>(.*?)</(?:a|button)', html, re.IGNORECASE | re.DOTALL)
    ctas = list({re.sub(r"<[^>]+>", "", c).strip() for c in ctaMatches if 2 < len(c.strip()) < 50})[:10]

    prices = re.findall(r'R\$\s*[\d.,]+|US\$\s*[\d.,]+|\$\s*[\d.,]+|€\s*[\d.,]+', html)
    prices = list(dict.fromkeys(prices))[:8]

    system = "Você é um estrategista de growth que fez engenharia reversa de centenas de sites de alto desempenho."

    prompt = f"""Analise este site e extraia TUDO que pode ser replicado ou melhorado:

URL: {url}
Título: {title_text}
Meta Description: {desc_text}
H1s: {h1s}
H2s: {h2s[:5]}
CTAs encontrados: {ctas}
Preços encontrados: {prices}
Conteúdo (primeiros 5000 chars): {text[:5000]}

FOCO DA ANÁLISE: {focus}

Extraia e analise:

## 1. PROPOSTA DE VALOR
- O que eles prometem entregar?
- Em quantas palavras comunicam o valor?
- O que funciona? O que poderia ser melhor?

## 2. ESTRUTURA DO FUNIL
- Como é a jornada do visitante?
- Onde estão os CTAs? Quantos?
- O que vem antes do CTA principal?

## 3. COPY PATTERNS
- Quais palavras e frases mais aparecem?
- Tom de voz (formal/informal, técnico/emocional)?
- Gatilhos mentais usados?

## 4. PROVA SOCIAL
- Quais sinais de confiança usam?
- Depoimentos, números, logos?

## 5. DESIGN & UX
- Cores principais e emoções que evocam
- Layout acima da dobra
- O que chama mais atenção?

## 6. SEO STRUCTURE
- Title tag otimizado?
- H1/H2 estratégicos?
- Keywords implícitas?

## 7. O QUE ROUBAR (eticamente)
- Top 5 elementos a replicar no seu site
- Top 3 melhorias que você faria no site deles

Seja cirúrgico e acionável. Exemplos concretos do HTML acima."""

    ai_result = _ai(prompt, system=system, max_tokens=3000)
    return f"# Engenharia Reversa: {url}\n\n{ai_result}"


# ===========================================================================
# 3. Padrões de Copy do Nicho
# ===========================================================================

def niche_copy_patterns(niche: str, copy_element: str = "headlines") -> str:
    """
    Analisa e lista os padrões de copy mais eficazes usados pelos líderes do nicho.
    copy_element: headlines | ctas | taglines | value_props | email_subjects
    """
    system = "Você é especialista em copywriting e pesquisa de mercado com foco em padrões que convertem."

    prompt = f"""Analise o nicho: {niche}
Elemento de copy: {copy_element}

Liste os 15 padrões mais usados pelos sites líderes deste nicho.

Para cada padrão:
1. **Nome do padrão** (ex: "Específico + Resultado")
2. **Template:** "[variável] para [resultado] em [tempo]"
3. **Exemplo real** do nicho (cite empresa real se possível)
4. **Por que funciona** (neurociência/psicologia em 1 frase)
5. **Versão para seu produto:** como adaptar o template

Depois, mostre:
## Padrões a EVITAR neste nicho (clichês que não convertem mais)
## Tendências emergentes (o que os disruptores do nicho estão fazendo diferente)
## Vocabulary map: 20 palavras/frases específicas do nicho que aumentam conversão"""

    result = _ai(prompt, system=system, max_tokens=3000)
    return f"# Copy Patterns — {niche} ({copy_element})\n\n{result}"


# ===========================================================================
# 4. Análise de SERP (resultados do Google)
# ===========================================================================

def serp_analyze(keyword: str, intent: str = "auto") -> str:
    """
    Analisa o que o Google está mostrando para uma keyword e o que isso significa
    para a estratégia de conteúdo. Usa DuckDuckGo API (sem chave).
    """
    # Busca via DuckDuckGo
    try:
        r = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": keyword, "format": "json", "no_redirect": "1", "no_html": "1"},
            timeout=15,
        )
        dd = r.json()
        abstract = dd.get("AbstractText", "")
        related = [t.get("Text", "") for t in dd.get("RelatedTopics", [])[:8] if t.get("Text")]
        source = dd.get("AbstractSource", "")
    except Exception:
        abstract, related, source = "", [], ""

    system = "Você é especialista em SEO e intent analysis. Base suas respostas em dados reais do mercado."

    prompt = f"""Keyword analisada: "{keyword}"

Dados do DuckDuckGo:
- Resumo: {abstract[:500] if abstract else "N/A"}
- Fonte: {source}
- Relacionados: {related}

Analise completamente:

## 1. INTENÇÃO DE BUSCA
- Tipo: Informacional | Navegacional | Transacional | Comercial
- O que o usuário REALMENTE quer quando pesquisa isso?
- Momento da jornada de compra (consciência/consideração/decisão)?

## 2. O QUE O GOOGLE QUER VER
- Tipo de conteúdo preferido para esta keyword (blog/landing page/produto/vídeo)
- Estrutura ideal (H1, H2s, comprimento)
- Sinal de relevância mais importante para ranquear

## 3. ESTRATÉGIA DE CONTEÚDO
- 5 ângulos únicos para criar conteúdo sobre este tema
- Keywords semânticas relacionadas a incluir
- Perguntas "People Also Ask" prováveis

## 4. OPORTUNIDADE COMPETITIVA
- Dificuldade estimada para ranquear (1-10)
- Estratégia para entrar neste SERP
- Quick wins (o que pode ranquear em 30-90 dias)

## 5. MONETIZAÇÃO
- Como monetizar o tráfego desta keyword
- CPL/CPC estimado se usar como paid"""

    result = _ai(prompt, system=system, max_tokens=2500)
    return f"# Análise SERP: \"{keyword}\"\n\n{result}"


# ===========================================================================
# 5. Content Gap Finder
# ===========================================================================

def content_gap_finder(niche: str, your_topics: list[str] | None = None) -> str:
    """
    Encontra lacunas de conteúdo que os líderes do nicho não estão cobrindo.
    Estas lacunas são oportunidades de SEO e autoridade.
    """
    your_topics = your_topics or []

    system = "Você é estrategista de conteúdo que identifica oportunidades inexploradas com precisão cirúrgica."

    prompt = f"""Nicho: {niche}
Seus tópicos atuais: {your_topics if your_topics else "não informados"}

Analise o nicho profundamente e identifique:

## LACUNAS DE CONTEÚDO (oportunidades inexploradas)

### 1. Tópicos com Alta Demanda e Baixa Concorrência
Liste 10 tópicos que:
- Usuários buscam muito
- Poucos sites do nicho cobrem bem
- Você pode dominar com 1 artigo/página excelente

### 2. Ângulos Diferentes do Óbvio
Os líderes cobrem [tópico X] de forma [Y]. Você pode cobrir de forma [Z] diferente e melhor.
Liste 5 exemplos concretos.

### 3. Audiências Sub-servidas
Segmentos do público que os líderes ignoram. Quem são e o que precisam?

### 4. Formatos Inexplorados
O nicho usa muito: [formato]. Você pode se destacar com: [outros formatos].

### 5. Perguntas sem Resposta
As 15 perguntas mais frequentes do nicho que ninguém responde de forma satisfatória.
(Fonte de tráfego de cauda longa de altíssima intenção)

### 6. Conteúdo Desatualizado para Atualizar
Tópicos em que o conteúdo existente está desatualizado e você pode criar a versão definitiva.

Para cada lacuna: **Potencial de tráfego** + **Dificuldade de criar** + **Tempo estimado para ranquear**"""

    result = _ai(prompt, system=system, max_tokens=3000)
    return f"# Content Gap Analysis — {niche}\n\n{result}"


# ===========================================================================
# 6. Vocabulário do Nicho
# ===========================================================================

def niche_vocabulary(niche: str, output_format: str = "completo") -> str:
    """
    Extrai o vocabulário, jargões, metáforas e frases-chave do nicho.
    Use isso para escrever copy que ressoa como insider, não outsider.
    output_format: completo | csv | glossario
    """
    system = "Você é antropólogo de mercado especialista em como subculturas e nichos se comunicam."

    prompt = f"""Nicho: {niche}

Extraia o vocabulário completo que um insider usa vs um outsider:

## 1. JARGÕES E TERMOS TÉCNICOS
| Termo | Significado | Quando usar |
Inclua 20 termos específicos do nicho com definição e contexto de uso.

## 2. METÁFORAS E ANALOGIAS COMUNS
As 10 metáforas que especialistas do nicho usam naturalmente.

## 3. PALAVRAS QUE AUMENTAM CREDIBILIDADE
Palavras e frases que fazem você soar como expert do nicho (não genérico).

## 4. PALAVRAS A EVITAR
Termos que soam amadores, desatualizados ou de fora do nicho.

## 5. FRASES-CHAVE DO NICHO
As 15 expressões que você DEVE usar no copy para resonar com o público.
Ex: no nicho de e-commerce: "abandono de carrinho", "LTV", "CAC payback"

## 6. PAIN POINTS EM LINGUAGEM DO NICHO
Como o público NOMEIA seus próprios problemas (não como você nomeia para eles).

## 7. ASPIRAÇÕES EM LINGUAGEM DO NICHO
Como eles descrevem o sucesso, o objetivo, o resultado desejado.

## 8. OBJEÇÕES EM LINGUAGEM DO NICHO
As 10 objeções exatas que o público usa, com as palavras exatas que eles usam.

Format: {output_format} (se csv: gere tabela com ,separando colunas)"""

    result = _ai(prompt, system=system, max_tokens=3000)
    return f"# Vocabulário do Nicho: {niche}\n\n{result}"


# ===========================================================================
# 7. Mapeamento de Trust Signals
# ===========================================================================

def trust_signals_audit(url: str = "", niche: str = "") -> str:
    """
    Mapeia todos os sinais de confiança usados pelos líderes do nicho.
    Se URL fornecida: analisa esse site específico.
    Se niche fornecido: analisa padrões do nicho.
    """
    context = ""
    if url:
        try:
            html = _fetch_html(url)
            context = f"\nConteúdo do site ({url}):\n{_extract_text(html)[:4000]}"
        except Exception as e:
            context = f"\n(Não foi possível carregar {url}: {e})"

    system = "Você é especialista em CRO e psicologia da confiança na web."

    prompt = f"""{"Nicho: " + niche if niche else ""}
{"URL analisada: " + url if url else ""}{context}

Mapeie e avalie todos os sinais de confiança:

## TIER 1 — Sinais de Maior Impacto na Conversão
(cada um pode aumentar conversão em 10-30%)

### Social Proof Quantificado
- [✅/❌] Número de clientes/usuários (específico, não "milhares")
- [✅/❌] Avaliações com nota (ex: ★★★★★ 4.9 de 2.341 avaliações)
- [✅/❌] Logos de clientes famosos
- [✅/❌] Depoimentos com foto + nome + cargo + empresa
- [✅/❌] Casos de sucesso com resultado numérico

### Autoridade
- [✅/❌] Menções na mídia (Forbes, G1, TechCrunch...)
- [✅/❌] Prêmios e certificações
- [✅/❌] Anos no mercado
- [✅/❌] Fundadores com credenciais

## TIER 2 — Sinais de Impacto Médio

### Segurança
- [✅/❌] HTTPS + cadeado visível
- [✅/❌] Selos de segurança (SSL, PCI, LGPD)
- [✅/❌] Política de privacidade acessível
- [✅/❌] Termos de uso claros

### Garantias
- [✅/❌] Garantia de devolução (X dias)
- [✅/❌] Teste grátis sem cartão
- [✅/❌] SLA explícito
- [✅/❌] Suporte humano visível

## TIER 3 — Micro-sinais

- [✅/❌] Endereço físico
- [✅/❌] CNPJ visível
- [✅/❌] Redes sociais ativas (com seguidores reais)
- [✅/❌] Blog/conteúdo atualizado

## SCORE FINAL E RECOMENDAÇÕES
Score: X/20
Top 3 sinais a implementar primeiro (maior impacto, menor esforço)
Custo estimado de implementação de cada um"""

    result = _ai(prompt, system=system, max_tokens=2500)
    return f"# Trust Signals Audit\n{'**' + url + '**' if url else '**Nicho: ' + niche + '**'}\n\n{result}"


# ===========================================================================
# 8. Pricing Intelligence
# ===========================================================================

def pricing_intelligence(niche: str, product_type: str = "saas") -> str:
    """
    Mapeia estratégias de pricing do nicho: modelos, faixas, psicologia de preço.
    product_type: saas | ecommerce | servicos | infoproduto | consultoria
    """
    system = "Você é especialista em estratégia de pricing com dados de mercado."

    prompt = f"""Nicho: {niche}
Tipo de produto: {product_type}

Análise completa de pricing do nicho:

## 1. MODELOS DE PRICING USADOS
Quais modelos os líderes usam e por quê:
- Freemium → pago
- Free trial → pago
- Por usuário/assento
- Por uso (usage-based)
- Por funcionalidade/tier
- Projeto único
- Retainer mensal
- Revenue share

## 2. FAIXAS DE PREÇO TÍPICAS
| Tier | Faixa de preço | O que inclui | Público-alvo |
Inclua 3-4 tiers típicos do nicho com preços reais de referência.

## 3. PSICOLOGIA DE PREÇO APLICADA
- Charm pricing (R$97 vs R$100): usa no nicho? Por quê?
- Preço âncora: como os líderes criam ancoragem?
- Plano iscaappelida: o plano intermediário é a âncora?
- Decoy pricing: têm plano "ruim de propósito"?
- Price-quality signal: preço alto como sinal de qualidade?

## 4. ESTRATÉGIAS DE CONVERSÃO FREEMIUM → PAGO
As 5 táticas que os líderes usam para converter free → paid.

## 5. OBJEÇÕES DE PREÇO MAIS COMUNS
Como o nicho lida com "está caro"?

## 6. RECOMENDAÇÃO DE PRICING
Para um novo entrante neste nicho:
- Estratégia de entrada (penetration vs premium)
- Price point ideal (com justificativa)
- Como crescer o preço ao longo do tempo (expansion revenue)"""

    result = _ai(prompt, system=system, max_tokens=2500)
    return f"# Pricing Intelligence — {niche} ({product_type})\n\n{result}"


# ===========================================================================
# 9. Padrões de Headline que Vencem
# ===========================================================================

def winning_headline_patterns(niche: str, goal: str = "conversão") -> str:
    """
    Analisa e lista os padrões de headline com maior performance histórica
    para o nicho, baseado em dados de copy de alta conversão.
    """
    system = "Você é diretor de copy com histórico de headlines que geraram milhões em receita."

    prompt = f"""Nicho: {niche} | Objetivo: {goal}

Analise os padrões de headline com maior taxa de conversão para este nicho.

## OS 20 TEMPLATES DE HEADLINE MAIS EFICAZES

Para cada template:
1. **Template:** "[estrutura]"
2. **Exemplo real do nicho**
3. **Por que converte** (princípio psicológico)
4. **Score de impacto:** ★★★★★

Inclua templates para:
- Hero section (landing page)
- Email subject lines
- Anúncios pagos (Meta/Google)
- Posts orgânicos
- Blog posts (SEO)

## ANÁLISE DOS PADRÕES
- Qual padrão funciona melhor para {goal}?
- Número vs pergunta vs afirmação?
- Quanto custa NÃO testar headlines?

## GERADOR DE HEADLINES
Para o nicho {niche}, gere 5 headlines prontos para testar A/B,
um para cada template mais eficaz identificado.

## RED FLAGS — Headlines que matam conversão neste nicho
Os 5 erros de headline mais comuns que os amadores cometem."""

    result = _ai(prompt, system=system, max_tokens=2500)
    return f"# Winning Headline Patterns — {niche}\n\n{result}"
