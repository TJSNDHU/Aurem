"""Bootstrap package — factored-out pieces of the old monolithic server.py.

Submodules:
    middlewares       — SecurityHeaders, JWTBlocklist, usage metering
    health_routes     — /health, /api/health, /ready, /, /api/platform/health
    wellknown_routes  — /.well-known/assetlinks.json, /.well-known/ucp
"""
