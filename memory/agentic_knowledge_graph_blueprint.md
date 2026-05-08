# AUREM Agentic Knowledge Graph Architecture — Implementation Blueprint

> Source: User-provided technical blueprint (Lyra DETAIL Mode)
> Purpose: Transition from chatbot to agentic knowledge graph architecture
> Saved: February 2026

---

## Phase A: Brain Integration

Host MCP server locally (Lenovo Legion). Aurem agents query the graph database directly before any code modification.

### Impact Tool Pattern
```python
impact = mcp.call_tool("get_impact_radius", {"file": "sentiment_engine.py"})
if impact.risk_score > 7:
    trigger_war_room_alert("High-risk refactor detected in Sentiment Module.")
```

## Phase B: Selective Context Injection

1. Identify target function (e.g., `analyze_sentiment()`)
2. Request transitive dependencies from graph
3. Feed only ~200 relevant lines to LLM (not 40k)

---

## Business Benefits

- **Token ROI**: ~90% reduction in token consumption — enables using GPT-4o/Claude Sonnet at the price of cheaper models
- **War Room Stability**: Graph reveals invisible connections before commits. No silent breaks
- **5x Faster Modularization**: No guessing which parts are safe to cut
- **GEO Advantage**: Technical authority through agentic AI architecture

---

## Sentiment Analyzer Extraction Prompt

```
Role: Principal Systems Architect specializing in Python Monolith Decomposition
Context: Extracting 'Sentiment Analyzer' from Aurem 40k-line backend
Infrastructure: code-review-graph via MCP on Lenovo Legion 5i
Constraint: Do NOT read entire file. Use architecture_map tool first.

Task:
1. Call architecture_map — identify SentimentAnalyzer class and 1st-degree callers
2. Call get_impact_radius — find hidden dependencies on Aurem-Gen UI pulsing logic
3. Propose Phase C extraction plan:
   - Define sentiment_service.py
   - Create JSON-LD schema for service-to-core communication
   - Maintain Scientific-Luxe copper-wireframe aesthetic in monitoring logs

Output: Step-by-step extraction checklist + code diffs only
```

---

## Implementation Priority
- Phase A: MCP server setup on Legion → local graph API
- Phase B: Python gatekeeper function in Aurem backend
- Phase C: Begin extraction (Sentiment Analyzer first)
