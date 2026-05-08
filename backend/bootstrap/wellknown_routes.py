"""Well-known / discovery endpoints — assetlinks.json + UCP manifest.

Extracted from the former 1,820 LOC server.py as part of the final surgery.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse


# Hardcoded Digital Asset Links for Android TWA verification — avoids any
# file-reading path that could fail during deployment.
ASSETLINKS_JSON = [
    {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "ca.reroots.app",
            "sha256_cert_fingerprints": [
                "FF:D5:B2:D6:30:7D:82:B7:28:A6:6E:B1:BF:AF:B4:7B:3E:53:C3:6F:64:74:99:00:0E:C0:03:91:C1:0A:93:89"
            ],
        },
    }
]


def register_wellknown_routes(app) -> None:
    """Attach /.well-known/assetlinks.json and /.well-known/ucp to `app`."""

    @app.get("/.well-known/assetlinks.json")
    async def assetlinks():
        """Serve Digital Asset Links for Android TWA verification."""
        return JSONResponse(
            content=ASSETLINKS_JSON,
            media_type="application/json",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @app.get("/.well-known/ucp")
    async def wellknown_ucp():
        """UCP discovery file — the 'business card' for AI buyer agents."""
        from routers.ucp_router import ucp_manifest
        return await ucp_manifest()


__all__ = ["register_wellknown_routes", "ASSETLINKS_JSON"]
