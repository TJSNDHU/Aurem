"""
AUREM Advanced RAG — Hybrid Search Engine
==========================================
Combines BM25 keyword matching with vector embeddings for superior retrieval.
Includes MMR reranking for result diversity and metadata filtering.
Recursive Retrieval: auto second-degree search if top score < 0.85.
Tracks retrieval quality, recall, and context misses for Sentinel Overwatch.
"""
import math
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("[HybridSearch] rank_bm25 not installed — BM25 disabled")

# Retrieval quality metrics (ring buffer)
_retrieval_metrics = []
_MAX_METRICS = 200

# Recall tracking
_recall_stats = {
    "total_queries": 0,
    "high_confidence": 0,    # top score >= 0.85
    "low_confidence": 0,     # top score < 0.85
    "recursive_triggered": 0, # second-degree searches
    "recursive_improved": 0,  # recursive search actually helped
    "context_misses": 0,      # zero results returned
    "avg_top_score": 0.0,
}


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return [t for t in text.split() if len(t) > 1]


class BM25Index:
    """BM25 keyword index over a document corpus."""

    def __init__(self):
        self.documents = []
        self.doc_ids = []
        self.doc_metadatas = []
        self.tokenized_corpus = []
        self.bm25 = None

    def build(self, doc_ids: List[str], documents: List[str], metadatas: List[Dict]):
        """Build BM25 index from documents."""
        self.doc_ids = doc_ids
        self.documents = documents
        self.doc_metadatas = metadatas
        self.tokenized_corpus = [_tokenize(doc) for doc in documents]

        if BM25_AVAILABLE and self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            logger.info(f"[BM25] Index built: {len(documents)} documents")
        else:
            self.bm25 = None

    def search(self, query: str, top_k: int = 10, metadata_filter: Optional[Dict] = None) -> List[Dict]:
        """Search BM25 index. Returns [{id, document, metadata, bm25_score}]."""
        if not self.bm25 or not self.documents:
            return []

        tokenized_query = _tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)

        # Build results with optional metadata filter
        results = []
        for i, score in enumerate(scores):
            if score <= 0:
                continue

            # Apply metadata filter
            if metadata_filter and not _matches_filter(self.doc_metadatas[i], metadata_filter):
                continue

            results.append({
                "id": self.doc_ids[i],
                "document": self.documents[i],
                "metadata": self.doc_metadatas[i],
                "bm25_score": float(score),
            })

        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_k]

    @property
    def count(self):
        return len(self.documents)


def _matches_filter(metadata: Dict, filters: Dict) -> bool:
    """Check if metadata matches all filter criteria."""
    for key, value in filters.items():
        if key not in metadata:
            return False

        meta_val = metadata[key]

        # Range filter: {"price": {"$gte": 10, "$lte": 100}}
        if isinstance(value, dict):
            if "$gte" in value and meta_val < value["$gte"]:
                return False
            if "$lte" in value and meta_val > value["$lte"]:
                return False
            if "$gt" in value and meta_val <= value["$gt"]:
                return False
            if "$lt" in value and meta_val >= value["$lt"]:
                return False
            if "$eq" in value and meta_val != value["$eq"]:
                return False
            if "$ne" in value and meta_val == value["$ne"]:
                return False
            if "$in" in value and meta_val not in value["$in"]:
                return False
            continue

        # Exact match
        if isinstance(value, str) and isinstance(meta_val, str):
            if value.lower() != meta_val.lower():
                return False
        elif meta_val != value:
            return False

    return True


def mmr_rerank(
    query_embedding: List[float],
    doc_embeddings: List[List[float]],
    doc_results: List[Dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> List[Dict]:
    """
    Maximal Marginal Relevance (MMR) reranking.
    Balances relevance to query with diversity among results.
    lambda_param: 1.0 = pure relevance, 0.0 = pure diversity
    """
    if not doc_results or not doc_embeddings:
        return doc_results[:top_k]

    def cosine_sim(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # Compute query-doc similarities
    query_sims = [cosine_sim(query_embedding, emb) for emb in doc_embeddings]

    selected = []
    remaining = list(range(len(doc_results)))

    for _ in range(min(top_k, len(doc_results))):
        best_idx = None
        best_score = -float('inf')

        for idx in remaining:
            relevance = query_sims[idx]

            # Max similarity to already selected docs
            max_sim_to_selected = 0.0
            for sel_idx in selected:
                sim = cosine_sim(doc_embeddings[idx], doc_embeddings[sel_idx])
                max_sim_to_selected = max(max_sim_to_selected, sim)

            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected.append(best_idx)
            remaining.remove(best_idx)

    return [doc_results[i] for i in selected]


def hybrid_search(
    query: str,
    vector_results: List[Dict],
    bm25_index: BM25Index,
    top_k: int = 5,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
    metadata_filter: Optional[Dict] = None,
    use_mmr: bool = True,
    mmr_lambda: float = 0.7,
    query_embedding: Optional[List[float]] = None,
) -> Dict:
    """
    Hybrid search combining vector similarity and BM25 keyword matching.
    Returns fused results with retrieval quality metrics.
    """
    t0 = time.time()

    # BM25 search
    bm25_results = bm25_index.search(query, top_k=top_k * 2, metadata_filter=metadata_filter)

    # Apply metadata filter to vector results too
    filtered_vector = vector_results
    if metadata_filter:
        filtered_vector = [r for r in vector_results if _matches_filter(r.get("metadata", {}), metadata_filter)]

    # Reciprocal Rank Fusion (RRF) to merge both result sets
    rrf_k = 60  # Standard RRF constant
    fused_scores = {}

    for rank, result in enumerate(filtered_vector):
        doc_id = result.get("id", result.get("product_id", str(rank)))
        rrf_score = vector_weight / (rrf_k + rank + 1)
        fused_scores[doc_id] = {
            "rrf_score": rrf_score,
            "vector_rank": rank + 1,
            "vector_score": result.get("relevance_score", result.get("distance", 0)),
            "bm25_rank": None,
            "bm25_score": 0,
            "result": result,
        }

    for rank, result in enumerate(bm25_results):
        doc_id = result["id"]
        rrf_score = bm25_weight / (rrf_k + rank + 1)
        if doc_id in fused_scores:
            fused_scores[doc_id]["rrf_score"] += rrf_score
            fused_scores[doc_id]["bm25_rank"] = rank + 1
            fused_scores[doc_id]["bm25_score"] = result["bm25_score"]
        else:
            fused_scores[doc_id] = {
                "rrf_score": rrf_score,
                "vector_rank": None,
                "vector_score": 0,
                "bm25_rank": rank + 1,
                "bm25_score": result["bm25_score"],
                "result": result,
            }

    # Sort by fused RRF score
    sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x]["rrf_score"], reverse=True)

    # Build final results
    fused_results = []
    doc_embeddings_for_mmr = []

    for doc_id in sorted_ids[:top_k * 2]:
        entry = fused_scores[doc_id]
        result = entry["result"]
        result["hybrid_score"] = round(entry["rrf_score"], 6)
        result["vector_rank"] = entry["vector_rank"]
        result["bm25_rank"] = entry["bm25_rank"]
        result["retrieval_method"] = (
            "hybrid" if entry["vector_rank"] and entry["bm25_rank"]
            else "vector" if entry["vector_rank"]
            else "bm25"
        )
        fused_results.append(result)

        # Collect embeddings for MMR
        if query_embedding and result.get("embedding"):
            doc_embeddings_for_mmr.append(result["embedding"])
        else:
            doc_embeddings_for_mmr.append(None)

    # MMR Reranking
    if use_mmr and query_embedding:
        valid_embeddings = [e for e in doc_embeddings_for_mmr if e is not None]
        if len(valid_embeddings) >= 2:
            valid_results = [r for r, e in zip(fused_results, doc_embeddings_for_mmr) if e is not None]
            fused_results = mmr_rerank(
                query_embedding, valid_embeddings, valid_results,
                top_k=top_k, lambda_param=mmr_lambda,
            )
            # Add back results without embeddings
            remaining = [r for r, e in zip(fused_results, doc_embeddings_for_mmr) if e is None]
            fused_results = fused_results + remaining
        else:
            fused_results = fused_results[:top_k]
    else:
        fused_results = fused_results[:top_k]

    elapsed_ms = int((time.time() - t0) * 1000)

    # ── RECURSIVE RETRIEVAL: If top score < 0.85, do a second-degree search ──
    recursive_applied = False
    recursive_improved = False
    if fused_results:
        top_score = fused_results[0].get("hybrid_score", fused_results[0].get("relevance_score", 0))
        if top_score < 0.85 and bm25_index.count > 0:
            # Extract keywords from top result for second-degree search
            top_doc = fused_results[0].get("document", "")
            if top_doc:
                recursive_applied = True
                # Use top result's keywords as a second query
                second_query_words = _tokenize(top_doc)[:10]
                second_query = " ".join(second_query_words)
                second_bm25 = bm25_index.search(second_query, top_k=top_k, metadata_filter=metadata_filter)

                # Merge new results that aren't already in fused_results
                existing_ids = {r.get("id", "") for r in fused_results}
                new_found = 0
                for r2 in second_bm25:
                    if r2["id"] not in existing_ids:
                        r2["retrieval_method"] = "recursive_bm25"
                        r2["hybrid_score"] = r2.get("bm25_score", 0) * 0.3
                        fused_results.append(r2)
                        existing_ids.add(r2["id"])
                        new_found += 1
                        if new_found >= 2:
                            break

                if new_found > 0:
                    recursive_improved = True
                    logger.info(f"[RAG] Recursive retrieval added {new_found} results (top score was {top_score:.2f})")

                fused_results = fused_results[:top_k]

    elapsed_ms = int((time.time() - t0) * 1000)

    # Compute retrieval quality metrics + recall tracking
    hybrid_count = sum(1 for r in fused_results if r.get("retrieval_method") == "hybrid")
    vector_only = sum(1 for r in fused_results if r.get("retrieval_method") == "vector")
    bm25_only = sum(1 for r in fused_results if r.get("retrieval_method") == "bm25")
    recursive_count = sum(1 for r in fused_results if r.get("retrieval_method") == "recursive_bm25")

    # Top score for recall tracking
    top_score_val = 0.0
    if fused_results:
        top_score_val = fused_results[0].get("hybrid_score", fused_results[0].get("relevance_score", 0))

    is_context_miss = len(fused_results) == 0

    # Update recall stats
    _recall_stats["total_queries"] += 1
    if is_context_miss:
        _recall_stats["context_misses"] += 1
    elif top_score_val >= 0.85:
        _recall_stats["high_confidence"] += 1
    else:
        _recall_stats["low_confidence"] += 1
    if recursive_applied:
        _recall_stats["recursive_triggered"] += 1
    if recursive_improved:
        _recall_stats["recursive_improved"] += 1
    # Running average of top scores
    n = _recall_stats["total_queries"]
    _recall_stats["avg_top_score"] = round(
        ((_recall_stats["avg_top_score"] * (n - 1)) + top_score_val) / n, 4
    )

    quality = {
        "total_results": len(fused_results),
        "hybrid_matches": hybrid_count,
        "vector_only": vector_only,
        "bm25_only": bm25_only,
        "recursive_results": recursive_count,
        "overlap_ratio": round(hybrid_count / max(len(fused_results), 1), 2),
        "latency_ms": elapsed_ms,
        "top_score": round(top_score_val, 4),
        "recursive_applied": recursive_applied,
        "recursive_improved": recursive_improved,
        "context_miss": is_context_miss,
        "bm25_index_size": bm25_index.count,
        "metadata_filter_applied": metadata_filter is not None,
        "mmr_applied": use_mmr,
    }

    # Track metric
    _retrieval_metrics.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "query_length": len(query),
        **quality,
    })
    if len(_retrieval_metrics) > _MAX_METRICS:
        _retrieval_metrics.pop(0)

    return {
        "results": fused_results,
        "quality": quality,
    }


def get_retrieval_metrics() -> Dict:
    """Get retrieval quality metrics for Sentinel Overwatch."""
    if not _retrieval_metrics:
        return {
            "total_queries": 0,
            "avg_latency_ms": 0,
            "avg_overlap_ratio": 0,
            "avg_results": 0,
            "avg_top_score": 0,
            "method_distribution": {"hybrid": 0, "vector": 0, "bm25": 0, "recursive": 0},
            "recall": _recall_stats,
        }

    total = len(_retrieval_metrics)
    avg_latency = sum(m["latency_ms"] for m in _retrieval_metrics) / total
    avg_overlap = sum(m["overlap_ratio"] for m in _retrieval_metrics) / total
    avg_results = sum(m["total_results"] for m in _retrieval_metrics) / total
    avg_top = sum(m.get("top_score", 0) for m in _retrieval_metrics) / total

    method_dist = {"hybrid": 0, "vector": 0, "bm25": 0, "recursive": 0}
    for m in _retrieval_metrics:
        method_dist["hybrid"] += m.get("hybrid_matches", 0)
        method_dist["vector"] += m.get("vector_only", 0)
        method_dist["bm25"] += m.get("bm25_only", 0)
        method_dist["recursive"] += m.get("recursive_results", 0)

    # Compute recall rate
    recall_rate = 0.0
    if _recall_stats["total_queries"] > 0:
        recall_rate = round(
            (_recall_stats["high_confidence"] + _recall_stats["recursive_improved"])
            / _recall_stats["total_queries"] * 100, 1
        )

    return {
        "total_queries": total,
        "avg_latency_ms": round(avg_latency, 1),
        "avg_overlap_ratio": round(avg_overlap, 2),
        "avg_results": round(avg_results, 1),
        "avg_top_score": round(avg_top, 4),
        "method_distribution": method_dist,
        "recall": {
            **_recall_stats,
            "recall_rate": recall_rate,
            "context_miss_rate": round(
                _recall_stats["context_misses"] / max(_recall_stats["total_queries"], 1) * 100, 1
            ),
        },
        "recent": _retrieval_metrics[-10:],
    }
