"""
sentinel_triage.py — Cheap-LLM error triage layer.

Goal: classify a captured client_error in <500 input tokens via a free
OpenRouter model BEFORE we burn Claude's expensive context window. If
the triage classifier returns a high-confidence "trivial / already-known
pattern" verdict, the caller can short-circuit:
  • TRIVIAL  → skip Claude, store a low-confidence suggestion straight
               from the triage layer (auto_apply=False so a human still
               reviews it)
  • ESCALATE → proceed to full Claude diagnose (the existing path)
  • SKIP     → drop the error (e.g. CDN transient, robot probe noise)

This keeps the autonomous loop cheap on routine errors and reserves
Claude's context for genuinely novel/structural failures.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

_TRIAGE_SYSTEM = (
    "You are AUREM's error triage classifier. Output STRICT JSON only.\n"
    "Decide whether the captured error needs full senior-SRE diagnosis "
    "(Claude) or can be handled by a quick pattern match.\n\n"
    "Schema (no markdown, no prose):\n"
    "{\n"
    '  "verdict": "TRIVIAL"|"ESCALATE"|"SKIP",\n'
    '  "reason": "1-line classification",\n'
    '  "category": "auth_expired"|"network_transient"|"cdn_5xx"|'
    '"validation_error"|"npe_or_undefined"|"unknown_runtime"|"novel",\n'
    '  "confidence": 0.0-1.0,\n'
    '  "quick_fix_hint": "optional 1-line suggestion if TRIVIAL"\n'
    "}\n\n"
    "Rules:\n"
    "• TRIVIAL  → recurring known patterns, auth blips, idempotent UI redos.\n"
    "• SKIP     → CDN/origin transients, robot probes, noise.\n"
    "• ESCALATE → anything novel, structural, or with confidence < 0.75.\n"
    "Be conservative: when in doubt, ESCALATE."
)

_VALID_VERDICTS = {"TRIVIAL", "ESCALATE", "SKIP"}


def compress_stack(stack: str, max_frames: int = 5, head_chars: int = 800) -> str:
    """Trim noisy stack traces to the top N frames. Most of the
    information density lives in the first 5 frames; the rest is
    framework boilerplate that bloats prompts without helping the LLM."""
    s = (stack or "").strip()
    if not s:
        return ""
    # Try frame-aware split first (`at fn (file:line)` style or `\n  at ...`).
    frames = re.split(r"\n\s*(?=at\s)|\n", s)
    frames = [f for f in (fr.strip() for fr in frames) if f]
    if frames:
        return "\n".join(frames[:max_frames])[:head_chars]
    return s[:head_chars]


async def triage(err: Dict[str, Any]) -> Dict[str, Any]:
    """Run the cheap classifier. Returns parsed JSON (with safe defaults
    on parse failure → ESCALATE so we never accidentally drop real errors)."""
    from services.llm_gateway_v2 import route

    compact = {
        "type": err.get("type"),
        "classification": err.get("classification"),
        "message": (err.get("message") or "")[:400],
        "status_code": err.get("status_code"),
        "url": err.get("url"),
        "method": err.get("method"),
        "stack_top": compress_stack(err.get("stack") or "", max_frames=3, head_chars=400),
    }
    prompt = f"Error to triage:\n{json.dumps(compact, indent=2)}"

    result = await route(
        task_type="triage_classify",
        prompt=prompt,
        system=_TRIAGE_SYSTEM,
        max_tokens=200,
    )
    raw = (result.get("text") or "").strip()
    if not result.get("ok") or not raw:
        return {"verdict": "ESCALATE", "reason": "triage_unavailable",
                "category": "novel", "confidence": 0.0, "quick_fix_hint": ""}

    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return {"verdict": "ESCALATE", "reason": "triage_no_json",
                "category": "novel", "confidence": 0.0, "quick_fix_hint": ""}
    try:
        parsed = json.loads(raw[start : end + 1])
    except Exception:
        return {"verdict": "ESCALATE", "reason": "triage_parse_error",
                "category": "novel", "confidence": 0.0, "quick_fix_hint": ""}

    if parsed.get("verdict") not in _VALID_VERDICTS:
        parsed["verdict"] = "ESCALATE"
    parsed.setdefault("category", "novel")
    parsed.setdefault("confidence", 0.0)
    parsed.setdefault("quick_fix_hint", "")
    parsed.setdefault("reason", "")
    return parsed
