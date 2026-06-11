"""
Unified LLM gateway — iter 282al-5 (Legion Sovereign Node priority).

Provider priority chain:
  1. Sovereign Node  (Legion Ollama via Cloudflare Tunnel / ngrok)
  2. OpenRouter      (cloud, cheap, pay-per-token)
  3. Emergent Key    (last resort — budget may be exhausted)

One entry point: `call_llm(system_prompt, user_prompt, ...)` → str.
Never raises — on total failure returns a short disabled-message string
AND sets `failure_reason` on the result. Call sites that want to detect
total failure should check the return prefix.

The function also returns a structured tuple via `call_llm_with_meta()`
for callers that need to know which provider served the request
(composer + morning brief log this for cost tracking).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal, Optional

logger = logging.getLogger(__name__)

Provider = Literal["sovereign", "openrouter", "emergent", "fallback"]

# Fixed fallback string — short + safe.
FAIL_MSG = "(LLM unavailable — all providers exhausted.)"


async def _try_sovereign(system_prompt: str, user_prompt: str,
                           max_tokens: int) -> Optional[str]:
    """Sovereign Node first. Uses existing chat_local() which already
    knows about retries / cold-start tunnel handling."""
    try:
        from services.local_llm_service import chat_local, is_available
        if not await is_available():
            return None
        resp = await asyncio.wait_for(
            chat_local(user_prompt, system_prompt=system_prompt or ""),
            timeout=45.0,
        )
        if resp and isinstance(resp, str) and resp.strip():
            logger.info(f"[llm_gateway] SERVED by sovereign ({len(resp)} chars, $0.00)")
            return resp.strip()[:max_tokens * 6]  # rough token-to-char cap
    except Exception as e:
        logger.debug(f"[llm_gateway] sovereign miss: {e}")
    return None


async def _try_openrouter(system_prompt: str, user_prompt: str,
                            max_tokens: int) -> Optional[str]:
    """OpenRouter primary tier for admin ORA CTO / ORA Paw chat (iter 325g).

    Model: DeepSeek V3.1 — ~$0.0001 per task, strong on code analysis.
    Claude Sonnet remains the next-tier fallback in `_try_emergent`
    for sensitive operations.

    Override via env vars:
        ORA_CTO_OPENROUTER_MODEL   — e.g. ``anthropic/claude-3.5-haiku``
        ORA_CTO_OPENROUTER_TEMP    — float, default 0.3 (lower than the
                                     legacy 0.4 because we want
                                     deterministic repair proposals).
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None
    model = (os.environ.get("ORA_CTO_OPENROUTER_MODEL", "").strip()
             or "deepseek/deepseek-chat-v3.1")
    try:
        temperature = float(os.environ.get("ORA_CTO_OPENROUTER_TEMP", "0.3"))
    except ValueError:
        temperature = 0.3
    try:
        import httpx
        payload = {
            "model":        model,
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://aurem.live",
                    "X-Title":       "AUREM",
                },
                json=payload,
            )
            if r.status_code != 200:
                logger.debug(f"[llm_gateway] openrouter {r.status_code}")
                return None
            data = r.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            content = msg.get("content") or msg.get("reasoning") or ""
            if content:
                logger.info(f"[llm_gateway] SERVED by openrouter/{model} ({len(content)} chars)")
                return content.strip()
    except Exception as e:
        logger.debug(f"[llm_gateway] openrouter miss: {e}")
    return None


async def _try_emergent(system_prompt: str, user_prompt: str,
                          max_tokens: int) -> Optional[str]:
    """Last-resort: Emergent universal key. Budget may be exhausted."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        # iter 322ep — use a UNIQUE session_id per call so the upstream
        # Emergent wrapper never carries stale conversation history
        # across unrelated gateway invocations. Reusing the literal
        # "gateway" session_id caused new skill broadcasts to be
        # ignored because Emergent's session cache pinned the old
        # system_message + assistant history.
        import uuid as _uuid
        sid = f"gw-{_uuid.uuid4().hex[:12]}"
        chat = (LlmChat(api_key=api_key, session_id=sid,
                         system_message=system_prompt or "")
                .with_model("anthropic", "claude-sonnet-4-5-20250929"))
        try:
            chat = chat.with_max_tokens(max_tokens)
        except Exception:
            pass
        resp = await asyncio.wait_for(
            chat.send_message(UserMessage(text=user_prompt)),
            timeout=30.0,
        )
        if isinstance(resp, str) and resp.strip():
            logger.info(f"[llm_gateway] SERVED by emergent ({len(resp)} chars)")
            return resp.strip()
    except Exception as e:
        # Common case: budget exceeded — log once at WARNING
        if "Budget" in str(e) or "exceeded" in str(e).lower():
            logger.warning("[llm_gateway] emergent key budget exhausted")
        else:
            logger.debug(f"[llm_gateway] emergent miss: {e}")
    return None


async def call_llm_with_meta(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    *,
    skip_sovereign: bool = False,
    bypass_cache: bool = False,
) -> dict:
    """Return {provider, content, ok} — never raises.

    iter 282al-13 — `skip_sovereign=True` skips the local node and goes
    straight to OpenRouter → Emergent. Useful for long-context dev-mode
    skill calls where the ngrok tunnel adds latency that bursts past
    chat-handler budgets.

    iter 322ec — Response cache wired here (the single chokepoint for
    every Claude/Groq/Sovereign call in AUREM). Identical (system, user)
    prompt pairs hit `llm_response_cache` instead of burning Emergent key
    budget. Pass `bypass_cache=True` for temperature-sensitive callers
    (creative writes, brainstorm). 12h TTL — short enough to drift with
    skill broadcast updates, long enough to absorb FAQ-style burst."""
    # Live skill broadcast — admin can push Antigravity SKILL.md playbooks
    # to ALL agents via /api/admin/antigravity-skills/broadcast. Every LLM
    # call routed through this gateway picks them up at runtime.
    #
    # Bug-fix #26 — `import server` here triggers a circular import the
    # FIRST time the module loads (server imports llm_gateway, llm_gateway
    # imports server). Python returns the half-built `server` module, so
    # `getattr(_srv, "db", None)` is None → addendum + cache silently miss.
    # Resolve via `sys.modules.get("server")` so we only see the module
    # AFTER it has finished initialising, and fall back gracefully on the
    # cold-start race.
    _db = None
    try:
        import sys as _sys
        _srv = _sys.modules.get("server")
        if _srv is not None:
            _db = getattr(_srv, "db", None)
    except Exception:
        _db = None
    try:
        from services.agent_skill_broadcast import get_addendum
        _ad = await get_addendum(_db, agent_name="GATEWAY")
        if _ad:
            system_prompt = (system_prompt or "") + _ad
    except Exception:
        pass

    # ── Cache lookup ────────────────────────────────────────────────
    # Compute the signature AFTER the skill-broadcast addendum so that
    # admin pushing a new SKILL.md auto-invalidates stale answers (the
    # signature changes with the addendum content).
    _cache_sig = ""
    if not bypass_cache and _db is not None and user_prompt:
        try:
            import hashlib as _hl
            _seed = f"{(system_prompt or '')[:1500]}||{user_prompt[:3000]}||{max_tokens}"
            _cache_sig = _hl.sha1(_seed.encode("utf-8")).hexdigest()[:20]
            from services.llm_response_cache import cache_get as _cg
            _hit = await _cg(_db, scope="llm_gateway",
                              signature=_cache_sig, prompt_seed="v1")
            if _hit and isinstance(_hit, dict) and _hit.get("content"):
                logger.info(f"[llm_gateway] cache HIT sig={_cache_sig[:8]} "
                            f"({_hit.get('provider','?')}, $0.00)")
                return {"provider": _hit.get("provider", "cache"),
                        "content": _hit["content"], "ok": True,
                        "cached": True}
        except Exception as _ce:
            logger.debug(f"[llm_gateway] cache_get failed: {_ce}")
            _cache_sig = ""  # don't try to write later if read path broke

    providers = (
        ("sovereign",   _try_sovereign),
        ("openrouter",  _try_openrouter),
        ("emergent",    _try_emergent),
    )
    if skip_sovereign:
        providers = providers[1:]
    for provider, fn in providers:
        try:
            content = await fn(system_prompt, user_prompt, max_tokens)
        except Exception as e:
            logger.debug(f"[llm_gateway] {provider} raised: {e}")
            continue
        if content:
            # ── Cache write (success only) ──────────────────────────
            if _cache_sig and _db is not None:
                try:
                    from services.llm_response_cache import cache_put as _cp
                    await _cp(_db, scope="llm_gateway",
                              signature=_cache_sig,
                              payload={"content": content, "provider": provider},
                              prompt_seed="v1", ttl_hours=12)
                except Exception as _ce:
                    logger.debug(f"[llm_gateway] cache_put failed: {_ce}")
            return {"provider": provider, "content": content, "ok": True}
    return {"provider": "fallback", "content": FAIL_MSG, "ok": False}


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    *,
    skip_sovereign: bool = False,
    bypass_cache: bool = False,
) -> str:
    """String-only convenience wrapper."""
    r = await call_llm_with_meta(
        system_prompt, user_prompt, max_tokens,
        skip_sovereign=skip_sovereign,
        bypass_cache=bypass_cache,
    )
    return r["content"]


# ─────────────────────────────────────────────────────────────────────
# Tool-calling loop (iter 322el) — for ORA / agents that need real
# investigation. Detects tool-call JSON in the LLM response, executes
# the tool server-side, feeds the REAL output back, re-invokes the LLM.
# Caps total iterations so it can't loop forever.
# ─────────────────────────────────────────────────────────────────────
import json as _json
import re as _re

_TOOL_CALL_RE = _re.compile(
    r"```(?:tool_call|json)?\s*"
    r"(\{[\s\S]*?\"tool\"[\s\S]*?\})"
    r"\s*```",
    _re.IGNORECASE,
)


def _extract_tool_calls(text: str) -> list[dict]:
    """Parse all valid `{"tool": "...", "args": {...}}` JSON blocks from
    the LLM response. Returns [] if none. Tolerates extra prose around
    the JSON — LLMs love to wrap things in explanation."""
    if not text:
        return []
    calls = []
    for m in _TOOL_CALL_RE.finditer(text):
        raw = m.group(1)
        try:
            obj = _json.loads(raw)
        except Exception:
            # Try to recover from trailing comma / single quotes
            try:
                obj = _json.loads(raw.replace("'", '"'))
            except Exception:
                continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            calls.append({
                "tool": obj["tool"],
                "args": obj.get("args") or {},
            })
    return calls


async def call_llm_with_tools(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    *,
    max_tool_iters: int = 4,
    actor: str = "ora",
) -> dict:
    """Full tool-calling loop:
        1. Call LLM with user prompt + system prompt + skill addendum +
           tool catalog appended.
        2. If response contains tool-call JSON blocks, execute each via
           services.ora_tools.invoke_tool (real subprocess / db / curl).
        3. Append tool results back into the conversation, re-call LLM.
        4. Repeat up to `max_tool_iters` times until LLM produces a final
           answer (no more tool calls) OR cap is hit.

    Returns:
        {
            ok:               bool,
            content:          str   (final LLM answer),
            tool_calls_run:   int,
            tool_invocations: [{tool, args, ok, elapsed_ms, ...}, ...],
            iterations:       int,
            provider:         str,
        }

    Used by the ORA chat handler when the user asks for live system data
    so the LLM can ACTUALLY check Mongo / grep code / curl endpoints
    instead of fabricating numbers (the iter 322ek hallucination trap).
    """
    from services.ora_tools import invoke_tool, list_tools

    # Inject the tool catalog so the LLM knows what's callable + the
    # exact JSON shape to emit.
    tool_catalog = list_tools()
    tool_help = (
        "\n\n# AVAILABLE TOOLS — call them when you need REAL data.\n"
        "Emit a JSON block (fenced with ```tool_call) like:\n"
        '```tool_call\n{\"tool\": \"<name>\", \"args\": {...}}\n```\n'
        "Then STOP. The gateway will execute it and feed you the real "
        "result. After the result lands, give your final answer.\n\n"
        "Tool catalog:\n"
    )
    for t in tool_catalog:
        tool_help += f"- {t['name']}: {t['description']}\n  args: {t['args_spec']}\n"

    enhanced_system = (system_prompt or "") + tool_help
    transcript = user_prompt
    invocations: list[dict] = []
    iters = 0
    final_provider = "?"
    # iter 322ey — fingerprint each (tool, args) call to detect loops where
    # the LLM re-emits the same expensive tool over and over (peer_review
    # with huge `context=` was the original offender). Second sighting of
    # the same fingerprint short-circuits straight to a synthesis prompt.
    _seen_fingerprints: set[str] = set()
    import hashlib as _hl

    def _fp(call_obj: dict) -> str:
        raw = call_obj.get("tool", "") + "::" + _json.dumps(
            call_obj.get("args") or {}, sort_keys=True, default=str
        )[:512]
        return _hl.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]

    while iters < max_tool_iters:
        iters += 1
        # Bypass cache because the conversation diverges each iter
        meta = await call_llm_with_meta(
            enhanced_system, transcript, max_tokens, bypass_cache=True,
        )
        content = meta.get("content") or ""
        final_provider = meta.get("provider") or final_provider

        calls = _extract_tool_calls(content)
        if not calls:
            # No more tool calls — this is the final answer.
            return {
                "ok":               meta.get("ok", True),
                "content":          content,
                "tool_calls_run":   len(invocations),
                "tool_invocations": invocations,
                "iterations":       iters,
                "provider":         final_provider,
            }

        # iter 322ey — loop-guard: detect tool-call replay.  If EVERY call
        # in this iter was already executed earlier with the same args, we
        # force a synthesis round instead of re-running the expensive work.
        all_replays = all(_fp(c) in _seen_fingerprints for c in calls)
        for c in calls:
            _seen_fingerprints.add(_fp(c))

        if all_replays:
            logger.warning(
                f"[llm_gateway] iter {iters}: all {len(calls)} tool calls "
                f"are duplicates — forcing synthesis"
            )
            transcript = (
                f"{transcript}\n\n"
                f"=== SYSTEM NOTE (iter {iters}) ===\n"
                f"You have already invoked {[c['tool'] for c in calls]} "
                f"with identical arguments earlier in this conversation. "
                f"Re-running them will give the same result. STOP calling "
                f"tools and synthesise your FINAL answer using the prior "
                f"tool results above. Do not emit another tool_call.\n"
                f"=== END SYSTEM NOTE ===\n"
            )
            continue  # next iter: LLM should produce final text

        # Execute each tool call SERVER-SIDE with real subprocess/db.
        results_for_llm = []
        for call in calls:
            res = await invoke_tool(call["tool"], call["args"], actor=actor)
            invocations.append({
                "tool":       call["tool"],
                "args":       call["args"],
                "ok":         res.get("ok"),
                "elapsed_ms": res.get("elapsed_ms"),
                "error":      res.get("error"),
                # Keep result compact for the next LLM turn — cap fields
                "result_preview": {
                    k: (v if not isinstance(v, str) else v[:400])
                    for k, v in res.items()
                    if k not in ("tool", "ts", "elapsed_ms", "ok")
                },
            })
            results_for_llm.append({
                "tool": call["tool"],
                "args": call["args"],
                "result": res,
            })

        # Feed real results back into the transcript and continue.
        transcript = (
            f"{transcript}\n\n"
            f"=== TOOL RESULTS (iter {iters}) ===\n"
            f"{_json.dumps(results_for_llm, default=str)[:4000]}\n"
            f"=== END TOOL RESULTS ===\n"
            f"Now give your FINAL answer using only these real results "
            f"(or call more tools if you need them)."
        )

    # Cap hit — return whatever the LLM said last
    return {
        "ok":               True,
        "content":          content,
        "tool_calls_run":   len(invocations),
        "tool_invocations": invocations,
        "iterations":       iters,
        "provider":         final_provider,
        "max_iters_hit":    True,
    }


# ─────────────────────────────────────────────────────────────────────
# Health — for Pillars Map + admin chip
# ─────────────────────────────────────────────────────────────────────
async def sovereign_health() -> dict:
    """Health for the Legion Sovereign Node (Ollama local LLM accelerator).

    Status logic:
      GREEN  = either tunnel reachable with models, OR tunnel intentionally
               offline AND a fallback LLM provider is configured (so the
               LLM subsystem as a whole is healthy).
      YELLOW = tunnel set but unreachable AND no fallback configured
               (LLM subsystem genuinely degraded).
      GREY   = URL not configured AND no fallback configured (LLM stack
               completely absent — fresh install state).

    Sovereign is OPT-IN sovereignty for tenants that want zero outbound
    LLM traffic. Most pods (including the founder preview + production)
    route through OpenRouter or Emergent's universal key. An unreachable
    Ollama tunnel is NOT an outage when those upstream providers work.
    """
    url = (os.environ.get("OLLAMA_URL")
           or os.environ.get("SOVEREIGN_NODE_URL") or "").strip()

    # Detect whether a fallback LLM provider is wired. Either explicit
    # keys, or the universal Emergent key.
    fallback_configured = bool(
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("EMERGENT_LLM_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )

    if not url:
        if fallback_configured:
            return {"ok": True, "status": "green",
                    "detail": "Sovereign Node not configured · cloud LLM fallback active",
                    "url": None, "models": [], "tunnel_status": "not_configured",
                    "fallback_active": True}
        return {"ok": True, "status": "grey",
                "detail": "SOVEREIGN_NODE_URL not configured · no LLM provider available",
                "url": None, "models": [], "tunnel_status": "not_configured",
                "fallback_active": False}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{url}/api/tags")
            if r.status_code != 200:
                # Tunnel reachable but returning error.
                if fallback_configured:
                    return {"ok": True, "status": "green",
                            "detail": f"Ollama tunnel returned {r.status_code} · cloud LLM fallback active",
                            "url": url, "models": [],
                            "tunnel_status": "error", "fallback_active": True}
                return {"ok": False, "status": "yellow",
                        "detail": f"tunnel returned {r.status_code}",
                        "url": url, "models": [],
                        "tunnel_status": "error", "fallback_active": False}
            data = r.json() or {}
            models = [m.get("name") for m in (data.get("models") or [])
                       if m.get("name")]
            return {
                "ok":     True,
                "status": "green",
                "detail": (f"sovereign reachable — {len(models)} models loaded"
                           if models
                           else "sovereign reachable · 0 models loaded · cloud LLM fallback active"),
                "url":    url,
                "models": models[:10],
                "tunnel_status": "online",
                "fallback_active": fallback_configured,
            }
    except Exception as e:
        # Sovereign tunnel unreachable. If fallback is configured, the LLM
        # subsystem is still healthy — report green with informational detail
        # about the offline accelerator. Otherwise, yellow (degraded, fallback
        # chain has no providers).
        if fallback_configured:
            return {"ok": True, "status": "green",
                    "detail": (f"Ollama tunnel offline ({type(e).__name__}) · "
                               f"cloud LLM fallback active"),
                    "url": url, "models": [],
                    "tunnel_status": "offline", "fallback_active": True}
        return {"ok": False, "status": "yellow",
                "detail": f"unreachable — {type(e).__name__}: {str(e)[:120]}",
                "url": url, "models": [],
                "tunnel_status": "offline", "fallback_active": False}


LLM_PROVIDER_ORDER = ("sovereign", "openrouter", "emergent", "fallback")

__all__ = [
    "call_llm",
    "call_llm_with_meta",
    "sovereign_health",
    "LLM_PROVIDER_ORDER",
    "FAIL_MSG",
]
