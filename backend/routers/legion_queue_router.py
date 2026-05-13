import os
import logging
import hmac
from pathlib import Path as _Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

from services.legion_queue import (
    set_db as _set_queue_db,
    enqueue_job,
    claim_next_job,
    ack_job,
    approve_job,
    reject_job,
    get_job_result,
    list_recent,
)

_db = None

def set_db(database):
    global _db
    _db = database
    _set_queue_db(database)

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter(prefix='/api/legion/queue', tags=['legion'])

async def get_admin_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds:
        raise HTTPException(status_code=401, detail='Missing token')
    secret = os.environ.get('JWT_SECRET') or os.environ.get('JWT_SECRET_KEY') or ''
    if not secret:
        raise HTTPException(status_code=500, detail='Server config error')
    try:
        payload = jwt.decode(creds.credentials, secret, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail='Invalid token')
    email = (payload.get('email') or payload.get('sub') or '').lower()
    if not email:
        raise HTTPException(status_code=401, detail='Invalid token claims')
    if payload.get('is_admin') or payload.get('is_super_admin'):
        return {'email': email, 'is_admin': True}
    user = await _db.users.find_one({'email': email}, {'_id': 0, 'is_admin': 1, 'is_super_admin': 1, 'role': 1})
    if not user or not (user.get('is_admin') or user.get('is_super_admin') or user.get('role') in ('admin', 'super_admin')):
        raise HTTPException(status_code=403, detail='Admin access required')
    return {'email': email, 'is_admin': True}

def require_daemon_token(authorization: Optional[str] = Header(None)):
    expected = os.getenv('LEGION_DAEMON_TOKEN')
    if not expected:
        raise HTTPException(status_code=503, detail='LEGION_DAEMON_TOKEN not configured on server')
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Missing bearer')
    got = authorization.split(' ', 1)[1].strip()
    if not hmac.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail='Bad daemon token')
    return True

class EnqueueRequest(BaseModel):
    cmd: str = Field(min_length=1, max_length=4000)
    # iter 322g — default to /tmp instead of /opt/aurem-cto. The original
    # default required `sudo install.sh` to create /opt/aurem-cto with
    # daemon-user perms. On WSL / non-systemd installs the daemon user
    # can't chdir into that path → 100% jobs fail with PermissionError.
    # /tmp is world-writable on every POSIX system.
    cwd: str = '/tmp'
    timeout_s: int = Field(default=60, ge=1, le=600)
    env: dict = {}
    risk_hint: Optional[str] = None

class AckRequest(BaseModel):
    job_id: str
    exit_code: int
    stdout: str = ''
    stderr: str = ''
    elapsed_ms: int = 0

@router.get('/_/health')
async def health():
    return {
        'ok': True,
        'service': 'legion-queue',
        'has_daemon_token': bool(os.getenv('LEGION_DAEMON_TOKEN'))
    }

@router.post('/enqueue')
async def enqueue(req: EnqueueRequest, user: dict = Depends(get_admin_user)):
    job = await enqueue_job(
        cmd=req.cmd,
        cwd=req.cwd,
        timeout_s=req.timeout_s,
        env=req.env,
        risk_hint=req.risk_hint,
        actor=user['email']
    )
    return job

@router.get('/next')
async def next_job(_daemon: bool = Depends(require_daemon_token)):
    # iter 322g — stamp daemon heartbeat on every poll so ora_agent can
    # fast-fail the 120s ollama wait when the laptop is offline.
    try:
        if _db is not None:
            from datetime import datetime, timezone
            await _db.legion_daemon_status.update_one(
                {'_id': 'global'},
                {'$set': {
                    'last_poll_at': datetime.now(timezone.utc).isoformat(),
                    'last_poll_ts': datetime.now(timezone.utc).timestamp(),
                }},
                upsert=True,
            )
    except Exception as e:
        logger.debug(f'[legion] heartbeat write skipped: {e}')
    res = await claim_next_job()
    return res or {'job_id': None}

@router.post('/ack')
async def ack(req: AckRequest, _daemon: bool = Depends(require_daemon_token)):
    await ack_job(
        job_id=req.job_id,
        exit_code=req.exit_code,
        stdout=req.stdout,
        stderr=req.stderr,
        elapsed_ms=req.elapsed_ms
    )
    return {'ok': True}

@router.get('/result/{job_id}')
async def result(job_id: str, user: dict = Depends(get_admin_user)):
    r = await get_job_result(job_id)
    if not r:
        raise HTTPException(status_code=404, detail='Job not found')
    return r

@router.get('/list')
async def list_jobs(limit: int = 20, user: dict = Depends(get_admin_user)):
    return await list_recent(limit)

@router.post('/approve/{job_id}')
async def approve(job_id: str, user: dict = Depends(get_admin_user)):
    ok = await approve_job(job_id, user['email'])
    if not ok:
        raise HTTPException(status_code=404, detail='Job not found')
    return {'ok': True}

@router.post('/reject/{job_id}')
async def reject(job_id: str, user: dict = Depends(get_admin_user)):
    ok = await reject_job(job_id, user['email'])
    if not ok:
        raise HTTPException(status_code=404, detail='Job not found')
    return {'ok': True}


# iter 322fa — serve daemon source + install script for one-line bootstrap
# These endpoints are intentionally UNAUTHENTICATED (public): the daemon
# script is non-secret (no embedded tokens), and the install.sh prompts
# the founder for LEGION_DAEMON_TOKEN interactively (or via env).
# Mounted at /api/legion/ (NOT /api/legion/queue/) so the curl|bash UX is clean.

_DAEMON_PATH  = _Path('/app/aurem-cto/daemon/legion_daemon.py')
_INSTALL_PATH = _Path('/app/aurem-cto/daemon/install.sh')
# iter 322fg/322fh — production deploys ship only /app/backend/. The legion
# daemon + installer are baked into legion_embedded_assets.py (base64) so
# they're guaranteed to ship with the backend code itself. The helpers
# transparently prefer canonical → mirror → embedded.
try:
    from legion_embedded_assets import (
        get_daemon_source as _get_daemon_embedded,
        get_install_script as _get_install_embedded,
    )
except Exception:
    _get_daemon_embedded = None
    _get_install_embedded = None

bootstrap_router = APIRouter(prefix='/api/legion', tags=['legion'])


@bootstrap_router.get('/daemon-source', response_class=PlainTextResponse)
async def daemon_source():
    """Returns the legion_daemon.py source code. Used by install.sh."""
    if _get_daemon_embedded is not None:
        try:
            return _get_daemon_embedded()
        except Exception:
            pass
    if _DAEMON_PATH.is_file():
        return _DAEMON_PATH.read_text()
    raise HTTPException(status_code=503, detail='daemon source not deployed')


@bootstrap_router.get('/install', response_class=PlainTextResponse)
async def install_script():
    """Returns the install.sh script. Use with: curl -fsSL .../install | sudo bash"""
    if _get_install_embedded is not None:
        try:
            return _get_install_embedded()
        except Exception:
            pass
    if _INSTALL_PATH.is_file():
        return _INSTALL_PATH.read_text()
    raise HTTPException(status_code=503, detail='install script not deployed')