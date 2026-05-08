"""
OpenRouter Zero-Cost Client — SOVEREIGN Free-Tier AI for AUREM
===============================================================

ALL models are FREE. Paid models are LAST RESORT only.

FREE_MODELS rotation list (if one fails, try next):
  1. qwen/qwen3-235b-a22b:free              (235B, primary general brain)
  2. nvidia/llama-3.1-nemotron-ultra-253b-v1:free  (253B, analysis beast)
  3. meta-llama/llama-3.3-70b-instruct:free  (70B, natural voice + search)
  4. microsoft/mai-ds-r1:free                (reasoning)
  5. deepseek/deepseek-r1:free               (deep reasoning)

ORA Brain routing:
  GENERAL  → qwen/qwen3-235b-a22b:free
  ANALYSIS → nvidia/llama-3.1-nemotron-ultra-253b-v1:free
  SEARCH   → meta-llama/llama-3.3-70b-instruct:free + DuckDuckGo

Agent → Model Routing:
  Scout     → nvidia/nemotron-3-super-120b-a12b:free  (262K, logic)
  Critic    → openai/gpt-oss-120b:free                (131K, reasoning)
  Architect → qwen/qwen3.6-plus:free                  (1M, coding)
  Heartbeat → stepfun/step-3.5-flash:free             (256K, speed)
  Envoy     → meta-llama/llama-3.3-70b-instruct:free  (natural voice)
  Oracle    → qwen/qwen3.6-plus:free                  (1M, forecasting)
  Closer    → nvidia/nemotron-3-super-120b-a12b:free  (deal analysis)

Paid fallback: ONLY if all 5 free models fail simultaneously.
"""

import os
import re
import json
import asyncio
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"

# ═══════════════════════════════════════════════════
# SOVEREIGN FREE MODELS — $0 OPERATIONAL COST
# ═══════════════════════════════════════════════════

FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-4-26b-it:free",
    "minimax/minimax-m2.5:free",
]

# Hierarchical model assignment per agent role (Strategy 4)
# Scout/Closer/Verifier = cheapest, Architect = deeper reasoning
AGENT_MODEL_MAP = {
    "scout": "meta-llama/llama-3.3-70b-instruct:free",
    "architect": "zai-org/glm-5.1",
    "envoy": "meta-llama/llama-3.3-70b-instruct:free",
    "closer": "meta-llama/llama-3.3-70b-instruct:free",
    "verifier": "meta-llama/llama-3.3-70b-instruct:free",
    "orchestrator": "nvidia/nemotron-3-super-120b-a12b:free",
    "repair": "zai-org/glm-5.1",
}

# ORA Brain model mapping (all free + :floor)
ORA_GENERAL_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
ORA_ANALYSIS_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
ORA_SEARCH_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
ORA_PAID_FALLBACK = "openai/gpt-4o"  # LAST RESORT only


async def _log_cost(model: str, query_type: str, response_time_ms: int = 0, success: bool = True):
    """Fire-and-forget cost logging."""
    try:
        from services.cost_savings_tracker import log_query_cost
        await log_query_cost(model, query_type, "system", response_time_ms, success)
    except Exception:
        pass

# ═══════════════════════════════════════════════════
# AGENT → FREE MODEL ROUTING TABLE
# ═══════════════════════════════════════════════════

AGENT_MODELS = {
    "scout":     "minimax/minimax-m2.5:free",
    "critic":    "openai/gpt-oss-120b:free",
    "architect": "zai-org/glm-5.1",
    "heartbeat": "meta-llama/llama-3.3-70b-instruct:free",
    "envoy":     "meta-llama/llama-3.3-70b-instruct:free",
    "oracle":    "minimax/minimax-m2.5:free",
    "closer":    "nvidia/nemotron-3-super-120b-a12b:free",
    "repair":    "zai-org/glm-5.1",
}

CRITIC_CONSENSUS_MODELS = [
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

# Paid OpenRouter fallbacks — used when free-tier models are rate-limited
# AND Emergent failover is unreachable. Cheap, reliable, no free-tier quotas.
OPENROUTER_PAID_FALLBACKS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-sonnet",
]

_db = None
_http_client: Optional[httpx.AsyncClient] = None
_free_model_cooldown_until = 0.0  # Unix timestamp; skip free models until then
_openrouter_key_invalid_until = 0.0  # Unix timestamp; skip ALL OpenRouter calls until then
_openrouter_key_dead = False  # Permanent kill-switch: once 401 seen, disable for process lifetime
_logged_429_models: set = set()  # Models we've already logged 429 for this pod — prevents spam
_emergent_failover_cooldown_until = 0.0  # Skip Emergent failover after repeated 502
_OPENROUTER_KEY_COOLDOWN = 3600  # 1 hour cooldown on 401 (reduce log spam)
_EMERGENT_502_COOLDOWN = 300  # 5 min cooldown when Emergent 502s repeatedly


def _set_cooldown(until_ts: float):
    global _free_model_cooldown_until
    _free_model_cooldown_until = until_ts


def set_db(database):
    global _db
    _db = database


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=12.0)
    return _http_client


# ═══════════════════════════════════════════════════
# CORE API CALL
# ═══════════════════════════════════════════════════

async def call_model(
    model: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.4,
    max_tokens: int = 2000,
) -> Dict:
    """Call an OpenRouter model. Falls back to Emergent on failure."""
    global _openrouter_key_invalid_until, _openrouter_key_dead

    # Permanent kill-switch: once 401 confirmed, never try OpenRouter again this pod.
    if _openrouter_key_dead:
        return await _emergent_failover(
            system_prompt, user_message, temperature, "openrouter_dead"
        )

    # If key was recently flagged as invalid, skip OpenRouter entirely
    if time.time() < _openrouter_key_invalid_until:
        return await _emergent_failover(
            system_prompt, user_message, temperature, "openrouter_key_cooldown"
        )

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("[OpenRouter] No API key — Emergent failover")
        return await _emergent_failover(system_prompt, user_message, temperature, "no_openrouter_key")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurem.ai",
        "X-Title": "AUREM AI Platform",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        client = _get_http_client()
        resp = await client.post(OPENROUTER_BASE, headers=headers, json=payload)

        if resp.status_code == 429:
            # Log only the FIRST 429 per model per pod — prevents 50×/min spam.
            if model not in _logged_429_models:
                logger.info(f"[OpenRouter] 429 rate limit on {model} — using Emergent fallback (suppressing further 429 logs for this model)")
                _logged_429_models.add(model)
            return await _emergent_failover(
                system_prompt, user_message, temperature, f"rate_limit_429_{model}"
            )

        if resp.status_code == 401:
            # One-shot kill switch. This key is invalid. Log ONCE then disable.
            if not _openrouter_key_dead:
                logger.warning(f"[OpenRouter] 401 auth on {model} — disabling for this pod, using Emergent fallback (graceful).")
                _openrouter_key_dead = True
            _openrouter_key_invalid_until = time.time() + _OPENROUTER_KEY_COOLDOWN
            return await _emergent_failover(
                system_prompt, user_message, temperature, "openrouter_401_auth"
            )

        resp.raise_for_status()
        data = resp.json()

        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content") or ""
        # Some reasoning models return answer in reasoning field
        if not content and msg.get("reasoning"):
            content = msg["reasoning"]

        logger.info(f"[OpenRouter] {model} → {len(content)} chars")

        return {
            "content": content,
            "model": model,
            "provider": "openrouter_paid" if not model.endswith(":free") else "openrouter_free",
            "usage": data.get("usage", {}),
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"[OpenRouter] HTTP {e.response.status_code} on {model}")
        return await _emergent_failover(
            system_prompt, user_message, temperature, f"http_{e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"[OpenRouter] Error on {model}: {e}")
        return await _emergent_failover(
            system_prompt, user_message, temperature, str(e)[:100]
        )


# ═══════════════════════════════════════════════════
# EMERGENT FAILOVER
# ═══════════════════════════════════════════════════

async def _try_paid_openrouter_fallback(
    system_prompt: str,
    user_message: str,
    temperature: float,
    max_tokens: int,
    reason: str,
) -> Optional[Dict]:
    """
    Try paid OpenRouter models before falling back to Emergent.
    Returns a result dict on success, None to let caller proceed to Emergent.

    Used when the free-tier model was 429'd. These paid models have their own
    independent quotas, so they usually work even when the free tier is
    congested upstream.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurem.ai",
        "X-Title": "AUREM ORA Brain (paid fallback)",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for model in OPENROUTER_PAID_FALLBACKS:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            client = _get_http_client()
            # 10s hard cap per paid-fallback model
            resp = await asyncio.wait_for(
                client.post(OPENROUTER_BASE, headers=headers, json=payload),
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content") or msg.get("reasoning") or ""
                if content:
                    logger.info(f"[ORA Brain] paid fallback {model} succeeded ({len(content)} chars) after {reason}")
                    return {
                        "content": content,
                        "model": model,
                        "provider": "openrouter_paid_fallback",
                        "failover_reason": reason,
                        "usage": data.get("usage", {}),
                    }
            else:
                logger.warning(f"[ORA Brain] paid fallback {model} returned {resp.status_code}")
        except asyncio.TimeoutError:
            logger.warning(f"[ORA Brain] paid fallback {model} timed out at 10s")
        except Exception as e:
            logger.warning(f"[ORA Brain] paid fallback {model} exception: {type(e).__name__}: {str(e)[:120]}")

    return None


async def _emergent_failover(
    system_prompt: str,
    user_message: str,
    temperature: float,
    reason: str,
) -> Dict:
    """Failover to Emergent LLM Key (GPT-4o) — ensures 100% uptime."""
    global _emergent_failover_cooldown_until
    # Short-circuit if Emergent has been repeatedly 502-ing — prevents event-loop
    # starvation from back-to-back 12s hangs.
    if time.time() < _emergent_failover_cooldown_until:
        return {
            "content": "",
            "model": "none",
            "provider": "failed",
            "error": "Emergent in cooldown (recent 502 burst)",
            "failover_reason": reason,
        }

    logger.info(f"[OpenRouter] Failover → Emergent GPT-4o (reason: {reason})")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            return {
                "content": "",
                "model": "none",
                "provider": "failed",
                "error": "No EMERGENT_LLM_KEY",
            }

        session = LlmChat(
            api_key=key,
            session_id=f"failover_{int(datetime.now(timezone.utc).timestamp())}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-4o-mini")

        # Hard 12s cap — Emergent failover occasionally 502s, and when it does
        # the SDK can block indefinitely, starving the uvicorn event loop and
        # making the whole backend unresponsive to new requests.
        response = await asyncio.wait_for(
            session.send_message(UserMessage(text=user_message)),
            timeout=12.0,
        )

        return {
            "content": response,
            "model": "gpt-4o-mini",
            "provider": "emergent_failover",
            "failover_reason": reason,
        }
    except asyncio.TimeoutError:
        logger.error("[OpenRouter] Emergent failover exceeded 12s timeout — engaging cooldown")
        _emergent_failover_cooldown_until = time.time() + _EMERGENT_502_COOLDOWN
        return {
            "content": "",
            "model": "none",
            "provider": "failed",
            "error": "Emergent failover timeout (12s)",
        }
    except Exception as e:
        # On 502/503/404/RateLimit, engage cooldown so we don't keep hitting upstream
        err_text = str(e).lower()
        if ("502" in err_text or "503" in err_text or "404" in err_text
                or "badgateway" in err_text or "serviceunavailable" in err_text
                or "notfounderror" in err_text or "ratelimiterror" in err_text
                or "no deployments available" in err_text):
            _emergent_failover_cooldown_until = time.time() + _EMERGENT_502_COOLDOWN
            logger.warning(f"[OpenRouter] Emergent failover upstream error → {_EMERGENT_502_COOLDOWN}s cooldown ({type(e).__name__})")
        else:
            logger.error(f"[OpenRouter] Emergent failover failed: {e}")
        return {
            "content": "",
            "model": "none",
            "provider": "failed",
            "error": str(e),
        }


# ═══════════════════════════════════════════════════
# AGENT-AWARE ROUTING
# ═══════════════════════════════════════════════════

async def call_agent_model(
    agent_id: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.4,
    max_tokens: int = 2000,
) -> Dict:
    """Route an agent call to its designated free model."""
    model = AGENT_MODELS.get(agent_id, "qwen/qwen3.6-plus:free")
    result = await call_model(
        model, system_prompt, user_message, temperature, max_tokens
    )
    await _audit_model_usage(agent_id, result)
    return result


# ═══════════════════════════════════════════════════
# CONSENSUS VALIDATION (Dual-Model Critic)
# ═══════════════════════════════════════════════════

async def consensus_validate(
    system_prompt: str,
    review_input: str,
) -> Dict:
    """
    Critic Consensus Validation — dual-model review.

    Both GPT-OSS-120B and Qwen 3.6 Plus review the same output.
    Both must agree for APPROVED. Disagreement defaults to FLAGGED.
    Cost: $0 (both models are free tier).
    """
    tasks = [
        call_model(model, system_prompt, review_input, temperature=0.2, max_tokens=1500)
        for model in CRITIC_CONSENSUS_MODELS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    parsed: List[Dict] = []
    for i, r in enumerate(results):
        model_name = CRITIC_CONSENSUS_MODELS[i]

        if isinstance(r, Exception):
            parsed.append({
                "verdict": "ERROR",
                "model": model_name,
                "error": str(r),
            })
            continue

        content = r.get("content", "") if isinstance(r, dict) else ""
        try:
            clean = content.strip()
            if clean.startswith("```"):
                match = re.search(r"```(?:json)?\s*\n(.*?)\n```", clean, re.DOTALL)
                if match:
                    clean = match.group(1)
            review = json.loads(clean)
            review["model"] = model_name
            review["provider"] = (
                r.get("provider", "openrouter_free") if isinstance(r, dict) else "unknown"
            )
            parsed.append(review)
        except (json.JSONDecodeError, Exception):
            parsed.append({
                "verdict": "PARSE_ERROR",
                "model": model_name,
                "confidence": 0.3,
                "raw": content[:200],
            })

    # Consensus logic
    verdicts = [p.get("verdict", "UNKNOWN") for p in parsed]

    if all(v == "APPROVED" for v in verdicts):
        consensus = "APPROVED"
        confidence = min((p.get("confidence", 0.8) for p in parsed), default=0.8)
    elif all(v in ("FLAGGED", "CHALLENGED") for v in verdicts):
        consensus = "FLAGGED"
        confidence = max((p.get("confidence", 0.5) for p in parsed), default=0.5)
    else:
        consensus = "FLAGGED"  # Disagreement → cautious
        confidence = 0.5

    # Audit the consensus
    await _audit_model_usage("critic_consensus", {
        "model": ",".join(CRITIC_CONSENSUS_MODELS),
        "provider": "openrouter_consensus",
        "consensus": consensus,
    })

    return {
        "consensus_verdict": consensus,
        "consensus_confidence": confidence,
        "models_used": CRITIC_CONSENSUS_MODELS,
        "individual_reviews": parsed,
        "agreement": len(set(verdicts)) == 1 if verdicts else False,
    }


# ═══════════════════════════════════════════════════
# BLOCKCHAIN AUDIT TRAIL
# ═══════════════════════════════════════════════════

async def _audit_model_usage(agent_id: str, result: Dict):
    """Log which model handled each task in the P4 Blockchain Audit."""
    if _db is None:
        return
    try:
        from routers.agent_execution_router import create_audit_entry

        audit_data = {
            "model": result.get("model", "unknown"),
            "provider": result.get("provider", "unknown"),
            "agent": agent_id,
        }
        if result.get("failover_reason"):
            audit_data["failover_reason"] = result["failover_reason"]

        await create_audit_entry(
            _db,
            action=f"model_route_{agent_id}",
            agent_id=agent_id,
            data=audit_data,
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════
# STATUS / ROUTING TABLE
# ═══════════════════════════════════════════════════

def get_routing_table() -> Dict:
    """Return current agent → model routing configuration."""
    has_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    return {
        "status": "SOVEREIGN" if has_key else "NO_KEY",
        "mode": "$0_FREE_TIER",
        "agent_models": AGENT_MODELS,
        "ora_brain": {
            "general": ORA_GENERAL_MODEL,
            "analysis": ORA_ANALYSIS_MODEL,
            "search": ORA_SEARCH_MODEL,
            "paid_fallback": ORA_PAID_FALLBACK,
        },
        "free_models": FREE_MODELS,
        "consensus_models": CRITIC_CONSENSUS_MODELS,
        "failover_chain": "free_rotation → paid_gpt4o → emergent_key",
        "estimated_cost": "$0/month (free tier)",
    }


# ═══════════════════════════════════════════════════
# ORA BRAIN — Sovereign Free Model Routing
# ═══════════════════════════════════════════════════

# Query type keywords → analysis model for deep reasoning
ANALYSIS_KEYWORDS = [
    "analyze", "analysis", "strategy", "forecast", "plan",
    "evaluate", "compare", "assess", "ooda", "swot",
    "breakdown", "deep dive", "root cause", "diagnose",
]


def _select_model_for_query(user_text: str) -> str:
    """Route: analysis → Nemotron 253B (free), general → Qwen 235B (free)."""
    lower = user_text.lower()
    if any(kw in lower for kw in ANALYSIS_KEYWORDS):
        return ORA_ANALYSIS_MODEL
    return ORA_GENERAL_MODEL


async def _try_free_model_rotation(
    api_key: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    start_model: str,
    reason: str,
) -> Dict:
    """Rotate through FREE_MODELS list when a model fails. Paid is LAST RESORT."""
    import time
    global _free_model_cooldown_until

    # If in cooldown, skip free models entirely → go straight to Emergent failover
    if time.time() < _free_model_cooldown_until:
        logger.info("[ORA Brain] Free models in cooldown — direct Emergent failover")
        return await _emergent_failover(
            messages[0]["content"] if messages else "",
            messages[-1]["content"] if messages else "",
            temperature, "free_models_cooldown",
        )

    # Build ordered list: start_model first, then rest of FREE_MODELS, then paid
    tried = {start_model}
    remaining_free = [m for m in FREE_MODELS if m != start_model]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurem.ai",
        "X-Title": "AUREM ORA Brain",
    }

    for model in remaining_free:
        tried.add(model)
        logger.info(f"[ORA Brain] Rotating to free model: {model} (reason: {reason})")
        try:
            client = _get_http_client()
            resp = await client.post(OPENROUTER_BASE, headers=headers, json={
                "model": model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens,
            })

            if resp.status_code == 401:
                logger.warning(f"[ORA Brain] 401 auth on rotation — key invalid, global cooldown {_OPENROUTER_KEY_COOLDOWN}s")
                _openrouter_key_invalid_until = time.time() + _OPENROUTER_KEY_COOLDOWN
                break

            if resp.status_code == 429:
                logger.warning(f"[ORA Brain] 429 on {model}, trying next...")
                continue

            resp.raise_for_status()
            data = resp.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            content = msg.get("content") or ""
            if not content and msg.get("reasoning"):
                content = msg["reasoning"]

            if content:
                logger.info(f"[ORA Brain] FREE rotation success: {model} → {len(content)} chars")
                asyncio.create_task(_log_cost(model, "general", 0, True))
                return {
                    "content": content, "model": model,
                    "provider": "openrouter_free", "web_searched": False,
                    "usage": data.get("usage", {}),
                }
        except Exception as e:
            logger.warning(f"[ORA Brain] {model} failed: {e}")
            continue

    # ALL free models failed → paid GPT-4o as absolute last resort
    # Set 5-minute cooldown to avoid spamming free models
    _free_model_cooldown_until_ref = time.time() + 300  # 5 min cooldown
    _set_cooldown(_free_model_cooldown_until_ref)
    logger.warning(f"[ORA Brain] All {len(tried)} free models rate-limited, cooling down 5min → PAID {ORA_PAID_FALLBACK}")
    try:
        client = _get_http_client()
        resp = await client.post(OPENROUTER_BASE, headers=headers, json={
            "model": ORA_PAID_FALLBACK, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        })
        if resp.status_code == 429:
            # Even paid is rate-limited, go to Emergent
            return await _emergent_failover(
                messages[0]["content"] if messages else "",
                messages[-1]["content"] if messages else "",
                temperature, "all_openrouter_exhausted",
            )
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content") or ""
        if not content and msg.get("reasoning"):
            content = msg["reasoning"]
        asyncio.create_task(_log_cost(ORA_PAID_FALLBACK, "general", 0, bool(content)))
        return {
            "content": content, "model": ORA_PAID_FALLBACK,
            "provider": "openrouter_paid_fallback", "web_searched": False,
            "usage": data.get("usage", {}),
        }
    except Exception:
        asyncio.create_task(_log_cost("emergent_failover", "general", 0, False))
        return await _emergent_failover(
            messages[0]["content"] if messages else "",
            messages[-1]["content"] if messages else "",
            temperature, "all_models_exhausted",
        )


async def call_ora_brain(
    system_prompt: str,
    user_message: str,
    conversation_history: list = None,
    enable_web_search: bool = False,
    model_override: str = None,
    temperature: float = 0.6,
    max_tokens: int = 800,
) -> Dict:
    """
    ORA's primary brain — SOVEREIGN FREE MODEL ROUTING.
    
    Model selection (all free):
      GENERAL  → qwen/qwen3-235b-a22b:free (235B)
      ANALYSIS → nvidia/llama-3.1-nemotron-ultra-253b-v1:free (253B)
      SEARCH   → meta-llama/llama-3.3-70b-instruct:free + ScoutSearch
    
    Fallback chain on 429/error:
      1. Try next free model in FREE_MODELS list
      2. Try third free model  
      3. Try fourth, fifth...
      4. ONLY THEN fall back to paid gpt-4o (last resort)
      5. Ultimate fallback: Emergent LLM Key
    """
    global _openrouter_key_invalid_until, _free_model_cooldown_until

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return await _emergent_failover(system_prompt, user_message, temperature, "no_openrouter_key")

    # Global key cooldown — skip OpenRouter entirely
    if time.time() < _openrouter_key_invalid_until:
        return await _emergent_failover(system_prompt, user_message, temperature, "openrouter_key_cooldown")

    # Free model cooldown — try paid OpenRouter before Emergent
    if time.time() < _free_model_cooldown_until:
        paid = await _try_paid_openrouter_fallback(
            system_prompt, user_message, temperature, max_tokens, "free_models_cooldown",
        )
        if paid:
            return paid
        return await _emergent_failover(system_prompt, user_message, temperature, "free_models_cooldown")

    # SOVEREIGN model routing — all free
    if enable_web_search:
        model = ORA_SEARCH_MODEL
        query_type = "search"
    elif any(kw in user_message.lower() for kw in ANALYSIS_KEYWORDS):
        model = model_override or ORA_ANALYSIS_MODEL
        query_type = "analysis"
    else:
        model = model_override or _select_model_for_query(user_message)
        query_type = "general"

    _start_time = time.time()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurem.ai",
        "X-Title": "AUREM ORA Brain",
    }

    # Build messages array
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        for msg in conversation_history[-8:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        client = _get_http_client()
        resp = await client.post(OPENROUTER_BASE, headers=headers, json=payload)

        if resp.status_code == 429:
            logger.warning(f"[ORA Brain] 429 rate limit on {model} — trying paid OpenRouter fallback first")
            _free_model_cooldown_until = time.time() + 120  # 2 min cooldown on free tier
            # Try paid OpenRouter before Emergent (upstream-independent)
            paid = await _try_paid_openrouter_fallback(
                system_prompt, user_message, temperature, max_tokens, f"429_on_{model}",
            )
            if paid:
                return paid
            return await _emergent_failover(system_prompt, user_message, temperature, f"429_on_{model}")

        if resp.status_code == 401:
            logger.warning(f"[ORA Brain] 401 auth failed — key invalid, cooldown {_OPENROUTER_KEY_COOLDOWN}s")
            _openrouter_key_invalid_until = time.time() + _OPENROUTER_KEY_COOLDOWN
            return await _emergent_failover(system_prompt, user_message, temperature, "openrouter_401_auth")

        resp.raise_for_status()
        data = resp.json()

        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content") or ""
        if not content and msg.get("reasoning"):
            content = msg["reasoning"]

        provider_tag = "openrouter_free" if ":free" in model else "openrouter_paid"
        logger.info(f"[ORA Brain] {model} → {len(content)} chars, web_search={enable_web_search}, cost=$0")

        elapsed_ms = int((time.time() - _start_time) * 1000)
        asyncio.create_task(_log_cost(model, query_type, elapsed_ms, bool(content)))

        return {
            "content": content,
            "model": model,
            "provider": provider_tag,
            "web_searched": enable_web_search,
            "usage": data.get("usage", {}),
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"[ORA Brain] HTTP {e.response.status_code} on {model}")
        return await _try_free_model_rotation(
            api_key, messages, temperature, max_tokens, model, f"http_{e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"[ORA Brain] Error on {model}: {e}")
        return await _try_free_model_rotation(
            api_key, messages, temperature, max_tokens, model, str(e)[:100]
        )
