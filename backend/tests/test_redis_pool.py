"""
Regression tests for utils.redis_pool — verifies the shared pool
singleton behaviour that fixed the production "max number of clients reached" leak.
"""
import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset module-level singletons between tests so each test starts clean."""
    from utils import redis_pool
    redis_pool.reset_for_hot_reload()
    yield
    redis_pool.reset_for_hot_reload()


def test_pool_module_exports():
    from utils import redis_pool
    assert hasattr(redis_pool, "get_async_redis")
    assert hasattr(redis_pool, "get_sync_redis")
    assert hasattr(redis_pool, "close_pools")
    assert hasattr(redis_pool, "reset_for_hot_reload")
    assert hasattr(redis_pool, "get_async_pool")
    assert hasattr(redis_pool, "pool_stats")


def test_shared_connection_pool_object_identity():
    """All services sharing the pool must see the SAME ConnectionPool object."""
    from utils import redis_pool
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL not set")

    async def _run():
        # Simulate two services (e.g. CacheManager + RateLimiter) each calling get_async_redis
        svc_a = await redis_pool.get_async_redis()
        svc_b = await redis_pool.get_async_redis()
        if svc_a is None or svc_b is None:
            return None, None
        return svc_a.connection_pool, svc_b.connection_pool

    pool_a, pool_b = asyncio.run(_run())
    if pool_a is None:
        pytest.skip("Redis unreachable")
    assert pool_a is pool_b, "Every service must bind to the SAME ConnectionPool object"


def test_no_redis_url_returns_none(monkeypatch):
    """When REDIS_URL is empty, both pool accessors return None gracefully."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    from utils import redis_pool
    redis_pool.reset_for_hot_reload()

    assert redis_pool.get_sync_redis() is None

    async def _check():
        return await redis_pool.get_async_redis()
    assert asyncio.run(_check()) is None


def test_async_pool_is_singleton():
    """get_async_redis must return the same object on repeated calls."""
    from utils import redis_pool
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL not set in this environment")

    async def _run():
        a = await redis_pool.get_async_redis()
        b = await redis_pool.get_async_redis()
        c = await redis_pool.get_async_redis()
        return a, b, c

    a, b, c = asyncio.run(_run())
    if a is None:
        pytest.skip("Redis unreachable in this environment")
    assert a is b is c, "Shared async pool must be a singleton"


def test_sync_pool_is_singleton():
    """get_sync_redis must return the same object on repeated calls."""
    from utils import redis_pool
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL not set in this environment")

    a = redis_pool.get_sync_redis()
    b = redis_pool.get_sync_redis()
    c = redis_pool.get_sync_redis()
    if a is None:
        pytest.skip("Redis unreachable in this environment")
    assert a is b is c, "Shared sync pool must be a singleton"


def test_reset_for_hot_reload_clears_cache():
    """reset_for_hot_reload() must force re-creation on next call."""
    from utils import redis_pool
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL not set in this environment")

    first = redis_pool.get_sync_redis()
    if first is None:
        pytest.skip("Redis unreachable")
    redis_pool.reset_for_hot_reload()
    second = redis_pool.get_sync_redis()
    assert first is not second, "Reset should yield a fresh client"


def test_async_pool_bounded_max_connections():
    """Shared async pool must respect REDIS_MAX_CONNECTIONS cap (critical leak fix)."""
    from utils import redis_pool
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL not set in this environment")

    async def _run():
        r = await redis_pool.get_async_redis()
        if r is None:
            return None
        # redis-py exposes connection_pool.max_connections on the client
        return getattr(r.connection_pool, "max_connections", None)

    max_conn = asyncio.run(_run())
    if max_conn is None:
        pytest.skip("Redis unreachable or attribute unavailable")
    # Should be bounded (not the default 2^31)
    assert max_conn <= 50, f"Pool must be bounded; got max_connections={max_conn}"


def test_default_async_cap_is_ten_or_less():
    """iter 325k — defaults must stay <=10 to fit the 30-client free tier
    (10 async + 3 sync + 1 pubsub + buffer = 14). Any future change that
    raises the in-code default must consciously update this lock."""
    import importlib
    from utils import redis_pool
    # Force re-read the module-level constant respecting the env override
    importlib.reload(redis_pool)
    assert redis_pool.MAX_CONNECTIONS <= 10, (
        f"Async pool cap regressed: MAX_CONNECTIONS={redis_pool.MAX_CONNECTIONS}, "
        f"must stay <=10 for Redis Cloud free tier"
    )
    assert redis_pool.SYNC_MAX_CONNECTIONS <= 3, (
        f"Sync pool cap regressed: SYNC_MAX_CONNECTIONS={redis_pool.SYNC_MAX_CONNECTIONS}"
    )


def test_concurrent_callers_get_same_pool():
    """100 concurrent coroutines must share one pool instance (no thundering herd)."""
    from utils import redis_pool
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL not set")

    async def _run():
        results = await asyncio.gather(*[redis_pool.get_async_redis() for _ in range(100)])
        return results

    results = asyncio.run(_run())
    if results[0] is None:
        pytest.skip("Redis unreachable")
    first = results[0]
    assert all(r is first for r in results), "All concurrent callers must get the same pooled client"
