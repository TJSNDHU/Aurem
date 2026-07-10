"""
AI Studio Image — Gerador de Imagens (v2 — Enhanced)

Script principal que conecta com Google AI Studio (Gemini/Imagen)
para gerar imagens humanizadas. Suporta todos os modelos oficiais,
fallback automatico de API keys, e metadados completos.
"""

import argparse
import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    MODELS,
    DEFAULT_MODEL,
    DEFAULT_FORMAT,
    DEFAULT_HUMANIZATION,
    DEFAULT_MODE,
    DEFAULT_RESOLUTION,
    DEFAULT_PERSON_GENERATION,
    IMAGE_FORMATS,
    FORMAT_ALIASES,
    OUTPUTS_DIR,
    OUTPUT_SETTINGS,
    get_api_key,
    get_all_api_keys,
    safety_check_model,
    safety_check_daily_limit,
)
from prompt_engine import humanize_prompt, analyze_prompt, resolve_format


def _check_dependencies():
    """Verifica dependencias necessarias."""
    try:
        import google.genai  # noqa: F401
    except ImportError:
        print("=" * 60)
        print("  DEPENDENCIA FALTANDO: google-genai")
        print("=" * 60)
        print()
        print("  Instale com:")
        print("    pip install google-genai Pillow python-dotenv")
        print()
        print("  Ou use o requirements.txt:")
        scripts_dir = Path(__file__).parent
        print(f"    pip install -r {scripts_dir / 'requirements.txt'}")
        print()
        sys.exit(1)


def _get_client(api_key: str):
    """Cria cliente Google GenAI."""
    from google import genai
    return genai.Client(api_key=api_key)


# =============================================================================
# GERACAO VIA IMAGEN (imagen-4, imagen-4-ultra, imagen-4-fast)
# =============================================================================

def generate_with_imagen(
    prompt: str,
    model_id: str,
    aspect_ratio: str,
    num_images: int,
    api_key: str,
    resolution: str = "1K",
    person_generation: str = DEFAULT_PERSON_GENERATION,
) -> list[dict]:
    """Gera imagens usando Imagen 4."""
    from google.genai import types

    client = _get_client(api_key)

    config_params = {
        "number_of_images": num_images,
        "aspect_ratio": aspect_ratio,
        "output_mime_type": OUTPUT_SETTINGS["default_mime_type"],
        "person_generation": person_generation,
    }

    # Resolucao (apenas Standard e Ultra suportam 2K)
    if resolution in ("2K",) and "fast" not in model_id:
        config_params["image_size"] = resolution

    config = types.GenerateImagesConfig(**config_params)

    response = client.models.generate_images(
        model=model_id,
        prompt=prompt,
        config=config,
    )

    results = []
    if response.generated_images:
        for img in response.generated_images:
            img_bytes = img.image.image_bytes
            if isinstance(img_bytes, str):
                img_bytes = base64.b64decode(img_bytes)
            results.append({
                "image_bytes": img_bytes,
                "mime_type": OUTPUT_SETTINGS["default_mime_type"],
            })

    return results


# =============================================================================
# GERACAO VIA GEMINI (gemini-flash-image, gemini-pro-image)
# =============================================================================

def generate_with_gemini(
    prompt: str,
    model_id: str,
    aspect_ratio: str,
    api_key: str,
    resolution: str = "1K",
    reference_images: list[Path] | None = None,
) -> list[dict]:
    """Gera imagens usando Gemini (generateContent com modalidade IMAGE)."""
    from google.genai import types
    from PIL import Image

    client = _get_client(api_key)

    # Construir contents
    contents = []

    # Adicionar imagens de referencia (se Gemini Pro Image)
    if reference_images:
        for ref_path in reference_images:
            if Path(ref_path).exists():
                contents.append(Image.open(str(ref_path)))

    contents.append(prompt)

    # Alguns modelos (ex: gemini-2.0-flash-exp) nao suportam aspect_ratio/ImageConfig
    # Verificar via config ou fallback por ID
    supports_ar = True
    for _mk, _mc in MODELS.items():
        if _mc["id"] == model_id:
            supports_ar = _mc.get("supports_aspect_ratio", True)
            break

    if not supports_ar:
        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        )
    else:
        # Config com modalidades e aspect ratio
        image_config = types.ImageConfig(aspect_ratio=aspect_ratio)

        # Resolucao (Pro suporta ate 4K)
        if resolution in ("2K", "4K") and "pro" in model_id.lower():
            image_config = types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=resolution,
            )

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=image_config,
        )

    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=config,
    )

    results = []
    if response.candidates:
        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        img_bytes = part.inline_data.data
                        if isinstance(img_bytes, str):
                            img_bytes = base64.b64decode(img_bytes)
                        results.append({
                            "image_bytes": img_bytes,
                            "mime_type": part.inline_data.mime_type or "image/png",
                        })

    return results


# =============================================================================
# SALVAR IMAGEM + METADADOS
# =============================================================================

def save_image(
    image_data: dict,
    output_dir: Path,
    mode: str,
    template: str,
    index: int,
    metadata: dict,
) -> Path:
    """Salva imagem e metadados no disco."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mime = image_data.get("mime_type", "image/png")
    ext = "png" if "png" in mime else "jpg"

    # Nome descritivo
    template_clean = template.replace(" ", "-")[:20]
    filename = f"{mode}_{template_clean}_{timestamp}_{index}.{ext}"
    filepath = output_dir / filename

    # Salvar imagem
    filepath.write_bytes(image_data["image_bytes"])

    # Salvar metadados
    if OUTPUT_SETTINGS["save_metadata"]:
        meta_path = output_dir / f"{filename}.meta.json"
        meta_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    return filepath


# =============================================================================
# HELPERS DE GENERATE (refatorados para reduzir tamanho da funcao)
# =============================================================================

def _run_safety_checks(model_name: str, num_images: int, force_paid: bool):
    """Executa verificacoes de seguranca de modelo e limite diario."""
    allowed, msg = safety_check_model(model_name, force=force_paid)
    if not allowed:
        raise SystemExit(f"[SAFETY] {msg}")
    print(f"[SAFETY] {msg}")

    allowed, msg = safety_check_daily_limit(num_images)
    if not allowed:
        raise SystemExit(f"[SAFETY] {msg}")
    print(f"[SAFETY] {msg}")


def _get_api_keys():
    """Obtem lista de API keys ou encerra com mensagem de erro."""
    api_keys = get_all_api_keys()
    if not api_keys:
        print("=" * 60)
        print("  ERRO: Nenhuma GEMINI_API_KEY encontrada!")
        print("=" * 60)
        print()
        print("  Configure de uma dessas formas:")
        print("  1. Variavel de ambiente: set GEMINI_API_KEY=sua-key")
        print("  2. Arquivo .env em: C:\\Users\\renat\\skills\\ai-studio-image\\")
        print()
        print("  Obtenha sua key em: https://aistudio.google.com/apikey")
        sys.exit(1)
    return api_keys


def _resolve_final_prompt(
    prompt: str,
    mode: str,
    humanization: str,
    lighting: str | None,
    template_context: str | None,
    shot_type: str | None,
    resolution: str,
    skip_humanization: bool,
) -> str:
    """Humaniza o prompt ou retorna o original se skip."""
    if skip_humanization:
        return prompt
    return humanize_prompt(
        user_prompt=prompt,
        mode=mode,
        humanization=humanization,
        lighting=lighting,
        template_context=template_context,
        shot_type=shot_type,
        resolution=resolution,
    )


def _print_generation_header(
    model_config: dict,
    mode: str,
    format_name: str,
    aspect_ratio: str,
    humanization: str,
    resolution: str,
    num_images: int,
    lighting: str | None,
    reference_images: list[Path] | None,
    output_dir: Path,
):
    """Imprime o cabecalho informativo antes da geracao."""
    print("=" * 60)
    print("  AI STUDIO IMAGE — Gerando Imagem Humanizada")
    print("=" * 60)
    print(f"  Modelo:         {model_config['id']}")
    print(f"  Tipo:           {model_config['type']}")
    print(f"  Modo:           {mode}")
    print(f"  Formato:        {format_name} ({aspect_ratio})")
    print(f"  Humanizacao:    {humanization}")
    print(f"  Resolucao:      {resolution}")
    print(f"  Imagens:        {num_images}")
    if lighting:
        print(f"  Iluminacao:     {lighting}")
    if reference_images:
        print(f"  Referencias:    {len(reference_images)} imagem(ns)")
    print(f"  Output:         {output_dir}")
    print("=" * 60)
    print()


def _generate_with_fallback(
    final_prompt: str,
    model_config: dict,
    aspect_ratio: str,
    num_images: int,
    api_keys: list[str],
    resolution: str,
    person_generation: str,
    reference_images: list[Path] | None,
) -> tuple[list[dict], int]:
    """
    Tenta gerar imagens com fallback de API keys e retries.

    Retorna (images, used_key_index).
    """
    images: list[dict] = []
    used_key_index = 0
    start_time = time.time()

    max_retries = 3
    retry_delay = 15  # seconds

    for attempt in range(max_retries):
        for i, api_key in enumerate(api_keys):
            try:
                if model_config["type"] == "imagen":
                    images = generate_with_imagen(
                        prompt=final_prompt,
                        model_id=model_config["id"],
                        aspect_ratio=aspect_ratio,
                        num_images=num_images,
                        api_key=api_key,
                        resolution=resolution,
                        person_generation=person_generation,
                    )
                else:
                    images = generate_with_gemini(
                        prompt=final_prompt,
                        model_id=model_config["id"],
                        aspect_ratio=aspect_ratio,
                        api_key=api_key,
                        resolution=resolution,
                        reference_images=reference_images,
                    )

                if images:
                    used_key_index = i
                    break

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg
                is_last_key = i >= len(api_keys) - 1

                if not is_last_key:
                    print(f"  Key {i+1} falhou ({error_msg[:60]}...), tentando backup...")
                    continue
                elif is_rate_limit and attempt < max_retries - 1:
                    # Extrair delay sugerido da resposta se possivel
                    delay_match = re.search(r'retryDelay.*?(\d+)', error_msg)
                    wait_time = int(delay_match.group(1)) if delay_match else retry_delay
                    wait_time = min(wait_time + 5, 60)  # cap at 60s
                    print(f"  Rate limit atingido. Aguardando {wait_time}s (tentativa {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    break  # Break inner loop to retry all keys
                else:
                    print(f"\n  ERRO: Todas as tentativas falharam.")
                    print(f"  Ultimo erro: {error_msg[:200]}")
                    print()
                    if is_rate_limit:
                        print("  Rate limit esgotado. Sugestoes:")
                        print("  - Aguarde alguns minutos e tente novamente")
                        print("  - Habilite billing no Google Cloud para limites maiores")
                        print("  - Use um modelo diferente (--model imagen-4-fast)")
                    else:
                        print("  Dicas:")
                        print("  - Verifique se a API key e valida")
                        print("  - O prompt pode conter conteudo restrito")
                        print("  - Tente simplificar o prompt")
                    print("  - Verifique: https://aistudio.google.com/")
                    return [], 0

        if images:
            break

    elapsed = time.time() - start_time
    print(f"\n  Geracao concluida em {elapsed:.1f}s")
    return images, used_key_index


def _save_results(
    images: list[dict],
    output_dir: Path,
    mode: str,
    template: str,
    metadata: dict,
) -> list[Path]:
    """Salva todas as imagens geradas e retorna a lista de paths."""
    saved_paths = []
    for idx, img_data in enumerate(images):
        filepath = save_image(
            image_data=img_data,
            output_dir=output_dir,
            mode=mode,
            template=template,
            index=idx,
            metadata=metadata,
        )
        saved_paths.append(filepath)
        print(f"  Salvo: {filepath}")
    return saved_paths


# =============================================================================
# FUNCAO PRINCIPAL — COM FALLBACK DE API KEYS
# =============================================================================

def generate(
    prompt: str,
    mode: str = DEFAULT_MODE,
    format_name: str = DEFAULT_FORMAT,
    humanization: str = DEFAULT_HUMANIZATION,
    lighting: str | None = None,
    model_name: str = DEFAULT_MODEL,
    num_images: int = 1,
    template: str = "custom",
    template_context: str | None = None,
    output_dir: Path | None = None,
    skip_humanization: bool = False,
    resolution: str = DEFAULT_RESOLUTION,
    person_generation: str = DEFAULT_PERSON_GENERATION,
    reference_images: list[Path] | None = None,
    shot_type: str | None = None,
    force_paid: bool = False,
) -> list[Path]:
    """
    Funcao principal de geracao de imagens.

    Fluxo:
    1. Valida e tenta API keys com fallback
    2. Humaniza o prompt (se nao skip)
    3. Chama a API apropriada (Imagen ou Gemini)
    4. Salva imagens + metadados completos
    5. Retorna paths dos arquivos gerados