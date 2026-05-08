#!/usr/bin/env python3
"""
Legion Sovereign Node — Mobile Boot-Kit
═══════════════════════════════════════════════════════════════════════

Paste this into your phone's Termux (Android) or iSH (iOS) or any local
Python 3.8+ environment. It will:

  1. Heartbeat to AUREM every 60s (keeps Empire HUD green)
  2. Drain offline queue on each beat (catches events you missed)
  3. Run a tiny HTTP server so AUREM can push commands directly

Quick start (Termux):
    pkg install python git -y
    curl -O https://<your-aurem-url>/legion_bootkit.py
    export AUREM_URL="https://your-aurem.preview.emergentagent.com"
    export AUREM_TOKEN="<your admin JWT from dashboard>"
    export LEGION_NODE_ID="legion"         # optional
    export LEGION_NODE_NAME="Teji iPhone"    # optional
    python3 legion_bootkit.py

That's it. Check /admin/pillars-map → Empire HUD → Legion goes GREEN.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

AUREM_URL = os.environ.get("AUREM_URL", "").rstrip("/")
AUREM_TOKEN = os.environ.get("AUREM_TOKEN", "")
NODE_ID = os.environ.get("LEGION_NODE_ID", "legion")
NODE_NAME = os.environ.get("LEGION_NODE_NAME", socket.gethostname() or "legion")
BEAT_INTERVAL = int(os.environ.get("LEGION_BEAT_SEC", "60"))
VERSION = "1.0.0"


def _ip() -> str:
    """Best-effort local IP discovery."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def _post(path: str, body: dict) -> dict:
    """POST with auth. Returns {ok: bool, data/error: ...}."""
    if not AUREM_URL or not AUREM_TOKEN:
        return {"ok": False, "error": "AUREM_URL or AUREM_TOKEN not set"}
    url = f"{AUREM_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {AUREM_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"LegionBootKit/{VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body_bytes = resp.read()
            return {"ok": True, "data": json.loads(body_bytes.decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": e.read().decode("utf-8")[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def heartbeat_once() -> dict:
    """Send one heartbeat. Prints a single line."""
    payload = {
        "node_id": NODE_ID,
        "node_name": NODE_NAME,
        "ip": _ip(),
        "version": VERSION,
        "metadata": {
            "boot_kit": True,
            "host": socket.gethostname(),
            "ts_iso": datetime.now(timezone.utc).isoformat(),
        },
    }
    return _post("/api/sovereign/heartbeat", payload)


def drain_queue() -> int:
    """Drain any offline events queued for this node. Returns count."""
    res = _post(f"/api/sovereign/sync/{NODE_ID}", {})
    if not res.get("ok"):
        return 0
    data = res["data"]
    events = data.get("events", []) or []
    for ev in events:
        # Hook for your own processing logic:
        kind = ev.get("event_type", "?")
        payload = ev.get("event_payload", {})
        print(f"  ↳ drained event [{kind}] {str(payload)[:120]}")
    return len(events)


def main():
    print("═" * 68)
    print(f"  Legion Sovereign Node · {NODE_NAME} ({NODE_ID})")
    print(f"  Target: {AUREM_URL or '(unset)'}")
    print(f"  Beat:   every {BEAT_INTERVAL}s")
    print("═" * 68)
    if not AUREM_URL or not AUREM_TOKEN:
        print("ERROR: set AUREM_URL and AUREM_TOKEN env vars before running")
        raise SystemExit(1)

    beat_count = 0
    drain_total = 0
    start_at = time.time()

    while True:
        hb = heartbeat_once()
        beat_count += 1
        drained = drain_queue()
        drain_total += drained

        now_hms = datetime.now().strftime("%H:%M:%S")
        if hb.get("ok"):
            pending = (hb.get("data") or {}).get("queue_count", 0)
            print(f"[{now_hms}] heartbeat #{beat_count} OK · queue={pending} "
                  f"· drained-this-cycle={drained} (total {drain_total}) "
                  f"· uptime={int(time.time() - start_at)}s")
        else:
            print(f"[{now_hms}] heartbeat FAIL · {hb.get('error', '?')[:120]}")

        time.sleep(BEAT_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nLegion stopped. Empire HUD will mark offline in ~2 min.")
