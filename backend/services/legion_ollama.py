"""
legion_ollama.py — Bridge ORA to local Ollama running on the founder's
Legion laptop (iter 322fi-ollama).

Why this exists:
  Groq daily TPD limit + Cloudflare 520s on aurem.live keep killing ORA's
  ability to reply. The founder already runs Ollama (qwen2.5:7b) locally
  on the Legion laptop and the reverse-poll daemon is up. We piggy-back
  on legion_exec to call `curl localhost:11434/api/generate` from inside
  Legion — same plumbing, no daemon changes needed.

Flow:
  ORA chat → public_ora_demo_router._try_legion_ollama(text, history)
  → ask_legion_ollama(prompt) builds a JSON payload
  → enqueue shell job: curl http://localhost:11434/api/generate ...
  → Legion daemon picks it up in ≤5s, runs curl, captures stdout
  → POST /api/legion/queue/ack {stdout, ...}
  → parse Ollama's JSON, return clean text reply

Cost: ZERO (local). Latency: ~5-12s end-to-end depending on model + length.

Sovereignty: 100% — request never leaves the founder's hardware after
it leaves the pod's queue.
"""
from __future__ import annotations

import json
import logging
import os
import shlex

from services.legion_tool import legion_exec

logger = logging.getLogger(__name__)

DEFAULT_MODEL    = os.environ.get("LEGION_OLLAMA_MODEL", "qwen2.5:7b")
DEFAULT_OLLAMA   = os.environ.get("LEGION_OLLAMA_URL", "http://localhost:11434")
DEFAULT_TIMEOUT  = int(os.environ.get("LEGION_OLLAMA_TIMEOUT_S", "120"))


def _build_curl_cmd(payload: dict, ollama_url: str, timeout_s: int) -> str:
    """Build a shell-safe curl command that asks Ollama for a completion."""
    body = json.dumps(payload, ensure_ascii=False)
    # shlex.quote handles single-quote escapes for the JSON body
    return (
        f"curl -sS --max-time {int(timeout_s)} "
        f"-H 'Content-Type: application/json' "
        f"-d {shlex.quote(body)} "
        f"{ollama_url.rstrip('/')}/api/generate"
    )


async def ask_legion_ollama(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
    ollama_url: str | None = None,
    timeout_s: int | None = None,
    wait_max_s: int = 180,
) -> dict:
    """Send a prompt to Ollama on Legion and return the parsed reply.

    Returns:
        {ok: bool, reply: str, model: str, source: 'legion-ollama',
         elapsed_ms: int, raw?: dict, error?: str}
    """
    if not prompt or not isinstance(prompt, str):
        return {"ok": False, "source": "legion-ollama",
                "error": "prompt must be a non-empty string"}

    model_name = (model or DEFAULT_MODEL).strip()
    url = (ollama_url or DEFAULT_OLLAMA).strip()
    t = int(timeout_s or DEFAULT_TIMEOUT)

    payload: dict = {
        "model":   model_name,
        "prompt":  prompt[:8000],
        "stream":  False,
        "options": {
            "temperature": float(temperature),
            "num_predict": int(max_tokens),
        },
    }
    if system:
        payload["system"] = system[:4000]

    cmd = _build_curl_cmd(payload, url, t)
    logger.info(f"[legion-ollama] dispatching to {url} model={model_name} "
                f"prompt_len={len(prompt)}")

    result = await legion_exec(
        cmd=cmd,
        cwd="/opt/aurem-cto",
        timeout_s=t + 10,        # daemon-side timeout (curl's own + small grace)
        risk_hint="low",         # plain HTTP to localhost — no Telegram gate
        wait_max_s=wait_max_s,   # pod-side wait for daemon ack
    )
    if not result.get("ok"):
        return {"ok": False, "source": "legion-ollama",
                "error": result.get("error") or "legion_exec failed",
                "raw":   result}

    if int(result.get("exit_code", -1)) != 0:
        return {"ok": False, "source": "legion-ollama",
                "error": f"curl exit_code={result.get('exit_code')}",
                "stderr": (result.get("stderr") or "")[:400],
                "stdout_preview": (result.get("stdout") or "")[:300]}

    stdout = (result.get("stdout") or "").strip()
    if not stdout:
        return {"ok": False, "source": "legion-ollama",
                "error": "empty stdout from Ollama curl"}

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        return {"ok": False, "source": "legion-ollama",
                "error": f"non-JSON stdout: {e}",
                "stdout_preview": stdout[:300]}

    reply = (data.get("response") or "").strip()
    if not reply:
        return {"ok": False, "source": "legion-ollama",
                "error": "Ollama returned empty 'response'",
                "raw": data}

    return {
        "ok":         True,
        "source":     "legion-ollama",
        "model":      data.get("model") or model_name,
        "reply":      reply,
        "elapsed_ms": int(result.get("elapsed_ms", 0)),
        "eval_count": data.get("eval_count"),
        "total_duration_ns": data.get("total_duration"),
        "done":       data.get("done", True),
    }


async def ollama_health() -> dict:
    """Quick health probe — runs `curl ${OLLAMA_URL}/api/tags` on Legion."""
    cmd = (
        f"curl -sS --max-time 8 -o /tmp/.aurem-ollama-tags.json "
        f"-w '%{{http_code}}' "
        f"{DEFAULT_OLLAMA.rstrip('/')}/api/tags && "
        f"cat /tmp/.aurem-ollama-tags.json"
    )
    result = await legion_exec(
        cmd=cmd, cwd="/opt/aurem-cto", timeout_s=15,
        risk_hint="low", wait_max_s=20,
    )
    if not result.get("ok"):
        return {"ok": False, "reachable": False,
                "error": result.get("error") or "daemon enqueue failed"}
    stdout = (result.get("stdout") or "").strip()
    if not stdout:
        return {"ok": False, "reachable": False, "error": "empty response"}
    try:
        # First line of stdout is the http_code (from -w), rest is JSON body
        code = stdout[:3]
        body = stdout[3:].strip()
        if body:
            data = json.loads(body)
            return {"ok": True, "reachable": True, "http_code": code,
                    "models": [m.get("name") for m in data.get("models", [])]}
        return {"ok": True, "reachable": True, "http_code": code}
    except Exception as e:
        return {"ok": False, "reachable": False, "parse_error": str(e),
                "stdout_preview": stdout[:200]}
