"""Skill registry."""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, dict[str, Any]] = {}


def skill(*, name: str, description: str, requires_db: bool = False,
            requires_keys: list[str] | None = None) -> Callable:
    """Decorator: register an async function as an invokable skill."""
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        params = [
            {"name": p, "annotation": str(sig.parameters[p].annotation),
              "default": (None if sig.parameters[p].default is inspect.Parameter.empty
                            else sig.parameters[p].default)}
            for p in sig.parameters if p != "db"
        ]
        _REGISTRY[name] = {
            "fn":            fn,
            "name":          name,
            "description":   description,
            "requires_db":   requires_db,
            "requires_keys": list(requires_keys or []),
            "params":        params,
        }
        return fn
    return decorator


def list_skills() -> list[str]:
    return sorted(_REGISTRY.keys())


def manifest() -> list[dict]:
    """Public manifest — used by the CTO LLM to know what's available."""
    return [
        {"name": v["name"], "description": v["description"],
          "params": v["params"], "requires_keys": v["requires_keys"]}
        for v in sorted(_REGISTRY.values(), key=lambda x: x["name"])
    ]


async def invoke(name: str, db=None, **kwargs) -> dict[str, Any]:
    """Execute a skill by name.

    Returns {"ok": True, "result": ...} on success or
    {"ok": False, "error": "...", "skill": name} on failure.
    """
    entry = _REGISTRY.get(name)
    if not entry:
        return {"ok": False, "skill": name, "error": "unknown_skill"}
    try:
        if entry["requires_db"]:
            if db is None:
                return {"ok": False, "skill": name,
                          "error": "db_required_but_not_provided"}
            result = await entry["fn"](db=db, **kwargs)
        else:
            result = await entry["fn"](**kwargs)
        return {"ok": True, "skill": name, "result": result}
    except Exception as e:
        logger.exception(f"[cto_skills] {name} failed")
        return {"ok": False, "skill": name,
                 "error": f"{type(e).__name__}: {e}"}
