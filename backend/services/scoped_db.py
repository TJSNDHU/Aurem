"""
AUREM Scoped Database — Transparent Tenant Isolation Proxy

Wraps Motor's AsyncIOMotorDatabase so every collection read/write
is automatically filtered by tenant_id. Routes need ZERO changes.

Usage:
    raw_db = client[db_name]
    db = TenantScopedDatabase(raw_db)
    # Now db.leads.find({}) becomes db.leads.find({"tenant_id": <current>})
"""

import logging
from middleware.tenant_guard import TenantGuard

logger = logging.getLogger(__name__)

# ─── Collections that must NOT be tenant-scoped ─────────────────
GLOBAL_COLLECTIONS = frozenset({
    # Auth / user lookup (email-based cross-tenant)
    "users",
    "tenants",
    "platform_users",   # iter 288.1 — founder DB oracle needs cross-tenant view
    "aurem_onboarding", # iter 288.1 — for LIST_WEBSITES across tenants
    "business_profiles",  # iter 288.1 — already partially listed below; centralised here
    "roles",
    "team_members",
    "webauthn_challenges",
    # Shared definitions
    "subscription_plans",
    "service_registry",
    "admin_api_keys",
    # Push (already scoped by endpoint/user_id)
    "push_subscriptions",
    # Nexus (already manually scoped by user_id in router)
    "nexus_credentials",
    # Shared reports (public read access)
    "shared_reports",
    # Repair fixes (scoped by user_id in router)
    "repair_fixes",
    # Repair deployments (scoped by user_id in router)
    "repair_deployments",
    # Intelligence Hub (scoped by user_id)
    "business_profiles",
    "offer_sets",
    "recovery_queue",
    "agent_activations",
    # System-level logs (admin only)
    "system_health",
    "migration_log",
    # Iter 288.0 — Revenue-Reflector / Sovereign Boardroom (platform-internal)
    "agent_ledger_entries",
    "agent_rates",
    "agent_kill_switch_log",
    "ora_command_log",
})


class ScopedCollection:
    """
    Transparent proxy around a Motor collection.
    Injects {"tenant_id": <current>} into every query filter
    and stamps it onto every inserted document.
    """

    __slots__ = ("_col", "_tid")

    def __init__(self, collection, tenant_id: str):
        object.__setattr__(self, "_col", collection)
        object.__setattr__(self, "_tid", tenant_id)

    # ── Filter injection ────────────────────────────────────────
    def _scope(self, filt=None):
        f = dict(filt) if filt else {}
        f["tenant_id"] = self._tid
        return f

    def _stamp(self, doc):
        d = dict(doc)
        d.setdefault("tenant_id", self._tid)
        return d

    # ── Reads ───────────────────────────────────────────────────
    def find(self, filter=None, *args, **kwargs):
        return self._col.find(self._scope(filter), *args, **kwargs)

    async def find_one(self, filter=None, *args, **kwargs):
        return await self._col.find_one(self._scope(filter), *args, **kwargs)

    async def count_documents(self, filter=None, **kwargs):
        return await self._col.count_documents(self._scope(filter), **kwargs)

    async def distinct(self, key, filter=None, **kwargs):
        return await self._col.distinct(key, self._scope(filter), **kwargs)

    def aggregate(self, pipeline, *args, **kwargs):
        scoped = [{"$match": {"tenant_id": self._tid}}] + list(pipeline)
        return self._col.aggregate(scoped, *args, **kwargs)

    # ── Writes ──────────────────────────────────────────────────
    async def insert_one(self, document, *args, **kwargs):
        return await self._col.insert_one(self._stamp(document), *args, **kwargs)

    async def insert_many(self, documents, *args, **kwargs):
        return await self._col.insert_many(
            [self._stamp(d) for d in documents], *args, **kwargs
        )

    # ── Updates ─────────────────────────────────────────────────
    async def update_one(self, filter, update, *args, **kwargs):
        # For upserts, ensure tenant_id is in $setOnInsert
        if kwargs.get("upsert"):
            if "$setOnInsert" not in update:
                update = {**update, "$setOnInsert": {"tenant_id": self._tid}}
            elif "tenant_id" not in update["$setOnInsert"]:
                update["$setOnInsert"]["tenant_id"] = self._tid
        return await self._col.update_one(self._scope(filter), update, *args, **kwargs)

    async def update_many(self, filter, update, *args, **kwargs):
        return await self._col.update_many(self._scope(filter), update, *args, **kwargs)

    async def replace_one(self, filter, replacement, *args, **kwargs):
        return await self._col.replace_one(
            self._scope(filter), self._stamp(replacement), *args, **kwargs
        )

    # ── Deletes ─────────────────────────────────────────────────
    async def delete_one(self, filter, *args, **kwargs):
        return await self._col.delete_one(self._scope(filter), *args, **kwargs)

    async def delete_many(self, filter=None, *args, **kwargs):
        return await self._col.delete_many(self._scope(filter), *args, **kwargs)

    # ── Find-and-modify ─────────────────────────────────────────
    async def find_one_and_update(self, filter, update, *args, **kwargs):
        return await self._col.find_one_and_update(
            self._scope(filter), update, *args, **kwargs
        )

    async def find_one_and_delete(self, filter, *args, **kwargs):
        return await self._col.find_one_and_delete(
            self._scope(filter), *args, **kwargs
        )

    async def find_one_and_replace(self, filter, replacement, *args, **kwargs):
        return await self._col.find_one_and_replace(
            self._scope(filter), self._stamp(replacement), *args, **kwargs
        )

    # ── Index / schema ops (pass-through, no scoping needed) ───
    async def create_index(self, *args, **kwargs):
        return await self._col.create_index(*args, **kwargs)

    async def create_indexes(self, *args, **kwargs):
        return await self._col.create_indexes(*args, **kwargs)

    async def drop_index(self, *args, **kwargs):
        return await self._col.drop_index(*args, **kwargs)

    async def index_information(self):
        return await self._col.index_information()

    # ── Properties & fallback ───────────────────────────────────
    @property
    def name(self):
        return self._col.name

    @property
    def full_name(self):
        return self._col.full_name

    def __getattr__(self, name):
        return getattr(self._col, name)

    def __repr__(self):
        return f"<ScopedCollection({self._col.name}, tenant={self._tid})>"


class TenantScopedDatabase:
    """
    Transparent proxy wrapping Motor's AsyncIOMotorDatabase.

    When a collection is accessed (db.leads, db["leads"]), this proxy
    checks the current TenantGuard context:
    - No tenant → raw collection (public endpoints)
    - Admin user → raw collection (full visibility)
    - Regular user → ScopedCollection (auto-filtered by tenant_id)
    - Global collection → always raw (auth tables, plans, etc.)
    """

    def __init__(self, raw_db):
        object.__setattr__(self, "_raw_db", raw_db)

    def _resolve(self, name):
        raw = self._raw_db[name]
        tenant_id = TenantGuard.get()

        # No tenant context → unscoped (public / unauthenticated)
        if not tenant_id:
            return raw

        # Admin bypass → full visibility
        if TenantGuard.is_admin():
            return raw

        # Global collection → never scope
        if name in GLOBAL_COLLECTIONS:
            return raw

        return ScopedCollection(raw, tenant_id)

    # ── Collection access ───────────────────────────────────────
    def __getattr__(self, name):
        # Forward internal / Motor properties directly
        if name.startswith("_"):
            return getattr(self._raw_db, name)
        return self._resolve(name)

    def __getitem__(self, name):
        return self._resolve(name)

    def get_collection(self, name, *args, **kwargs):
        return self._resolve(name)

    # ── Database-level operations (always unscoped) ─────────────
    async def list_collection_names(self, *args, **kwargs):
        return await self._raw_db.list_collection_names(*args, **kwargs)

    async def command(self, *args, **kwargs):
        return await self._raw_db.command(*args, **kwargs)

    async def create_collection(self, *args, **kwargs):
        return await self._raw_db.create_collection(*args, **kwargs)

    async def drop_collection(self, *args, **kwargs):
        return await self._raw_db.drop_collection(*args, **kwargs)

    # ── Truthiness (MotorDatabase bool fix) ─────────────────────
    def __bool__(self):
        return self._raw_db is not None

    @property
    def name(self):
        return self._raw_db.name

    @property
    def client(self):
        return self._raw_db.client

    def __repr__(self):
        return f"<TenantScopedDatabase({self._raw_db.name})>"
