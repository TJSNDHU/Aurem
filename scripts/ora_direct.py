#!/usr/bin/env python3
"""
ora_direct.py — Invoke ORA's tool-call loop WITHOUT going through HTTP.

Usage:
    python ora_direct.py <prompt_file.json>

Reads `{prompt, max_tool_iters, system?}` from the JSON file and prints
the full result. Bypasses the FastAPI / watchdog / preview-proxy stack
so long-running prompts (>60s) can complete reliably.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure /app/backend is on sys.path so `services.*` imports work
BACKEND = Path("/app/backend")
sys.path.insert(0, str(BACKEND))

# Load env so MONGO_URL / GROQ_API_KEY / EMERGENT_LLM_KEY are present
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


async def main(prompt_path: str):
    spec = json.loads(Path(prompt_path).read_text())
    prompt = spec["prompt"]
    max_iters = int(spec.get("max_tool_iters", 4))
    system = spec.get("system") or (
        "You are ORA CTO, the AUREM autonomous engineer. Apply Zero "
        "Hallucination Charter: every claim must be tool-grounded. Use "
        "your tools. Quote real output. End with 3-proof footer."
    )

    # Wire up DB so audit logging works
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo = AsyncIOMotorClient(
            os.environ["MONGO_URL"],
            serverSelectionTimeoutMS=5000,
        )
        db = mongo[os.environ.get("DB_NAME", "aurem_db")]
        from services.ora_tools import set_db
        set_db(db)
    except Exception as e:
        print(f"[warn] DB wire-up failed: {e}", file=sys.stderr)

    from services.llm_gateway import call_llm_with_tools

    start = time.time()
    res = await call_llm_with_tools(
        system_prompt=system,
        user_prompt=prompt,
        max_tokens=2400,
        max_tool_iters=max_iters,
        actor="main-agent-direct",
    )
    elapsed = time.time() - start

    # Shape the same way /api/ora-chat/ask does
    out = {
        "ok": res.get("ok"),
        "provider": res.get("provider"),
        "iterations": res.get("iterations"),
        "tool_calls_run": res.get("tool_calls_run"),
        "tool_invocations": [
            {
                "tool": inv.get("tool"),
                "ok": inv.get("ok"),
                "elapsed_ms": inv.get("elapsed_ms"),
                "error": inv.get("error"),
                "args_keys": list((inv.get("args") or {}).keys()),
            }
            for inv in (res.get("tool_invocations") or [])
        ],
        "content": res.get("content"),
        "wall_clock_s": round(elapsed, 2),
    }
    # Write to result file (2nd arg) if given, else stderr — keep stdout clean
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    payload = json.dumps(out, default=str, indent=2)
    if out_path:
        Path(out_path).write_text(payload)
        sys.stderr.write(f"[ora_direct] result written to {out_path}\n")
    else:
        sys.stderr.write(payload + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("usage: ora_direct.py <prompt.json> [out.json]\n")
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
