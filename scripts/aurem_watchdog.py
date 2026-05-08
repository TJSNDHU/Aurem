#!/usr/bin/env python3
"""
AUREM Watchdog (iter 303)
=========================
Lightweight out-of-process probe that polls /api/health every 5s.
If the backend fails 3 consecutive probes, runs `supervisorctl restart
backend`. K8s liveness probes already do this from outside the pod;
this watchdog gives a faster in-pod recovery (≤ 15s detection +
≤ 5s restart).

Runs under supervisord as program `aurem-watchdog`.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime

import urllib.request
import urllib.error

HEALTH_URL = os.environ.get("WATCHDOG_HEALTH_URL", "http://localhost:8001/health")
PROBE_INTERVAL_S = int(os.environ.get("WATCHDOG_INTERVAL", "5"))
FAIL_THRESHOLD = int(os.environ.get("WATCHDOG_FAIL_THRESHOLD", "3"))
PROBE_TIMEOUT_S = int(os.environ.get("WATCHDOG_TIMEOUT", "4"))
COOLDOWN_S = int(os.environ.get("WATCHDOG_COOLDOWN", "60"))
POST_RESTART_GRACE_S = int(os.environ.get("WATCHDOG_POST_RESTART_GRACE", "45"))


def _log(msg: str) -> None:
    sys.stdout.write(f"[watchdog {datetime.utcnow().isoformat()}Z] {msg}\n")
    sys.stdout.flush()


def _probe() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=PROBE_TIMEOUT_S) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False
    except Exception as e:
        _log(f"probe exception: {e}")
        return False


def _restart_backend() -> None:
    try:
        out = subprocess.run(
            ["sudo", "supervisorctl", "restart", "backend"],
            capture_output=True, text=True, timeout=30,
        )
        _log(f"restart issued · stdout={out.stdout.strip()} · stderr={out.stderr.strip()}")
    except Exception as e:
        _log(f"restart failed: {e}")


def main() -> None:
    _log(f"started · url={HEALTH_URL} · interval={PROBE_INTERVAL_S}s · "
         f"threshold={FAIL_THRESHOLD} · cooldown={COOLDOWN_S}s")
    consecutive_fails = 0
    last_restart_at = 0.0
    while True:
        ok = _probe()
        if ok:
            if consecutive_fails:
                _log(f"recovered after {consecutive_fails} fails")
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            _log(f"probe FAIL #{consecutive_fails}/{FAIL_THRESHOLD}")
            now = time.time()
            if (consecutive_fails >= FAIL_THRESHOLD
                    and (now - last_restart_at) >= COOLDOWN_S):
                _log("threshold reached — restarting backend")
                _restart_backend()
                last_restart_at = now
                consecutive_fails = 0
                # give supervisor + uvicorn cold-boot grace before next probe
                # (registers ~280 routers + APScheduler — ~30s on a busy pod)
                _log(f"sleeping {POST_RESTART_GRACE_S}s for cold-boot grace")
                time.sleep(POST_RESTART_GRACE_S)
        time.sleep(PROBE_INTERVAL_S)


if __name__ == "__main__":
    main()
