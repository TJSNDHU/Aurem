import asyncio
import json
import logging
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional

logger = logging.getLogger(__name__)

_COLD_DIR = Path(os.getenv("SCOUT_COLD_DIR", "/tmp/scout_cold"))
_KEY_FILE = _COLD_DIR / ".fernet.key"
_FERNET_INSTANCE: Optional[Fernet] = None

_COLD_DIR.mkdir(parents=True, exist_ok=True)


def _get_fernet() -> Fernet:
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is not None:
        return _FERNET_INSTANCE
    
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        os.chmod(_KEY_FILE, 0o600)
    
    _FERNET_INSTANCE = Fernet(key)
    return _FERNET_INSTANCE


async def save_cold(job_id: str, payload: dict) -> dict:
    fernet = _get_fernet()
    
    plaintext = json.dumps(payload).encode("utf-8")
    encrypted = fernet.encrypt(plaintext)
    
    file_path = _COLD_DIR / f"{job_id}.enc"
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, file_path.write_bytes, encrypted)
    
    size_bytes = len(encrypted)
    sha256_hash = hashlib.sha256(encrypted).hexdigest()
    captured_at = datetime.now(timezone.utc).isoformat()
    
    return {
        "job_id": job_id,
        "path": str(file_path),
        "size_bytes": size_bytes,
        "sha256": sha256_hash,
        "captured_at": captured_at,
    }


async def load_cold(job_id: str) -> Optional[dict]:
    file_path = _COLD_DIR / f"{job_id}.enc"
    
    if not file_path.exists():
        return None
    
    fernet = _get_fernet()
    
    loop = asyncio.get_event_loop()
    encrypted = await loop.run_in_executor(None, file_path.read_bytes)
    
    try:
        plaintext = fernet.decrypt(encrypted)
        payload = json.loads(plaintext.decode("utf-8"))
        return payload
    except Exception as e:
        logger.error(f"Failed to decrypt/parse {job_id}: {e}")
        return None


async def list_cold_jobs(limit: int = 50) -> list:
    if not _COLD_DIR.exists():
        return []
    
    loop = asyncio.get_event_loop()
    
    def _list_files():
        files = []
        for f in _COLD_DIR.glob("*.enc"):
            stat = f.stat()
            files.append((f, stat.st_mtime, stat.st_size))
        files.sort(key=lambda x: x[1], reverse=True)
        return files[:limit]
    
    files = await loop.run_in_executor(None, _list_files)
    
    result = []
    for f, mtime, size in files:
        job_id = f.stem
        captured_at_mtime = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        result.append({
            "job_id": job_id,
            "size_bytes": size,
            "captured_at_mtime": captured_at_mtime,
        })
    
    return result


async def delete_cold(job_id: str) -> bool:
    file_path = _COLD_DIR / f"{job_id}.enc"
    
    if not file_path.exists():
        return False
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, file_path.unlink)
    
    return True


def summarize_for_cloud(payload: dict, max_fields: int = 5) -> dict:
    import re
    
    safe_key_pattern = re.compile(r"^(name|title|url|count|score|status|source)$", re.IGNORECASE)
    
    summary = {}
    for k, v in payload.items():
        if len(summary) >= max_fields:
            break
        if not safe_key_pattern.match(k):
            continue
        if isinstance(v, (str, int, float, bool)):
            summary[k] = v
    
    return summary