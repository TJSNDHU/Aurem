"""
Deep Scout — Multi-Step Iterative Search with Gap Analysis (P1)
================================================================
3 steps max. After each step:
  - LLM evaluates what's still missing
  - If complete: return results
  - If incomplete: run next targeted query
Only triggers for complex queries (>10 words).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


def is_complex_query(query: str) -> bool:
    """Only trigger deep scout for complex queries (>10 words)."""
    return len((query or "").split()) > 10


def _extract_keywords(query: str) -> list:
    """Extract key search terms from a complex query."""
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "must", "shall",
                  "can", "for", "and", "but", "or", "nor", "not", "so", "yet",
                  "at", "by", "in", "of", "on", "to", "up", "it", "its", "with",
                  "from", "as", "into", "about", "that", "this", "what", "which",
                  "who", "whom", "how", "when", "where", "why", "all", "each",
                  "every", "both", "few", "more", "most", "other", "some", "such",
                  "no", "only", "own", "same", "than", "too", "very"}
    words = [w.strip(".,!?;:\"'()[]{}") for w in (query or "").lower().split()]
    return [w for w in words if w and w not in stop_words and len(w) > 2]


async def _search_step(tenant_id: str, query: str, step: int, previous_findings: list) -> dict:
    """Execute one search step. Returns findings + gap analysis."""
    db = _get_db()
    findings = []
    keywords = _extract_keywords(query)

    # Search knowledge_base
    if db is not None:
        for kw in keywords[:5]:
            async for doc in db.knowledge_base.find(
                {"tenant_id": tenant_id, "$or": [
                    {"pattern": {"$regex": kw, "$options": "i"}},
                    {"action_taken": {"$regex": kw, "$options": "i"}},
                ]},
                {"_id": 0}
            ).limit(3):
                findings.append({
                    "source": "knowledge_base",
                    "content": doc.get("pattern", doc.get("action_taken", "")),
                    "confidence": doc.get("confidence", 0.5),
                    "hit_count": doc.get("hit_count", 0),
                })

        # Search episodic_memory
        for kw in keywords[:3]:
            async for doc in db.episodic_memory.find(
                {"tenant_id": tenant_id, "$or": [
                    {"action_taken": {"$regex": kw, "$options": "i"}},
                    {"learned_pattern": {"$regex": kw, "$options": "i"}},
                ]},
                {"_id": 0}
            ).sort("timestamp", -1).limit(3):
                findings.append({
                    "source": "episodic_memory",
                    "content": doc.get("learned_pattern", doc.get("action_taken", "")),
                    "outcome": doc.get("outcome", "unknown"),
                })

        # Search leads for business context
        for kw in keywords[:2]:
            async for doc in db.leads.find(
                {"tenant_id": tenant_id, "$or": [
                    {"company": {"$regex": kw, "$options": "i"}},
                    {"name": {"$regex": kw, "$options": "i"}},
                ]},
                {"_id": 0, "name": 1, "company": 1, "status": 1, "enrichment": 1}
            ).limit(3):
                findings.append({
                    "source": "leads",
                    "content": f"{doc.get('name', '')} at {doc.get('company', '')} ({doc.get('status', '')})",
                })

    # Deduplicate by content
    seen = set()
    unique = []
    for f in findings:
        key = f.get("content", "")[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(f)

    # Gap analysis: LLM evaluates what's still missing
    covered_kws = set()
    for f in unique + previous_findings:
        content_lower = (f.get("content", "") or "").lower()
        for kw in keywords:
            if kw in content_lower:
                covered_kws.add(kw)
    missing_kws = [kw for kw in keywords if kw not in covered_kws]
    coverage = round(len(covered_kws) / max(len(keywords), 1) * 100, 1)

    # LLM gap analysis — evaluate completeness
    # iter 323r — routed through llm_gateway (Sovereign Ollama → OpenRouter →
    # Emergent fallback). Was direct EMERGENT_LLM_KEY → budget exhaustion.
    llm_analysis = ""
    llm_next_query = ""
    try:
        if unique:
            from services.llm_gateway import call_llm
            findings_text = "\n".join(f"- [{f.get('source')}] {f.get('content','')}" for f in unique[:10])
            prompt = (
                f"Original query: \"{query}\"\n\n"
                f"Findings so far (step {step}):\n{findings_text}\n\n"
                f"Missing keywords: {', '.join(missing_kws) if missing_kws else 'none'}\n\n"
                f"In 1-2 sentences: What information is still missing to fully answer the query? "
                f"If complete, say 'COMPLETE'. If incomplete, suggest a focused follow-up search query."
            )
            llm_analysis = await call_llm(
                system_prompt="You are a research gap analyst. Be concise.",
                user_prompt=prompt,
                max_tokens=300,
            )
            llm_analysis = (llm_analysis or "").strip()
            if llm_analysis.startswith("(LLM unavailable"):
                llm_analysis = ""
            elif "COMPLETE" in llm_analysis.upper():
                coverage = max(coverage, 90)
            elif llm_analysis and "search query:" in llm_analysis.lower():
                llm_next_query = llm_analysis.split("search query:")[-1].strip()
    except Exception as e:
        logger.warning(f"[DEEP_SCOUT] LLM gap analysis error (non-fatal): {e}")

    return {
        "step": step,
        "findings": unique,
        "covered_keywords": list(covered_kws),
        "missing_keywords": missing_kws,
        "coverage_pct": coverage,
        "is_complete": coverage >= 80 or len(missing_kws) == 0,
        "llm_analysis": llm_analysis,
        "llm_next_query": llm_next_query,
    }


async def deep_scout_search(tenant_id: str, query: str, max_steps: int = 3) -> dict:
    """
    Multi-step iterative search with gap analysis.
    Returns after coverage >= 80% or max_steps reached.
    """
    if not is_complex_query(query):
        return {
            "tenant_id": tenant_id,
            "query": query,
            "skipped": True,
            "reason": "simple_query",
            "steps": 0,
        }

    all_findings = []
    steps_log = []
    current_query = query

    for step in range(1, max_steps + 1):
        result = await _search_step(tenant_id, current_query, step, all_findings)
        all_findings.extend(result["findings"])
        steps_log.append(result)

        if result["is_complete"]:
            break

        # Refine query: use LLM suggestion or fallback to missing keywords
        if result.get("llm_next_query"):
            current_query = result["llm_next_query"]
        elif result["missing_keywords"]:
            current_query = " ".join(result["missing_keywords"])

    # Log the deep scout session
    db = _get_db()
    if db is not None:
        await db.deep_scout_log.insert_one({
            "tenant_id": tenant_id,
            "original_query": query,
            "steps_taken": len(steps_log),
            "total_findings": len(all_findings),
            "final_coverage": steps_log[-1]["coverage_pct"] if steps_log else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "tenant_id": tenant_id,
        "query": query,
        "skipped": False,
        "steps_taken": len(steps_log),
        "steps": steps_log,
        "total_findings": len(all_findings),
        "findings": all_findings,
        "final_coverage": steps_log[-1]["coverage_pct"] if steps_log else 0,
    }


async def get_deep_scout_stats(tenant_id: str = None) -> dict:
    """Stats for the deep scout system."""
    db = _get_db()
    if db is None:
        return {}
    query = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.deep_scout_log.count_documents(query)
    pipeline = [{"$match": query}] if query else []
    pipeline.append({"$group": {"_id": None,
                                "avg_steps": {"$avg": "$steps_taken"},
                                "avg_coverage": {"$avg": "$final_coverage"},
                                "avg_findings": {"$avg": "$total_findings"}}})
    avgs = {}
    async for doc in db.deep_scout_log.aggregate(pipeline):
        avgs = doc
    return {
        "total_searches": total,
        "avg_steps": round(avgs.get("avg_steps", 0), 1),
        "avg_coverage": round(avgs.get("avg_coverage", 0), 1),
        "avg_findings": round(avgs.get("avg_findings", 0), 1),
    }
