# AUREM PROJECT TEMPLATES — Scaffold Patterns

Loaded when keywords trigger: new project, scaffold, from scratch, build,
green-field, template, skeleton.

## Folder Structure

A new AUREM-style FastAPI + React app:

```
/app/
├── backend/
│   ├── server.py                  # FastAPI app + startup
│   ├── routers/                   # All API routes, /api prefixed
│   │   └── example_router.py
│   ├── services/                  # Business logic (no HTTP)
│   │   └── example_service.py
│   ├── models/                    # Pydantic models
│   │   └── example.py
│   ├── tests/                     # pytest
│   │   ├── conftest.py
│   │   └── test_example.py
│   ├── .env                       # MONGO_URL, DB_NAME, secrets
│   ├── .env.example               # safe-to-commit template
│   └── requirements.txt           # pinned versions
├── frontend/
│   ├── src/
│   │   ├── App.js                 # router + providers
│   │   ├── pages/                 # one per route
│   │   ├── components/
│   │   │   └── ui/                # Shadcn components
│   │   ├── hooks/                 # custom hooks
│   │   └── lib/                   # utils
│   ├── public/                    # static assets
│   ├── .env                       # REACT_APP_BACKEND_URL
│   ├── package.json
│   └── tailwind.config.js
└── memory/
    ├── PRD.md
    ├── tier1/                     # always-on rules
    ├── tier2/                     # keyword-gated playbooks
    └── tier3/                     # reference docs
```

## FastAPI Route Template

```python
# /app/backend/routers/leads_router.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import os
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/leads", tags=["leads"])

_db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

class Lead(BaseModel):
    name: str
    email: str
    phone: str | None = None

class LeadOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: str

@router.post("", response_model=LeadOut)
async def create_lead(body: Lead) -> LeadOut:
    doc = body.model_dump()
    doc["_id"] = doc["id"] = os.urandom(16).hex()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await _db.leads.insert_one(doc)
    doc.pop("_id", None)
    return LeadOut(**doc)

@router.get("", response_model=list[LeadOut])
async def list_leads() -> list[LeadOut]:
    docs = await _db.leads.find({}, {"_id": 0}).to_list(length=200)
    return [LeadOut(**d) for d in docs]
```

## React Component Template

```jsx
// /app/frontend/src/pages/LeadsPage.jsx
import { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";

const API = process.env.REACT_APP_BACKEND_URL;

export default function LeadsPage() {
  const [leads, setLeads] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      setBusy(true);
      const r = await fetch(`${API}/api/leads`);
      setLeads(await r.json());
      setBusy(false);
    })();
  }, []);

  return (
    <div data-testid="leads-page" className="p-6 space-y-4">
      <h1 className="text-2xl">Leads</h1>
      {busy ? <p>Loading…</p> : leads.map(l => (
        <Card key={l.id} data-testid={`lead-card-${l.id}`}>
          <CardContent className="p-4">
            <p>{l.name}</p>
            <p className="text-sm text-gray-500">{l.email}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

## .env.example

```
MONGO_URL=mongodb://localhost:27017
DB_NAME=app_db
JWT_SECRET=change-me
EMERGENT_LLM_KEY=
STRIPE_SECRET_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ORA_SESSION_USD_CAP=5.00
ORA_AUTONOMY_LEVEL=all
```

## requirements.txt Pattern

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
motor==3.6.0
pydantic==2.9.2
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

## Pytest Template

```python
# /app/backend/tests/test_leads.py
import pytest, os, httpx

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")

@pytest.mark.asyncio
async def test_create_then_list_lead():
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API}/api/leads",
                         json={"name": "T", "email": "t@x.com"})
        assert r.status_code == 200
        lid = r.json()["id"]
        r2 = await c.get(f"{API}/api/leads")
        assert any(d["id"] == lid for d in r2.json())
```

## Dockerfile (if needed)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

## 12-Step Scaffold Procedure (use with `propose_build_plan`)

1. Read founder's spec → write down acceptance criteria.
2. Sketch data model → Pydantic + Mongo collection name.
3. Create router file with empty endpoints.
4. Wire router into `server.py`.
5. Create service module for business logic.
6. Write pytest first (failing).
7. Implement until pytest passes.
8. Run `check_coverage` — must be ≥80%.
9. Run `run_linter` — must be 0 errors.
10. Create React page + form + list view.
11. Hit endpoint from React with `REACT_APP_BACKEND_URL`.
12. `verify_endpoint` smoke-test + screenshot + done.
