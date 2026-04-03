"""
Seed Script for AUREM TOON-based SaaS System
Seeds:
1. Service Registry (all available third-party services)
2. Subscription Plans (Free, Starter, Professional, Enterprise)
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
from datetime import datetime, timezone

# Add backend to path
sys.path.append('/app/backend')

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'aurem_db')


async def seed_service_registry(db):
    """Seed service registry with all available third-party services"""
    
    services = [
        # LLM Services
        {
            "service_id": "gpt-4o",
            "name": "GPT-4o",
            "category": "llm",
            "provider": "OpenAI",
            "cost_per_1k_tokens": 0.005,
            "features": ["chat", "completion", "vision", "function_calling"],
            "requires_api_key": True,
            "api_key_field_name": "OPENAI_API_KEY",
            "available_in_tiers": ["starter", "professional", "enterprise"],
            "status": "no_keys",
            "docs_url": "https://platform.openai.com/docs",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "service_id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "category": "llm",
            "provider": "OpenAI",
            "cost_per_1k_tokens": 0.00015,
            "features": ["chat", "completion"],
            "requires_api_key": True,
            "api_key_field_name": "OPENAI_API_KEY",
            "available_in_tiers": ["free", "starter", "professional", "enterprise"],
            "status": "no_keys",
            "docs_url": "https://platform.openai.com/docs",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "service_id": "claude-sonnet-4",
            "name": "Claude Sonnet 4",
            "category": "llm",
            "provider": "Anthropic",
            "cost_per_1k_tokens": 0.003,
            "features": ["chat", "completion", "reasoning"],
            "requires_api_key": True,
            "api_key_field_name": "ANTHROPIC_API_KEY",
            "available_in_tiers": ["professional", "enterprise"],
            "status": "no_keys",
            "docs_url": "https://docs.anthropic.com",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "service_id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "category": "llm",
            "provider": "Google",
            "cost_per_1k_tokens": 0.0002,
            "features": ["chat", "completion", "fast"],
            "requires_api_key": True,
            "api_key_field_name": "GOOGLE_API_KEY",
            "available_in_tiers": ["starter", "professional", "enterprise"],
            "status": "no_keys",
            "docs_url": "https://ai.google.dev/docs",
            "created_at": datetime.now(timezone.utc)
        },
        
        # Voice Services
        {
            "service_id": "openai-tts",
            "name": "OpenAI TTS",
            "category": "voice",
            "provider": "OpenAI",
            "cost_per_1k_tokens": 0.015,
            "features": ["text_to_speech", "multiple_voices"],
            "requires_api_key": True,
            "api_key_field_name": "OPENAI_API_KEY",
            "available_in_tiers": ["starter", "professional", "enterprise"],
            "status": "no_keys",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "service_id": "openai-whisper",
            "name": "OpenAI Whisper",
            "category": "voice",
            "provider": "OpenAI",
            "cost_per_minute": 0.006,
            "features": ["speech_to_text", "multilingual"],
            "requires_api_key": True,
            "api_key_field_name": "OPENAI_API_KEY",
            "available_in_tiers": ["starter", "professional", "enterprise"],
            "status": "no_keys",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "service_id": "voxtral-tts",
            "name": "Voxtral TTS",
            "category": "voice",
            "provider": "Mistral",
            "cost_per_minute": 0.002,
            "features": ["text_to_speech", "premium_quality", "low_latency"],
            "requires_api_key": True,
            "api_key_field_name": "MISTRAL_API_KEY",
            "available_in_tiers": ["professional", "enterprise"],
            "status": "no_keys",
            "created_at": datetime.now(timezone.utc)
        },
        
        # Image Services
        {
            "service_id": "gpt-image-1",
            "name": "GPT Image 1 (DALL-E)",
            "category": "image",
            "provider": "OpenAI",
            "cost_per_image": 0.04,
            "features": ["image_generation", "high_quality"],
            "requires_api_key": True,
            "api_key_field_name": "OPENAI_API_KEY",
            "available_in_tiers": ["professional", "enterprise"],
            "status": "no_keys",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "service_id": "nano-banana",
            "name": "Nano Banana (Gemini)",
            "category": "image",
            "provider": "Google",
            "cost_per_image": 0.02,
            "features": ["image_generation", "fast"],
            "requires_api_key": True,
            "api_key_field_name": "GOOGLE_API_KEY",
            "available_in_tiers": ["professional", "enterprise"],
            "status": "no_keys",
            "created_at": datetime.now(timezone.utc)
        },
        
        # Payments
        {
            "service_id": "stripe-payments",
            "name": "Stripe Payments",
            "category": "payments",
            "provider": "Stripe",
            "cost_per_api_call": 0.029,  # 2.9% fee
            "features": ["payments", "subscriptions", "invoicing"],
            "requires_api_key": True,
            "api_key_field_name": "STRIPE_SECRET_KEY",
            "available_in_tiers": ["free", "starter", "professional", "enterprise"],
            "status": "no_keys",
            "created_at": datetime.now(timezone.utc)
        },
    ]
    
    # Insert or update services
    for service in services:
        await db.service_registry.update_one(
            {"service_id": service["service_id"]},
            {"$set": service},
            upsert=True
        )
    
    print(f"✅ Seeded {len(services)} services into service_registry")


async def seed_subscription_plans(db):
    """Seed subscription plans"""
    
    plans = [
        # FREE TIER
        {
            "plan_id": "plan_free",
            "tier": "free",
            "name": "Free Forever",
            "tagline": "Perfect for trying out AUREM AI",
            "price_monthly": 0,
            "price_annual": 0,
            "currency": "usd",
            "limits": {
                "ai_tokens": 5000,
                "formulas": 3,
                "content_pieces": 5,
                "workflows": 1,
                "videos": 0
            },
            "features": {
                "ai_chat": True,
                "voice_tts": "browser",
                "voice_to_voice": False,
                "multi_agent": False,
                "crew_ai": [],
                "video_upscaling": False,
                "competitive_intelligence": False,
                "api_access": False,
                "white_label": False,
                "priority_support": False
            },
            "included_services": ["gpt-4o-mini"],
            "features_list": [
                "3 Formula Storage",
                "5 AI Content/Month",
                "Basic Browser Voice",
                "1 Automation Workflow",
                "Community Support"
            ],
            "is_popular": False,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        },
        
        # STARTER TIER
        {
            "plan_id": "plan_starter",
            "tier": "starter",
            "name": "Starter",
            "tagline": "Perfect for solopreneurs",
            "price_monthly": 99,
            "price_annual": 950,  # 20% discount
            "currency": "usd",
            "limits": {
                "ai_tokens": 50000,
                "formulas": 20,
                "content_pieces": 50,
                "workflows": 5,
                "videos": 0
            },
            "features": {
                "ai_chat": True,
                "voice_tts": "openai",
                "voice_to_voice": False,
                "multi_agent": False,
                "crew_ai": [],
                "video_upscaling": False,
                "competitive_intelligence": False,
                "api_access": False,
                "white_label": True,
                "priority_support": False
            },
            "included_services": ["gpt-4o-mini", "gpt-4o", "openai-tts", "stripe-payments"],
            "features_list": [
                "20 Formula Storage",
                "50 AI Content/Month",
                "Premium OpenAI TTS",
                "5 Automation Workflows",
                "Email Support (48hr)",
                "Remove Branding"
            ],
            "is_popular": True,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        },
        
        # PROFESSIONAL TIER
        {
            "plan_id": "plan_professional",
            "tier": "professional",
            "name": "Professional",
            "tagline": "For growing brands",
            "price_monthly": 399,
            "price_annual": 3830,  # 20% discount
            "currency": "usd",
            "limits": {
                "ai_tokens": 200000,
                "formulas": 50,
                "content_pieces": 200,
                "workflows": 20,
                "videos": 10
            },
            "features": {
                "ai_chat": True,
                "voice_tts": "openai",
                "voice_to_voice": True,
                "multi_agent": True,
                "crew_ai": ["editorial", "support", "logistics"],
                "video_upscaling": True,
                "competitive_intelligence": True,
                "api_access": True,
                "white_label": True,
                "priority_support": True
            },
            "included_services": ["gpt-4o", "openai-tts", "openai-whisper", "voxtral-tts", "gpt-image-1", "nano-banana", "stripe-payments"],
            "features_list": [
                "50 Formula Storage",
                "200 AI Content/Month",
                "Voice-to-Voice AI",
                "3 Multi-Agent Crews",
                "10 Video Upscaling/Month",
                "Weekly Competitor Reports",
                "API Access",
                "Priority Support (24hr)"
            ],
            "is_popular": True,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        },
        
        # ENTERPRISE TIER
        {
            "plan_id": "plan_enterprise",
            "tier": "enterprise",
            "name": "Enterprise",
            "tagline": "Autonomous Business Operating System",
            "price_monthly": 999,
            "price_annual": 9590,  # 20% discount
            "currency": "usd",
            "limits": {
                "ai_tokens": 999999999,  # Unlimited
                "formulas": 999999999,
                "content_pieces": 999999999,
                "workflows": 999999999,
                "videos": 999999999
            },
            "features": {
                "ai_chat": True,
                "voice_tts": "voxtral",
                "voice_to_voice": True,
                "multi_agent": True,
                "crew_ai": ["editorial", "support", "logistics", "biotech", "security"],
                "video_upscaling": True,
                "competitive_intelligence": True,
                "api_access": True,
                "white_label": True,
                "priority_support": True,
                "custom_development": True,
                "3d_visualization": True,
                "embeddable_widget": True
            },
            "included_services": ["gpt-4o", "claude-sonnet-4", "openai-tts", "openai-whisper", "voxtral-tts", "gpt-image-1", "nano-banana", "stripe-payments"],
            "features_list": [
                "Unlimited Everything",
                "Premium Voxtral Voice",
                "5 Multi-Agent Crews",
                "Unlimited Video Processing",
                "Daily Intelligence Reports",
                "3D Visualizations",
                "Embeddable AI Widget",
                "Dedicated Support",
                "Custom Development"
            ],
            "is_popular": False,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        },
    ]
    
    # Insert or update plans
    for plan in plans:
        await db.subscription_plans.update_one(
            {"plan_id": plan["plan_id"]},
            {"$set": plan},
            upsert=True
        )
    
    print(f"✅ Seeded {len(plans)} subscription plans")


async def main():
    """Main seed function"""
    print("🌱 Starting AUREM SaaS Seed...")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Seed service registry
    await seed_service_registry(db)
    
    # Seed subscription plans
    await seed_subscription_plans(db)
    
    print("✅ Seed complete!")
    
    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
