"""
AUREM Graphify Knowledge Graph Service
========================================
Integrates safishamsi/graphify into ORA's brain.
Builds a persistent knowledge graph from the codebase using tree-sitter AST (deterministic, $0).
Provides graph query, god nodes, surprising connections for ORA's retrieval pipeline.
"""
import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

GRAPH_DIR = Path("/app/backend/graphify-out")
GRAPH_JSON = GRAPH_DIR / "graph.json"
GRAPH_REPORT = GRAPH_DIR / "GRAPH_REPORT.md"

# In-memory graph cache
_graph = None
_graph_stats = {}
_last_build = None


def _ensure_dir():
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)


def build_knowledge_graph(
    target_dir: str = "/app/backend",
    include_frontend: bool = False,
) -> Dict:
    """
    Build the knowledge graph using graphify's deterministic AST pass.
    Code files: tree-sitter extraction ($0, no LLM needed).
    Returns build stats.
    """
    global _graph, _graph_stats, _last_build
    _ensure_dir()

    try:
        from graphify.extract import extract, collect_files
        from graphify.build import build
        from graphify.analyze import god_nodes, surprising_connections, suggest_questions

        # Collect target directories
        targets = [Path(target_dir)]
        if include_frontend:
            frontend_path = Path("/app/frontend/src")
            if frontend_path.exists():
                targets.append(frontend_path)

        all_files = []
        total_files = 0

        for target in targets:
            if not target.exists():
                continue
            files = collect_files(target)
            if files:
                all_files.extend(files)
                total_files += len(files)

        if not all_files:
            return {"status": "empty", "files_scanned": 0, "nodes": 0}

        logger.info(f"[Graphify] Extracting AST from {total_files} files...")

        # Extract using tree-sitter (deterministic, no LLM)
        extraction = extract(all_files)

        if not extraction or not extraction.get("nodes"):
            return {"status": "empty", "files_scanned": total_files, "nodes": 0}

        # Build the NetworkX graph
        logger.info(f"[Graphify] Building graph from {len(extraction['nodes'])} nodes, {len(extraction['edges'])} edges...")
        graph = build([extraction])

        # Analyze
        gods = god_nodes(graph, top_n=10)
        surprises = surprising_connections(graph, top_n=10)
        questions = []
        try:
            # Build community data for suggest_questions
            communities_dict = {}
            community_labels = {}
            for node_id, data in graph.nodes(data=True):
                c = data.get("community", -1)
                if c >= 0:
                    if c not in communities_dict:
                        communities_dict[c] = []
                        community_labels[c] = f"Community {c}"
                    communities_dict[c].append(str(node_id))
            if communities_dict:
                questions = suggest_questions(graph, communities_dict, community_labels)
        except Exception as e:
            logger.debug(f"[Graphify] suggest_questions: {e}")

        # Export graph.json
        graph_data = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "files_scanned": total_files,
                "extractions": len(extraction.get("nodes", [])),
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
            }
        }

        for node_id, data in graph.nodes(data=True):
            graph_data["nodes"].append({
                "id": str(node_id),
                "label": data.get("label", str(node_id)),
                "type": data.get("type", "unknown"),
                "file": data.get("file", ""),
                "community": data.get("community", -1),
            })

        for u, v, data in graph.edges(data=True):
            graph_data["edges"].append({
                "source": str(u),
                "target": str(v),
                "relation": data.get("relation", "related_to"),
                "confidence": data.get("confidence_score", 1.0),
                "tag": data.get("tag", "EXTRACTED"),
            })

        # Save
        with open(GRAPH_JSON, "w") as f:
            json.dump(graph_data, f, indent=2)

        # Generate report
        report_lines = [
            "# AUREM Knowledge Graph Report",
            f"\nBuilt: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Files scanned: {total_files}",
            f"Nodes: {graph.number_of_nodes()} | Edges: {graph.number_of_edges()}",
            "\n## God Nodes (Highest Connectivity)",
        ]
        for g in gods:
            if isinstance(g, dict):
                name = g.get("label", g.get("id", ""))
                ec = g.get("edges", "")
                report_lines.append(f"- **{name}** ({ec} connections)" if ec else f"- **{name}**")
            elif isinstance(g, tuple):
                report_lines.append(f"- **{g[0]}**")
            else:
                report_lines.append(f"- **{g}**")

        report_lines.append("\n## Surprising Connections")
        for s in surprises:
            if isinstance(s, tuple) and len(s) >= 2:
                report_lines.append(f"- {s[0]} <-> {s[1]}")
            else:
                report_lines.append(f"- {s}")

        report_lines.append("\n## Suggested Questions")
        for q in (questions or []):
            report_lines.append(f"- {q}")

        report_text = "\n".join(report_lines)
        with open(GRAPH_REPORT, "w") as f:
            f.write(report_text)

        # Cache in memory
        _graph = graph
        _last_build = datetime.now(timezone.utc).isoformat()
        _graph_stats = {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "files_scanned": total_files,
            "god_nodes": [g.get("label", g.get("id", "")) if isinstance(g, dict) else (g[0] if isinstance(g, tuple) else str(g)) for g in gods[:5]],
            "communities": len(set(d.get("community", -1) for _, d in graph.nodes(data=True))) - (1 if -1 in set(d.get("community", -1) for _, d in graph.nodes(data=True)) else 0),
            "built_at": _last_build,
        }

        logger.info(f"[Graphify] Graph built: {_graph_stats['nodes']} nodes, {_graph_stats['edges']} edges")
        return {"status": "built", **_graph_stats}

    except Exception as e:
        logger.error(f"[Graphify] Build failed: {e}")
        return {"status": "error", "error": str(e)}


def load_graph() -> Optional[Dict]:
    """Load graph.json from disk into memory."""
    global _graph, _graph_stats
    if GRAPH_JSON.exists():
        try:
            with open(GRAPH_JSON) as f:
                data = json.load(f)
            _graph_stats = data.get("metadata", {})
            return data
        except Exception as e:
            logger.warning(f"[Graphify] Failed to load graph: {e}")
    return None


def query_graph_local(query: str, top_k: int = 10) -> List[Dict]:
    """
    Query the knowledge graph using keyword matching on node labels.
    Returns relevant nodes and their connections.
    """
    data = load_graph()
    if not data:
        return []

    query_lower = query.lower()
    query_words = set(query_lower.split())

    # Score nodes by relevance
    scored = []
    for node in data.get("nodes", []):
        label = node.get("label", "").lower()
        node_type = node.get("type", "").lower()
        file_name = node.get("file", "").lower()

        score = 0
        for w in query_words:
            if len(w) < 3:
                continue
            if w in label:
                score += 3
            if w in node_type:
                score += 1
            if w in file_name:
                score += 1

        if score > 0:
            scored.append((score, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []

    node_ids = {n["id"] for _, n in scored[:top_k]}

    for score, node in scored[:top_k]:
        # Find edges connected to this node
        connections = []
        for edge in data.get("edges", []):
            if edge["source"] == node["id"] or edge["target"] == node["id"]:
                other = edge["target"] if edge["source"] == node["id"] else edge["source"]
                connections.append({
                    "target": other,
                    "relation": edge.get("relation", "related_to"),
                    "confidence": edge.get("confidence", 1.0),
                })

        results.append({
            "node": node["label"],
            "type": node.get("type", ""),
            "file": node.get("file", ""),
            "community": node.get("community", -1),
            "relevance_score": score,
            "connections": connections[:5],
        })

    return results


def get_graph_context(query: str, max_tokens: int = 500) -> str:
    """Get graph context for ORA's system prompt injection."""
    results = query_graph_local(query, top_k=5)
    if not results:
        return ""

    lines = ["=== KNOWLEDGE GRAPH CONTEXT ==="]
    char_count = 0
    for r in results:
        entry = f"[{r['type']}] {r['node']} (file: {r['file']})"
        if r['connections']:
            conns = ", ".join(f"{c['relation']}→{c['target']}" for c in r['connections'][:3])
            entry += f" → {conns}"
        if char_count + len(entry) > max_tokens * 4:
            break
        lines.append(entry)
        char_count += len(entry)

    return "\n".join(lines)


def get_graph_report() -> str:
    """Get the GRAPH_REPORT.md content."""
    if GRAPH_REPORT.exists():
        return GRAPH_REPORT.read_text(encoding="utf-8")
    return ""


def get_graph_stats() -> Dict:
    """Get current graph statistics for Overwatch."""
    if _graph_stats and _graph_stats.get("nodes"):
        return _graph_stats

    if GRAPH_JSON.exists():
        try:
            with open(GRAPH_JSON) as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            return {
                "nodes": meta.get("node_count", len(nodes)),
                "edges": meta.get("edge_count", len(edges)),
                "files_scanned": meta.get("files_scanned", 0),
                "built_at": meta.get("built_at", ""),
                "communities": len(set(n.get("community", -1) for n in nodes)) if nodes else 0,
            }
        except Exception:
            pass

    return {"nodes": 0, "edges": 0, "files_scanned": 0, "built_at": None, "status": "not_built"}
