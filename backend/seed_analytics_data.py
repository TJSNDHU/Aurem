"""
Seed Anonymized Lead Data for Analytics Dashboard Testing
Creates sample leads across industries and geographies
"""

import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from uuid import uuid4
import random

# MongoDB connection
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'aurem_ai')

def seed_analytics_leads():
    """Create sample leads for analytics testing"""
    
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("📊 Seeding anonymized leads for Analytics Dashboard...")
    
    industries = ['E-commerce', 'Healthcare', 'Real Estate', 'Professional Services', 'Education', 'Technology']
    countries = ['United States', 'France', 'Spain', 'China', 'Saudi Arabia', 'Germany', 'Japan', 'Brazil']
    tenants = ['tenant_001', 'tenant_002', 'tenant_003', 'tenant_004', 'tenant_005']
    
    leads = []
    
    # Create 50 sample leads across last 30 days
    for i in range(50):
        days_ago = random.randint(0, 30)
        created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        
        lead = {
            "lead_id": str(uuid4()),
            "tenant_id": random.choice(tenants),
            "industry": random.choice(industries),
            "country": random.choice(countries),
            "status": random.choice(['new', 'contacted', 'qualified', 'won', 'lost']),
            "interest": random.choice(['Product Demo', 'Pricing Info', 'Support', 'Partnership', 'General Inquiry']),
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
            # No PII - names/emails/phones excluded for anonymization
        }
        leads.append(lead)
    
    # Insert leads
    if leads:
        db.leads.insert_many(leads)
    
    print(f"✅ Created {len(leads)} anonymized leads")
    print(f"   Industries: {len(industries)}")
    print(f"   Countries: {len(countries)}")
    print(f"   Tenants: {len(tenants)}")
    
    # Show aggregated stats
    total = db.leads.count_documents({})
    by_industry = {}
    by_country = {}
    
    for industry in industries:
        count = db.leads.count_documents({"industry": industry})
        by_industry[industry] = count
    
    for country in countries:
        count = db.leads.count_documents({"country": country})
        by_country[country] = count
    
    print(f"\n📈 Current Database Stats:")
    print(f"   Total Leads: {total}")
    print(f"   Top Industry: {max(by_industry, key=by_industry.get)} ({by_industry[max(by_industry, key=by_industry.get)]} leads)")
    print(f"   Top Country: {max(by_country, key=by_country.get)} ({by_country[max(by_country, key=by_country.get)]} leads)")
    
    client.close()

if __name__ == "__main__":
    seed_analytics_leads()
