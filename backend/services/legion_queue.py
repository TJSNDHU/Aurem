import asyncio
import os
import re
import uuid
import html
from datetime import datetime, timezone, timedelta
from typing import Optional

_db = None

def set_db(database):
    global _db
    _db = database

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HIGH_TIMEOUT_S = 300

HIGH_PATTERNS = [
    r'^\s*sudo\b',
    r'rm\s+-r[fF]',
    r'\bdd\b',
    r'\bmkfs',
    r'chmod\s+777\s+/',
    r'curl\s+[^|]*\|\s*(bash|sh)',
    r'wget\s+[^|]*\|\s*(bash|sh)',
    r'>>\s*/etc/',
    r'\bapt\s+(install|remove|purge)',
    r'\bsystemctl\s+(enable|start|stop|restart|disable)',
    r'\bpasswd\b',
    r'\buseradd\b',
    r'\buserdel\b',
    r'\biptables\b',
    r'\bufw\b',
    r'/etc/sudoers',
    r'\bsu\s+'
]

LOW_PATTERN = r'^\s*(ls|cat|head|tail|grep|find|ps|df|free|uptime|whoami|pwd|date|uname|wc|stat|file|which|echo|git\s+(status|log|diff)|docker\s+(ps|logs|images|version)|systemctl\s+status|curl\s+-s\s+-X?\s*GET)\b'

def classify_risk(cmd: str) -> str:
    for pattern in HIGH_PATTERNS:
        if re.search(pattern, cmd):
            return 'high'
    if re.match(LOW_PATTERN, cmd):
        return 'low'
    return 'medium'

async def enqueue_job(cmd: str, cwd: str = '/opt/aurem-cto', timeout_s: int = 60, env: Optional[dict] = None, risk_hint: Optional[str] = None, actor: str = 'ora') -> dict:
    job_id = uuid.uuid4().hex
    risk = risk_hint or classify_risk(cmd)
    status = 'pending' if risk in ('low', 'medium') else 'awaiting_approval'
    job = {
        'job_id': job_id,
        'cmd': cmd,
        'cwd': cwd,
        'timeout_s': timeout_s,
        'env': env or {},
        'risk': risk,
        'status': status,
        'enqueued_at': datetime.now(timezone.utc).isoformat(),
        'actor': actor
    }
    # iter 322fa fix — `insert_one` MUTATES the input dict by adding an ObjectId
    # `_id` field. Returning the same dict to FastAPI then fails JSON serialization.
    # Insert a copy so the original `job` returned to the caller stays clean.
    await _db.legion_queue.insert_one(dict(job))
    if risk == 'high':
        asyncio.create_task(_send_telegram_approval(job))
    return job

async def _send_telegram_approval(job: dict):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import httpx
        url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        text = f"<b>HIGH-RISK LEGION CMD</b>\n<code>{html.escape(job['cmd'][:500])}</code>\nReason: {job.get('risk_reason', 'pattern_match')}\njob_id: <code>{job['job_id']}</code>"
        body = {
            'chat_id': TELEGRAM_CHAT_ID,
            'parse_mode': 'HTML',
            'text': text,
            'reply_markup': {
                'inline_keyboard': [[
                    {'text': 'Approve', 'callback_data': f"legion_approve:{job['job_id']}"},
                    {'text': 'Reject', 'callback_data': f"legion_reject:{job['job_id']}"}
                ]]
            }
        }
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=body)
    except Exception:
        pass

async def claim_next_job() -> Optional[dict]:
    result = await _db.legion_queue.find_one_and_update(
        {'status': {'$in': ['pending', 'approved']}},
        {'$set': {'status': 'claimed', 'claimed_at': datetime.now(timezone.utc).isoformat()}},
        sort=[('enqueued_at', 1)],
        projection={'_id': 0}
    )
    return result

async def ack_job(job_id: str, exit_code: int, stdout: str, stderr: str, elapsed_ms: int) -> dict:
    finished_at = datetime.now(timezone.utc).isoformat()
    await _db.legion_queue.update_one(
        {'job_id': job_id},
        {'$set': {
            'status': 'done',
            'exit_code': exit_code,
            'stdout': stdout[:65536],
            'stderr': stderr[:16384],
            'elapsed_ms': elapsed_ms,
            'finished_at': finished_at
        }}
    )
    job = await _db.legion_queue.find_one({'job_id': job_id}, {'_id': 0})
    if job:
        await _db.legion_command_audit.insert_one(job)
    return {'ok': True}

async def approve_job(job_id: str, actor: str) -> bool:
    result = await _db.legion_queue.update_one(
        {'job_id': job_id, 'status': 'awaiting_approval'},
        {'$set': {
            'status': 'approved',
            'approved_by': actor,
            'approved_at': datetime.now(timezone.utc).isoformat()
        }}
    )
    return result.matched_count > 0

async def reject_job(job_id: str, actor: str, reason: str = 'manual') -> bool:
    result = await _db.legion_queue.update_one(
        {'job_id': job_id, 'status': 'awaiting_approval'},
        {'$set': {
            'status': 'rejected',
            'rejected_by': actor,
            'rejected_at': datetime.now(timezone.utc).isoformat(),
            'reject_reason': reason
        }}
    )
    return result.matched_count > 0

async def get_job_result(job_id: str) -> Optional[dict]:
    return await _db.legion_queue.find_one({'job_id': job_id}, {'_id': 0})

async def list_recent(limit: int = 20) -> list:
    cursor = _db.legion_queue.find(
        {},
        {'_id': 0, 'job_id': 1, 'cmd': 1, 'risk': 1, 'status': 1, 'enqueued_at': 1, 'exit_code': 1, 'elapsed_ms': 1}
    ).sort('enqueued_at', -1).limit(limit)
    return await cursor.to_list(length=limit)

async def expire_stale_approvals() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=HIGH_TIMEOUT_S)).isoformat()
    result = await _db.legion_queue.update_many(
        {'status': 'awaiting_approval', 'enqueued_at': {'$lt': cutoff}},
        {'$set': {'status': 'rejected', 'reject_reason': 'approval_timeout'}}
    )
    return result.modified_count


# Background loop — runs forever inside Pillar 1 worker so HIGH-risk jobs
# that the operator never approved (Telegram missed, asleep, etc.) auto-
# reject after `HIGH_TIMEOUT_S` instead of jamming the queue forever.
async def expire_stale_approvals_loop(poll_s: int = 60) -> None:
    while True:
        try:
            if _db is not None:
                n = await expire_stale_approvals()
                if n:
                    import logging
                    logging.getLogger("legion_queue").info(
                        "[legion-queue] expired %d stale approvals", n
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import logging
            logging.getLogger("legion_queue").warning(
                "[legion-queue] expire loop err: %s", e
            )
        await asyncio.sleep(poll_s)