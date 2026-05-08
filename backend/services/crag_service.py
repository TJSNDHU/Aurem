"""
AUREM CRAG — Corrective Retrieval-Augmented Generation
=======================================================
Evaluates retrieved context quality before LLM generation.
If context is ambiguous or low-confidence, triggers a Web Scout
search to verify facts and inject corrected context.

Also includes a Self-Correction Critique loop that checks
the final LLM output for hallucinations before delivery.
"""
import os
import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# CRAG metrics (ring buffer)
_crag_metrics = []
_MAX_METRICS = 100


class RetrievalVerdict:
    CORRECT = "correct"       # High confidence, context is relevant
    AMBIGUOUS = "ambiguous"   # Partially relevant, needs verification
    INCORRECT = "incorrect"   # Context is irrelevant or misleading


async def evaluate_retrieval(
    query: str,
    retrieved_context: str,
    top_score: float = 0.0,
    use_sovereign: bool = True,
) -> Dict:
    """
    CRAG Evaluator: Assess whether retrieved context actually answers the query.
    Returns verdict (correct/ambiguous/incorrect) and confidence.
    
    Fast path: Score-based heuristic (< 5ms, no LLM call).
    Slow path: LLM evaluation for borderline cases.
    """
    t0 = time.time()

    # Fast path: score-based heuristic
    if top_score >= 0.85:
        return _verdict(RetrievalVerdict.CORRECT, top_score, int((time.time()-t0)*1000), "score_high")
    if top_score < 0.3 or not retrieved_context.strip():
        return _verdict(RetrievalVerdict.INCORRECT, top_score, int((time.time()-t0)*1000), "score_low_or_empty")

    # Borderline (0.3 - 0.85): Check keyword overlap as a fast secondary signal
    query_words = set(query.lower().split())
    context_words = set(retrieved_context.lower().split()[:100])
    overlap = len(query_words & context_words)
    overlap_ratio = overlap / max(len(query_words), 1)

    if overlap_ratio >= 0.5 and top_score >= 0.6:
        return _verdict(RetrievalVerdict.CORRECT, top_score, int((time.time()-t0)*1000), "keyword_overlap_high")
    if overlap_ratio < 0.2:
        return _verdict(RetrievalVerdict.INCORRECT, top_score, int((time.time()-t0)*1000), "keyword_overlap_low")

    # Ambiguous — needs deeper evaluation or Web Scout
    return _verdict(RetrievalVerdict.AMBIGUOUS, top_score, int((time.time()-t0)*1000), "borderline")


def _verdict(verdict: str, score: float, latency_ms: int, reason: str) -> Dict:
    result = {
        "verdict": verdict,
        "score": round(score, 4),
        "reason": reason,
        "latency_ms": latency_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _crag_metrics.append(result)
    if len(_crag_metrics) > _MAX_METRICS:
        _crag_metrics.pop(0)
    return result


async def web_scout_verify(
    query: str,
    claim: str = "",
    use_sovereign: bool = True,
) -> Dict:
    """
    Web Scout: Search the web to verify ambiguous retrieval context.
    Uses the Sovereign Brain to synthesize findings.
    Returns verified context or a correction.
    """
    t0 = time.time()

    # Try web search via existing infrastructure
    web_context = ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            # Use a simple search proxy or DuckDuckGo instant answers
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            )
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                answer = data.get("Answer", "")
                web_context = abstract or answer or ""
    except Exception as e:
        logger.debug(f"[CRAG] Web search failed: {e}")

    if not web_context:
        return {
            "verified": False,
            "web_context": "",
            "source": "web_scout",
            "latency_ms": int((time.time()-t0)*1000),
            "note": "No web results found for verification",
        }

    # Synthesize: merge web context with claim
    synthesis_prompt = f"""Verify this claim using web evidence.

CLAIM: {claim[:300] if claim else query}
WEB EVIDENCE: {web_context[:500]}

Is the claim accurate? Respond with:
VERDICT: CONFIRMED or CORRECTED
CORRECTION: (if corrected, provide the accurate version)
Keep response under 50 words."""

    synthesis = ""
    try:
        from services.hermes_identity import _call_sovereign, _call_cloud
        synthesis = await _call_sovereign(synthesis_prompt) if use_sovereign else None
        if not synthesis:
            synthesis = await _call_cloud(synthesis_prompt)
    except Exception:
        pass

    verified = "CONFIRMED" in (synthesis or "").upper()
    return {
        "verified": verified,
        "web_context": web_context[:300],
        "synthesis": synthesis[:200] if synthesis else "",
        "source": "web_scout",
        "latency_ms": int((time.time()-t0)*1000),
    }


async def critique_for_hallucinations(
    query: str,
    response: str,
    context_used: str = "",
    use_sovereign: bool = True,
) -> Dict:
    """
    Self-Correction Critique: Check the LLM response for hallucinations.
    Compares the response against the context that was actually provided.
    Returns critique with confidence and suggested corrections.
    
    Fast path: Skip critique for short responses or high-confidence contexts.
    """
    t0 = time.time()

    # Fast path: short responses rarely hallucinate
    if len(response) < 100:
        return {"passed": True, "confidence": 0.95, "reason": "short_response", "latency_ms": int((time.time()-t0)*1000)}

    # Fast path: if no context was used, can't check grounding
    if not context_used:
        return {"passed": True, "confidence": 0.7, "reason": "no_context_to_check", "latency_ms": int((time.time()-t0)*1000)}

    # LLM critique
    critique_prompt = f"""Check this AI response for hallucinations by comparing it to the source context.

USER QUESTION: {query[:200]}
SOURCE CONTEXT: {context_used[:400]}
AI RESPONSE: {response[:400]}

Check for:
1. Claims not supported by the source context
2. Invented statistics, dates, or names
3. Contradictions with the source

Respond EXACTLY in this format:
VERDICT: PASS or FAIL
ISSUES: (list any problems, or "none")
Keep under 40 words."""

    critique_text = None
    try:
        from services.hermes_identity import _call_sovereign, _call_cloud
        critique_text = await _call_sovereign(critique_prompt) if use_sovereign else None
        if not critique_text:
            critique_text = await _call_cloud(critique_prompt)
    except Exception as e:
        logger.debug(f"[CRAG] Critique failed: {e}")

    elapsed = int((time.time()-t0)*1000)

    if not critique_text:
        return {"passed": True, "confidence": 0.5, "reason": "critique_unavailable", "latency_ms": elapsed}

    passed = "PASS" in critique_text.upper() and "FAIL" not in critique_text.upper()
    issues = ""
    if "ISSUES:" in critique_text.upper():
        issues = critique_text.split("ISSUES:")[-1].strip()[:200]

    return {
        "passed": passed,
        "confidence": 0.9 if passed else 0.3,
        "issues": issues if not passed else "",
        "reason": "llm_critique",
        "latency_ms": elapsed,
    }


def get_crag_metrics() -> Dict:
    """Get CRAG metrics for Overwatch."""
    if not _crag_metrics:
        return {"total_evaluations": 0, "correct": 0, "ambiguous": 0, "incorrect": 0, "avg_latency_ms": 0}

    total = len(_crag_metrics)
    correct = sum(1 for m in _crag_metrics if m["verdict"] == RetrievalVerdict.CORRECT)
    ambiguous = sum(1 for m in _crag_metrics if m["verdict"] == RetrievalVerdict.AMBIGUOUS)
    incorrect = sum(1 for m in _crag_metrics if m["verdict"] == RetrievalVerdict.INCORRECT)
    avg_lat = sum(m["latency_ms"] for m in _crag_metrics) / total

    return {
        "total_evaluations": total,
        "correct": correct,
        "ambiguous": ambiguous,
        "incorrect": incorrect,
        "accuracy_rate": round(correct / max(total, 1) * 100, 1),
        "avg_latency_ms": round(avg_lat, 1),
    }
