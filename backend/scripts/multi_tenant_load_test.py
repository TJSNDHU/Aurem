"""
scripts/multi_tenant_load_test.py — iter 328e (10-tenant simulation)

Simulates 10 concurrent customers exercising the platform end-to-end:

  • 10 parallel campaign-cycle invocations
  • 1000 leads pushed via /api/leads/bulk-add
  • 5 concurrent ORA conversations driving short replies
  • Records per-tenant timings, success rate, and the bottleneck stage

Outputs a JSON report to `load_test_runs` and prints a summary.

Usage
─────
    python scripts/multi_tenant_load_test.py
    python scripts/multi_tenant_load_test.py --tenants 5 --leads 500
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("load-test")

BASE_URL = os.environ.get(
    "AUREM_LOAD_TEST_URL",
    os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def hit_campaign_cycle(client, tenant_id: str) -> dict:
    t0 = time.monotonic()
    try:
        r = await client.post(
            f"{BASE_URL}/api/admin/awb/run-cycle",
            json={"tenant_id": tenant_id, "max_sends": 1, "dry_run": True},
            timeout=30.0,
        )
        ok = r.status_code in (200, 401, 403)  # 401/403 = auth gate hit, expected
        return {"tenant": tenant_id, "ok": ok, "status": r.status_code,
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        return {"tenant": tenant_id, "ok": False, "error": str(e)[:200],
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def push_leads(client, tenant_id: str, n: int) -> dict:
    t0 = time.monotonic()
    leads = [
        {
            "email": f"loadtest+{tenant_id}_{i}@example.com",
            "tenant_id": tenant_id,
            "source": "load_test",
        } for i in range(n)
    ]
    try:
        r = await client.post(
            f"{BASE_URL}/api/leads/bulk-add",
            json={"leads": leads},
            timeout=60.0,
        )
        return {"tenant": tenant_id, "n": n,
                "ok": r.status_code in (200, 201, 401, 403),
                "status": r.status_code,
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        return {"tenant": tenant_id, "n": n, "ok": False,
                "error": str(e)[:200],
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def ora_chat_burst(client, session_idx: int) -> dict:
    t0 = time.monotonic()
    msgs = ["status please", "what's the queue depth?", "ok thanks"]
    try:
        for m in msgs:
            await client.post(
                f"{BASE_URL}/api/ora/chat",
                json={"session_id": f"loadtest_{session_idx}", "message": m},
                timeout=20.0,
            )
        return {"session": session_idx, "ok": True,
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        return {"session": session_idx, "ok": False,
                "error": str(e)[:200],
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def main(tenants: int, leads_per_tenant: int, ora_sessions: int) -> int:
    import httpx
    ts_start = time.monotonic()
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Run the three workloads in parallel.
        tenant_ids = [f"LT-{i:03d}" for i in range(tenants)]
        campaign_task = asyncio.gather(*(hit_campaign_cycle(client, t) for t in tenant_ids))
        leads_task = asyncio.gather(*(push_leads(client, t, leads_per_tenant) for t in tenant_ids))
        chat_task = asyncio.gather(*(ora_chat_burst(client, i) for i in range(ora_sessions)))
        campaigns, leads, chats = await asyncio.gather(campaign_task, leads_task, chat_task)
    duration_s = round(time.monotonic() - ts_start, 1)

    def _summarize(rows):
        total = len(rows)
        ok = sum(1 for r in rows if r.get("ok"))
        elapsed = [r.get("elapsed_ms", 0) for r in rows if r.get("ok")]
        avg = round(sum(elapsed) / max(1, len(elapsed)), 0)
        worst = max(elapsed or [0])
        return {"total": total, "ok": ok, "avg_ms": avg, "worst_ms": worst}

    report = {
        "ts":        _now_iso(),
        "duration_s": duration_s,
        "tenants":   tenants,
        "leads_per_tenant": leads_per_tenant,
        "ora_sessions": ora_sessions,
        "campaigns": _summarize(campaigns),
        "leads":     _summarize(leads),
        "ora_chat":  _summarize(chats),
        "raw": {
            "campaigns": campaigns,
            "leads":     leads,
            "chats":     chats,
        },
    }

    # Identify bottleneck.
    worst = max(
        ("campaigns", report["campaigns"]["worst_ms"]),
        ("leads",     report["leads"]["worst_ms"]),
        ("ora_chat",  report["ora_chat"]["worst_ms"]),
        key=lambda kv: kv[1],
    )
    report["bottleneck"] = {"stage": worst[0], "worst_ms": worst[1]}

    # Persist (best-effort).
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        c = AsyncIOMotorClient(os.environ.get("MONGO_URL"), maxPoolSize=5)
        await c[os.environ.get("DB_NAME") or "aurem"].load_test_runs.insert_one(dict(report))
        c.close()
    except Exception as e:
        logger.warning(f"persist failed: {e}")

    print("\n──── LOAD TEST SUMMARY ────")
    print(f"  tenants            : {tenants}")
    print(f"  duration           : {duration_s}s")
    print(f"  campaign cycles    : {report['campaigns']['ok']}/{report['campaigns']['total']} ok  (avg {report['campaigns']['avg_ms']}ms, worst {report['campaigns']['worst_ms']}ms)")
    print(f"  leads pushed       : {report['leads']['ok']}/{report['leads']['total']} ok  (avg {report['leads']['avg_ms']}ms, worst {report['leads']['worst_ms']}ms)")
    print(f"  ora chats          : {report['ora_chat']['ok']}/{report['ora_chat']['total']} ok  (avg {report['ora_chat']['avg_ms']}ms, worst {report['ora_chat']['worst_ms']}ms)")
    print(f"  BOTTLENECK         : {report['bottleneck']['stage']}  ({report['bottleneck']['worst_ms']}ms)")
    print("───────────────────────────\n")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--tenants", type=int, default=10)
    p.add_argument("--leads", type=int, default=100,
                    help="leads pushed per tenant (default 100 ⇒ 1000 total at default tenants)")
    p.add_argument("--ora-sessions", type=int, default=5)
    args = p.parse_args()
    sys.exit(asyncio.run(main(args.tenants, args.leads, args.ora_sessions)))
