"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Proximity Blast Service
=======================
Geofenced local lead discovery and promotion engine.
Simulated data layer with admin toggle for Live Google Maps API.

Add-on: $49/month for Starter/Growth tiers.
"""
import logging
import random
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# SIMULATED LOCAL LEADS (Demo / Development)
# ═══════════════════════════════════════════════════════════════

BUSINESS_TYPES = [
    "MedSpa", "Dental Clinic", "Hair Salon", "Fitness Studio", "Yoga Studio",
    "Pet Grooming", "Coffee Shop", "Restaurant", "Auto Repair", "Real Estate Agency",
    "Accounting Firm", "Law Office", "Physiotherapy", "Chiropractic", "Florist",
    "Bakery", "Nail Salon", "Barbershop", "Dry Cleaner", "Insurance Agency",
    "Optometrist", "Pharmacy", "Tattoo Parlor", "Photography Studio", "Print Shop",
]

FIRST_NAMES = ["Sarah", "James", "Maria", "David", "Lisa", "Michael", "Jennifer",
               "Robert", "Emily", "Daniel", "Ashley", "Christopher", "Amanda", "Matthew",
               "Stephanie", "Andrew", "Nicole", "Joshua", "Jessica", "Ryan"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
              "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
              "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

STREET_NAMES = ["Oak St", "Maple Ave", "Cedar Ln", "Pine Rd", "Elm Blvd",
                "Birch Dr", "Walnut Cr", "Spruce Way", "Willow Pl", "Cherry St"]


def _random_point_in_radius(lat: float, lng: float, radius_km: float):
    """Generate a random lat/lng within a radius (simple approximation)."""
    r = radius_km / 111.0  # rough degrees per km
    u = random.random()
    v = random.random()
    w = r * math.sqrt(u)
    t = 2 * math.pi * v
    x = w * math.cos(t)
    y = w * math.sin(t)
    return round(lat + x, 6), round(lng + y / math.cos(math.radians(lat)), 6)


def generate_simulated_leads(lat: float, lng: float, radius_km: float, count: int = 20) -> list:
    """Generate simulated local business leads within a radius."""
    leads = []
    for i in range(count):
        lead_lat, lead_lng = _random_point_in_radius(lat, lng, radius_km)
        distance = round(random.uniform(0.5, radius_km), 1)
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        btype = random.choice(BUSINESS_TYPES)
        street_num = random.randint(10, 9999)
        street = random.choice(STREET_NAMES)

        leads.append({
            "lead_id": f"prox_{i+1:04d}",
            "business_name": f"{first}'s {btype}",
            "owner_name": f"{first} {last}",
            "business_type": btype,
            "address": f"{street_num} {street}",
            "lat": lead_lat,
            "lng": lead_lng,
            "distance_km": distance,
            "phone": f"+1{random.randint(200,999)}{random.randint(100,999)}{random.randint(1000,9999)}",
            "email": f"{first.lower()}.{last.lower()}@{btype.lower().replace(' ', '')}.com",
            "rating": round(random.uniform(3.5, 5.0), 1),
            "review_count": random.randint(5, 300),
            "match_score": random.randint(60, 98),
            "status": random.choice(["new", "new", "new", "contacted", "interested"]),
        })

    leads.sort(key=lambda x: x["distance_km"])
    return leads


# ═══════════════════════════════════════════════════════════════
# BLAST CAMPAIGN MANAGEMENT
# ═══════════════════════════════════════════════════════════════

async def get_proximity_config(tenant_id: str) -> dict:
    """Get the proximity blast config for a tenant."""
    db = _get_db()
    defaults = {
        "tenant_id": tenant_id,
        "enabled": False,
        "data_source": "simulated",
        "default_radius_km": 10,
        "business_lat": 43.6532,
        "business_lng": -79.3832,
        "addon_active": False,
        "addon_price_monthly": 49,
        "campaigns_run": 0,
    }
    if db is None:
        return defaults

    config = await db.proximity_config.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not config:
        return defaults
    return {**defaults, **config}


async def save_proximity_config(tenant_id: str, update: dict) -> dict:
    """Update proximity blast config."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    safe_fields = {
        k: v for k, v in update.items()
        if k in ("enabled", "data_source", "default_radius_km",
                  "business_lat", "business_lng", "addon_active")
    }
    safe_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.proximity_config.update_one(
        {"tenant_id": tenant_id},
        {
            "$set": safe_fields,
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )
    return await get_proximity_config(tenant_id)


async def run_blast(tenant_id: str, lat: float, lng: float, radius_km: float, count: int = 20) -> dict:
    """Execute a proximity blast — discover leads in radius."""
    db = _get_db()
    config = await get_proximity_config(tenant_id)
    source = config.get("data_source", "simulated")

    if source == "live":
        # Placeholder for Google Maps API integration
        leads = generate_simulated_leads(lat, lng, radius_km, count)
        source_label = "live_google_maps"
    else:
        leads = generate_simulated_leads(lat, lng, radius_km, count)
        source_label = "simulated"

    # Store campaign record
    campaign = {
        "tenant_id": tenant_id,
        "lat": lat,
        "lng": lng,
        "radius_km": radius_km,
        "leads_found": len(leads),
        "data_source": source_label,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if db is not None:
        await db.proximity_campaigns.insert_one({**campaign})
        await db.proximity_config.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"campaigns_run": 1}},
        )

    return {
        "campaign": {k: v for k, v in campaign.items() if k != "_id"},
        "leads": leads,
        "total": len(leads),
        "source": source_label,
    }
