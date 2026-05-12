#!/usr/bin/env python3
"""ora_direct_v2.py — like ora_direct.py but no tool loop, no DB wire-up,
just a SINGLE LLM call via openrouter (skip_sovereign). Faster for pure
design prompts that don't need any tools."""
import asyncio, json, os, sys, time, logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
BACKEND = Path("/app/backend")
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


async def main(prompt_path, out_path):
    spec = json.loads(Path(prompt_path).read_text())
    # iter 322ey — wire server.db so agent_skill_broadcast.get_addendum()
    # actually finds the active broadcast. Without this the gateway's
    # `_db = getattr(server, "db", None)` returns None → empty addendum →
    # ORA never sees the live skill teachings. THIS WAS THE REAL BUG
    # behind "ORA didn't pick up the lesson" during my verification.
    from motor.motor_asyncio import AsyncIOMotorClient
    import server as _srv
    _srv.db = AsyncIOMotorClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000,
    )[os.environ.get("DB_NAME", "aurem_db")]

    from services.llm_gateway import call_llm_with_meta
    sys_prompt = spec.get("system") or (
        "You are ORA CTO Sovereign. Output exactly the format requested. "
        "No prose, no commentary, no apologies."
    )
    start = time.time()
    res = await call_llm_with_meta(
        sys_prompt, spec["prompt"], max_tokens=4000,
        skip_sovereign=True, bypass_cache=True,
    )
    elapsed = time.time() - start
    out = {
        "ok": res.get("ok"),
        "provider": res.get("provider"),
        "content": res.get("content"),
        "wall_clock_s": round(elapsed, 2),
    }
    Path(out_path).write_text(json.dumps(out, default=str, indent=2))
    sys.stderr.write(f"[v2] {out_path} | provider={out['provider']} | {elapsed:.1f}s\n")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
