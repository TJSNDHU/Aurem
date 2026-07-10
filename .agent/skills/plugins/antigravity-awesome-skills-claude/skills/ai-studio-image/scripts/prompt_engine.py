"""
AI Studio Image — Motor de Humanizacao de Prompts (v2 — Enhanced)

Transforma qualquer prompt em uma foto genuinamente humana usando 5 camadas
de realismo + tecnicas avancadas da documentacao oficial do Google AI Studio.

Principio-chave da Google: "Describe the scene, don't just list keywords."
Paragrafos narrativos e descritivos superam listas desconectadas de palavras
porque aproveitam a compreensao profunda de linguagem do modelo.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    HUMANIZATION_LEVELS,
    LIGHTING_OPTIONS,
    MODES,
    SHOT_TYPES,
    PROMPT_TEMPLATES,
    IMAGE_FORMATS,
    FORMAT_ALIASES,
    DEFAULT_HUMANIZATION,
    DEFAULT_MODE,
    DEFAULT_LIGHTING,
    RATE_LIMITS,
)


# =============================================================================
# CAMADAS DE HUMANIZACAO — Sistema de 5 camadas
# =============================================================================

LAYER_DEVICE = {
    "core": [
        "photograph taken with a smartphone camera, not a professional DSLR",
        "natural depth of field characteristic of a small phone camera lens",
        "no professional flash or external lighting — only ambient light",
    ],
    "enhanced": [
        "subtle lens distortion at the edges typical of wide-angle phone cameras",
        "natural image sensor noise that adds organic texture to the photograph",
        "phone auto-focus creating natural bokeh blur in the background",
        "slight chromatic aberration visible at high-contrast edges",
    ],
}

LAYER_LIGHTING = {
    "core": [
        "illuminated only by natural available light sources in the environment",
        "organic soft shadows with gradual transitions, no sharp artificial shadows",
        "no ring lights, studio softboxes, or professional lighting equipment visible",
    ],
    "enhanced": [
        "subtle light reflections on natural surfaces like skin, glass, and metal",
        "color temperature naturally varying across the scene from mixed light sources",
        "gentle light falloff creating natural depth and three-dimensionality",
    ],
}

LAYER_IMPERFECTION = {
    "core": [
        "composition is slightly imperfect — not mathematically centered or perfectly aligned",
        "natural selective focus where some elements are slightly soft in the background",
    ],
    "enhanced": [
        "micro hand tremor resulting in sharpness that is natural, not pixel-perfect",
        "random real-world elements in the environment that weren't intentionally placed",
        "the scene looks lived-in and genuine, not a carefully curated set",
        "horizon line may be very slightly tilted as happens with handheld phone shots",
    ],
}

LAYER_AUTHENTICITY = {
    "core": [
        "genuine natural facial expression — relaxed, candid, and human, not a stock photo pose",
        "wearing everyday clothing appropriate for the setting, not styled for a photoshoot",
        "real human skin texture — visible pores, subtle natural blemishes, organic color variation",
        "realistic natural body proportions without any exaggeration or idealization",
    ],
    "enhanced": [
        "captured in a candid moment, either unaware of the camera or casually self-aware",
        "hair has natural texture and movement, not perfectly salon-styled",
        "subtle imperfections that make the person immediately feel real and relatable",
        "eyes have natural moisture and light reflections, not digitally perfect catchlights",
        "hands and fingers look natural with visible knuckle creases and subtle veins",
    ],
}

LAYER_ENVIRONMENT = {
    "core": [
        "set in a real-world environment, not a generic studio backdrop or green screen",
        "everyday objects naturally present in the scene adding authenticity",
        "lighting is consistent with the physical location and time of day",
    ],
    "enhanced": [
        "time of day is coherent with the activity being performed in the scene",
        "background tells a story — a lived-in space with personality and history",
        "environmental details that anchor the scene firmly in reality",
        "natural depth with foreground, midground, and background layers",
        "subtle atmospheric elements like dust motes in light, steam, or air movement",
    ],
}


def _get_layers_for_level(level: str) -> list[str]:
    """Seleciona modificadores de camada baseado no nivel de humanizacao."""
    all_layers = [LAYER_DEVICE, LAYER_LIGHTING, LAYER_IMPERFECTION,
                  LAYER_AUTHENTICITY, LAYER_ENVIRONMENT]

    modifiers = []
    for layer in all_layers:
        modifiers.extend(layer["core"])
        if level in ("ultra", "natural"):
            modifiers.extend(layer["enhanced"])

    return modifiers


def _detect_shot_type(prompt: str) -> str | None:
    """Detecta o tipo de enquadramento ideal baseado no prompt."""
    prompt_lower = prompt.lower()

    shot_hints = {
        "close-up": ["rosto", "face", "retrato", "portrait", "close-up", "detalhe",
                     "macro", "olhos", "eyes", "labios"],
        "medium": ["sentado", "sitting", "mesa", "table", "cadeira", "chair",
                   "cafe", "coffee", "trabalhando", "working"],
        "wide": ["paisagem", "landscape", "praia", "beach", "montanha", "mountain",
                "cidade", "city", "parque", "park", "rua", "street"],
        "top-down": ["flat lay", "comida", "food", "mesa vista de cima", "overhead",
                    "ingredients", "ingredientes"],
        "medium-close": ["selfie", "busto", "conversando", "talking", "explicando"],
        "over-shoulder": ["tela", "screen", "computador", "computer", "notebook",
                        "livro", "book", "reading"],
        "pov": ["minha visao", "my view", "perspectiva", "primeira pessoa"],
    }

    for shot_type, keywords in shot_hints.items():
        if any(kw in prompt_lower for kw in keywords):
            return shot_type

    return "medium"  # default equilibrado


# =============================================================================
# FUNCAO PRINCIPAL DE HUMANIZACAO
# =============================================================================

def _build_narrative_sections(
    user_prompt: str,
    shot_type: str,
    mode_config: dict,
    layer_mods: list[str],
    level_config: dict,
    lighting: str | None,
    template_context: str | None,
) -> list[str]:
    """Constroi as secoes narrativas do prompt humanizado em paragrafos."""
    sections = []

    sections.append(
        f"A realistic {shot_type} photograph: {user_prompt}. "
        f"This is an authentic moment captured with a smartphone, "
        f"not a professional studio photograph."
    )

    style_narrative = " ".join(mode_config["base_style"])
    sections.append(style_narrative)

    if len(layer_mods) > 6:
        mid = len(layer_mods) // 2
        sections.append(". ".join(layer_mods[:mid]))
        sections.append(". ".join(layer_mods[mid:]))
    else:
        sections.append(". ".join(layer_mods))

    sections.append(". ".join(level_config["modifiers"]))

    if lighting and lighting in LIGHTING_OPTIONS:
        light_mods = LIGHTING_OPTIONS[lighting]["modifiers"]
        sections.append(". ".join(light_mods))

    if template_context:
        sections.append(template_context)

    avoid_narrative = ". ".join(mode_config["avoid"])
    sections.append(avoid_narrative)

    sections.append(
        "The final image must be completely indistinguishable from a real photograph "
        "taken by a real person with their smartphone in their everyday life. "
        "It should radiate genuine human warmth and authenticity — "
        "never looking artificial, sterile, AI-generated, or like stock photography."
    )

    return sections


def _build_compact_prompt(
    user_prompt: str,
    shot_type: str,
    mode_config: dict,
    layer_mods: list[str],
    level_config: dict,
) -> str:
    """Constroi uma versao compacta do prompt quando o limite de tokens e excedido."""
    compact = [
        f"A realistic {shot_type} photograph: {user_prompt}.",
        " ".join(mode_config["base_style"][:3]) + ".",
        ". ".join(layer_mods[:6]) + ".",
        ". ".join(level_config["modifiers"][:4]) + ".",
        ". ".join(mode_config["avoid"][:3]) + ".",
        "Must look like a real phone photo, genuinely human and authentic.",
    ]
    return " ".join(compact)


def humanize_prompt(
    user_prompt: str,
    mode: str = DEFAULT_MODE,
    humanization: str = DEFAULT_HUMANIZATION,
    lighting: str | None = DEFAULT_LIGHTING,
    template_context: str | None = None,
    shot_type: str | None = None,
    resolution: str | None = None,
) -> str:
    """
    Transforma o prompt do usuario em um prompt humanizado completo.

    Usa a abordagem narrativa recomendada pela Google:
    paragrafos descritivos > listas de keywords.
    """
    if not shot_type:
        shot_type = _detect_shot_type(user_prompt)

    mode_config = MODES.get(mode, MODES[DEFAULT_MODE])
    layer_mods = _get_layers_for_level(humanization)
    level_config = HUMANIZATION_LEVELS.get(humanization, HUMANIZATION_LEVELS[DEFAULT_HUMANIZATION])

    sections = _build_narrative_sections(
        user_prompt, shot_type, mode_config, layer_mods, level_config,
        lighting, template_context,
    )

    prompt = "\n\n".join(s.rstrip(".") + "." for s in sections)

    max_chars = RATE_LIMITS["max_prompt_tokens"] * 4  # ~4 chars por token
    if len(prompt) > max_chars:
        prompt = _build_compact_prompt(
            user_prompt, shot_type, mode_config, layer_mods, level_config,
        )

    return prompt


# =============================================================================
# ANALISADOR INTELIGENTE DE PROMPT
# =============================================================================

def analyze_prompt(user_prompt: str) -> dict:
    """
    Analisa o prompt do usuario e sugere configuracoes ideais para cada parametro.
    Retorna um dict completo com todas as sugestoes.
    """
    prompt_lower = user_prompt.lower()

    # ---- Detectar modo ----
    edu_keywords = [
        "aula", "curso", "tutorial", "ensino", "treino", "explicar",
        "demonstrar", "passo", "step", "educacao", "teach", "learn",
        "lesson", "workshop", "apresentacao", "presentation", "slide",
        "infografico", "diagram", "how-to", "how to", "como fazer",
        "aprenda", "aprender", "classe", "class", "professor", "teacher",
        "aluno", "student", "quadro", "whiteboard", "lousa",
    ]
    mode = "educacional" if any(kw in prompt_lower for kw in edu_keywords) else "influencer"

    # ---- Detectar formato ----
    format_hints = {
        "stories": ["stories", "story", "reels", "reel", "tiktok", "vertical", "shorts"],
        "widescreen": ["banner", "thumbnail", "youtube", "desktop", "panorama",
                       "landscape", "wide", "widescreen", "tv", "cinematico"],
        "ultrawide