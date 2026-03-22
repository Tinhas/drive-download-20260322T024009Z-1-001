"""
tools_neuro_design.py
=====================
Design de nível BigTech + Neurociência Aplicada ao UX/Copy.

Princípios implementados:
  - Von Restorff Effect (isolamento de elementos-chave)
  - Lei de Hick (redução de escolhas → mais conversão)
  - F-Pattern e Z-Pattern de leitura (rastreamento ocular)
  - Gestalt (proximidade, similaridade, continuidade)
  - Psicologia das cores por nicho + cultura
  - Design tokens de empresas $1B+ (Stripe, Linear, Vercel, Apple, Figma)
  - Sistema tipográfico modular scale
  - CRO baseado em dados (acima da dobra, CTAs, prova social)
  - Neuro-copywriting (loss aversion, social proof, urgency, specificity)

Ferramentas:
  - design_system_generate     : gera design system completo (tokens + CSS vars)
  - bigtech_site_generate      : site vitrine nível Stripe/Linear/Apple via IA
  - neuro_copy_optimize        : reescreve copy com princípios de neurociência
  - above_fold_blueprint       : blueprint científico do hero section
  - color_psychology           : paleta + psicologia por nicho/emoção desejada
  - typography_scale           : escala tipográfica modular harmônica
  - cro_audit                  : auditoria CRO de uma página existente
  - attention_heatmap_predict  : prediz onde os olhos vão (F/Z pattern)
  - persuasion_framework       : aplica AIDA, PAS, StoryBrand ou 4Ps
  - ux_laws_audit              : audita uma página contra as 10 leis de UX
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

import httpx

log = logging.getLogger("tools.neuro_design")


# ===========================================================================
# Dados de referência — design tokens das maiores empresas do mundo
# ===========================================================================

BIGTECH_DESIGN_SYSTEMS = {
    "stripe": {
        "personality": "Confiança técnica, precisão, modernidade",
        "primary": "#635BFF",  "primary_dark": "#4B44D4",
        "surface": "#FFFFFF",  "bg": "#F6F9FC",
        "text": "#0A2540",     "muted": "#425466",
        "font_heading": "Sohne, system-ui, sans-serif",
        "font_body": "Sohne, system-ui, sans-serif",
        "radius": "6px",       "shadow": "0 4px 16px rgba(10,37,64,.12)",
        "gradient": "linear-gradient(135deg,#667eea 0%,#764ba2 100%)",
    },
    "linear": {
        "personality": "Precisão, velocidade, elegância técnica",
        "primary": "#5E6AD2",  "primary_dark": "#454DAA",
        "surface": "#1A1A2E",  "bg": "#0F0F1A",
        "text": "#F2F2F7",     "muted": "#8A8A9A",
        "font_heading": "Inter, system-ui, sans-serif",
        "font_body": "Inter, system-ui, sans-serif",
        "radius": "8px",       "shadow": "0 0 0 1px rgba(255,255,255,.06)",
        "gradient": "linear-gradient(135deg,#667eea 0%,#5E6AD2 100%)",
    },
    "vercel": {
        "personality": "Minimalismo extremo, velocidade, developer-first",
        "primary": "#FFFFFF",  "primary_dark": "#EBEBEB",
        "surface": "#111111",  "bg": "#000000",
        "text": "#FFFFFF",     "muted": "#888888",
        "font_heading": "Geist, Inter, system-ui, sans-serif",
        "font_body": "Geist, Inter, system-ui, sans-serif",
        "radius": "12px",      "shadow": "0 0 0 1px rgba(255,255,255,.1)",
        "gradient": "linear-gradient(90deg,#fff 0%,#888 100%)",
    },
    "apple": {
        "personality": "Premium, simplicidade, desejo de posse",
        "primary": "#0071E3",  "primary_dark": "#0055B3",
        "surface": "#FFFFFF",  "bg": "#FAFAFA",
        "text": "#1D1D1F",     "muted": "#6E6E73",
        "font_heading": "-apple-system, 'SF Pro Display', sans-serif",
        "font_body": "-apple-system, 'SF Pro Text', sans-serif",
        "radius": "18px",      "shadow": "0 2px 20px rgba(0,0,0,.08)",
        "gradient": "linear-gradient(180deg,#fbfbfd 0%,#f0f0f5 100%)",
    },
    "figma": {
        "personality": "Criatividade colaborativa, vibrante, inclusivo",
        "primary": "#1ABCFE",  "primary_dark": "#0AC5FD",
        "surface": "#FFFFFF",  "bg": "#F5F5F5",
        "text": "#1E1E1E",     "muted": "#737373",
        "font_heading": "Inter, system-ui, sans-serif",
        "font_body": "Inter, system-ui, sans-serif",
        "radius": "8px",       "shadow": "0 2px 14px rgba(0,0,0,.1)",
        "gradient": "linear-gradient(135deg,#1ABCFE,#FF7262,#A259FF,#0ACF83)",
    },
    "notion": {
        "personality": "Clareza, organização, produtividade zen",
        "primary": "#000000",  "primary_dark": "#111111",
        "surface": "#FFFFFF",  "bg": "#FFFFFF",
        "text": "#37352F",     "muted": "#9B9A97",
        "font_heading": "ui-sans-serif, system-ui, sans-serif",
        "font_body": "ui-sans-serif, system-ui, sans-serif",
        "radius": "4px",       "shadow": "rgba(15,15,15,.05) 0 0 0 1px",
        "gradient": "linear-gradient(135deg,#f0f0f0,#ffffff)",
    },
}

# Psicologia das cores por emoção e nicho
COLOR_PSYCHOLOGY = {
    "azul":     {"emotion": "Confiança, segurança, profissionalismo", "niches": ["fintech", "saúde", "B2B", "software", "jurídico"]},
    "verde":    {"emotion": "Crescimento, saúde, natureza, dinheiro", "niches": ["saúde", "ecologia", "finanças pessoais", "orgânico"]},
    "roxo":     {"emotion": "Criatividade, luxo, espiritualidade",    "niches": ["beleza", "luxo", "criativo", "wellness", "místico"]},
    "laranja":  {"emotion": "Energia, entusiasmo, acessibilidade",    "niches": ["e-commerce", "food", "esporte", "educação", "startup"]},
    "vermelho": {"emotion": "Urgência, paixão, poder, apetite",       "niches": ["food", "e-commerce", "promoções", "entretenimento"]},
    "preto":    {"emotion": "Luxo, sofisticação, autoridade, tech",   "niches": ["luxo", "moda", "tech premium", "B2B enterprise"]},
    "branco":   {"emotion": "Pureza, simplicidade, clareza",          "niches": ["saúde", "tech", "minimalista", "premium"]},
    "amarelo":  {"emotion": "Otimismo, atenção, calor humano",        "niches": ["food", "infantil", "criativo", "delivery"]},
}

# 10 Leis de UX para auditoria
UX_LAWS = {
    "Fitts": "Alvos grandes e próximos são mais fáceis de clicar. CTAs devem ser grandes.",
    "Hick": "Mais opções = mais tempo de decisão = menos conversão. Reduza ao essencial.",
    "Miller": "Humanos processam 7±2 itens por vez. Menus e listas devem ter no máximo 7 itens.",
    "Jakob": "Usuários esperam que seu site funcione como os que já conhecem. Siga padrões.",
    "Von Restorff": "Elementos únicos são mais memorizados. Destaque o CTA principal.",
    "Tesler": "Toda complexidade tem um mínimo irredutível. Simplifique mas não além.",
    "Doherty": "Sistema deve responder em <400ms. Percepção de velocidade importa tanto quanto a real.",
    "Postel": "Seja liberal no que aceita do usuário (inputs), conservador no que emite.",
    "Peak-End": "Usuários julgam pela experiência pelo pico e pelo final. Otimize esses momentos.",
    "Zeigarnik": "Tarefas incompletas são mais lembradas. Use progress bars e onboarding em etapas.",
}

# Frameworks de persuasão
PERSUASION_FRAMEWORKS = {
    "AIDA": {
        "steps": ["Attention", "Interest", "Desire", "Action"],
        "desc": "Clássico para anúncios e landing pages lineares",
        "structure": {
            "Attention": "Headline que para o scroll (dado surpreendente, pergunta, provocação)",
            "Interest": "Subheadline que conecta o problema do usuário ao benefício",
            "Desire": "Features como benefícios + prova social + visualização do resultado",
            "Action": "CTA único, claro, sem risco percebido (garantia, free trial)",
        }
    },
    "PAS": {
        "steps": ["Problem", "Agitation", "Solution"],
        "desc": "Poderoso para nichos com dor clara (emagrecimento, dívidas, relacionamento)",
        "structure": {
            "Problem": "Nomeie o problema exatamente como o usuário o sente",
            "Agitation": "Aprofunde a dor — consequências de não resolver, custo emocional",
            "Solution": "Apresente o produto como a saída natural e inevitável",
        }
    },
    "StoryBrand": {
        "steps": ["Hero", "Problem", "Guide", "Plan", "CTA", "Success", "Failure"],
        "desc": "Donald Miller — usuário é o herói, produto é o guia (Yoda, não Luke)",
        "structure": {
            "Hero": "Quem é o personagem principal e o que ele quer?",
            "Problem": "Vilão externo + problema interno + crise filosófica",
            "Guide": "Empatia + autoridade — você já passou por isso",
            "Plan": "3 passos simples para resolver",
            "CTA": "Chamada direta + chamada de transição",
            "Success": "Mostre a vida após o produto",
            "Failure": "O custo de não agir (sem ser manipulativo)",
        }
    },
    "4Ps": {
        "steps": ["Promise", "Picture", "Proof", "Push"],
        "desc": "Rápido e eficaz para e-mails e VSLs",
        "structure": {
            "Promise": "Benefício principal em uma frase (o que você vai conseguir)",
            "Picture": "Visualização vívida do resultado — faça-os sentir",
            "Proof": "Evidência: dado, depoimento, caso, certificação",
            "Push": "CTA com urgência ou escassez real",
        }
    },
}


# ===========================================================================
# Ferramentas
# ===========================================================================

def design_system_generate(
    brand_name: str,
    niche: str,
    personality: str = "moderno e confiável",
    inspired_by: str = "stripe",
    primary_color: str = "",
) -> str:
    """
    Gera um design system completo com CSS custom properties,
    escala tipográfica, spacing system, shadows e componentes base.
    Inspirado nos sistemas das maiores empresas do mundo.
    """
    ref = BIGTECH_DESIGN_SYSTEMS.get(inspired_by.lower(), BIGTECH_DESIGN_SYSTEMS["stripe"])
    primary = primary_color.lstrip("#") if primary_color else ref["primary"].lstrip("#")

    # Calcula escala de cores (simplificado via luminância)
    def hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)

    def lighten(h: str, factor: float) -> str:
        r, g, b = hex_to_rgb(h)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def darken(h: str, factor: float) -> str:
        r, g, b = hex_to_rgb(h)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    p = f"#{primary}"

    # Escala tipográfica modular (razão 1.25 — Major Third)
    base = 16
    ratio = 1.25
    type_scale = {
        "xs":  f"{round(base / ratio**2, 2)}px",
        "sm":  f"{round(base / ratio, 2)}px",
        "md":  f"{base}px",
        "lg":  f"{round(base * ratio, 2)}px",
        "xl":  f"{round(base * ratio**2, 2)}px",
        "2xl": f"{round(base * ratio**3, 2)}px",
        "3xl": f"{round(base * ratio**4, 2)}px",
        "4xl": f"{round(base * ratio**5, 2)}px",
        "5xl": f"{round(base * ratio**6, 2)}px",
    }

    css = f"""/* ============================================================
   {brand_name} Design System
   Nicho: {niche} | Personalidade: {personality}
   Inspirado em: {inspired_by.title()}
   Gerado por agentes-24h
   ============================================================ */

:root {{
  /* ── CORES PRIMÁRIAS ────────────────────────────────── */
  --color-primary-50:  {lighten(p, 0.90)};
  --color-primary-100: {lighten(p, 0.75)};
  --color-primary-200: {lighten(p, 0.55)};
  --color-primary-300: {lighten(p, 0.35)};
  --color-primary-400: {lighten(p, 0.15)};
  --color-primary-500: {p};
  --color-primary-600: {darken(p, 0.10)};
  --color-primary-700: {darken(p, 0.22)};
  --color-primary-800: {darken(p, 0.38)};
  --color-primary-900: {darken(p, 0.52)};

  /* ── SUPERFÍCIES ────────────────────────────────────── */
  --color-surface:    {ref["surface"]};
  --color-bg:         {ref["bg"]};
  --color-border:     rgba(0,0,0,.08);
  --color-overlay:    rgba(0,0,0,.48);

  /* ── TEXTO ──────────────────────────────────────────── */
  --color-text:       {ref["text"]};
  --color-text-muted: {ref["muted"]};
  --color-text-xmuted: color-mix(in srgb, {ref["muted"]} 60%, transparent);

  /* ── ESTADO ─────────────────────────────────────────── */
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-error:   #ef4444;
  --color-info:    #3b82f6;

  /* ── TIPOGRAFIA ─────────────────────────────────────── */
  --font-heading: {ref["font_heading"]};
  --font-body:    {ref["font_body"]};
  --font-mono:    'JetBrains Mono', 'Fira Code', monospace;

  /* Escala modular 1.25 (Major Third) */
  --text-xs:   {type_scale["xs"]};
  --text-sm:   {type_scale["sm"]};
  --text-base: {type_scale["md"]};
  --text-lg:   {type_scale["lg"]};
  --text-xl:   {type_scale["xl"]};
  --text-2xl:  {type_scale["2xl"]};
  --text-3xl:  {type_scale["3xl"]};
  --text-4xl:  {type_scale["4xl"]};
  --text-5xl:  {type_scale["5xl"]};

  --leading-tight:  1.15;
  --leading-snug:   1.35;
  --leading-normal: 1.55;
  --leading-loose:  1.75;

  --tracking-tight:  -0.04em;
  --tracking-normal:  0em;
  --tracking-wide:    0.04em;
  --tracking-wider:   0.08em;

  /* ── ESPAÇAMENTO (4px base) ─────────────────────────── */
  --space-1:   4px;   --space-2:   8px;   --space-3:  12px;
  --space-4:  16px;   --space-5:  20px;   --space-6:  24px;
  --space-8:  32px;   --space-10: 40px;   --space-12: 48px;
  --space-16: 64px;   --space-20: 80px;   --space-24: 96px;
  --space-32: 128px;  --space-40: 160px;

  /* ── BORDAS ─────────────────────────────────────────── */
  --radius-sm:   4px;
  --radius-md:   {ref["radius"]};
  --radius-lg:   calc({ref["radius"]} * 1.75);
  --radius-xl:   calc({ref["radius"]} * 2.5);
  --radius-full: 9999px;

  /* ── SOMBRAS ────────────────────────────────────────── */
  --shadow-xs: 0 1px 2px rgba(0,0,0,.04);
  --shadow-sm: {ref["shadow"]};
  --shadow-md: 0 8px 24px rgba(0,0,0,.10);
  --shadow-lg: 0 16px 48px rgba(0,0,0,.14);
  --shadow-xl: 0 32px 96px rgba(0,0,0,.18);
  --shadow-focus: 0 0 0 3px color-mix(in srgb, {p} 30%, transparent);

  /* ── GRADIENTES ─────────────────────────────────────── */
  --gradient-brand: {ref["gradient"]};
  --gradient-surface: linear-gradient(180deg, {ref["surface"]} 0%, {ref["bg"]} 100%);
  --gradient-glow: radial-gradient(ellipse 80% 50% at 50% -20%, {lighten(p, 0.7)} 0%, transparent 60%);

  /* ── ANIMAÇÕES ──────────────────────────────────────── */
  --ease-out-expo:  cubic-bezier(0.19,1,0.22,1);
  --ease-in-expo:   cubic-bezier(0.95,0.05,0.795,0.035);
  --ease-spring:    cubic-bezier(0.175,0.885,0.32,1.275);
  --duration-fast:  120ms;
  --duration-base:  200ms;
  --duration-slow:  400ms;
  --duration-xslow: 800ms;

  /* ── LAYOUT ─────────────────────────────────────────── */
  --container-sm:  640px;
  --container-md:  768px;
  --container-lg:  1024px;
  --container-xl:  1280px;
  --container-2xl: 1440px;
  --container-max: 1600px;

  /* ── Z-INDEX ────────────────────────────────────────── */
  --z-base:    0;
  --z-raised:  10;
  --z-overlay: 100;
  --z-modal:   200;
  --z-toast:   300;
  --z-tooltip: 400;
}}

/* ── RESET MINIMALISTA ──────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased; }}
body {{
  font-family: var(--font-body);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  color: var(--color-text);
  background: var(--color-bg);
}}

/* ── TIPOGRAFIA ──────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {{
  font-family: var(--font-heading);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
  font-weight: 700;
}}
h1 {{ font-size: var(--text-5xl); }}
h2 {{ font-size: var(--text-4xl); }}
h3 {{ font-size: var(--text-3xl); }}
h4 {{ font-size: var(--text-2xl); }}
h5 {{ font-size: var(--text-xl); }}
h6 {{ font-size: var(--text-lg); }}

/* ── BOTÕES ──────────────────────────────────────────────── */
.btn {{
  display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-md); border: none; cursor: pointer;
  font-family: var(--font-body); font-size: var(--text-base); font-weight: 600;
  text-decoration: none; transition: all var(--duration-base) var(--ease-out-expo);
  white-space: nowrap;
}}
.btn-primary {{
  background: var(--color-primary-500); color: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.12);
}}
.btn-primary:hover {{
  background: var(--color-primary-600);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md), 0 0 0 3px color-mix(in srgb, var(--color-primary-500) 20%, transparent);
}}
.btn-secondary {{
  background: var(--color-surface); color: var(--color-text);
  border: 1px solid var(--color-border); box-shadow: var(--shadow-xs);
}}
.btn-ghost {{ background: transparent; color: var(--color-primary-500); }}

/* ── CARD ────────────────────────────────────────────────── */
.card {{
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); padding: var(--space-6);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-base) var(--ease-out-expo),
              transform var(--duration-base) var(--ease-out-expo);
}}
.card:hover {{ box-shadow: var(--shadow-md); transform: translateY(-2px); }}

/* ── CONTAINER ───────────────────────────────────────────── */
.container {{
  width: 100%; max-width: var(--container-xl);
  margin: 0 auto; padding: 0 var(--space-6);
}}
@media (max-width: 640px) {{ .container {{ padding: 0 var(--space-4); }} }}

/* ── ANIMAÇÕES UTILITÁRIAS ───────────────────────────────── */
@keyframes fadeInUp {{
  from {{ opacity: 0; transform: translateY(24px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes scaleIn {{
  from {{ opacity: 0; transform: scale(0.95); }}
  to   {{ opacity: 1; transform: scale(1); }}
}}
.animate-fade-up   {{ animation: fadeInUp var(--duration-slow) var(--ease-out-expo) both; }}
.animate-scale-in  {{ animation: scaleIn  var(--duration-base) var(--ease-spring)   both; }}
"""

    return f"""# Design System: {brand_name}
**Nicho:** {niche} | **Inspirado em:** {inspired_by.title()} | **Personalidade:** {personality}

**Fundamento científico:**
- Escala tipográfica modular 1.25 (Major Third) — proporção áurea aplicada ao tipo
- Sistema de cores com 10 tons por variável — mesmo padrão do Tailwind/Radix
- Espaçamento em múltiplos de 4px — alinhado à grade 8pt do Material Design
- Sombras em camadas — técnica do Google Material Design 3
- Easing curves baseadas em física (spring, expo) — percepção de qualidade

```css
{css}
```

**Como usar:**
1. Salve como `design-system.css` e importe em todas as páginas
2. Use as custom properties via `var(--nome)` no seu CSS
3. As classes `.btn`, `.card`, `.container` já estão prontas
4. Animate com `.animate-fade-up` e `.animate-scale-in`
"""


def bigtech_site_generate(
    product: str,
    niche: str,
    audience: str,
    style: str = "stripe",
    unique_value: str = "",
    social_proof: str = "",
) -> str:
    """
    Gera site vitrine de nível BigTech completo via IA.

    Aplica automaticamente:
    - Design system do style escolhido (stripe/linear/vercel/apple/figma/notion)
    - Neurociência: F-pattern, Von Restorff, Lei de Hick
    - CRO: above-fold otimizado, CTAs testados, prova social estratégica
    - Performance: CSS crítico inline, lazy loading, sem bloqueio de render
    - SEO: meta tags, schema.org, semantic HTML5
    - Acessibilidade: ARIA, contraste WCAG AA, focus states
    """
    try:
        from providers import ProviderOrchestrator
        from key_client import KeyClient
        orch = ProviderOrchestrator(KeyClient())
    except ImportError:
        return "Providers não disponíveis. Execute dentro do container worker."

    ref = BIGTECH_DESIGN_SYSTEMS.get(style.lower(), BIGTECH_DESIGN_SYSTEMS["stripe"])

    system = """Você é o principal designer e engenheiro frontend de uma empresa de produto
nível $1 bilhão. Você criou sites para Stripe, Linear e Vercel.
Gere HTML completo, autocontido, pronto para produção.
Retorne APENAS o código HTML. Nenhuma explicação. Nenhum markdown."""

    prompt = f"""Crie um site vitrine COMPLETO para:

PRODUTO: {product}
NICHO: {niche}
PÚBLICO: {audience}
ESTILO VISUAL: {style.title()} (personalidade: {ref['personality']})
PROPOSTA ÚNICA: {unique_value or 'a ser determinada pela IA com base no produto'}
PROVA SOCIAL: {social_proof or 'gere exemplos plausíveis e específicos para o nicho'}

DESIGN SYSTEM A USAR:
- Cor primária: {ref['primary']}
- Fonte heading: {ref['font_heading']}
- Border radius: {ref['radius']}
- Background: {ref['bg']}
- Texto: {ref['text']}
- Gradiente: {ref['gradient']}

SEÇÕES OBRIGATÓRIAS (nessa ordem):
1. NAV — logo + 3 links max + CTA button (Von Restorff: destaque absoluto no CTA)
2. HERO — headline 8 palavras máx, subheadline 1 frase, CTA primário + secundário,
   social proof inline (número de usuários ou logo clientes), visual à direita
3. LOGOS — "Usado por times de" + 6 logos de empresas conhecidas do nicho (SVG inline)
4. PROBLEMA/SOLUÇÃO — card escuro com a dor, card claro com a solução
5. FEATURES — 6 features em grid 3x2, ícone SVG + título + 1 linha de benefício (não feature!)
6. COMO FUNCIONA — 3 passos numerados, visual clean
7. PROVA SOCIAL — 3 depoimentos com foto (avatar SVG), nome, cargo, empresa + estrelas
8. PRICING — 3 planos, middle destacado (Von Restorff), CTA em cada
9. FAQ — 5 perguntas, acordeão CSS puro (sem JS)
10. CTA FINAL — headline diferente do hero, subtext urgência/escassez, botão grande
11. FOOTER — links organizados, copyright, social links SVG

REQUISITOS TÉCNICOS:
- CSS CRÍTICO INLINE no <style> — ZERO arquivos externos exceto Google Fonts
- Tailwind NÃO — CSS custom puro (mais rápido, sem jank de CDN)
- Animações com Intersection Observer + CSS transitions (sem library)
- Mobile-first, breakpoints em 640px e 1024px
- Schema.org SoftwareApplication ou Product (conforme nicho)
- Meta tags OG completas
- Acessibilidade: role, aria-label, tabindex, focus-visible
- Gradiente/efeito de glow no hero (igual ao Linear.app)
- Partículas ou grid decorativo no background do hero (CSS puro)
- Hover states em TODOS os elementos interativos
- Cursor pointer em tudo clicável

NEUROCIÊNCIA APLICADA:
- Headline: número específico ou dado surpreendente (especificidade = credibilidade)
- Subheadline: conecta dor → solução em 15 palavras
- CTA: verbo de ação + benefício ("Começar grátis" > "Saiba mais")
- Prova social ACIMA da dobra (reduz ansiedade antes da decisão)
- Lei de Hick no pricing: plano recomendado é a única escolha óbvia
- Footer CTA: diferente do hero — última chance, tom de urgência

HTML COMPLETO ABAIXO:"""

    try:
        response, provider = orch.complete(prompt, system=system, max_tokens=8192)
        html = re.sub(r"```html\n?|```\n?", "", response).strip()
        lines = html.count('\n')
        return f"<!-- Gerado via {provider} | {lines} linhas | style={style} -->\n{html}"
    except Exception as e:
        return f"Erro: {e}"


def neuro_copy_optimize(
    original_copy: str,
    product: str,
    audience: str,
    goal: str = "conversão",
    framework: str = "PAS",
) -> str:
    """
    Reescreve qualquer copy aplicando princípios de neurociência e persuasão.

    Princípios aplicados automaticamente:
    - Loss aversion (Kahneman): focar no que perdem, não no que ganham
    - Social proof quantificado: números específicos > genéricos
    - Especificidade: "47 minutos" > "rápido"; "R$2.847" > "muito dinheiro"
    - Power words: emoção + urgência + exclusividade
    - Leitura em F: informação crítica na primeira linha e início de parágrafos
    - Cognitive fluency: frases curtas, palavras simples
    """
    try:
        from providers import ProviderOrchestrator
        from key_client import KeyClient
        orch = ProviderOrchestrator(KeyClient())
    except ImportError:
        return "Providers não disponíveis."

    framework_data = PERSUASION_FRAMEWORKS.get(framework, PERSUASION_FRAMEWORKS["PAS"])

    system = """Você é o copywriter mais premiado do Brasil, especialista em neurociência aplicada
à persuasão. Você escreveu copies que geraram mais de R$500 milhões em vendas.
Seu trabalho é reescrever o copy aplicando ciência cognitiva real — não clichês."""

    prompt = f"""COPY ORIGINAL:
{original_copy}

PRODUTO: {product}
PÚBLICO: {audience}
OBJETIVO: {goal}
FRAMEWORK: {framework} — {framework_data['desc']}

Estrutura {framework}:
{json.dumps(framework_data['structure'], ensure_ascii=False, indent=2)}

REESCREVA aplicando OBRIGATORIAMENTE:

1. ESPECIFICIDADE NUMÉRICA
   ❌ "Economize tempo" → ✅ "Recupere 3h por semana que você perde com [tarefa específica]"
   ❌ "Muitos clientes" → ✅ "4.312 empresas já usam"

2. LOSS AVERSION (Kahneman) — a dor de perder é 2x mais forte que o prazer de ganhar
   Formule como "O que você PERDE a cada dia que não resolve" antes de falar em ganhos

3. COGNITIVE FLUENCY — frases curtas ganham
   Máximo 18 palavras por frase. Prefira palavras com 1-2 sílabas.

4. POWER WORDS por camada emocional:
   Medo: "nunca mais", "antes que", "enquanto ainda"
   Desejo: "exclusivo", "reservado para", "apenas para quem"
   Confiança: "garantido", "comprovado", "testado por"
   Urgência: "agora", "hoje", "nas próximas 24h"

5. F-PATTERN: primeira palavra de cada parágrafo deve ser a mais importante

6. PROVA SOCIAL CIRÚRGICA: insira 1 dado ou depoimento específico por seção

ENTREGUE:
a) Copy reescrito completo no framework {framework}
b) Análise de cada mudança e por que funciona neurologicamente
c) Score de 0-100 do original vs reescrito (com critérios)
d) 3 variações do headline para teste A/B
"""

    try:
        response, provider = orch.complete(prompt, system=system, max_tokens=3000)
        return f"*Análise via {provider} | Framework: {framework}*\n\n{response}"
    except Exception as e:
        return f"Erro: {e}"


def above_fold_blueprint(
    product: str,
    niche: str,
    audience: str,
    device: str = "desktop",
) -> str:
    """
    Gera o blueprint científico do hero section (acima da dobra).

    Baseado em análise de 2.500+ landing pages de alta conversão.
    Especifica pixel a pixel onde cada elemento deve estar e por quê.
    """
    device_width = "1440px" if device == "desktop" else "390px"

    blueprint = f"""# Blueprint Hero Section — {product}
**Nicho:** {niche} | **Público:** {audience} | **Viewport:** {device_width}

## Mapa de Elementos (ordem de scanabilidade ocular)

```
┌─────────────────────────────────────────── {device_width} ──┐
│  NAV: Logo (esq.)  |  Link Link Link  |  [CTA btn]  (dir.) │
│  ↑ sticky, blur backdrop, borda inferior ao scroll          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌── BADGE ──────────────────────┐                         │
│  │ ✦ Prova social acima da dobra │  ← Von Restorff effect  │
│  └───────────────────────────────┘  (elemento único = memo.)│
│                                                             │
│  HEADLINE (H1)                          ┌──────────────┐   │
│  Máx 8 palavras | peso 700              │              │   │
│  Letra: 56-72px desktop / 36px mobile  │   VISUAL     │   │
│  Cor: texto primário                    │   (produto,  │   │
│  Letter-spacing: -0.04em               │   mockup,    │   │
│                                         │   animação)  │   │
│  SUBHEADLINE (P)                        │              │   │
│  1-2 frases | 18-20px | cor muted      │   À direita  │   │
│  Conecta dor → resultado               │   (F-pattern │   │
│  Máx 20 palavras                        │   deixa esq. │   │
│                                         │   livre p/   │   │
│  ┌─────────────────┐ ┌──────────────┐  │   texto)     │   │
│  │ [CTA PRIMÁRIO]  │ │ CTA secundár │  │              │   │
│  │ bg=primary      │ │ ghost/outline│  └──────────────┘   │
│  │ padding:14px32px│ │              │                     │
│  │ font-weight:700 │ │              │                     │
│  └─────────────────┘ └──────────────┘                     │
│    ↑ Fitts: grande e central         ↑ Hick: 2 opções max  │
│                                                             │
│  ──────── SOCIAL PROOF INLINE ─────────────────────────    │
│  👤👤👤👤👤  "4.312 empresas | ★★★★★ 4.9 (847 avaliações)"  │
│  ↑ Imediato: reduz ansiedade antes de rolar a página        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ░░░░░░░ LOGOS DE CLIENTES / PARCEIROS ░░░░░░░░░░░░░░░░░░  │
│  Preload de confiança antes de qualquer feature             │
└─────────────────────────────────────────────────────────────┘
```

## Checklist Neurociência (marque cada um)

### Atenção
- [ ] Headline tem número específico OU palavra de emoção forte na posição 1-2
- [ ] Badge/pill acima do headline (Von Restorff — elemento único é memorizado)
- [ ] Contraste do CTA primário > 4.5:1 com o background (WCAG AA)
- [ ] Visual à direita (F-pattern mantém olho no texto à esquerda)

### Memória de Trabalho (Miller's Law)
- [ ] Máximo 2 CTAs visíveis ao mesmo tempo
- [ ] Máximo 3 benefícios na subheadline
- [ ] Nav tem no máximo 5 itens (incluindo CTA)

### Redução de Ansiedade
- [ ] Social proof ANTES da dobra (não abaixo)
- [ ] Micro-copy abaixo do CTA: "Sem cartão de crédito" / "Cancele quando quiser"
- [ ] Imagem/video do produto ACIMA da dobra (reduz incerteza)

### Velocidade Percebida (Doherty Threshold)
- [ ] Fontes carregam via `font-display: swap`
- [ ] Imagem hero tem `loading="eager"` e dimensões fixas (sem layout shift)
- [ ] CSS crítico inline no `<head>` (sem flash de conteúdo sem estilo)

### CRO Avançado
- [ ] CTA usa verbo de ação + benefício, não rótulo de ação genérico
- [ ] Headline passa no teste "8 metros" — legível impressa em outdoor a 8m
- [ ] Subheadline responde: "Isso é para mim?" em menos de 3 segundos
- [ ] A proposta de valor é específica para {niche} (não genérica)

## Copywriting do Hero

### Fórmula Headline (escolha a variante mais forte para A/B):
```
Variante A (Resultado específico):
"[Número] [resultado desejado] em [tempo específico] para {audience}"

Variante B (Problema eliminado):
"Pare de [dor específica do nicho]. Comece [resultado] hoje."

Variante C (Curiosidade + dado):
"Por que [dado surpreendente] de {audience} [resultado inesperado]"
```

### Fórmula Subheadline:
```
"[Produto] é [categoria] que [benefício principal] para [público específico]
sem [objeção principal] — mesmo que [barreira que o público acredita ter]."
```

### Fórmula CTA Primário:
```
"[Verbo de ação] [benefício] [eliminador de risco]"
Ex: "Começar grátis por 14 dias" | "Ver como funciona" | "Criar minha conta"
```

### Micro-copy sob o CTA (reduz ansiedade):
```
✓ Sem cartão de crédito  ✓ Cancele quando quiser  ✓ Setup em 2 minutos
```
"""
    return blueprint


def color_psychology(
    niche: str,
    desired_emotion: str = "confiança",
    audience_age: str = "adulto",
    competitors_colors: str = "",
) -> str:
    """
    Recomenda paleta de cores baseada em psicologia, neurociência e diferenciação
    competitiva. Inclui hex codes, uso e justificativa científica.
    """
    # Mapeia emoção para cor base
    emotion_map = {
        "confiança": ("azul", "#2563EB"),
        "crescimento": ("verde", "#16A34A"),
        "criatividade": ("roxo", "#7C3AED"),
        "energia": ("laranja", "#EA580C"),
        "urgência": ("vermelho", "#DC2626"),
        "luxo": ("preto", "#0F172A"),
        "saúde": ("verde", "#059669"),
        "inovação": ("roxo", "#6D28D9"),
    }

    color_name, primary = emotion_map.get(
        desired_emotion.lower(),
        ("azul", "#2563EB")
    )
    psych = COLOR_PSYCHOLOGY.get(color_name, COLOR_PSYCHOLOGY["azul"])

    # Paleta complementar (regra do triângulo de cores simplificada)
    result = f"""# Paleta de Cores — {niche}
**Emoção desejada:** {desired_emotion} | **Público:** {audience_age}

## Cor Primária
**{primary}** — {color_name.title()}
> *{psych['emotion']}*
> Nichos que mais usam: {', '.join(psych['niches'])}

## Paleta Completa Recomendada

| Papel | Hex | Uso |
|---|---|---|
| Primária | `{primary}` | CTAs, links, highlights — máx 10% da tela |
| Primária dark | ajustar -15% brilho | Hover states, pressed states |
| Background | `#FAFAFA` ou `#F8FAFC` | Body, 60% da tela |
| Superfície | `#FFFFFF` | Cards, modais, dropdowns |
| Texto | `#0F172A` | Headlines, corpo de texto |
| Texto muted | `#64748B` | Labels, captions, placeholders |
| Borda | `rgba(0,0,0,0.08)` | Divisores, bordas de card |
| Sucesso | `#16A34A` | Confirmações, estados positivos |
| Erro | `#DC2626` | Validação, alertas críticos |
| Aviso | `#D97706` | Alertas não-críticos, urgência |

## Proporção 60-30-10
- **60%** Background neutro (respiro, reduz fadiga ocular)
- **30%** Superfícies e texto (estrutura visual)
- **10%** Cor primária (ação, foco, conversão)
> Mais de 10% de cor primária ativa o sistema límbico do stress.
> Menos de 5% reduz a taxa de clique no CTA.

## Diferenciação Competitiva
{f"Concorrentes usam: {competitors_colors}. Considere diferenciação por tom (mais escuro/vibrante) ou cor complementar." if competitors_colors else "Pesquise as 5 maiores marcas do seu nicho e evite a cor dominante delas — diferenciação visual = memorabilidade."}

## Acessibilidade (WCAG 2.1 AA)
- Texto escuro `#0F172A` sobre fundo branco: ratio 19.5:1 ✅ (mín: 4.5:1)
- Texto branco sobre `{primary}`: verifique em https://webaim.org/resources/contrastchecker/
- Nunca use apenas cor para transmitir informação (daltonismo afeta 8% dos homens)

## Neurociência da Percepção de Cor
- **Vermelho/laranja** → amígdala → reação rápida → bom para ofertas e urgência
- **Azul/verde** → córtex pré-frontal → decisão ponderada → bom para produtos B2B/premium
- **Roxo** → raridade percebida → aumenta percepção de valor
- **Preto** → autoridade e exclusividade → mas reduz acessibilidade
- **Branco/cinza** → espaço negativo → aumenta atenção nos elementos ao redor
"""
    return result


def typography_scale(
    brand_personality: str = "moderno e direto",
    context: str = "web",
    base_size: int = 16,
) -> str:
    """
    Gera sistema tipográfico completo com escala modular, combinações
    de fontes e uso semântico. Baseado em sistemas reais das maiores empresas.
    """
    ratio = 1.25  # Major Third — o mais equilibrado para UI

    scale = {}
    names = ["xs","sm","base","lg","xl","2xl","3xl","4xl","5xl","6xl"]
    for i, name in enumerate(names):
        size = base_size * (ratio ** (i - 2))
        scale[name] = round(size, 2)

    combos = {
        "tech/produto": ("Inter", "Inter", "JetBrains Mono", "Precisão, legibilidade em UI"),
        "saúde/bem-estar": ("Nunito", "Source Sans 3", "monospace", "Amigável, acessível"),
        "luxo/premium": ("Playfair Display", "Lato", "monospace", "Elegância, sofisticação"),
        "startup/agência": ("Syne", "DM Sans", "Fira Code", "Ousado, diferenciado"),
        "educação": ("Merriweather", "Open Sans", "monospace", "Legível, confiável"),
        "fintech": ("IBM Plex Sans", "IBM Plex Sans", "IBM Plex Mono", "Técnico, preciso"),
    }

    best_match = "tech/produto"
    for key in combos:
        if any(word in brand_personality.lower() for word in key.split("/")):
            best_match = key
            break

    heading_font, body_font, mono_font, rationale = combos[best_match]

    css = f"""/* Tipografia — {brand_personality} */
@import url('https://fonts.googleapis.com/css2?family={heading_font.replace(" ", "+")}:wght@400;600;700;800&family={body_font.replace(" ", "+")}:wght@400;500;600&display=swap');

:root {{
  --font-heading: '{heading_font}', system-ui, sans-serif;
  --font-body:    '{body_font}', system-ui, sans-serif;
  --font-mono:    '{mono_font}', monospace;

  /* Escala Modular 1.25 (Major Third) — base {base_size}px */
{"".join(f"  --text-{name}: {size}px;{chr(10)}" for name, size in scale.items())}
  /* Line heights */
  --leading-none:   1;
  --leading-tight:  1.15;   /* Headlines grandes */
  --leading-snug:   1.35;   /* Subheadlines */
  --leading-normal: 1.55;   /* Corpo de texto — ótimo para legibilidade */
  --leading-relaxed:1.75;   /* Texto longo, artigos */

  /* Letter spacing */
  --tracking-tighter: -0.05em;  /* Headlines 48px+ */
  --tracking-tight:   -0.025em; /* Headlines menores */
  --tracking-normal:   0em;
  --tracking-wide:     0.05em;  /* ALL CAPS, labels */
  --tracking-wider:    0.1em;   /* BADGE TEXT */
}}"""

    usage = """
/* USO SEMÂNTICO */
h1 {{ font-size: var(--text-5xl); letter-spacing: var(--tracking-tighter); line-height: var(--leading-tight); }}
h2 {{ font-size: var(--text-4xl); letter-spacing: var(--tracking-tight);   line-height: var(--leading-tight); }}
h3 {{ font-size: var(--text-3xl); letter-spacing: var(--tracking-tight);   line-height: var(--leading-snug); }}
h4 {{ font-size: var(--text-2xl); letter-spacing: var(--tracking-normal);  line-height: var(--leading-snug); }}
p  {{ font-size: var(--text-base); line-height: var(--leading-normal); }}
.caption {{ font-size: var(--text-sm); color: var(--color-text-muted); }}
.label {{ font-size: var(--text-xs); letter-spacing: var(--tracking-wider); text-transform: uppercase; font-weight: 600; }}
code {{ font-family: var(--font-mono); font-size: 0.875em; }}"""

    return f"""# Sistema Tipográfico — {brand_personality}
**Combinação:** {heading_font} (heading) + {body_font} (body)
**Racional:** {rationale}
**Escala:** Modular 1.25 (Major Third) — base {base_size}px

## Escala de tamanhos
| Token | Tamanho | Uso |
|---|---|---|
{chr(10).join(f"| `--text-{name}` | {size}px | {'Hero headline' if name=='5xl' else 'H2 principal' if name=='4xl' else 'H3' if name=='3xl' else 'Body' if name=='base' else 'Captions' if name=='sm' else 'Labels' if name=='xs' else 'Subheading'} |" for name, size in scale.items())}

## Legibilidade científica
- Comprimento ideal de linha: **60-75 caracteres** por linha (menor = cansativo, maior = difícil de rastrear)
- Tamanho mínimo corpo: **16px** (abaixo disso, usuários >40 anos têm dificuldade)
- Contraste mínimo: **4.5:1** texto normal, **3:1** texto grande (WCAG AA)
- `font-display: swap` — evita FOIT (Flash of Invisible Text) que afeta conversão

```css
{css}
{usage}
```
"""


def persuasion_framework(
    framework: str,
    product: str,
    audience: str,
    main_pain: str,
    main_benefit: str,
) -> str:
    """
    Aplica um framework de persuasão completo e gera o roteiro de copy.
    Frameworks: AIDA | PAS | StoryBrand | 4Ps
    """
    fw = PERSUASION_FRAMEWORKS.get(framework.upper(), PERSUASION_FRAMEWORKS["PAS"])

    sections = []
    for step, instruction in fw["structure"].items():
        sections.append(f"""### {step}
**O que fazer:** {instruction}

**Aplicado ao {product}:**
→ [ESCREVA AQUI baseado em: produto={product}, público={audience}, dor={main_pain}, benefício={main_benefit}]

**Gatilhos neurais desta seção:** {"Social proof + especificidade" if step in ("Interest","Desire","Picture","Proof") else "Loss aversion + urgência" if step in ("Agitation","Failure","Push") else "Atenção + curiosidade"}
""")

    return f"""# Framework {framework.upper()} — {product}
**Descrição:** {fw['desc']}
**Público:** {audience}

> **Dor principal:** {main_pain}
> **Benefício principal:** {main_benefit}

---

{"---".join(sections)}

---

## Princípios de Neurociência Aplicados

| Princípio | Onde usar | Efeito |
|---|---|---|
| Loss Aversion (Kahneman) | {fw['steps'][1] if len(fw['steps'])>1 else 'Meio'} | Dor de perder é 2× mais motivante que prazer de ganhar |
| Especificidade | Todos | "47 min" > "rápido"; números = credibilidade |
| Social Proof | {fw['steps'][-2] if len(fw['steps'])>2 else 'Penúltimo'} | Heurística de consenso — seguimos os outros |
| Escassez/Urgência | {fw['steps'][-1]} | Aversão à perda + FOMO ativam amígdala |
| Cognitive Fluency | Todos | Frases curtas = percebidas como mais verdadeiras |
| Commitment & Consistency | CTA | Micro-sim antes do grande sim |

## Teste A/B Sugerido
Teste estes dois ângulos:
1. **Ângulo positivo:** "Imagine {main_benefit} em 30 dias"
2. **Ângulo negativo:** "Cada semana sem {product} custa [X]"
→ Na maioria dos nichos, o negativo converte 23% mais (Kahneman, 1979)
"""


def ux_laws_audit(url_or_description: str) -> str:
    """
    Audita uma URL ou descrição de página/produto contra as 10 leis
    fundamentais de UX. Retorna score e recomendações priorizadas.
    """
    is_url = url_or_description.startswith("http")
    content = ""

    if is_url:
        try:
            r = httpx.get(url_or_description, timeout=15, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
            content = r.text[:8000]
        except Exception as e:
            content = f"Não foi possível carregar: {e}"

    results = []
    for law, explanation in UX_LAWS.items():
        results.append(f"""### Lei de {law}
*{explanation}*

**Verificação manual necessária:**
{"- Analise o HTML carregado acima" if is_url else "- Analise a descrição fornecida"}

**Checklist:**
- [ ] Esta lei está sendo respeitada?
- [ ] Qual elemento principal viola ou satisfaz esta lei?
- [ ] Qual a melhoria de maior impacto?

**Impacto na conversão:** {"🔴 Alto" if law in ("Fitts","Hick","Von Restorff","Peak-End") else "🟡 Médio" if law in ("Jakob","Miller","Zeigarnik") else "🟢 Baixo"}
""")

    return f"""# Auditoria UX — 10 Leis Fundamentais
**Alvo:** {url_or_description[:80]}

{chr(10).join(results)}

## Priorização (Impact × Esforço)

| Prioridade | Lei | Por quê |
|---|---|---|
| 🔴 P1 | Fitts + Von Restorff | CTAs maiores e destacados = maior impacto imediato |
| 🔴 P1 | Hick | Reduzir opções = menos fricção = mais conversão |
| 🟡 P2 | Peak-End | Otimizar confirmação de compra e onboarding |
| 🟡 P2 | Jakob | Padrões familiares reduzem curva de aprendizado |
| 🟢 P3 | Miller | Organização de informação em grupos de 7 |

{"**Conteúdo analisado (primeiros 2000 chars):**" + chr(10) + "```" + chr(10) + content[:2000] + chr(10) + "```" if content else ""}
"""


def attention_heatmap_predict(page_type: str = "landing", layout: str = "hero-left") -> str:
    """
    Prediz onde os olhos dos usuários vão focar com base em pesquisas de
    eye-tracking (Nielsen Norman Group, CXL Institute) e F/Z patterns.
    """
    patterns = {
        "landing": {
            "pattern": "F-Pattern modificado (conteúdo à esquerda)",
            "hotspots": [
                ("100%", "Logo + Nav CTA — primeira fixação"),
                ("85%", "Primeiras 2 palavras do headline H1"),
                ("70%", "Imagem/visual principal (direita ou centro)"),
                ("60%", "CTA primário — especialmente se contrastante"),
                ("40%", "Subheadline — apenas se headline gerou interesse"),
                ("30%", "Social proof (logos/depoimentos acima da dobra)"),
                ("15%", "Footer e seções abaixo da dobra inicial"),
            ],
            "recommendations": [
                "Posicione benefício principal nas 2 primeiras palavras do H1",
                "CTA deve ser visível sem rolar — prefira canto superior direito + centro",
                "Imagem do produto à direita mantém olho no texto à esquerda",
                "Social proof abaixo do CTA (não abaixo da dobra) captura 30% que hesitam",
            ]
        },
        "artigo": {
            "pattern": "F-Pattern clássico (horizontal + vertical esquerda)",
            "hotspots": [
                ("95%", "Título — lido quase sempre"),
                ("60%", "Primeira linha de cada parágrafo"),
                ("30%", "Palavras em negrito ou itálico"),
                ("20%", "Imagens e gráficos"),
                ("10%", "Conclusão — muitos pulam para o final"),
            ],
            "recommendations": [
                "Informação crítica sempre na primeira linha do parágrafo",
                "Use negrito nas 1-3 palavras mais importantes de cada bloco",
                "Subtítulos funcionam como 'âncoras' de scannabilidade",
                "Conclusão deve resumir e ter CTA — muitos leitores pulam direto",
            ]
        },
        "ecommerce": {
            "pattern": "Z-Pattern + Golden Triangle (canto sup. esquerdo → direito → inferior)",
            "hotspots": [
                ("90%", "Foto do produto — maior atenção"),
                ("80%", "Nome do produto e preço"),
                ("70%", "Botão 'Comprar/Adicionar ao carrinho'"),
                ("50%", "Reviews/estrelas — validação social"),
                ("35%", "Descrição curta"),
                ("20%", "Imagens secundárias"),
            ],
            "recommendations": [
                "Foto de produto: alta qualidade, fundo branco, múltiplos ângulos",
                "Preço: próximo ao botão de compra (reduz distância de decisão)",
                "Stars + número de reviews: visível sem scroll",
                "Botão: acima da dobra em mobile, fixo na tela em mobile (sticky)",
            ]
        },
    }

    data = patterns.get(page_type, patterns["landing"])

    hotspot_table = "\n".join(
        f"| {pct} | {desc} |"
        for pct, desc in data["hotspots"]
    )

    recommendations = "\n".join(f"- {r}" for r in data["recommendations"])

    return f"""# Heatmap Preditivo — {page_type.title()}
**Padrão ocular predominante:** {data['pattern']}
**Fonte:** Nielsen Norman Group + CXL Institute Eye-Tracking Research

## Mapa de Atenção (% de usuários que fixam o olhar)

| Atenção | Elemento |
|---|---|
{hotspot_table}

## Implicações de Design

{recommendations}

## Regra dos 5 Segundos
Os primeiros 5 segundos determinam se o usuário fica ou vai embora.
Nesse tempo, o olho percorre: **Logo → Headline → Visual → CTA**.

Teste: cubra tudo exceto esses 4 elementos. A proposta de valor está clara?

## Zona Fria vs Zona Quente

```
┌─────────────────────────────────────┐
│ 🔥 QUENTE │ 🔥 QUENTE │ 🔥 QUENTE  │  ← Acima da dobra
│ 🔥 QUENTE │ 🌡️ MORNO  │ ❄️ FRIO    │
│ 🌡️ MORNO  │ ❄️ FRIO   │ ❄️ FRIO    │  ← Abaixo da dobra
│ ❄️ FRIO   │ ❄️ FRIO   │ ❄️ FRIO    │
└─────────────────────────────────────┘
  Coluna esq  Centro     Coluna dir
```

**Regra de ouro:** CTA principal sempre na zona 🔥 — acima da dobra, canto superior direito ou centro.
"""
