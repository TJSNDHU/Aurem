"""
AUREM BitNet Worker — Lightweight Skill Executor
=================================================
Uses qwen2:0.5b (via Ollama) as a micro-worker for offloaded skills.
When a skill reaches 100% stability, ORA hands it off to this worker
instead of using the full llama3.1 brain — saving GPU cycles.

Skill Stability Scoring:
  - Each consolidation tags skills with a stability score (0-100)
  - Score increases with successful executions, decreases on failures
  - At 100%, the skill is auto-offloaded to the BitNet worker
"""
import os
import json
import logging
import asyncio
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
STABILITY_FILE = Path(__file__).parent.parent / "identity" / "SKILL_STABILITY.json"

# BitNet worker config
WORKER_MODEL = "qwen2:0.5b"
STABILITY_THRESHOLD = 100  # Score at which skill gets offloaded

# In-memory stability registry
_stability_registry: Dict[str, Dict] = {}


def _load_stability():
    """Load stability scores from disk."""
    global _stability_registry
    try:
        if STABILITY_FILE.exists():
            _stability_registry = json.loads(STABILITY_FILE.read_text(encoding="utf-8"))
    except Exception:
        _stability_registry = {}


def _save_stability():
    """Persist stability scores to disk."""
    try:
        STABILITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        STABILITY_FILE.write_text(json.dumps(_stability_registry, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[BitNet] Failed to save stability: {e}")


def get_skill_stability(skill_name: str) -> Dict:
    """Get stability data for a skill."""
    _load_stability()
    return _stability_registry.get(skill_name, {
        "score": 0, "executions": 0, "successes": 0, "failures": 0,
        "offloaded": False, "last_execution": None,
    })


def update_stability(skill_name: str, success: bool):
    """Update stability score after a skill execution."""
    _load_stability()

    if skill_name not in _stability_registry:
        _stability_registry[skill_name] = {
            "score": 0, "executions": 0, "successes": 0, "failures": 0,
            "offloaded": False, "created_at": datetime.now(timezone.utc).isoformat(),
        }

    entry = _stability_registry[skill_name]
    entry["executions"] += 1
    entry["last_execution"] = datetime.now(timezone.utc).isoformat()

    if success:
        entry["successes"] += 1
        # Score increases: +20 per success, capped at 100
        entry["score"] = min(100, entry["score"] + 20)
    else:
        entry["failures"] += 1
        # Score decreases: -30 per failure, floor at 0
        entry["score"] = max(0, entry["score"] - 30)

    # Auto-offload check
    if entry["score"] >= STABILITY_THRESHOLD and not entry["offloaded"]:
        entry["offloaded"] = True
        entry["offloaded_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[BitNet] Skill '{skill_name}' reached 100% stability — OFFLOADED to {WORKER_MODEL}")

    _stability_registry[skill_name] = entry
    _save_stability()
    return entry


def tag_consolidation_stability(session_id: str, mistakes: int, habits: int) -> int:
    """
    Tag a Dream Consolidation with a stability score.
    Score based on: no mistakes = high stability, many habits = higher.
    """
    base = 50
    if mistakes == 0:
        base += 30
    else:
        base -= mistakes * 15

    base += min(habits * 10, 20)
    return max(0, min(100, base))


def get_all_stability() -> Dict[str, Dict]:
    """Get stability data for all skills."""
    _load_stability()
    return _stability_registry


def get_offloaded_skills() -> List[str]:
    """Get list of skills that have been offloaded to the BitNet worker."""
    _load_stability()
    return [name for name, data in _stability_registry.items() if data.get("offloaded")]


async def call_worker(
    prompt: str,
    skill_context: str = "",
    ollama_url: Optional[str] = None,
) -> Dict:
    """
    Call the BitNet worker (qwen2:0.5b) for offloaded skill execution.
    Lightweight and fast — doesn't load the full llama3.1 brain.
    """
    if not ollama_url:
        try:
            from services.local_llm_service import get_config
            cfg = get_config()
            ollama_url = cfg.get("ollama_url", "")
        except Exception:
            pass

    if not ollama_url:
        return {"success": False, "error": "No Ollama URL configured", "worker": WORKER_MODEL}

    system = "You are a precise task executor. Follow the skill procedure exactly."
    if skill_context:
        system += f"\n\nSKILL REFERENCE:\n{skill_context}"

    try:
        import httpx
        t0 = time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ollama_url}/v1/chat/completions",
                headers={},
                json={
                    "model": WORKER_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                    "stream": False,
                }
            )
            elapsed_ms = int((time.time() - t0) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("completion_tokens", len(content.split()))
                tps = round(tokens / (elapsed_ms / 1000), 1) if elapsed_ms > 0 else 0

                return {
                    "success": True,
                    "response": content,
                    "worker": WORKER_MODEL,
                    "latency_ms": elapsed_ms,
                    "tokens": tokens,
                    "tps": tps,
                    "cost": "$0.00",
                }
            elif resp.status_code == 404:
                return {
                    "success": False,
                    "error": f"Model {WORKER_MODEL} not found. Run: ollama pull {WORKER_MODEL}",
                    "worker": WORKER_MODEL,
                    "action": f"Pull the model on your Legion: ollama pull {WORKER_MODEL}",
                }
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}", "worker": WORKER_MODEL}
    except Exception as e:
        return {"success": False, "error": str(e), "worker": WORKER_MODEL}


async def execute_offloaded_skill(skill_name: str, task_input: str, ollama_url: Optional[str] = None) -> Dict:
    """
    Execute a task using an offloaded skill via the BitNet worker.
    Loads the skill doc as context, sends to qwen2:0.5b.
    Updates stability score based on result.
    """
    # Load skill document
    skill_path = SKILLS_DIR / f"{skill_name}.md"
    if not skill_path.exists():
        # Fuzzy match
        for f in SKILLS_DIR.glob("*.md"):
            if skill_name.lower() in f.stem.lower():
                skill_path = f
                break

    skill_context = ""
    if skill_path.exists():
        skill_context = skill_path.read_text(encoding="utf-8")

    result = await call_worker(task_input, skill_context, ollama_url)

    # Update stability
    success = result.get("success", False)
    if success and result.get("response") and len(result["response"]) > 20:
        update_stability(skill_name, True)
        result["stability"] = get_skill_stability(skill_name)
    else:
        update_stability(skill_name, False)
        result["stability"] = get_skill_stability(skill_name)

    return result


def get_worker_stats() -> Dict:
    """Get BitNet worker stats for Overwatch."""
    _load_stability()
    total = len(_stability_registry)
    offloaded = sum(1 for d in _stability_registry.values() if d.get("offloaded"))
    total_execs = sum(d.get("executions", 0) for d in _stability_registry.values())
    total_success = sum(d.get("successes", 0) for d in _stability_registry.values())
    avg_score = round(
        sum(d.get("score", 0) for d in _stability_registry.values()) / max(total, 1), 1
    )

    return {
        "worker_model": WORKER_MODEL,
        "total_skills": total,
        "offloaded_skills": offloaded,
        "stability_threshold": STABILITY_THRESHOLD,
        "avg_stability_score": avg_score,
        "total_executions": total_execs,
        "success_rate": round(total_success / max(total_execs, 1) * 100, 1),
        "skills": {
            name: {
                "score": data.get("score", 0),
                "offloaded": data.get("offloaded", False),
                "executions": data.get("executions", 0),
            }
            for name, data in _stability_registry.items()
        },
    }
