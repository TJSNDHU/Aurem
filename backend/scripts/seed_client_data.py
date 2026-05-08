"""
Seed ReRoots & Aurem client business profiles, scan history, and repair fixes.
Idempotent — safe to run multiple times.
"""
import asyncio
import os
import secrets
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")

CLIENTS = [
    {
        "profile_id": f"bp_{secrets.token_urlsafe(8)}",
        "business_name": "ReRoots Aesthetics",
        "website_url": "https://reroots.ca",
        "email": "pawandeep19may1985@gmail.com",
        "category": "health_beauty",
        "sub_category": "Aesthetics & Med Spa",
        "revenue_model": "service_booking",
        "target_audience": "Women 25-55 seeking aesthetic treatments",
        "growth_stage": "growth",
        "urgency_score": 8,
        "status": "active",
        "plan": "professional",
        "onboarded_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
    },
    {
        "profile_id": f"bp_{secrets.token_urlsafe(8)}",
        "business_name": "AUREM AI Platform",
        "website_url": "https://aurem.ai",
        "email": "teji.ss1986@gmail.com",
        "category": "technology",
        "sub_category": "SaaS / AI Platform",
        "revenue_model": "subscription",
        "target_audience": "Small businesses seeking AI automation",
        "growth_stage": "launch",
        "urgency_score": 9,
        "status": "active",
        "plan": "enterprise",
        "onboarded_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    },
]

SCAN_TYPES = ["seo", "security", "performance", "accessibility"]


def _make_scan(client, scan_type, days_ago, score):
    scan_id = f"scan_{secrets.token_urlsafe(8)}"
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    issues = max(0, 100 - score) // 10
    return {
        "scan_id": scan_id,
        "profile_id": client["profile_id"],
        "business_name": client["business_name"],
        "website_url": client["website_url"],
        "scan_type": scan_type,
        "overall_score": score,
        "issues_found": issues,
        "critical_issues": max(0, issues - 2),
        "status": "completed",
        "created_at": ts,
        "completed_at": ts,
    }


def _make_repair(client, scan_id, fix_type, category, days_ago, status="deployed"):
    fix_id = f"fix_{secrets.token_urlsafe(8)}"
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    descriptions = {
        "seo": [
            "Added missing meta description tag",
            "Optimized H1 heading for target keywords",
            "Added structured data (JSON-LD) markup",
            "Fixed duplicate title tags across pages",
            "Added Open Graph tags for social sharing",
        ],
        "security": [
            "Enforced HTTPS redirect on all pages",
            "Added Content-Security-Policy header",
            "Enabled X-Frame-Options: DENY",
            "Set Strict-Transport-Security header",
            "Patched outdated jQuery version",
        ],
        "performance": [
            "Compressed hero images (saved 450KB)",
            "Enabled browser caching headers",
            "Minified CSS and JS bundles",
            "Lazy-loaded below-fold images",
            "Eliminated render-blocking resources",
        ],
        "accessibility": [
            "Added alt text to 12 images",
            "Fixed color contrast ratio on CTA buttons",
            "Added ARIA labels to navigation",
            "Fixed missing form input labels",
            "Added skip-to-content link",
        ],
    }
    import random
    desc = random.choice(descriptions.get(category, ["General fix applied"]))
    return {
        "fix_id": fix_id,
        "scan_id": scan_id,
        "profile_id": client["profile_id"],
        "business_name": client["business_name"],
        "website_url": client["website_url"],
        "category": category,
        "fix_type": fix_type,
        "description": desc,
        "status": status,
        "created_at": ts,
        "deployed_at": ts if status == "deployed" else None,
    }


async def seed():
    client_conn = AsyncIOMotorClient(MONGO_URL)
    db = client_conn[DB_NAME]

    profiles_added = 0
    scans_added = 0
    repairs_added = 0

    for c in CLIENTS:
        existing = await db.business_profiles.find_one(
            {"website_url": c["website_url"]}, {"_id": 1}
        )
        if existing:
            print(f"  [skip] {c['business_name']} already exists")
            # Get the profile_id from existing
            ex_full = await db.business_profiles.find_one(
                {"website_url": c["website_url"]}, {"_id": 0, "profile_id": 1}
            )
            if ex_full:
                c["profile_id"] = ex_full["profile_id"]
            continue
        c["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.business_profiles.insert_one({k: v for k, v in c.items()})
        profiles_added += 1
        print(f"  [+] Business profile: {c['business_name']}")

    # Seed scans & repairs for each client
    for c in CLIENTS:
        existing_scans = await db.scan_history.count_documents(
            {"website_url": c["website_url"]}
        )
        if existing_scans > 0:
            print(f"  [skip] {c['business_name']} already has {existing_scans} scans")
            continue

        import random
        for st in SCAN_TYPES:
            # 2 scans per type: one older, one recent
            score_old = random.randint(45, 70)
            score_new = random.randint(80, 98)
            scan_old = _make_scan(c, st, days_ago=30, score=score_old)
            scan_new = _make_scan(c, st, days_ago=2, score=score_new)
            await db.scan_history.insert_one({k: v for k, v in scan_old.items()})
            await db.scan_history.insert_one({k: v for k, v in scan_new.items()})
            scans_added += 2

            # 3-5 repairs per scan type
            num_repairs = random.randint(3, 5)
            for i in range(num_repairs):
                repair = _make_repair(
                    c,
                    scan_new["scan_id"],
                    fix_type="auto_patch",
                    category=st,
                    days_ago=1,
                    status="deployed",
                )
                await db.repair_fixes.insert_one({k: v for k, v in repair.items()})
                repairs_added += 1

    print(f"\nSeed complete: {profiles_added} profiles, {scans_added} scans, {repairs_added} repairs")
    client_conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
