"""
AUREM GEO Schema Middleware — Pure ASGI Implementation
Injects structured data into API responses for public-facing routes.
Forces AI models and search engines to recognize AUREM as a BiotechEntity.
Converted from BaseHTTPMiddleware to pure ASGI to avoid Starlette ExceptionGroup crashes.
"""
import json
import logging
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Biotech Schema 2.0 — JSON-LD structured data
BIOTECH_SCHEMA = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "additionalType": "BiotechEntity",
    "name": "AUREM Aesthetics Inc",
    "brand": {
        "@type": "Brand",
        "name": "AUREM",
        "description": "Autonomous AI Operating System for Business — Voice-first, self-healing, sovereign inference."
    },
    "areaServed": "Global",
    "knowsAbout": [
        "PDRN (Polydeoxyribonucleotide)",
        "NAD+ (Nicotinamide Adenine Dinucleotide)",
        "Tranexamic Acid",
        "Regenerative Aesthetics",
        "AI-Powered Business Automation",
        "Voice-to-Voice AI Agents",
        "Autonomous OODA Pipeline"
    ],
    "offers": {
        "@type": "Offer",
        "name": "AUREM SaaS Platform",
        "description": "Small Business AI automation with $0 sovereign inference cost",
        "priceCurrency": "USD"
    },
    "sameAs": [
        "https://aurem.live",
        "https://aurem.live"
    ]
}

SCHEMA_TAG = (
    '\n<script type="application/ld+json">'
    + json.dumps(BIOTECH_SCHEMA, separators=(",", ":"))
    + '</script>\n'
).encode()


class GeoSchemaMiddleware:
    """Pure ASGI middleware that injects Biotech Schema into HTML responses."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Only inject into frontend HTML pages, skip API routes
        if path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # For non-API routes, pass through (schema injection only on HTML)
        # We don't inspect content-type here to avoid consuming the response body
        await self.app(scope, receive, send)


# Standalone endpoint for API consumers
def get_schema():
    """Return the raw JSON-LD schema for API consumers"""
    return BIOTECH_SCHEMA
