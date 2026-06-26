---
name: dev_fastapi
description: "FastAPI development patterns for the AUREM platform — Motor async MongoDB, Pydantic v2, JWT auth, Emergent deploy"
risk: low
source: internal
date_added: "2026-01-15"
---

# FastAPI Development Skill — AUREM Platform

## Overview

This skill guides development on the AUREM backend, built with FastAPI + Python 3.11 + Motor (async MongoDB driver) + Pydantic v2. It covers the real patterns used in this repo — not generic FastAPI templates.

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| Language | Python 3.11+ |
| Database | MongoDB (Motor async driver) |
| ODM | motor.motor_asyncio.AsyncIOMotorClient |
| Validation | Pydantic v2 |
| Migrations | TTL indexes via registry.py init |
| Auth | JWT + OAuth2 (python-jose, PyJWT) |
| Testing | pytest + pytest-asyncio |
| Deploy | Emergent platform (supervisor-managed hot-reload) |
| Cache | Redis 7.4 (aioredis) |
| HTTP Client | httpx (async) |

## Phase 1: Project Structure

```
backend/
  routers/          # FastAPI APIRouter modules (426+ files)
  services/         # Business logic + autonomous systems
  config.py         # Centralized config via os.environ.get
  server.py         # App entry, CORS, lifespan, route registration
  middleware/       # Auth, rate limiting, tenant isolation
  tests/            # pytest test suite
```

## Phase 2: Database Setup (Motor + MongoDB)

Use Motor async MongoDB. Never use synchronous PyMongo in route handlers.

```python
from motor.motor_asyncio import AsyncIOMotorClient
import os

_client = AsyncIOMotorClient(os.environ.get("MONGO_URL", ""))
_db = _client[os.environ.get("DB_NAME", "aurem")]
```

### Tenant-Scoped Database

Use `TenantScopedDatabase` from `services/scoped_db.py` for multi-tenant isolation. Every query must scope by `FOUNDER_BIN` or tenant ID.

```python
from services.scoped_db import get_tenant_db

db = await get_tenant_db(founder_bin)
cursor = db.leads.find(
    {"founder_bin": founder_bin},
    {"_id": 0}  # always exclude _id via projection
)
```

### TTL Indexes

All time-series collections need TTL indexes. Register them in `registry.py` so they are created on startup:

```python
await db.collection.create_index(
    "created_at",
    expireAfterSeconds=86400  # 24h TTL
)
```

### Projection Rules

- Always exclude `_id` in find projections: `{"_id": 0}`
- Reattach `timezone.utc` to any datetime fields read from MongoDB (MongoDB strips tzinfo)
- Never return raw `_id` ObjectId to the client

## Phase 3: Pydantic v2 Models

Use Pydantic v2 `BaseModel` with `model_config = ConfigDict(...)`:

```python
from pydantic import BaseModel, ConfigDict, Field

class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = None
    website: str | None = None
```

## Phase 4: Router Patterns

```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

@router.get("/{lead_id}")
async def get_lead(lead_id: str, db=Depends(get_db)):
    lead = await db.leads.find_one(
        {"lead_id": lead_id, "founder_bin": founder_bin},
        {"_id": 0}
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
```

## Phase 5: Authentication

- JWT tokens via `python-jose` or `PyJWT`
- OAuth2 password flow for login
- Admin check via `is_admin_email()` fallback
- Token expiry handled by PyJWT default verification
- Never hardcode secrets — always `os.environ.get("SECRET_KEY")`

## Phase 6: Error Handling

AUREM rule: services must never raise. Catch and log.

```python
import logging
logger = logging.getLogger(__name__)

async def process_lead(lead_data: dict) -> dict:
    try:
        result = await db.leads.insert_one(lead_data)
        return {"inserted_id": str(result.inserted_id)}
    except Exception as exc:
        logger.error("Failed to insert lead: %s", exc)
        return {"error": "insert_failed"}
```

## Phase 7: Environment Variables

- Read via `os.environ.get("KEY", default)` only
- Never hardcode credentials, tokens, or connection strings
- Required vars defined in `.env.example`
- Use `os.environ.get` not `os.getenv` for consistency with existing codebase

## Phase 8: Datetime Handling

- Use `datetime.datetime.now(datetime.timezone.utc)` for all timestamps
- Never use `datetime.datetime.utcnow()` — deprecated since Python 3.12
- MongoDB strips timezone info on read — always reattach `timezone.utc`

```python
from datetime import datetime, timezone

timestamp = datetime.now(timezone.utc)
```

## Phase 9: Deployment (Emergent Platform)

- Emergent platform manages the process via supervisor
- Hot-reload on deploy — no full restart needed
- Health check at `/health` endpoint
- Graceful shutdown via FastAPI lifespan events
- Deploy logs filtered for noise (see `server.py` suppression block)

## Phase 10: Testing

- pytest with `pytest-asyncio` for async tests
- Test files in `backend/tests/`
- Run: `pytest -q`
- Security tests in `backend/tests/test_security_*.py`

## AUREM-Specific Rules

1. **Never raise in services** — catch + log + return error dict
2. **All new collections need TTL** — register in `registry.py`
3. **MongoDB queries must exclude `_id`** via projection and reattach `timezone.utc`
4. **Env vars via `os.environ.get` only** — never hardcode
5. **Run `ruff check` + `pytest -q` after changes**
6. **Tenant isolation** — every query must scope by `founder_bin`
7. **No bare `except:`** — always catch specific exceptions
8. **Type hints required** on all function signatures
9. **Use `Depends()` for DB injection** in route handlers
10. **Async/await everywhere** — never block the event loop

## Common Anti-Patterns to Avoid

- Using synchronous PyMongo in async route handlers
- Returning raw `_id` ObjectId to clients
- Using `datetime.utcnow()` instead of `datetime.now(timezone.utc)`
- Hardcoding secrets or connection strings
- Bare `except:` clauses
- Missing tenant scope in MongoDB queries
- Raising exceptions from service-layer code
- Using `os.getenv` instead of `os.environ.get` (codebase convention)
