"""
Cloudflare R2 service (iter 299)
================================
S3-compatible upload helper for AUREM auto-built sites.

Bucket: aurem-sites
Object key: {slug}/index.html
Content-Type: text/html; charset=utf-8

Public API:
  upload_site_html(slug, html) -> {ok, key, etag, size}
  delete_site(slug)            -> {ok}
  is_configured()              -> bool
  bucket_url()                 -> "https://<account>.r2.cloudflarestorage.com" (S3 endpoint)

Notes:
- Uses boto3 in a thread executor (boto3 is sync; OK for tiny HTML uploads).
- Fails open: raises no exceptions, returns {"ok": False, "error": ...}.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

R2_BUCKET = os.environ.get("R2_BUCKET_NAME", "aurem-sites")


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def is_configured() -> bool:
    return bool(
        _env("CLOUDFLARE_ACCOUNT_ID")
        and _env("R2_ACCESS_KEY_ID")
        and _env("R2_SECRET_ACCESS_KEY")
    )


def bucket_url() -> str:
    acc = _env("CLOUDFLARE_ACCOUNT_ID")
    return f"https://{acc}.r2.cloudflarestorage.com" if acc else ""


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=bucket_url(),
        aws_access_key_id=_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _sync_upload(slug: str, html: str) -> Dict[str, Any]:
    try:
        cli = _client()
        body = html.encode("utf-8")
        key = f"{slug}/index.html"
        resp = cli.put_object(
            Bucket=R2_BUCKET, Key=key, Body=body,
            ContentType="text/html; charset=utf-8",
            CacheControl="public, max-age=300",
        )
        return {"ok": True, "key": key, "etag": resp.get("ETag", "").strip('"'),
                "size": len(body)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _sync_delete(slug: str) -> Dict[str, Any]:
    try:
        cli = _client()
        cli.delete_object(Bucket=R2_BUCKET, Key=f"{slug}/index.html")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def upload_site_html(slug: str, html: str) -> Dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "R2 not configured"}
    return await asyncio.get_event_loop().run_in_executor(None, _sync_upload, slug, html)


async def delete_site(slug: str) -> Dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "R2 not configured"}
    return await asyncio.get_event_loop().run_in_executor(None, _sync_delete, slug)


# ── Generic asset uploader (lead logos, hero photos, etc.) ─────────────
def _sync_upload_asset(key: str, body: bytes, content_type: str,
                        cache_seconds: int = 86400) -> Dict[str, Any]:
    try:
        cli = _client()
        resp = cli.put_object(
            Bucket=R2_BUCKET, Key=key, Body=body,
            ContentType=content_type,
            CacheControl=f"public, max-age={int(max(60, cache_seconds))}, immutable",
        )
        return {"ok": True, "key": key, "etag": resp.get("ETag", "").strip('"'),
                "size": len(body)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def upload_asset(key: str, body: bytes, content_type: str,
                       cache_seconds: int = 86400) -> Dict[str, Any]:
    """Upload arbitrary bytes (logo, photo, etc.) to R2 under `key`.

    Returns {ok, key, etag, size, public_url?} where public_url is the
    `img.aurem.live` URL if R2_PUBLIC_BASE is configured.
    """
    if not is_configured():
        return {"ok": False, "error": "R2 not configured"}
    res = await asyncio.get_event_loop().run_in_executor(
        None, _sync_upload_asset, key, body, content_type, cache_seconds,
    )
    if res.get("ok"):
        base = (os.environ.get("R2_PUBLIC_BASE") or "").strip().rstrip("/")
        if base:
            res["public_url"] = f"{base}/{key}"
    return res


def _sync_delete_asset(key: str) -> Dict[str, Any]:
    try:
        cli = _client()
        cli.delete_object(Bucket=R2_BUCKET, Key=key)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def delete_asset(key: str) -> Dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "R2 not configured"}
    return await asyncio.get_event_loop().run_in_executor(
        None, _sync_delete_asset, key,
    )
