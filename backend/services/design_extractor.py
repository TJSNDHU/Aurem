"""
Design Extractor (iter 307)
============================
Wraps `npx designlang <url>` CLI → returns flat AUREM-friendly token dict.

Public:
  await extract_design(url, timeout=60) -> dict

Returns:
  {
    "ok": True,
    "source_url": str,
    "extracted_at": iso,
    "duration_s": float,
    "colors": {primary, secondary, accent, bg, text, palette[]},
    "fonts":  {heading, body, families[]},
    "spacing": [str, ...],
    "shadows": [str, ...],
    "components": [pattern names],
    "score": int,        # designlang's quality score
    "raw_files": {tokens_json, tailwind_js, variables_css, theme_js},
  }

Falls back to {"ok": False, "error": ...} on any failure — caller is
expected to use the existing Gemini draft when this returns ok=False.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
LOG_COLLECTION = "design_extract_logs"


def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u.rstrip("/")


def _walk_color_leaves(node: Any, out: List[str]) -> None:
    if isinstance(node, dict):
        if node.get("$type") == "color" and isinstance(node.get("$value"), str):
            out.append(node["$value"])
            return
        for v in node.values():
            _walk_color_leaves(v, out)


def _flatten_tokens(tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DTCG $value/$type tree into AUREM-friendly flat dict."""
    out: Dict[str, Any] = {"colors": {}, "fonts": {}, "spacing": [], "shadows": []}

    primitive = tokens.get("primitive") or {}
    semantic = tokens.get("semantic") or {}

    # Colors — start from primitive.color.brand → semantic fallbacks
    p_color = (primitive.get("color") or {})
    brand = (p_color.get("brand") or {})
    out["colors"]["primary"] = (brand.get("primary") or {}).get("$value")
    out["colors"]["secondary"] = (brand.get("secondary") or {}).get("$value")
    out["colors"]["accent"] = (brand.get("accent") or {}).get("$value")

    bg_group = (p_color.get("background") or {})
    out["colors"]["bg"] = (bg_group.get("bg1") or {}).get("$value") \
                          or (bg_group.get("bg0") or {}).get("$value")
    text_group = (p_color.get("text") or {})
    out["colors"]["text"] = (text_group.get("text0") or {}).get("$value") \
                            or (text_group.get("text1") or {}).get("$value")

    palette: List[str] = []
    _walk_color_leaves(p_color, palette)
    # de-dup, preserve order, cap 12
    seen = set()
    out["colors"]["palette"] = [c for c in palette
                                 if not (c in seen or seen.add(c))][:12]

    # Fonts
    p_typo = (primitive.get("typography") or primitive.get("font") or {})
    if not p_typo:
        p_typo = (primitive.get("typeface") or {})
    families: List[str] = []
    for k, v in (p_typo.get("family") or {}).items():
        if isinstance(v, dict) and isinstance(v.get("$value"), str):
            families.append(v["$value"])
    if not families:
        # Walk any "fontFamily" type
        def _walk(n):
            if isinstance(n, dict):
                if n.get("$type") in ("fontFamily", "font-family") and isinstance(n.get("$value"), str):
                    families.append(n["$value"])
                for v in n.values():
                    _walk(v)
        _walk(tokens)
    families = [f for f in {f.strip() for f in families if f} if f][:4]

    sem_typo = ((semantic.get("typography") or {}))
    out["fonts"]["heading"] = (((sem_typo.get("heading") or {}).get("family") or {})
                                 .get("$value")) or (families[0] if families else None)
    out["fonts"]["body"] = (((sem_typo.get("body") or {}).get("family") or {})
                              .get("$value")) or (families[1] if len(families) > 1
                                                  else (families[0] if families else None))
    out["fonts"]["families"] = families

    # Spacing
    p_spc = (primitive.get("spacing") or {})
    spacings: List[str] = []
    for v in p_spc.values():
        if isinstance(v, dict) and isinstance(v.get("$value"), (str, int, float)):
            spacings.append(str(v["$value"]))
    out["spacing"] = spacings[:12]

    # Shadows
    p_sh = (primitive.get("shadow") or primitive.get("elevation") or {})
    shadows: List[str] = []
    for v in p_sh.values():
        if isinstance(v, dict):
            sv = v.get("$value")
            if isinstance(sv, str):
                shadows.append(sv)
            elif isinstance(sv, dict):
                shadows.append(json.dumps(sv)[:120])
    out["shadows"] = shadows[:6]

    return out


async def _run_cli(url: str, outdir: str, name: str,
                    timeout: int) -> Dict[str, Any]:
    cmd = ["npx", "--yes", "designlang", url, "--out", outdir, "--name", name]
    # Ensure the CLI inherits the playwright browsers path so the
    # subprocess can find chromium even when the parent supervisor
    # didn't pre-set this env.
    env = os.environ.copy()
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd="/tmp",
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"rc": 124, "out": "timeout", "err": ""}
    return {"rc": proc.returncode,
            "out": (stdout or b"").decode(errors="ignore")[-1500:],
            "err": (stderr or b"").decode(errors="ignore")[-1500:]}


async def extract_design(url: str, timeout: int = DEFAULT_TIMEOUT,
                          db=None) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)
    norm = _normalize_url(url)
    if not norm:
        return {"ok": False, "error": "invalid_url"}

    base = tempfile.mkdtemp(prefix="dl-")
    name = "extract"
    try:
        run = await _run_cli(norm, base, name, timeout)
        if run["rc"] != 0:
            err = run.get("err") or run.get("out") or "cli_failed"
            await _log(db, norm, ok=False, error=err[:400], duration=0.0)
            return {"ok": False, "error": f"cli_rc{run['rc']}: {err[:160]}"}

        tokens_path = os.path.join(base, f"{name}-design-tokens.json")
        if not os.path.isfile(tokens_path):
            await _log(db, norm, ok=False, error="tokens_missing", duration=0.0)
            return {"ok": False, "error": "tokens_file_missing"}

        with open(tokens_path) as f:
            tokens_dtcg = json.load(f)

        flat = _flatten_tokens(tokens_dtcg)

        # Optional companion files
        raw_files: Dict[str, Optional[str]] = {}
        for key, fname in (
            ("tokens_json", f"{name}-design-tokens.json"),
            ("tailwind_js", f"{name}-tailwind.config.js"),
            ("variables_css", f"{name}-variables.css"),
            ("theme_js", f"{name}-theme.js"),
            ("shadcn_css", f"{name}-shadcn-theme.css"),
            ("voice_json", f"{name}-voice.json"),
            ("visual_dna", f"{name}-visual-dna.json"),
        ):
            p = os.path.join(base, fname)
            if os.path.isfile(p) and os.path.getsize(p) < 60_000:
                with open(p) as f:
                    raw_files[key] = f.read()
            else:
                raw_files[key] = None

        # Components — pull from voice/intel json if present
        components: List[str] = []
        try:
            mcp_path = os.path.join(base, f"{name}-mcp.json")
            if os.path.isfile(mcp_path):
                with open(mcp_path) as f:
                    mcp = json.load(f)
                comps = (mcp.get("components") or {})
                if isinstance(comps, dict):
                    components = list(comps.keys())[:10]
        except Exception:
            pass

        # Score from stdout if mentioned
        score: Optional[int] = None
        m = re.search(r"Design Score:\s*(\d+)/100", run["out"])
        if m:
            try:
                score = int(m.group(1))
            except Exception:
                score = None

        duration = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
        await _log(db, norm, ok=True, error=None, duration=duration,
                    score=score, palette_size=len(flat["colors"]["palette"]))

        return {
            "ok": True, "source_url": norm,
            "extracted_at": started.isoformat(),
            "duration_s": duration,
            "colors": flat["colors"],
            "fonts": flat["fonts"],
            "spacing": flat["spacing"],
            "shadows": flat["shadows"],
            "components": components,
            "score": score,
            "raw_files": raw_files,
        }
    finally:
        try:
            shutil.rmtree(base, ignore_errors=True)
        except Exception:
            pass


async def _log(db, url: str, *, ok: bool, error: Optional[str],
               duration: float, **extra) -> None:
    if db is None:
        return
    try:
        await db[LOG_COLLECTION].insert_one({
            "url": url, "ok": ok, "error": error,
            "duration_s": duration, "ts": datetime.now(timezone.utc).isoformat(),
            **extra,
        })
    except Exception:
        pass


def design_prompt_snippet(design: Dict[str, Any]) -> str:
    """Compact text snippet to feed Gemini draft for repair/build mode.
    Falls back to empty string when design is None or extraction failed."""
    if not design or not design.get("ok"):
        return ""
    c = design.get("colors") or {}
    f = design.get("fonts") or {}
    return (
        "REFERENCE DESIGN TOKENS (extracted from "
        f"{design.get('source_url')} — score {design.get('score')}/100):\n"
        f"  primary={c.get('primary') or '?'} · "
        f"secondary={c.get('secondary') or '?'} · "
        f"accent={c.get('accent') or '?'}\n"
        f"  bg={c.get('bg') or '?'} · text={c.get('text') or '?'}\n"
        f"  palette={','.join((c.get('palette') or [])[:6])}\n"
        f"  heading_font={f.get('heading') or '?'} · "
        f"body_font={f.get('body') or '?'}\n"
        "Build the new site so it visually matches the original brand: same "
        "primary/accent colors, same typography pairing, same overall mood. "
        "Apply the AUREM build mode rules on top (fix accessibility, mobile, "
        "speed) WITHOUT changing the brand identity."
    )
