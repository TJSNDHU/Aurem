"""
AUREM Legion Reverse-Poll Daemon (iter 322fa)

Runs on the founder's Legion laptop. Polls the Emergent pod's queue every
LEGION_POLL_INTERVAL_S seconds, executes any pending jobs via subprocess,
and POSTs the results back. NO inbound ports required — pure HTTPS out.

Required env (loaded by systemd EnvironmentFile=/opt/aurem-cto/daemon/.env):
    LEGION_DAEMON_TOKEN     bearer secret (matches LEGION_DAEMON_TOKEN on pod)
    LEGION_QUEUE_URL        e.g. https://aurem.live  (default)
    LEGION_POLL_INTERVAL_S  default 5.0
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

import httpx

QUEUE_URL       = os.getenv("LEGION_QUEUE_URL", "https://aurem.live").rstrip("/")
DAEMON_TOKEN    = os.getenv("LEGION_DAEMON_TOKEN", "")
POLL_INTERVAL_S = float(os.getenv("LEGION_POLL_INTERVAL_S", "5.0"))
DAEMON_VERSION  = "1.0.0"
USER_AGENT      = f"aurem-cto-legion-daemon/{DAEMON_VERSION}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [legion] %(levelname)s %(message)s",
)
logger = logging.getLogger("legion-daemon")

_shutdown = asyncio.Event()


def _install_signals() -> None:
    """Graceful shutdown on SIGTERM / SIGINT (systemctl stop)."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown.set)
        except NotImplementedError:
            pass  # Windows


async def _http(method: str, path: str, **kw) -> dict | None:
    headers = {
        "Authorization": f"Bearer {DAEMON_TOKEN}",
        "User-Agent":    USER_AGENT,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.request(method, f"{QUEUE_URL}{path}", headers=headers, **kw)
            if r.status_code in (200, 201):
                return r.json()
            logger.warning(f"{method} {path} -> {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"{method} {path} raised {e!r}")
    return None


async def claim_next() -> dict | None:
    r = await _http("GET", "/api/legion/queue/next")
    if not r or not r.get("job_id"):
        return None
    return r


async def execute_cmd(job: dict) -> dict:
    cmd     = job["cmd"]
    cwd     = job.get("cwd", "/tmp")
    timeout = int(job.get("timeout_s", 60))
    env     = {**os.environ, **(job.get("env") or {})}
    # iter 322g — robust cwd fallback. mkdir(exist_ok=True) silently passes
    # if the dir EXISTS but the daemon user has no perm → subprocess then
    # crashes with PermissionError. Verify access explicitly; on any
    # failure use the user's home dir (always accessible) or /tmp.
    try:
        Path(cwd).mkdir(parents=True, exist_ok=True)
        if not os.access(cwd, os.R_OK | os.X_OK):
            raise PermissionError(f"no access to {cwd}")
    except Exception:
        for candidate in (os.path.expanduser("~"), "/tmp", os.getcwd()):
            try:
                if os.access(candidate, os.R_OK | os.W_OK | os.X_OK):
                    cwd = candidate
                    break
            except Exception:
                continue

    start = time.time()
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            rc = proc.returncode if proc.returncode is not None else -1
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            rc = 124
            stdout = b""
            stderr = f"killed: exceeded {timeout}s".encode()
    except Exception as e:
        return {
            "exit_code":  99,
            "stdout":     "",
            "stderr":     f"daemon error: {e!r}",
            "elapsed_ms": int((time.time() - start) * 1000),
        }
    return {
        "exit_code":  rc,
        "stdout":     (stdout or b"").decode("utf-8", "replace")[:64_000],
        "stderr":     (stderr or b"").decode("utf-8", "replace")[:16_000],
        "elapsed_ms": int((time.time() - start) * 1000),
    }


async def ack(job_id: str, result: dict) -> None:
    await _http("POST", "/api/legion/queue/ack", json={"job_id": job_id, **result})


async def heartbeat_loop() -> None:
    while not _shutdown.is_set():
        await _http("GET", "/api/legion/queue/_/health")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    if not DAEMON_TOKEN:
        logger.error("LEGION_DAEMON_TOKEN missing in environment. Refusing to start.")
        sys.exit(2)
    _install_signals()
    logger.info(
        f"legion-daemon {DAEMON_VERSION} starting "
        f"— queue={QUEUE_URL} poll={POLL_INTERVAL_S}s"
    )
    asyncio.create_task(heartbeat_loop())

    while not _shutdown.is_set():
        try:
            job = await claim_next()
            if job:
                logger.info(
                    f"job {job['job_id'][:12]} risk={job.get('risk')} "
                    f"cmd={(job['cmd'] or '')[:80]!r}"
                )
                result = await execute_cmd(job)
                await ack(job["job_id"], result)
                logger.info(
                    f"job {job['job_id'][:12]} done "
                    f"rc={result['exit_code']} elapsed={result['elapsed_ms']}ms"
                )
            else:
                try:
                    await asyncio.wait_for(_shutdown.wait(), timeout=POLL_INTERVAL_S)
                except asyncio.TimeoutError:
                    pass
        except Exception as e:
            logger.exception(f"daemon loop error: {e}")
            await asyncio.sleep(POLL_INTERVAL_S)

    logger.info("legion-daemon shutting down")


if __name__ == "__main__":
    asyncio.run(main())
