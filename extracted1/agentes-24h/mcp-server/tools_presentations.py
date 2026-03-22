"""
tools_presentations.py
======================
Criação de apresentações profissionais via IA — nível McKinsey/Andreessen Horowitz.

Abordagem:
  - O NotebookLM não tem API pública oficial → usa Gemini como backend
    com prompts estruturados que replicam o comportamento do NotebookLM
  - Gera apresentações HTML autocontidas (slides bonitos, sem PowerPoint)
  - Também gera estrutura de dados para conversão em PPTX via python-pptx

Ferramentas:
  - presentation_from_doc    : cria apresentação completa a partir de um documento
  - presentation_from_topic  : cria do zero sobre qualquer tema
  - slide_outline_generate   : gera apenas o outline (para revisar antes de criar)
  - executive_summary_slide  : slide único de resumo executivo (estilo McKinsey)
  - pitch_deck_generate      : pitch deck completo para investidores
  - presentation_to_html     : converte outline JSON em HTML interativo
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

log = logging.getLogger("tools.presentations")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _gemini(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """Chama Gemini diretamente (sem depender do orquestrador)."""
    key = GEMINI_KEY
    if not key:
        try:
            import httpx as hx
            from key_client import KeyClient
            kc = KeyClient()
            key = os.environ.get("GEMINI_API_KEY", "")
        except Exception:
            pass

    if not key:
        # Fallback: usa orquestrador local
        try:
            from providers import ProviderOrchestrator
            from key_client import KeyClient
            orch = ProviderOrchestrator(KeyClient())
            result, _ = orch.complete(prompt, system=system, max_tokens=max_tokens)
            return result
        except Exception as e:
            raise RuntimeError(f"Nenhum provedor disponível: {e}")

    parts = []
    if system:
        parts.append({"text": f"INSTRUÇÃO DO SISTEMA:\n{system}\n\n"})
    parts.append({"text": prompt})

    r = httpx.post(
        GEMINI_URL,
        params={"key": key},
        json={
            "contents": [{"parts": parts}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
        },
        timeout=180,
    )
    if r.status_code == 429:
        raise RuntimeError("Limite do Gemini atingido. Tente em alguns minutos.")
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json_response(text: str) -> Any:
    """Extrai JSON de uma resposta de LLM com robustez."""
    clean = re.sub(r"```json\n?|```\n?", "", text).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Tenta encontrar o JSON dentro do texto
        match = re.search(r"\[[\s\S]*\]|\{[\s\S]*\}", clean)
        if match:
            return json.loads(match.group())
        raise ValueError(f"JSON não encontrado na resposta: {clean[:300]}")


# ===========================================================================
# Ferramenta 1: Apresentação a partir de Documento
# ===========================================================================

def presentation_from_doc(
    document_text: str,
    presentation_goal: str = "informar",
    audience: str = "profissional",
    slide_count: int = 12,
    style: str = "corporativo",
) -> str:
    """
    Cria uma apresentação completa a partir de um documento.
    Replica o NotebookLM: entende o documento e estrutura os insights.

    presentation_goal: informar | persuadir | vender | treinar | reportar
    style: corporativo | startup | minimalista | criativo | dark
    """
    system = """Você é especialista em comunicação executiva, com experiência em McKinsey, BCG e Andreessen Horowitz.
Você transforma documentos complexos em apresentações de alto impacto.
Responda APENAS com JSON válido, sem markdown, sem explicações."""

    prompt = f"""Analise o documento abaixo e crie uma apresentação de {slide_count} slides.

OBJETIVO: {presentation_goal}
PÚBLICO: {audience}
ESTILO: {style}

DOCUMENTO:
{document_text[:15000]}

Retorne um JSON array com exatamente {slide_count} objetos, cada um com:
{{
  "slide_number": 1,
  "type": "cover|agenda|section|content|chart|quote|comparison|stats|cta|thank_you",
  "title": "Título do slide (máx 8 palavras)",
  "subtitle": "Subtítulo opcional",
  "key_message": "Uma frase que resume o insight principal deste slide",
  "bullet_points": ["ponto 1", "ponto 2", "ponto 3"],
  "data": {{"type": "bar|pie|line|table|none", "description": "descrição do dado"}},
  "speaker_notes": "Notas do apresentador com contexto adicional",
  "visual_suggestion": "Descrição do visual ideal para este slide",
  "source": "Trecho do documento que originou este slide"
}}

REGRAS:
- Slide 1: sempre cover com título impactante
- Slide 2: agenda/sumário
- Último slide: próximos passos ou CTA
- Máx 5 bullet points por slide
- Cada bullet: máx 12 palavras
- key_message deve ser memorável e autônomo (faz sentido fora de contexto)
- Extraia dados reais do documento para os slides de stats/chart"""

    raw = _gemini(prompt, system=system, max_tokens=6000)
    try:
        slides = _parse_json_response(raw)
    except Exception:
        return f"Erro ao parsear slides. Resposta bruta:\n{raw[:2000]}"

    return presentation_to_html(slides=slides, style=style, title=f"Apresentação — {presentation_goal.title()}")


# ===========================================================================
# Ferramenta 2: Apresentação sobre Qualquer Tema
# ===========================================================================

def presentation_from_topic(
    topic: str,
    depth: str = "intermediário",
    audience: str = "profissional",
    slide_count: int = 15,
    style: str = "startup",
    include_data: bool = True,
) -> str:
    """
    Cria apresentação completa sobre qualquer tema usando conhecimento da IA.
    depth: básico | intermediário | avançado | executivo
    """
    system = """Você é professor, consultor e apresentador de nível mundial.
Você cria apresentações que ensinam, convencem e inspiram.
Responda APENAS com JSON válido."""

    prompt = f"""Crie uma apresentação de {slide_count} slides sobre:

TEMA: {topic}
PROFUNDIDADE: {depth}
PÚBLICO: {audience}
ESTILO: {style}
INCLUIR DADOS: {include_data}

Retorne JSON array com {slide_count} slides, cada um:
{{
  "slide_number": 1,
  "type": "cover|agenda|section|content|chart|quote|comparison|stats|timeline|cta|thank_you",
  "title": "Título impactante (máx 8 palavras)",
  "subtitle": "Complemento opcional",
  "key_message": "O insight central deste slide em 1 frase",
  "bullet_points": ["até 5 pontos", "claros e objetivos"],
  "data": {{"type": "bar|pie|line|timeline|comparison|none", "labels": [], "values": [], "description": ""}},
  "quote": {{"text": "", "author": "", "role": ""}},
  "speaker_notes": "Contexto adicional para o apresentador (2-3 frases)",
  "visual_suggestion": "Que imagem/ícone usar aqui"
}}

REGRAS DE QUALIDADE:
- Princípio McKinsey: 1 ideia por slide, 1 slide por ideia
- Dados: use números reais e verificáveis quando possível
- Progressão: do contexto → problema → dados → solução → implementação → próximos passos
- Quotes: use citações reais de especialistas reconhecidos no tema
- Key messages: devem contar a história completa quando lidas em sequência
- Slide de stats: pelo menos 3 métricas impactantes com fonte
- Finalizar com slide de ação: o que o público deve fazer agora"""

    raw = _gemini(prompt, system=system, max_tokens=8000)
    try:
        slides = _parse_json_response(raw)
    except Exception:
        return f"Erro ao parsear. Resposta:\n{raw[:2000]}"

    return presentation_to_html(slides=slides, style=style, title=topic)


# ===========================================================================
# Ferramenta 3: Pitch Deck para Investidores
# ===========================================================================

def pitch_deck_generate(
    company_name: str,
    product: str,
    problem: str,
    solution: str,
    market_size: str,
    traction: str = "",
    ask: str = "",
    style: str = "dark",
) -> str:
    """
    Gera pitch deck completo no formato Sequoia/Y Combinator.
    12 slides: Problem → Solution → Market → Product → Traction → Team → Ask
    """
    system = """Você é um venture capitalist sênior que já analisou 5.000+ pitch decks.
Você conhece exatamente o que investidores querem ver.
Siga o framework Sequoia Capital rigorosamente.
Responda APENAS com JSON válido."""

    prompt = f"""Crie um pitch deck completo para investidores (framework Sequoia):

EMPRESA: {company_name}
PRODUTO: {product}
PROBLEMA: {problem}
SOLUÇÃO: {solution}
TAMANHO DO MERCADO: {market_size}
TRAÇÃO: {traction or "early stage, primeiros usuários"}
CAPTAÇÃO: {ask or "seed round"}

Retorne JSON array com exatamente 12 slides (formato Sequoia):
1. Cover, 2. Problem, 3. Solution, 4. Why Now, 5. Market Size (TAM/SAM/SOM),
6. Product, 7. Business Model, 8. Traction, 9. Team, 10. Competition,
11. Financials, 12. The Ask

Cada slide:
{{
  "slide_number": N,
  "type": "cover|problem|solution|market|product|traction|team|competition|financials|ask",
  "title": "Título do slide",
  "key_message": "A mensagem que o investidor deve sair sabendo",
  "bullet_points": ["máx 4 pontos", "diretos e com métricas"],
  "data": {{"type": "tam_sam_som|bar|comparison|none", "description": ""}},
  "speaker_notes": "O que falar além dos slides (1 parágrafo)",
  "visual_suggestion": "Foto, diagrama ou dado visual ideal",
  "vc_tip": "O que o VC vai pensar aqui e como antecipar a objeção"
}}

PADRÕES SEQUOIA:
- Problem: dor clara, quantificada, verificável
- Solution: simples de entender em 10 segundos
- Market: TAM > $1B para ser interessante a VCs
- Why Now: evento/tendência que torna o timing perfeito
- Traction: métricas reais (MRR, usuários, NPS, crescimento MoM)
- Team: por que VOCÊS são as pessoas certas para resolver ESSE problema
- Ask: valor, uso dos recursos, runway, próximos milestones"""

    raw = _gemini(prompt, system=system, max_tokens=8000)
    try:
        slides = _parse_json_response(raw)
    except Exception:
        return f"Erro: {raw[:1000]}"

    return presentation_to_html(
        slides=slides,
        style=style,
        title=f"{company_name} — Pitch Deck",
        subtitle="Confidencial",
    )


# ===========================================================================
# Ferramenta 4: Executive Summary Slide (1 página)
# ===========================================================================

def executive_summary_slide(
    topic: str,
    context: str,
    key_findings: list[str] | None = None,
    recommendation: str = "",
) -> str:
    """
    Gera 1 slide de resumo executivo estilo McKinsey (Minto Pyramid).
    Estrutura: SCR — Situation, Complication, Resolution.
    """
    system = """Você aplica o Princípio da Pirâmide de Barbara Minto.
Toda comunicação executiva começa pela conclusão e a suporta com evidências.
Responda APENAS com JSON."""

    prompt = f"""Crie um executive summary slide sobre: {topic}

CONTEXTO: {context}
FINDINGS: {json.dumps(key_findings or [], ensure_ascii=False)}
RECOMENDAÇÃO: {recommendation or "determine baseado no contexto"}

Retorne JSON:
{{
  "headline": "A conclusão/recomendação em 1 frase (começa pela resposta, Minto)",
  "situation": "O contexto em 2 frases (o que todos sabem)",
  "complication": "O problema/oportunidade em 2 frases (o que muda)",
  "resolution": "A recomendação em 2 frases (o que fazer)",
  "supporting_points": [
    {{"label": "Ponto 1", "detail": "evidência ou dado"}},
    {{"label": "Ponto 2", "detail": "evidência ou dado"}},
    {{"label": "Ponto 3", "detail": "evidência ou dado"}}
  ],
  "next_steps": ["ação 1 (owner, prazo)", "ação 2", "ação 3"],
  "key_metric": {{"label": "Métrica-chave", "value": "X", "trend": "up|down|stable"}}
}}"""

    raw = _gemini(prompt, system=system, max_tokens=2000)
    try:
        data = _parse_json_response(raw)
    except Exception:
        return f"Erro: {raw[:500]}"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Executive Summary — {topic}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', -apple-system, sans-serif; background: #0A0A0F;
          color: #F0F0F5; min-height: 100vh; display: flex; align-items: center;
          justify-content: center; padding: 40px 20px; }}
  .slide {{ max-width: 1100px; width: 100%; background: #111118;
            border: 1px solid rgba(255,255,255,.08); border-radius: 16px;
            padding: 56px; box-shadow: 0 32px 96px rgba(0,0,0,.5); }}
  .headline {{ font-size: 28px; font-weight: 700; line-height: 1.25;
               color: #fff; border-left: 4px solid #5E6AD2;
               padding-left: 20px; margin-bottom: 40px; }}
  .scr-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; margin-bottom: 40px; }}
  .scr-block {{ background: rgba(255,255,255,.04); border-radius: 12px;
                padding: 24px; border: 1px solid rgba(255,255,255,.06); }}
  .scr-label {{ font-size: 11px; font-weight: 700; letter-spacing: .1em;
                text-transform: uppercase; color: #5E6AD2; margin-bottom: 8px; }}
  .scr-text {{ font-size: 14px; line-height: 1.6; color: #C0C0CC; }}
  .points-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 32px; }}
  .point {{ background: rgba(94,106,210,.08); border: 1px solid rgba(94,106,210,.2);
            border-radius: 10px; padding: 16px; }}
  .point-label {{ font-size: 12px; font-weight: 600; color: #5E6AD2; margin-bottom: 4px; }}
  .point-detail {{ font-size: 13px; color: #A0A0B0; }}
  .next-steps h3 {{ font-size: 13px; font-weight: 700; text-transform: uppercase;
                    letter-spacing: .08em; color: #888; margin-bottom: 12px; }}
  .step {{ display: flex; gap: 10px; align-items: flex-start; margin-bottom: 8px; }}
  .step-num {{ width: 24px; height: 24px; background: #5E6AD2; border-radius: 50%;
               display: flex; align-items: center; justify-content: center;
               font-size: 12px; font-weight: 700; flex-shrink: 0; }}
  .step-text {{ font-size: 14px; color: #C0C0CC; padding-top: 2px; }}
  .metric {{ background: linear-gradient(135deg,rgba(94,106,210,.2),rgba(94,106,210,.05));
             border: 1px solid rgba(94,106,210,.3); border-radius: 12px;
             padding: 20px 24px; display: inline-flex; gap: 16px; align-items: center;
             margin-bottom: 32px; }}
  .metric-val {{ font-size: 36px; font-weight: 800; color: #fff; }}
  .metric-label {{ font-size: 13px; color: #888; }}
  @media (max-width: 768px) {{ .scr-grid,.points-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="slide">
  <div class="headline">{data.get('headline','')}</div>

  <div class="scr-grid">
    <div class="scr-block">
      <div class="scr-label">Situação</div>
      <div class="scr-text">{data.get('situation','')}</div>
    </div>
    <div class="scr-block">
      <div class="scr-label">Complicação</div>
      <div class="scr-text">{data.get('complication','')}</div>
    </div>
    <div class="scr-block">
      <div class="scr-label">Resolução</div>
      <div class="scr-text">{data.get('resolution','')}</div>
    </div>
  </div>

  {"<div class='metric'><div><div class='metric-val'>" + str(data.get('key_metric',{}).get('value','')) + "</div><div class='metric-label'>" + str(data.get('key_metric',{}).get('label','')) + "</div></div></div>" if data.get('key_metric') else ""}

  <div class="points-grid">
    {"".join(f"<div class='point'><div class='point-label'>{p.get('label','')}</div><div class='point-detail'>{p.get('detail','')}</div></div>" for p in data.get('supporting_points',[]))}
  </div>

  <div class="next-steps">
    <h3>Próximos Passos</h3>
    {"".join(f"<div class='step'><div class='step-num'>{i+1}</div><div class='step-text'>{step}</div></div>" for i, step in enumerate(data.get('next_steps',[])))}
  </div>
</div>
</body>
</html>"""

    return html


# ===========================================================================
# Ferramenta 5: Slide Outline (para revisar antes de gerar)
# ===========================================================================

def slide_outline_generate(
    topic: str,
    slide_count: int = 10,
    goal: str = "informar",
) -> str:
    """Gera apenas o outline da apresentação para aprovação antes de criar os slides."""
    system = "Você é especialista em estrutura de apresentações. Responda APENAS em JSON."

    prompt = f"""Outline de apresentação:
TEMA: {topic}
SLIDES: {slide_count}
OBJETIVO: {goal}

JSON array simples:
[{{"slide": N, "type": "tipo", "title": "título", "key_message": "mensagem central", "content_hint": "o que mostrar"}}]"""

    raw = _gemini(prompt, system=system, max_tokens=2000)
    try:
        outline = _parse_json_response(raw)
        result = f"# Outline: {topic}\n**{slide_count} slides | Objetivo: {goal}**\n\n"
        for slide in outline:
            n = slide.get("slide", "?")
            t = slide.get("title", "?")
            km = slide.get("key_message", "")
            ch = slide.get("content_hint", "")
            result += f"**Slide {n}:** {t}\n→ *{km}*\n💡 {ch}\n\n"
        return result
    except Exception:
        return raw


# ===========================================================================
# Ferramenta 6: Converter outline JSON → HTML de apresentação
# ===========================================================================

STYLES = {
    "corporativo": {
        "bg": "#FFFFFF", "surface": "#F8FAFC", "text": "#0F172A",
        "accent": "#2563EB", "muted": "#64748B", "font": "Inter, system-ui, sans-serif",
        "slide_bg": "#1E293B", "slide_text": "#F8FAFC",
    },
    "startup": {
        "bg": "#0F0F1A", "surface": "#1A1A2E", "text": "#F2F2F7",
        "accent": "#5E6AD2", "muted": "#8A8A9A", "font": "Inter, system-ui, sans-serif",
        "slide_bg": "#0F0F1A", "slide_text": "#F2F2F7",
    },
    "dark": {
        "bg": "#000000", "surface": "#111111", "text": "#FFFFFF",
        "accent": "#A855F7", "muted": "#888888", "font": "Inter, system-ui, sans-serif",
        "slide_bg": "#000000", "slide_text": "#FFFFFF",
    },
    "minimalista": {
        "bg": "#FAFAFA", "surface": "#FFFFFF", "text": "#1E1E1E",
        "accent": "#000000", "muted": "#737373", "font": "system-ui, sans-serif",
        "slide_bg": "#FFFFFF", "slide_text": "#1E1E1E",
    },
    "criativo": {
        "bg": "#1A0533", "surface": "#2D0A5B", "text": "#F5F0FF",
        "accent": "#FF6B6B", "muted": "#C084FC", "font": "Inter, system-ui, sans-serif",
        "slide_bg": "#1A0533", "slide_text": "#F5F0FF",
    },
}


def presentation_to_html(
    slides: list[dict],
    style: str = "startup",
    title: str = "Apresentação",
    subtitle: str = "",
) -> str:
    """
    Converte uma lista de slides (JSON) em HTML interativo de apresentação.
    Navegação por teclado (← →), fullscreen, modo apresentador.
    """
    s = STYLES.get(style, STYLES["startup"])

    def render_slide(slide: dict, index: int) -> str:
        stype = slide.get("type", "content")
        stitle = slide.get("title", "")
        subtitle_s = slide.get("subtitle", "")
        key_msg = slide.get("key_message", "")
        bullets = slide.get("bullet_points", [])
        notes = slide.get("speaker_notes", "")
        quote = slide.get("quote", {})
        data = slide.get("data", {})
        vc_tip = slide.get("vc_tip", "")

        is_cover = stype in ("cover", "thank_you")
        bg_extra = f"background: linear-gradient(135deg, {s['accent']}22 0%, transparent 60%);" if is_cover else ""

        bullets_html = ""
        if bullets:
            bullets_html = "<ul class='bullets'>" + "".join(
                f"<li>{b}</li>" for b in bullets[:5]
            ) + "</ul>"

        quote_html = ""
        if quote and quote.get("text"):
            quote_html = f"""<blockquote class="quote">
              <p>"{quote['text']}"</p>
              <cite>— {quote.get('author','')}{', ' + quote.get('role','') if quote.get('role') else ''}</cite>
            </blockquote>"""

        data_html = ""
        if data and data.get("type") != "none" and data.get("description"):
            data_html = f"<div class='data-block'>📊 {data['description']}</div>"

        tip_html = f"<div class='vc-tip'>💡 <strong>VC Insight:</strong> {vc_tip}</div>" if vc_tip else ""
        notes_html = f"<div class='notes' data-notes='{notes}'></div>" if notes else ""

        center_class = " center" if is_cover else ""

        return f"""
        <div class="slide{center_class}" data-index="{index}" style="{bg_extra}">
          <div class="slide-number">{index + 1}/{len(slides)}</div>
          {"<div class='slide-type-badge'>" + stype.upper() + "</div>" if not is_cover else ""}
          <div class="slide-content">
            <h1 class="slide-title {'big' if is_cover else ''}">{stitle}</h1>
            {"<p class='slide-subtitle'>" + subtitle_s + "</p>" if subtitle_s else ""}
            {"<p class='key-message'>" + key_msg + "</p>" if key_msg and not is_cover else ""}
            {bullets_html}
            {quote_html}
            {data_html}
            {tip_html}
          </div>
          {notes_html}
        </div>"""

    slides_html = "\n".join(render_slide(slide, i) for i, slide in enumerate(slides))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:{s['font']};background:{s['bg']};color:{s['text']};
       height:100vh;overflow:hidden;user-select:none}}

  .presentation{{width:100%;height:100vh;position:relative}}

  .slide{{
    position:absolute;inset:0;
    background:{s['slide_bg']};color:{s['slide_text']};
    display:flex;flex-direction:column;justify-content:center;
    padding:80px;opacity:0;pointer-events:none;
    transition:opacity .4s cubic-bezier(.19,1,.22,1),transform .4s cubic-bezier(.19,1,.22,1);
    transform:translateX(60px);
  }}
  .slide.active{{opacity:1;pointer-events:all;transform:translateX(0)}}
  .slide.prev{{transform:translateX(-60px)}}
  .slide.center{{align-items:center;text-align:center}}

  .slide-number{{
    position:absolute;bottom:32px;right:48px;
    font-size:12px;color:{s['muted']};font-weight:500;letter-spacing:.05em;
  }}
  .slide-type-badge{{
    position:absolute;top:32px;left:48px;
    font-size:10px;font-weight:700;letter-spacing:.12em;
    color:{s['accent']};text-transform:uppercase;
  }}

  .slide-content{{max-width:860px}}
  .slide-title{{
    font-size:clamp(28px,4vw,52px);font-weight:800;line-height:1.1;
    letter-spacing:-.03em;margin-bottom:20px;
  }}
  .slide-title.big{{font-size:clamp(36px,5.5vw,72px)}}
  .slide-subtitle{{font-size:clamp(16px,2vw,22px);color:{s['muted']};margin-bottom:28px}}
  .key-message{{
    font-size:clamp(15px,1.6vw,20px);color:{s['accent']};
    font-weight:500;margin-bottom:28px;line-height:1.5;
    padding-left:20px;border-left:3px solid {s['accent']};
  }}

  .bullets{{list-style:none;display:flex;flex-direction:column;gap:14px}}
  .bullets li{{
    font-size:clamp(14px,1.5vw,18px);line-height:1.5;
    padding-left:28px;position:relative;color:{s['slide_text']};opacity:.9;
  }}
  .bullets li::before{{
    content:'';position:absolute;left:0;top:8px;
    width:8px;height:8px;border-radius:50%;
    background:{s['accent']};
  }}

  .quote{{
    margin-top:24px;padding:24px 28px;
    border-left:4px solid {s['accent']};
    background:rgba(255,255,255,.04);border-radius:0 12px 12px 0;
  }}
  .quote p{{font-size:18px;font-style:italic;line-height:1.6;margin-bottom:12px}}
  .quote cite{{font-size:14px;color:{s['muted']};font-style:normal}}

  .data-block{{
    margin-top:24px;padding:20px;
    background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
    border-radius:12px;font-size:15px;color:{s['muted']};
  }}

  .vc-tip{{
    margin-top:20px;padding:16px 20px;
    background:rgba(168,85,247,.08);border:1px solid rgba(168,85,247,.2);
    border-radius:10px;font-size:13px;color:#C084FC;line-height:1.5;
  }}

  /* CONTROLES */
  .controls{{
    position:fixed;bottom:32px;left:50%;transform:translateX(-50%);
    display:flex;gap:12px;align-items:center;z-index:100;
  }}
  .btn-ctrl{{
    width:44px;height:44px;border-radius:50%;border:1px solid rgba(255,255,255,.15);
    background:rgba(255,255,255,.06);color:#fff;cursor:pointer;font-size:18px;
    display:flex;align-items:center;justify-content:center;
    transition:all .2s;backdrop-filter:blur(8px);
  }}
  .btn-ctrl:hover{{background:rgba(255,255,255,.15);transform:scale(1.05)}}

  .progress-bar{{
    position:fixed;top:0;left:0;height:3px;
    background:{s['accent']};transition:width .4s var(--ease);z-index:200;
  }}

  /* NOTAS DO APRESENTADOR */
  .presenter-panel{{
    position:fixed;bottom:0;left:0;right:0;max-height:0;overflow:hidden;
    background:rgba(0,0,0,.95);border-top:1px solid rgba(255,255,255,.1);
    transition:max-height .3s ease;z-index:300;padding:0 48px;
  }}
  .presenter-panel.open{{max-height:200px;padding:20px 48px}}
  .presenter-notes-text{{font-size:14px;color:#aaa;line-height:1.7}}

  @media(max-width:768px){{
    .slide{{padding:40px 24px}}
    .controls{{bottom:16px}}
  }}
</style>
</head>
<body>
<div class="progress-bar" id="progress"></div>
<div class="presentation" id="pres">
{slides_html}
</div>

<div class="controls">
  <button class="btn-ctrl" onclick="prev()" title="Anterior (←)">‹</button>
  <button class="btn-ctrl" onclick="toggleNotes()" title="Notas (N)">📝</button>
  <button class="btn-ctrl" onclick="toggleFullscreen()" title="Fullscreen (F)">⛶</button>
  <button class="btn-ctrl" onclick="next()" title="Próximo (→)">›</button>
</div>

<div class="presenter-panel" id="panel">
  <p style="font-size:11px;color:#555;margin-bottom:8px;text-transform:uppercase;letter-spacing:.08em">NOTAS DO APRESENTADOR</p>
  <p class="presenter-notes-text" id="notes-text"></p>
</div>

<script>
const slides = document.querySelectorAll('.slide');
const notes = [...slides].map(s => s.querySelector('[data-notes]')?.dataset.notes || '');
let cur = 0;

function show(n) {{
  slides[cur].classList.remove('active');
  slides[cur].classList.add('prev');
  setTimeout(() => slides[cur].classList.remove('prev'), 400);
  cur = Math.max(0, Math.min(n, slides.length - 1));
  slides[cur].classList.add('active');
  document.getElementById('progress').style.width = ((cur + 1) / slides.length * 100) + '%';
  document.getElementById('notes-text').textContent = notes[cur];
}}

function next() {{ if (cur < slides.length - 1) show(cur + 1); }}
function prev() {{ if (cur > 0) show(cur - 1); }}
function toggleNotes() {{
  const p = document.getElementById('panel');
  p.classList.toggle('open');
}}
function toggleFullscreen() {{
  if (!document.fullscreenElement) document.documentElement.requestFullscreen();
  else document.exitFullscreen();
}}

document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === ' ') next();
  if (e.key === 'ArrowLeft') prev();
  if (e.key === 'f' || e.key === 'F') toggleFullscreen();
  if (e.key === 'n' || e.key === 'N') toggleNotes();
}});

// Touch/swipe
let tx = 0;
document.addEventListener('touchstart', e => {{ tx = e.touches[0].clientX; }});
document.addEventListener('touchend', e => {{
  const dx = e.changedTouches[0].clientX - tx;
  if (Math.abs(dx) > 50) {{ dx < 0 ? next() : prev(); }}
}});

show(0);
</script>
</body>
</html>"""
