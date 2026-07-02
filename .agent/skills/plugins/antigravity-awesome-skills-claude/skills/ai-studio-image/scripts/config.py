"""
AI Studio Image — Configuracao Central (v2 — Enhanced with Official Docs)

Todas as constantes, paths, modelos, formatos, tecnicas e configuracoes
baseadas na documentacao oficial do Google AI Studio (Fev 2026).
"""

from pathlib import Path
import os

# =============================================================================
# PATHS
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
DATA_DIR = ROOT_DIR / "data"
OUTPUTS_DIR = DATA_DIR / "outputs"
REFERENCES_DIR = ROOT_DIR / "references"
ASSETS_DIR = ROOT_DIR / "assets"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# API KEY MANAGEMENT (com fallback para backup keys)
# =============================================================================

def _parse_env_file() -> dict[str, str]:
    """Parse .env file and return dict of key-value pairs."""
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return {}
    keys_found = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            keys_found[k.strip()] = v.strip().strip('"').strip("'")
    return keys_found


def get_api_key(try_backup: bool = True) -> str | None:
    """
    Busca API key com fallback automatico:
    1. GEMINI_API_KEY env var
    2. .env GEMINI_API_KEY
    3. .env GEMINI_API_KEY_BACKUP_1
    4. .env GEMINI_API_KEY_BACKUP_2
    """
    # 1. Variavel de ambiente
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    # 2. Arquivo .env
    keys_found = _parse_env_file()

    # Primaria
    if "GEMINI_API_KEY" in keys_found:
        return keys_found["GEMINI_API_KEY"]

    # Backups
    if try_backup:
        for backup_key in ["GEMINI_API_KEY_BACKUP_1", "GEMINI_API_KEY_BACKUP_2"]:
            if backup_key in keys_found:
                return keys_found[backup_key]

    return None


def get_all_api_keys() -> list[str]:
    """Retorna todas as API keys disponiveis para fallback."""
    keys_found = _parse_env_file()
    keys = [
        v for k, v in keys_found.items()
        if "GEMINI_API_KEY" in k and v
    ]

    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and env_key not in keys:
        keys.insert(0, env_key)

    return keys


# =============================================================================
# MODELOS — Todos os modelos oficiais (Fev 2026)
# =============================================================================

MODELS = {
    # ---- Imagen 4 (Standalone Image Generation) ----
    "imagen-4": {
        "id": "imagen-4.0-generate-001",
        "type": "imagen",
        "description": "Imagen 4 Standard — Alta qualidade, balanco ideal velocidade/qualidade",
        "max_images": 4,
        "max_resolution": "2K",
        "supports_aspect_ratio": True,
        "supports_reference_images": False,
        "supports_text_rendering": True,
        "text_limit": 25,  # caracteres max para texto na imagem
        "cost_per_image": 0.03,
    },
    "imagen-4-ultra": {
        "id": "imagen-4.0-ultra-generate-001",
        "type": "imagen",
        "description": "Imagen 4 Ultra — Maxima qualidade, resolucao 2K, detalhes superiores",
        "max_images": 4,
        "max_resolution": "2K",
        "supports_aspect_ratio": True,
        "supports_reference_images": False,
        "supports_text_rendering": True,
        "text_limit": 25,
        "cost_per_image": 0.06,
    },
    "imagen-4-fast": {
        "id": "imagen-4.0-fast-generate-001",
        "type": "imagen",
        "description": "Imagen 4 Fast — Geracao rapida, ideal para volume alto",
        "max_images": 4,
        "max_resolution": "1K",
        "supports_aspect_ratio": True,
        "supports_reference_images": False,
        "supports_text_rendering": True,
        "text_limit": 25,
        "cost_per_image": 0.02,
    },

    # ---- Gemini com geracao de imagem nativa (Nano Banana) ----
    "gemini-flash-image": {
        "id": "gemini-2.5-flash-image",
        "type": "gemini",
        "description": "Nano Banana (Gemini 2.5 Flash Image) — Rapido, eficiente, edicao de imagem",
        "max_images": 1,
        "max_resolution": "1K",
        "supports_aspect_ratio": True,
        "supports_reference_images": False,
        "supports_text_rendering": True,
        "supports_image_editing": True,
        "supports_multi_turn": True,
        "cost_per_image": 0.039,
    },
    "gemini-2-flash-exp": {
        "id": "gemini-2.0-flash-exp-image-generation",
        "type": "gemini",
        "description": "Gemini 2.0 Flash Experimental — GRATUITO, geracao experimental",
        "max_images": 1,
        "max_resolution": "1K",
        "supports_aspect_ratio": False,
        "supports_reference_images": False,
        "supports_text_rendering": True,
        "supports_image_editing": True,
        "supports_multi_turn": True,
        "cost_per_image": 0,
    },
    "gemini-pro-image": {
        "id": "gemini-3-pro-image-preview",
        "type": "gemini",
        "description": "Gemini 3 Pro Image — Maximo controle, 4K, ate 14 imagens referencia, thinking mode",
        "max_images": 1,
        "max_resolution": "4K",
        "supports_aspect_ratio": True,
        "supports_reference_images": True,
        "max_reference_objects": 6,
        "max_reference_humans": 5,
        "max_reference_total": 14,
        "supports_text_rendering": True,
        "supports_thinking_mode": True,
        "supports_search_grounding": True,
        "supports_image_editing": True,
        "supports_image_restoration": True,
        "supports_multi_turn": True,
        "cost_per_image": 0.134,
    },
}

# Modelo padrao — gemini-2-flash-exp e GRATUITO mesmo no nivel pago
DEFAULT_MODEL = os.environ.get("GEMINI_DEFAULT_MODEL", "gemini-2-flash-exp")

# =============================================================================
# FORMATOS DE IMAGEM — Todos os aspect ratios oficiais
# =============================================================================

IMAGE_FORMATS = {
    "square": {
        "aspect_ratio": "1:1",
        "description": "Feed Instagram, Facebook, perfis, produtos",
        "use_cases": ["instagram feed", "facebook post", "profile", "product"],
    },
    "portrait-34": {
        "aspect_ratio": "3:4",
        "description": "Instagram portrait, Pinterest pins",
        "use_cases": ["instagram portrait", "pinterest", "card"],
    },
    "portrait-45": {
        "aspect_ratio": "4:5",
        "description": "Instagram optimal portrait (mais area visivel no feed)",
        "use_cases": ["instagram optimal", "social media portrait"],
    },
    "portrait-23": {
        "aspect_ratio": "2:3",
        "description": "Retrato classico, posters, A4-like",
        "use_cases": ["poster", "print", "classic portrait"],
    },
    "landscape-43": {
        "aspect_ratio": "4:3",
        "description": "Formato classico fullscreen, apresentacoes",
        "use_cases": ["presentation", "fullscreen", "classic"],
    },
    "landscape-32": {
        "aspect_ratio": "3:2",
        "description": "Formato fotografico classico (35mm)",
        "use_cases": ["photography", "35mm", "classic landscape"],
    },
    "landscape-54": {
        "aspect_ratio": "5:4",
        "description": "Quase quadrado, formato 8x10",
        "use_cases": ["near-square", "8x10", "medium format"],
    },
    "widescreen": {
        "aspect_ratio": "16:9",
        "description": "YouTube thumbnails, banners, desktop, TV",
        "use_cases": ["youtube", "banner", "desktop", "tv", "thumbnail"],
    },
    "ultrawide": {
        "aspect_ratio": "21:9",
        "description": "Ultrawide cinematico, banners panoramicos",
        "use_cases": ["cinematic", "ultrawide", "panoramic banner"],
    },
    "stories": {
        "aspect_ratio": "9:16",
        "description": "Stories, Reels, TikTok, Shorts (vertical)",
        "use_cases": ["stories", "reels", "tiktok", "shorts", "vertical"],
    },
}

# Aliases para facilitar uso
FORMAT_ALIASES = {
    "square": "square",
    "1:1": "square",
    "portrait": "portrait-45",  # Instagram optimal como padrao
    "3:4": "portrait-34",
    "4:5": "portrait-45",
    "2:3": "portrait-23",
    "landscape": "widescreen",
    "16:9": "widescreen",
    "4:3": "landscape-43",
    "3:2": "landscape-32",
    "5:4": "landscape-54",
    "21:9": "ultrawide",
    "stories": "stories",
    "9:16": "stories",
    "reels": "stories",
    "tiktok": "stories",
    "youtube": "widescreen",
    "thumbnail": "widescreen",
    "banner": "widescreen",
    "pinterest": "portrait-23",
    "instagram": "square",
    "instagram-portrait": "portrait-45",
    "feed": "square",
}

DEFAULT_FORMAT = "square"

# =============================================================================
# NIVEIS DE HUMANIZACAO
# =============================================================================

HUMANIZATION_LEVELS = {
    "ultra": {
        "description": "Maximo realismo — parece 100% foto de celular amador",
        "modifiers": [
            "taken with an older model smartphone camera, slight quality reduction",
            "visible image sensor noise and grain, especially in shadows",
            "imperfect framing, noticeably off-center, slightly tilted",
            "natural motion blur from slight hand tremor while taking the photo",
            "visible lens distortion at edges typical of wide phone cameras",
            "unedited, straight from camera roll, no filters applied",
            "candid unposed moment, subject not aware of camera or casually posing",
            "fingerprint smudge slightly visible on lens edge",
            "auto-exposure not quite perfect, slightly over or underexposed areas",
        ],
    },
    "natural": {
        "description": "Equilibrio perfeito — foto casual de celular moderno",
        "modifiers": [
            "taken with a modern smartphone camera, natural quality",
            "subtle ambient light only, no professional flash or ring light",
            "casual framing, not perfectly composed but intentional",
            "real skin texture with visible pores, subtle blemishes, natural color variation",
            "genuine facial expression, natural and relaxed, not a stock photo pose",
            "everyday real-world setting with authentic environmental details",
            "shallow depth of field from phone lens, background naturally blurred",
            "natural color grading, not heavily filtered or processed",
        ],
    },
    "polished": {
        "description": "Natural mas cuidado — celular bom com boa luz",
        "modifiers": [
            "high quality smartphone photography, latest model phone camera",
            "well-lit natural lighting, photographer chose good conditions",
            "thoughtful but casual composition, follows rule of thirds loosely",
            "natural skin appearance, minimal retouching, healthy and real",
            "clean real environment with intentional but not staged background",
            "colors are vibrant but not oversaturated, true to life",
        ],
    },
    "editorial": {
        "description": "Estilo revista — natural com producao sutil",
        "modifiers": [
            "editorial photography style, natural but with subtle production quality",
            "professional