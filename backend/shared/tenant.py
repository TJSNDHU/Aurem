"""shared/tenant.py — iter D-83.

Single source of truth for the founder dogfood BIN used by the
platform's own acquisition pipeline (scout → blast → drip → close).

Every engine that operates on the founder's campaign data MUST scope
its Mongo queries with `business_id` so tenant isolation holds even
when customer tenants later share the same collections. Historical
rows were backfilled to AUR-FNDR-001 (scripts/backfill_business_id_d81a.py).
"""
import os

FOUNDER_BIN = os.environ.get("FOUNDER_BIN", "AUR-FNDR-001")
