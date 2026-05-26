"""
aurem_cto.services.stacks — Gap 2 (iter D-33)

Returns the catalog of supported stacks. The deploy system is
stack-agnostic so all four use the same `git pull && docker compose
up -d` deploy command.
"""
from __future__ import annotations

import pathlib
from typing import Any

STACKS_DIR = pathlib.Path(__file__).parent.parent / "templates" / "stacks"


def list_stacks() -> list[dict[str, Any]]:
    """Returns the four supported stacks with metadata."""
    catalog = [
        {
            "id":       "react-fastapi",
            "label":    "React + FastAPI",
            "tagline":  "The AUREM default. Best for SaaS landings + dashboards + APIs.",
            "tags":     ["python", "react", "mongo"],
            "default":  True,
            "ports":    {"ui": 3000, "api": 8001, "mongo": 27017},
        },
        {
            "id":       "nextjs-node",
            "label":    "Next.js + Node",
            "tagline":  "Single container. App Router serves UI + API together.",
            "tags":     ["typescript", "react", "mongo"],
            "default":  False,
            "ports":    {"app": 3000, "mongo": 27017},
        },
        {
            "id":       "vue-express",
            "label":    "Vue + Express",
            "tagline":  "Two containers. Best for teams already on Vue 3.",
            "tags":     ["javascript", "vue", "mongo"],
            "default":  False,
            "ports":    {"ui": 3000, "api": 8001, "mongo": 27017},
        },
        {
            "id":       "plain-html",
            "label":    "Plain HTML",
            "tagline":  "Zero build step. Caddy serves a static site/ folder.",
            "tags":     ["static", "caddy"],
            "default":  False,
            "ports":    {"http": 80, "https": 443},
        },
    ]
    # Verify every template directory exists (fail loud in tests).
    for s in catalog:
        s["template_present"] = (STACKS_DIR / s["id"] / "docker-compose.yml").exists()
    return catalog


def get_stack(stack_id: str) -> dict[str, Any] | None:
    for s in list_stacks():
        if s["id"] == stack_id:
            return s
    return None
