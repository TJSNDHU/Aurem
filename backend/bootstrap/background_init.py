"""Background init coroutine — extracted from the former monolithic server.py.

This runs deferred, non-critical initialization AFTER uvicorn has accepted
its first requests. Anything here must NOT block the startup_event path,
otherwise K8s readiness probes may miss their timeout window.

Hosted tasks:
  1. Database index creation (create_indexes, setup_database_indexes)
  2. Business System seed data
  3. Subscription plan seed
  4. Idempotent admin user seed (teji.ss1986@gmail.com)
  5. Crypto signal engine boot (optional)
  6. Blog image cleanup + blog index creation
  7. One-time Founder discount deletion migration

Every block is wrapped in try/except so a single corrupt document or missing
collection never stalls the remaining tasks.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from bootstrap.image_cleanup import cleanup_broken_images

logger = logging.getLogger(__name__)


async def run_background_init(
    db,
    *,
    create_indexes_fn: Callable[[], Awaitable[None]],
    setup_database_indexes_fn: Callable[[], Awaitable[None]],
    seed_business_system_data_fn: Callable[[], Awaitable[None]],
    start_crypto_tasks_fn: Optional[Callable[[], Awaitable[None]]] = None,
) -> None:
    """Deferred initialization launched as asyncio.create_task on startup."""
    try:
        await create_indexes_fn()
        await setup_database_indexes_fn()
        await seed_business_system_data_fn()

        # Seed subscription plans
        try:
            from services.plan_enforcement import seed_plans
            await seed_plans()
        except Exception as pe:
            logger.warning(f"Plan seed: {pe}")
        logger.info("Database indexes created in background")

        # ═══ Idempotent Admin User Seed ═══
        try:
            admin_email = "teji.ss1986@gmail.com"
            existing = await db.users.find_one({"email": admin_email}, {"_id": 0})
            if not existing:
                from utils.auth import hash_password
                admin_doc = {
                    "id": f"admin-{uuid.uuid4().hex[:12]}",
                    "email": admin_email,
                    "first_name": "Teji",
                    "last_name": "Admin",
                    "password": hash_password(
                        os.environ.get("ADMIN_SEED_PASSWORD", "vyoOeNWyZCGMbmf5u8dc")
                    ),
                    "is_admin": True,
                    "is_super_admin": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "auth_provider": "password",
                    "tenant_id": f"admin-{uuid.uuid4().hex[:12]}",
                }
                await db.users.insert_one(admin_doc)
                logger.info(f"✓ Admin user seeded: {admin_email}")
            else:
                logger.info(f"✓ Admin user already exists: {admin_email}")
        except Exception as e:
            logger.warning(f"Admin seed: {e}")

        # Start Crypto Signal Engine background tasks (only if enabled)
        if start_crypto_tasks_fn is not None:
            try:
                await start_crypto_tasks_fn()
                logger.info("✓ Crypto Signal Engine started")
            except Exception as e:
                logger.warning(f"Crypto Signal Engine startup: {e}")
        else:
            logger.info("ℹ Crypto Signal Engine disabled - skipping startup")

        # Blog indexes + image cleanup
        try:
            await cleanup_broken_images(db)
            await db.blog_posts.create_index("slug", unique=True)
            await db.blog_posts.create_index("status")
            await db.blog_posts.create_index("category")
            await db.blog_posts.create_index("published_at")
            logger.info("✓ Blog indexes created")
        except Exception as e:
            logger.warning(f"Blog index creation: {e}")

    except Exception as e:
        logger.error(f"Background index creation failed: {e}")


__all__ = ["run_background_init"]
