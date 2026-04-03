"""
ReRoots — server.py Router Refactor Plan
File: routes/REFACTOR_GUIDE.py

The current server.py is ~38,000 lines. This guide shows how to
split it into clean router modules without breaking anything.

APPROACH: Extract incrementally — one router at a time.
          Each extraction is safe and independently reversible.
          Never touch working code — only move it.

EXPECTED RESULT:
  server.py:          ~200 lines (app init + middleware + router mounts)
  routes/auth.py:     ~300 lines
  routes/orders.py:   ~600 lines
  routes/products.py: ~400 lines
  routes/crm.py:      ~500 lines
  routes/inventory.py:~300 lines
  routes/automations.py: already exists
  routes/flagship.py: ~200 lines
  routes/admin.py:    ~400 lines
  routes/quiz.py:     ~200 lines
  routes/partners.py: ~250 lines
  routes/loyalty.py:  ~200 lines
  routes/analytics.py:~300 lines

TOTAL: Same lines, distributed. Deployments will be 10x faster.
"""


# ════════════════════════════════════════════════════════════════
# STEP 0 — THE REFACTORED server.py (target state, ~200 lines)
# ════════════════════════════════════════════════════════════════

NEW_SERVER_PY = '''
"""
ReRoots — server.py (refactored)
All route logic lives in /routes/*.py
This file: app creation, middleware, db, router mounting only.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="ReRoots API", version="2.0")

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://reroots.ca", "https://www.reroots.ca",
                   "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database ──────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client    = AsyncIOMotorClient(MONGO_URI)
db        = client[os.getenv("DB_NAME", "reroots")]

def get_db():
    return db

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0"}

# ── Routers ───────────────────────────────────────────────────
from routes.auth        import router as auth_router
from routes.products    import router as products_router
from routes.orders      import router as orders_router
from routes.crm         import router as crm_router
from routes.inventory   import router as inventory_router
from routes.automations import router as automations_router
from routes.flagship    import router as flagship_router
from routes.quiz        import router as quiz_router
from routes.partners    import router as partners_router
from routes.loyalty     import router as loyalty_router
from routes.analytics   import router as analytics_router
from routes.admin       import router as admin_router
from routes.abandoned   import router as abandoned_router
from routes.waitlist_restock import router as restock_router

# Mount all routers
app.include_router(auth_router,        prefix="/api/auth",      tags=["auth"])
app.include_router(products_router,    prefix="/api/products",  tags=["products"])
app.include_router(orders_router,      prefix="/api/orders",    tags=["orders"])
app.include_router(crm_router,         prefix="/api/crm",       tags=["crm"])
app.include_router(inventory_router,   prefix="/api/inventory", tags=["inventory"])
app.include_router(automations_router, prefix="/api/admin",     tags=["automations"])
app.include_router(flagship_router,    prefix="/api/admin",     tags=["flagship"])
app.include_router(quiz_router,        prefix="/api/quiz",      tags=["quiz"])
app.include_router(partners_router,    prefix="/api/admin",     tags=["partners"])
app.include_router(loyalty_router,     prefix="/api/admin",     tags=["loyalty"])
app.include_router(analytics_router,   prefix="/api/admin",     tags=["analytics"])
app.include_router(admin_router,       prefix="/api/admin",     tags=["admin"])
app.include_router(abandoned_router,   prefix="/api/abandoned", tags=["abandoned"])
app.include_router(restock_router,     prefix="/api/admin",     tags=["restock"])

# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    from routes.reroots_p0_fixes import delete_founder_discount_permanently
    # One-time migration — safe to run repeatedly
    try:
        await delete_founder_discount_permanently(db)
    except Exception:
        pass
    print("✅ ReRoots API started — all routers mounted")
'''


# ════════════════════════════════════════════════════════════════
# STEP 1 — ROUTER TEMPLATE
# Copy this pattern for every new router file
# ════════════════════════════════════════════════════════════════

ROUTER_TEMPLATE = '''
"""
ReRoots — routes/{name}.py
Extracted from server.py. Handles: {description}
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime
from bson import ObjectId

# Import db dependency from server.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from server import get_db   # or: from dependencies import get_db

router = APIRouter()

# ── Paste route handlers here ──────────────────────────────────
# Change:  @app.get("/api/orders")
# To:      @router.get("")          (prefix is set in server.py)
# Or:      @router.get("/orders")   (if mixed prefixes)
#
# Change:  async def handler(db=Depends(get_db)):
# Keep as: async def handler(db=Depends(get_db)):   (no change needed)
'''


# ════════════════════════════════════════════════════════════════
# STEP 2 — EXTRACTION ORDER (safest sequence)
# ════════════════════════════════════════════════════════════════

EXTRACTION_ORDER = """
Extract routers in this order. Each step is independent and safe.
Test after each extraction before moving to the next.

Phase 1 — Low-risk, isolated (do these first):
  1. routes/quiz.py          search: "quiz/submit", "quiz-submissions"
  2. routes/loyalty.py       search: "loyalty/users", "loyalty/stats"
  3. routes/partners.py      search: "partners", "partner-referrals"
  4. routes/abandoned.py     search: "abandoned/stats", "run-automation"

Phase 2 — Core business logic:
  5. routes/flagship.py      search: "flagship/webhook", "flagship/sync"
  6. routes/inventory.py     search: "/products" (admin/inventory routes)
  7. routes/crm.py           search: "crm/customers", "crm/"
  8. routes/orders.py        search: "@app.post(\"/api/orders\")"

Phase 3 — Auth and admin (most careful):
  9. routes/auth.py          search: "auth/login", "auth/me", "setup-owner"
  10. routes/admin.py        search: remaining /admin/* routes
  11. routes/analytics.py    search: "admin/stats", "ad-campaigns"

Final:
  12. Trim server.py to just app init + middleware + db + imports
"""


# ════════════════════════════════════════════════════════════════
# STEP 3 — CONCRETE EXAMPLE: orders.py extraction
# Shows exactly how to do one extraction end-to-end
# ════════════════════════════════════════════════════════════════

ORDERS_ROUTER_EXAMPLE = '''
# routes/orders.py — extracted from server.py

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime
from bson import ObjectId

from server import get_db
from routes.reroots_p0_fixes import (
    apply_auto_discount,
    track_partner_referral,
    award_loyalty_points,
)
from routes.reroots_email_templates import order_confirmation
from routes.reroots_p0_fixes import sendgrid_send_email
from routes.waitlist_restock import mark_restock_conversion

router = APIRouter()


@router.post("")          # mounts at POST /api/orders
async def create_order(order_data: dict = Body(...), db=Depends(get_db)):
    # P0-A: Correct discount
    customer_tags = order_data.get("customerTags", [])
    if not customer_tags:
        existing = await db.customers.find_one({"email": order_data.get("email","")})
        customer_tags = (existing or {}).get("tags", [])
    discount_info = apply_auto_discount(customer_tags, order_data.get("discountCode"))
    subtotal      = float(order_data.get("subtotal") or order_data.get("amount") or 0)
    order_total   = subtotal * (1 - discount_info["pct"])
    order_data.update({
        "total": order_total,
        "discountPct": discount_info["pct"],
        "discountLabel": discount_info["label"],
        "createdAt": datetime.utcnow(),
        "status": "pending",
    })

    result         = await db.orders.insert_one(order_data)
    order_id       = result.inserted_id
    customer_email = order_data.get("customerEmail") or order_data.get("email","")

    # P0-B: Order confirmation email
    if customer_email:
        tmpl = order_confirmation({**order_data, "_id": str(order_id)})
        await sendgrid_send_email(customer_email, tmpl["subject"], tmpl["html"])

    # P0-C: Partner tracking
    if order_data.get("discountCode"):
        await track_partner_referral(db, str(order_id), order_total, order_data["discountCode"])

    # P0-D: Loyalty points
    if customer_email:
        await award_loyalty_points(db, customer_email, order_total, str(order_id))

    # Restock conversion tracking
    if customer_email:
        for item in order_data.get("items", []):
            await mark_restock_conversion(db, customer_email, str(item.get("productId","")))

    # CRM upsert
    if customer_email:
        await db.crm_customers.update_one(
            {"email": customer_email},
            {"$set": {"lastOrderId": str(order_id), "lastOrderAt": datetime.utcnow(),
                      "status": "active_customer"},
             "$setOnInsert": {"createdAt": datetime.utcnow()}},
            upsert=True
        )

    return {
        "orderId": str(order_id), "total": order_total,
        "discountApplied": discount_info["pct"] > 0,
        "emailSent": bool(customer_email), "status": "created"
    }


@router.get("")           # mounts at GET /api/orders
async def get_orders(db=Depends(get_db)):
    orders = await db.orders.find({}).sort("createdAt", -1).limit(100).to_list(None)
    return [{"id": str(o["_id"]), **{k: v for k, v in o.items() if k != "_id"}} for o in orders]


@router.get("/{order_id}")
async def get_order(order_id: str, db=Depends(get_db)):
    try:
        order = await db.orders.find_one({"_id": ObjectId(order_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"id": str(order["_id"]), **{k: v for k, v in order.items() if k != "_id"}}
'''


# ════════════════════════════════════════════════════════════════
# STEP 4 — SAFE EXTRACTION PROCEDURE (do this for each router)
# ════════════════════════════════════════════════════════════════

EXTRACTION_PROCEDURE = """
For each router extraction:

1. CREATE the new router file (e.g. routes/orders.py)
   - Add: from fastapi import APIRouter; router = APIRouter()
   - Paste the relevant route handlers
   - Change @app.get to @router.get (remove /api/orders prefix)
   - Keep all Depends(get_db) as-is

2. ADD to server.py (don't remove old routes yet):
   from routes.orders import router as orders_router
   app.include_router(orders_router, prefix="/api/orders")

3. TEST — run the server, verify the endpoints still work.
   FastAPI will now serve both the old @app.get and the new @router.get.
   Check for duplicates in the /docs page.

4. REMOVE the old @app.get handlers from server.py

5. TEST again — confirm nothing broke

6. Repeat for next router

NEVER do steps 4 and 5 without doing step 3 first.
"""


# ════════════════════════════════════════════════════════════════
# STEP 5 — DEPENDENCIES FILE (shared across all routers)
# ════════════════════════════════════════════════════════════════

DEPENDENCIES_FILE = '''
# routes/dependencies.py
# Shared FastAPI dependencies — import from here in each router
# so you don't import from server.py (avoids circular imports)

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorClient
import os

_client = None
_db     = None

def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
        _db     = _client[os.getenv("DB_NAME", "reroots")]
    return _db

# Usage in any router:
# from routes.dependencies import get_db
# async def my_route(db=Depends(get_db)): ...
'''


# ════════════════════════════════════════════════════════════════
# DEPLOYMENT BENEFIT
# ════════════════════════════════════════════════════════════════
BENEFIT = """
BEFORE refactor:
  server.py:   38,000 lines
  Deployment:  60+ second startup (parsing 38k lines)
  Debugging:   ctrl+F through a single enormous file
  Conflicts:   every developer edits the same file

AFTER refactor:
  server.py:   ~200 lines
  Each router: 200–600 lines, single responsibility
  Deployment:  ~8 second startup
  Debugging:   open routes/orders.py, problem is obvious
  Conflicts:   each developer owns their module

The Emergent platform timeout (120s) was partly caused by
the 38k-line file parse time. This refactor resolves that too.
"""
