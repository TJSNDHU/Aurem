"""
Tool-call loop orchestrator — sovereign LLM + tools_bridge.
Mirrors /app/backend/services/llm_gateway.py:call_llm_with_tools() but
self-contained (no upstream import; HTTP-proxies tool execution).

Returns: {ok, content, provider, iterations, tool_calls_run,
          tool_invocations, max_iters_hit}.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from .llm import call_llm_with_meta
from .tools_bridge import list_tools, invoke_tool, extract_tool_calls

logger = logging.getLogger(__name__)

# Build the tool-call fence syntax without typing literal triple-backticks
# in this file's source (avoids accidental docstring termination when LLMs
# regenerate this file).  iter 322ex teaching note: ORA designs that embed
# ``` inside f-strings risk truncation; assemble at runtime instead.
_BT = chr(96) * 3
_TOOL_HELP_TEMPLATE = (
    "\n\n# AVAILABLE TOOLS — call them when you need REAL data.\n"
    "Emit a JSON block (fenced with " + _BT + "tool_call) like:\n"
    + _BT + "tool_call\n"
    '{"tool": "<name>", "args": {...}}\n'
    + _BT + "\n"
    "Then STOP. The orchestrator will execute it and feed you the real "
    "result, after which give your final answer.\n\n"
    "Tool catalog:\n"
)


async def chat_with_tools(
    prompt: str,
    jwt_token: str,
    system: Optional[str] = None,
    max_iters: int = 4,
) -> dict:
    """Run the LLM tool-call loop until final answer (no more tool calls)
    or `max_iters` cap is hit.  Every tool call goes through `tools_bridge`
    which HTTP-proxies to upstream AUREM (`/api/ora-tools/execute`)."""

    # 1. Fetch tool catalog from upstream
    try:
        tools = await list_tools(jwt_token)
    except Exception as e:
        logger.warning(f"list_tools upstream failed: {e!r}")
        tools = []

    catalog_lines = [
        f"- {t.get('name')}: {t.get('description', '')}\n"
        f"  args: {t.get('args_spec') or t.get('args') or {}}"
        for t in (tools or [])
    ]
    catalog_text = "\n".join(catalog_lines) or "(no tools available — answer from your own knowledge)"

    base_system = system or "You are ORA CTO Sovereign, running on the Legion laptop."
    enhanced_system = base_system + _TOOL_HELP_TEMPLATE + catalog_text

    transcript = prompt
    invocations: list[dict] = []
    final_provider = "?"
    iters = 0
    fallback_chain: list[str] = []

    while iters < max_iters:
        iters += 1
        meta = await call_llm_with_meta(
            enhanced_system, transcript, max_tokens=1500,
        )
        content = meta.get("content") or ""
        final_provider = meta.get("provider") or final_provider
        for p in meta.get("fallback_chain") or []:
            if p not in fallback_chain:
                fallback_chain.append(p)

        calls = extract_tool_calls(content)
        if not calls:
            return {
                "ok": meta.get("ok", True),
                "content": content,
                "provider": final_provider,
                "fallback_chain": fallback_chain,
                "iterations": iters,
                "tool_calls_run": len(invocations),
                "tool_invocations": invocations,
            }

        # Execute every tool call and feed results back into the transcript
        results_for_llm: list[dict] = []
        for c in calls:
            res = await invoke_tool(c["tool"], c.get("args") or {}, jwt_token)
            invocations.append({
                "tool": c["tool"],
                "args": c.get("args") or {},
                "ok": res.get("ok"),
                "elapsed_ms": res.get("elapsed_ms"),
                "error": res.get("error"),
            })
            results_for_llm.append({"tool": c["tool"], "result": res})

        transcript = (
            f"{transcript}\n\n=== TOOL RESULTS (iter {iters}) ===\n"
            f"{json.dumps(results_for_llm, default=str)[:4000]}\n"
            f"=== END TOOL RESULTS ===\n"
            f"Now give your FINAL answer using only these real results "
            f"(or call more tools if needed)."
        )

    return {
        "ok": True,
        "content": content,
        "provider": final_provider,
        "fallback_chain": fallback_chain,
        "iterations": iters,
        "tool_calls_run": len(invocations),
        "tool_invocations": invocations,
        "max_iters_hit": True,
    }
