# AuremContextManager — Graph Bridge Implementation

> Source: User-provided implementation spec (Lyra)
> Purpose: Python gatekeeper connecting Aurem AI agents to local code-review-graph MCP server
> Saved: February 2026

---

## The Bridge Function

```python
import subprocess
import json

class AuremContextManager:
    """
    The 'Brain' of Aurem's token-saving architecture.
    Connects the AI Agent to the local Code-Review-Graph.
    """

    def __init__(self, repo_path):
        self.repo_path = repo_path

    def get_lean_context(self, target_entity):
        """
        Queries the graph to find ONLY the necessary lines of code.
        """
        try:
            result = subprocess.run(
                ["code-review-graph", "impact-radius", "--entity", target_entity, "--json"],
                capture_output=True, text=True, cwd=self.repo_path
            )

            impact_data = json.loads(result.stdout)

            if impact_data.get("risk_score", 0) > 7:
                self.trigger_panic_hook(target_entity, impact_data["risk_score"])

            return impact_data.get("related_code_snippets", [])

        except Exception as e:
            return f"Error connecting to Graph: {str(e)}"

    def trigger_panic_hook(self, entity, score):
        print(f"WAR ROOM ALERT: High-risk extraction for {entity} (Risk: {score}/10)")
        # Trigger Rose-Gold pulsing UI alert
```

---

## Business Value

1. **Monolith Debt Solution** — Turns 40k-line black box into a surgical map
2. **Scientific-Luxe Scalability** — Knowledge graph = highest form of software precision
3. **Financial Efficiency** — ~$0.50-$2.00 saved per agent call in token costs

---

## Next Steps (Pending User Decision)

- [ ] JSON-LD communication schema for Sentiment Service ↔ core server
- [ ] Emergent instruction to install bridge and run first impact-radius check on SentimentAnalyzer
