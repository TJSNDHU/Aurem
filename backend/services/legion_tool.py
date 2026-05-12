import asyncio
import logging
import time
from typing import Optional

from services.legion_queue import enqueue_job, get_job_result

logger = logging.getLogger(__name__)


async def legion_exec(
    cmd: str,
    cwd: str = '/opt/aurem-cto',
    timeout_s: int = 60,
    risk_hint: Optional[str] = None,
    wait_max_s: int = 360
) -> dict:
    '''Enqueue cmd on Legion daemon queue, then poll get_job_result every 2s up to wait_max_s.
    For HIGH-risk commands, wait_max_s should be >= 300 to cover the Telegram approval window.
    Returns {ok, job_id, exit_code, stdout, stderr, elapsed_ms, risk}.
    '''
    # ── Input validation ─────────────────────────────────────
    if not cmd or not isinstance(cmd, str):
        return {'ok': False, 'error': 'cmd must be a non-empty string'}
    if len(cmd) > 4000:
        return {'ok': False, 'error': 'cmd exceeds 4000 char limit'}
    if not (1 <= int(timeout_s) <= 600):
        return {'ok': False, 'error': 'timeout_s must be 1..600'}
    if not (1 <= int(wait_max_s) <= 900):
        return {'ok': False, 'error': 'wait_max_s must be 1..900'}
    
    # ── Enqueue ──────────────────────────────────────────────
    try:
        job = await enqueue_job(
            cmd=cmd,
            cwd=cwd,
            timeout_s=int(timeout_s),
            env={},
            risk_hint=risk_hint,
            actor='legion_exec'
        )
    except Exception as e:
        logger.exception('enqueue_job failed')
        return {'ok': False, 'error': f'enqueue failed: {e!r}'}
    
    job_id = job['job_id']
    risk = job.get('risk', '?')
    status = job.get('status', '?')
    logger.info(f'[legion_exec] enqueued {job_id[:12]} risk={risk} status={status}')
    
    # ── Poll loop ────────────────────────────────────────────
    start = time.time()
    last_status = status
    while (time.time() - start) < wait_max_s:
        await asyncio.sleep(2.0)
        try:
            result = await get_job_result(job_id)
        except Exception as e:
            logger.warning(f'get_job_result raised {e!r}')
            continue
        if not result:
            continue
        last_status = result.get('status', last_status)
        if last_status == 'done':
            return {
                'ok': result.get('exit_code') == 0,
                'job_id': job_id,
                'risk': risk,
                'exit_code': result.get('exit_code'),
                'stdout': result.get('stdout', ''),
                'stderr': result.get('stderr', ''),
                'elapsed_ms': result.get('elapsed_ms'),
                'finished_at': result.get('finished_at'),
            }
        if last_status == 'rejected':
            return {
                'ok': False,
                'job_id': job_id,
                'risk': risk,
                'error': 'rejected: ' + str(result.get('reject_reason', '?')),
            }
    
    return {
        'ok': False,
        'job_id': job_id,
        'risk': risk,
        'error': f'timeout after {wait_max_s}s — job stuck in status {last_status!r}',
        'last_status': last_status,
    }