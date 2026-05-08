"""
CONSORTIUM Mode — Multi-Model Hive-Mind Synthesis (Enterprise Only)
====================================================================
From G0DM0D3: Race 5+ models simultaneously, orchestrator synthesizes ground truth.

Flow:
  1. Send query to N models in parallel via Emergent LLM Key
  2. Collect all responses
  3. Orchestrator LLM synthesizes best composite answer
  4. Return combined ground truth + individual model outputs

Models used: GPT-4o, Claude Sonnet, Gemini Flash (via emergentintegrations)
"""
import os
import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Model roster for consortium
CONSORTIUM_MODELS = [
    {"id": "gpt-4o", "provider": "openai", "label": "GPT-4o"},
    {"id": "claude-sonnet-4-5-20250929", "provider": "anthropic", "label": "Claude Sonnet"},
    {"id": "gemini/gemini-2.0-flash", "provider": "google", "label": "Gemini Flash"},
]


async def _call_model(provider: str, model_id: str, query: str, system: str = "") -> Dict:
    """Call a single LLM model via emergentintegrations LlmChat."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            return {"text": "", "model": model_id, "provider": provider, "success": False, "error": "No EMERGENT_LLM_KEY"}

        chat = LlmChat(
            api_key=key,
            session_id=f"consortium_{secrets.token_hex(4)}",
            system_message=system or "You are a world-class analyst. Be precise, direct, comprehensive.",
        )
        chat.with_model(provider, model_id)
        response = await chat.send_message(UserMessage(text=query))
        text = response.message if hasattr(response, 'message') else str(response)
        return {"text": text, "model": model_id, "provider": provider, "success": bool(text and len(text) > 10)}

    except Exception as e:
        logger.warning(f"[CONSORTIUM] {provider}/{model_id} failed: {e}")
        return {"text": "", "model": model_id, "provider": provider, "success": False, "error": str(e)}


async def _synthesize(query: str, responses: List[Dict]) -> str:
    """Orchestrator synthesizes ground truth from multiple model outputs."""
    successful = [r for r in responses if r.get("success") and r.get("text")]
    if not successful:
        return "All models failed to respond."
    if len(successful) == 1:
        return successful[0]["text"]

    # Build synthesis prompt
    model_outputs = "\n\n".join(
        f"--- {r['label'] if 'label' in r else r['model']} ---\n{r['text']}"
        for r in successful
    )

    synthesis_prompt = f"""You are the CONSORTIUM Orchestrator. You have received responses from {len(successful)} AI models to the same query.

ORIGINAL QUERY: {query}

MODEL RESPONSES:
{model_outputs}

YOUR TASK: Synthesize these into ONE definitive answer that:
1. Takes the strongest, most accurate points from each model
2. Resolves any contradictions by choosing the most well-reasoned position
3. Removes redundancy and hedging
4. Delivers a confident, comprehensive ground truth
5. Is direct — no preambles, no "based on the models" meta-commentary

SYNTHESIZED ANSWER:"""

    # Use GPT-4o as the orchestrator
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        chat = LlmChat(
            api_key=key,
            session_id=f"consortium_synth_{secrets.token_hex(4)}",
            system_message="You are the CONSORTIUM Orchestrator. Synthesize multiple AI responses into one ground truth. Be direct and confident.",
        )
        chat.with_model("openai", "gpt-4o")
        response = await chat.send_message(UserMessage(text=synthesis_prompt))
        return response.message if hasattr(response, 'message') else str(response)
    except Exception as e:
        logger.warning(f"[CONSORTIUM] Synthesis failed: {e}")
        # Fallback: return longest response
        return max(successful, key=lambda r: len(r.get("text", "")))["text"]


async def run_consortium(
    query: str,
    system_prompt: str = "",
    models: Optional[List[Dict]] = None,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    Run CONSORTIUM mode: race multiple models, synthesize ground truth.
    Enterprise tier only.
    """
    consortium_id = f"con_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc)
    model_roster = models or CONSORTIUM_MODELS

    # Race all models in parallel
    tasks = [
        _call_model(m["provider"], m["id"], query, system_prompt)
        for m in model_roster
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    model_results = []
    for i, resp in enumerate(responses):
        if isinstance(resp, Exception):
            model_results.append({
                "model": model_roster[i]["id"],
                "label": model_roster[i]["label"],
                "provider": model_roster[i]["provider"],
                "success": False,
                "error": str(resp),
                "text": "",
            })
        else:
            resp["label"] = model_roster[i]["label"]
            model_results.append(resp)

    successful_count = sum(1 for r in model_results if r.get("success"))

    # Synthesize ground truth
    synthesis = await _synthesize(query, model_results)

    # Apply STM to synthesis
    try:
        from services.stm_service import apply_stm
        stm = apply_stm(synthesis, ["hedge_reducer", "direct_mode"])
        synthesis = stm["transformed"]
    except Exception:
        pass

    return {
        "consortium_id": consortium_id,
        "ground_truth": synthesis,
        "models_queried": len(model_roster),
        "models_responded": successful_count,
        "model_results": [
            {"model": r["label"], "provider": r["provider"], "success": r["success"],
             "preview": r.get("text", "")[:200] if r.get("success") else r.get("error", "")}
            for r in model_results
        ],
        "timestamp": now.isoformat(),
    }
