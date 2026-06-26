---
name: dev-fastapi-aurem
description: "FastAPI development in AUREM stack - FastAPI + Python 3.11+ + Motor (async MongoDB) + Pydantic v2 + Emergent deploy"
risk: moderate
source: internal
date_added: "2024-06-10"
---

# FastAPI Development for AUREM

Framework=FastAPI | Language=Python 3.11+ | Database=MongoDB (Motor async driver) | 
ODM=Motor/motor_asyncio | Validation=Pydantic v2 | Migrations=TTL indexes via registry.py | 
Auth=JWT+OAuth2 | Testing=pytest | Deploy=Emergent platform

## Project Setup (Phase 1)

1. **Virtual Environment** (mandatory):
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
