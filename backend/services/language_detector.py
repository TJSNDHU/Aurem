"""
Language Detector — dual-pass (iter 281.4 / Phase 2.4)
=========================================================
Pass 1: `langdetect` (offline, fast, ~95% accurate for major scripts)
Pass 2: Claude Sonnet 4.5 verifies + corrects edge cases (Hinglish,
        Punjabi-Latin, Arabic-mixed, very short inputs)

Returns: {
  "lang": ISO 639-1 (e.g. 'hi', 'pa', 'en', 'fr', 'ar'),
  "script": Latn / Deva / Guru / Arab / Hans / etc.,
  "confidence": 0.0-1.0,
  "is_mixed": bool — Hinglish / Punglish / etc.,
  "reply_address": friendly term ('boss', 'bhai', 'chef', 'أستاذ' ...)
}

Performance:
  - Pass 1 alone: ~1ms
  - Pass 2 (LLM): ~600-1500ms — only invoked when langdetect confidence
    is below threshold OR text is < 20 chars OR mixed-script detected.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Friendly address terms (per language) ─────────────────────────
_ADDRESS_BY_LANG = {
    "en": "boss",
    "hi": "boss",
    "pa": "bhai",
    "ur": "boss",
    "fr": "chef",
    "es": "jefe",
    "pt": "chefe",
    "ar": "أستاذ",
    "zh": "老板",
    "de": "chef",
    "it": "capo",
    "ja": "ボス",
    "ko": "보스",
    "ru": "босс",
    "tr": "patron",
    "fa": "رئیس",
    "bn": "boss",
    "ta": "boss",
    "te": "boss",
    "mr": "boss",
    "gu": "boss",
}

# ── Script detection (pure regex, no deps) ────────────────────────
_SCRIPT_RANGES = [
    ("Deva", re.compile(r"[\u0900-\u097F]")),  # Devanagari (Hindi/Marathi)
    ("Guru", re.compile(r"[\u0A00-\u0A7F]")),  # Gurmukhi (Punjabi)
    ("Arab", re.compile(r"[\u0600-\u06FF]")),  # Arabic / Urdu
    ("Hans", re.compile(r"[\u4E00-\u9FFF]")),  # Han (Chinese)
    ("Hira", re.compile(r"[\u3040-\u309F]")),  # Hiragana (Japanese)
    ("Kana", re.compile(r"[\u30A0-\u30FF]")),  # Katakana (Japanese)
    ("Hang", re.compile(r"[\uAC00-\uD7AF]")),  # Hangul (Korean)
    ("Cyrl", re.compile(r"[\u0400-\u04FF]")),  # Cyrillic
    ("Beng", re.compile(r"[\u0980-\u09FF]")),  # Bengali
    ("Taml", re.compile(r"[\u0B80-\u0BFF]")),  # Tamil
    ("Telu", re.compile(r"[\u0C00-\u0C7F]")),  # Telugu
    ("Gujr", re.compile(r"[\u0A80-\u0AFF]")),  # Gujarati
]


def _detect_script(text: str) -> str:
    """Detect the dominant non-Latin script. Defaults to 'Latn'."""
    counts = {}
    for name, rgx in _SCRIPT_RANGES:
        n = len(rgx.findall(text))
        if n:
            counts[name] = n
    if not counts:
        return "Latn"
    return max(counts, key=counts.get)


# Heuristic markers for Hinglish / Punglish — common loan-words written
# in Latin that langdetect classifies as English but ORA must mirror.
_HINGLISH_MARKERS = re.compile(
    r"\b(aaj|aap|kya|kaisa|kaise|haan|nahi|nahin|theek|ho|hai|"
    r"karo|karenge|chal|chalo|bhai|boss|kar|raha|rahi|rahe|"
    r"kitna|kitne|dikhao|batao|bhej|leke|chahiye|abhi|kal)\b",
    re.IGNORECASE,
)
_PUNGLISH_MARKERS = re.compile(
    r"\b(tusi|tussi|tuhada|sadda|kithe|kidda|veer|paaji|chal|"
    r"theek|haan|nahi|kar|karda|kardi|karde|sun|dasso)\b",
    re.IGNORECASE,
)


def _pass_1(text: str) -> Dict[str, Any]:
    """Cheap offline detection using script + langdetect."""
    text = (text or "").strip()
    if len(text) < 2:
        return {"lang": "en", "script": "Latn", "confidence": 0.0, "is_mixed": False}

    script = _detect_script(text)

    # Script-driven shortcut: non-Latin scripts are usually unambiguous.
    if script == "Deva":
        return {"lang": "hi", "script": "Deva", "confidence": 0.92, "is_mixed": False}
    if script == "Guru":
        return {"lang": "pa", "script": "Guru", "confidence": 0.95, "is_mixed": False}
    if script == "Arab":
        # Could be Arabic or Urdu — Pass 2 disambiguates.
        return {"lang": "ar", "script": "Arab", "confidence": 0.65, "is_mixed": False}
    if script in ("Hans",):
        return {"lang": "zh", "script": "Hans", "confidence": 0.92, "is_mixed": False}
    if script in ("Hira", "Kana"):
        return {"lang": "ja", "script": script, "confidence": 0.92, "is_mixed": False}
    if script == "Hang":
        return {"lang": "ko", "script": "Hang", "confidence": 0.92, "is_mixed": False}

    # Latin script — try langdetect, then heuristic for Hinglish/Punglish.
    lang_guess = "en"
    confidence = 0.5
    try:
        from langdetect import detect_langs
        results = detect_langs(text)
        if results:
            top = results[0]
            lang_guess = str(top.lang)
            confidence = float(top.prob)
    except Exception as e:
        logger.debug(f"[lang] langdetect failed: {e}")

    is_mixed = False
    # Hinglish / Punglish reclassification — langdetect often returns
    # 'en' or random other for these because the function-words are Latin.
    if _HINGLISH_MARKERS.search(text):
        lang_guess = "hi"
        is_mixed = True
        confidence = max(confidence, 0.78)
    elif _PUNGLISH_MARKERS.search(text):
        lang_guess = "pa"
        is_mixed = True
        confidence = max(confidence, 0.78)

    # langdetect's notorious Hindi → Croatian (hr) misclassification fix.
    if lang_guess == "hr":
        lang_guess = "hi"
        confidence = max(confidence, 0.7)
        is_mixed = True

    return {
        "lang": lang_guess[:2],
        "script": "Latn",
        "confidence": round(confidence, 3),
        "is_mixed": is_mixed,
    }


async def _pass_2_verify(text: str, p1: Dict[str, Any]) -> Dict[str, Any]:
    """Use Claude Sonnet to verify language + style. Only invoked when
    Pass 1 confidence < 0.85 OR text < 20 chars (LLM is better at very
    short inputs)."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"lang_verify_{uuid.uuid4()}",
            system_message=(
                "You are a language classifier. Output a single line in the "
                "format `lang=XX script=YYYY mixed=true|false`. lang is ISO "
                "639-1 (en/hi/pa/ur/fr/es/ar/zh/ja/ko/de/it/pt/ru/tr/fa/bn/"
                "ta/te/mr/gu). script is ISO 15924 (Latn/Deva/Guru/Arab/"
                "Hans/Hira/Hang/Cyrl/Beng/Taml/Telu/Gujr). mixed=true ONLY "
                "when 30%+ of the words are loan-words (e.g. Hinglish, "
                "Punglish, Spanglish). No prose."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        out = (await chat.send_message(UserMessage(text=text[:240]))).strip().lower()
        m = re.search(r"lang\s*=\s*(\w{2,3})", out)
        s = re.search(r"script\s*=\s*(\w{4})", out)
        mx = re.search(r"mixed\s*=\s*(true|false)", out)
        if m:
            p1["lang"] = m.group(1)[:2]
            p1["confidence"] = max(p1.get("confidence", 0.5), 0.92)
        if s:
            p1["script"] = s.group(1).capitalize()
        if mx:
            p1["is_mixed"] = mx.group(1) == "true"
    except Exception as e:
        logger.debug(f"[lang] pass-2 verify failed: {e}")
    return p1


async def detect_language(text: str, *, force_pass_2: bool = False) -> Dict[str, Any]:
    """Public dual-pass entry point. Returns lang/script/confidence/is_mixed
    + reply_address. Pass 2 only fires when needed to keep latency tight.
    """
    p1 = _pass_1(text)
    needs_verify = (
        force_pass_2
        or p1["confidence"] < 0.85
        or len((text or "").strip()) < 20
    )
    if needs_verify:
        p1 = await _pass_2_verify(text, p1)
    p1["reply_address"] = _ADDRESS_BY_LANG.get(p1["lang"], "boss")
    return p1


# ── Memory: store + auto-promote preferred_language ───────────────
async def remember_language(
    db,
    *,
    session_id: str,
    user: str,
    detected: Dict[str, Any],
    promote_threshold: int = 3,
) -> Optional[str]:
    """Update working memory + promote to preferred when same lang seen
    `promote_threshold` times in a row in the same session.

    Stores under `db.ora_session_memory` keyed by (user, session_id).
    Returns the *current preferred language* (or None if not yet promoted).
    """
    if db is None:
        return None
    try:
        now_lang = detected.get("lang")
        if not now_lang:
            return None
        doc = await db.ora_session_memory.find_one(
            {"user": user, "session_id": session_id}
        ) or {}
        history = (doc.get("recent_langs") or [])[-9:] + [now_lang]
        same_streak = 1
        for prev in reversed(history[:-1]):
            if prev == now_lang:
                same_streak += 1
            else:
                break
        preferred = doc.get("preferred_language")
        if same_streak >= promote_threshold:
            preferred = now_lang
        await db.ora_session_memory.update_one(
            {"user": user, "session_id": session_id},
            {"$set": {
                "user": user,
                "session_id": session_id,
                "preferred_language": preferred,
                "recent_langs": history,
                "last_detected": detected,
                "updated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            }},
            upsert=True,
        )
        # Persist platform-wide via Hermes (best-effort, fire-and-forget).
        if same_streak >= promote_threshold:
            try:
                from services.hermes_memory_agent import fire_and_forget_store
                fire_and_forget_store(
                    db=db,
                    tenant_id="aurem_platform",
                    input_text=f"User {user} prefers language: {preferred}",
                    success=True,
                    action_type="user_language_preference",
                )
            except Exception:
                pass
        return preferred
    except Exception as e:
        logger.debug(f"[lang] remember failed: {e}")
        return None


# ── Translate an English ORA reply into the detected language ─────
async def localize_reply(
    text: str, *, target_lang: str, is_mixed: bool = False, address: str = "boss"
) -> str:
    """Re-emit ORA's reply in the user's detected language using Claude.
    Falls back to the original text on any LLM failure."""
    if not text or not target_lang or target_lang == "en":
        return text
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        style_hint = " in Hinglish/Punglish style — keep ~30% English loan words" if is_mixed else ""
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"loc_{uuid.uuid4()}",
            system_message=(
                f"You are a translator for ORA, AUREM's AI orchestrator. "
                f"Translate the assistant's reply to ISO 639-1 `{target_lang}` "
                f"language{style_hint}. Keep ORA's tone: sharp, direct, "
                f"confident. Use `{address}` for addressing. Preserve any "
                f"numbers, file paths, and proposal IDs verbatim. Output "
                f"ONLY the translated text — no preface, no explanation."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        out = (await chat.send_message(UserMessage(text=text[:3000]))).strip()
        return out or text
    except Exception as e:
        logger.debug(f"[lang] localize failed: {e}")
        return text
