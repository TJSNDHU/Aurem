"""
Seed Multilingual Panic Events for War Room UI Testing
Creates realistic panic scenarios across multiple languages
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from uuid import uuid4

# MongoDB connection
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'aurem_ai')

async def seed_panic_events():
    """Create multilingual panic event samples"""
    
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🌍 Seeding multilingual panic events for War Room testing...")
    
    # Clear existing panic events for clean testing
    db.panic_events.delete_many({})
    
    # Sample panic events across languages
    panic_events = [
        {
            "event_id": str(uuid4()),
            "tenant_id": "aurem_platform",
            "conversation_id": f"conv_{uuid4().hex[:8]}",
            "customer": {
                "name": "Sarah Johnson",
                "email": "sarah.j@example.com",
                "phone": "+1-415-555-0123"
            },
            "trigger_reason": "High negative sentiment detected",
            "sentiment_score": -0.92,
            "sentiment_label": "panic",
            "detected_language": "en",
            "detected_keywords": ["frustrated", "terrible", "refund"],
            "original_message": "This is absolutely terrible! I've been waiting 3 weeks for my order and nobody is helping me. I want my money back NOW!",
            "english_translation": None,  # Already in English
            "last_message": "This is absolutely terrible! I've been waiting 3 weeks for my order and nobody is helping me. I want my money back NOW!",
            "status": "triggered",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        },
        {
            "event_id": str(uuid4()),
            "tenant_id": "aurem_platform",
            "conversation_id": f"conv_{uuid4().hex[:8]}",
            "customer": {
                "name": "Pierre Dubois",
                "email": "p.dubois@example.fr",
                "phone": "+33-1-42-86-82-00"
            },
            "trigger_reason": "Extreme frustration + refund keywords",
            "sentiment_score": -0.88,
            "sentiment_label": "panic",
            "detected_language": "fr",
            "detected_keywords": ["furieux", "inacceptable", "remboursement"],
            "original_message": "C'est absolument inacceptable! Je suis furieux. Votre service est catastrophique. Je veux un remboursement immédiat!",
            "english_translation": "This is absolutely unacceptable! I am furious. Your service is catastrophic. I want an immediate refund!",
            "last_message": "This is absolutely unacceptable! I am furious. Your service is catastrophic. I want an immediate refund!",
            "status": "triggered",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
        },
        {
            "event_id": str(uuid4()),
            "tenant_id": "aurem_platform",
            "conversation_id": f"conv_{uuid4().hex[:8]}",
            "customer": {
                "name": "María González",
                "email": "m.gonzalez@example.es",
                "phone": "+34-91-123-4567"
            },
            "trigger_reason": "Legal threat detected",
            "sentiment_score": -0.85,
            "sentiment_label": "panic",
            "detected_language": "es",
            "detected_keywords": ["abogado", "estafa", "denuncia"],
            "original_message": "¡Esto es una estafa! Voy a hablar con mi abogado y presentar una denuncia. Su empresa me debe dinero.",
            "english_translation": "This is a scam! I'm going to talk to my lawyer and file a complaint. Your company owes me money.",
            "last_message": "This is a scam! I'm going to talk to my lawyer and file a complaint. Your company owes me money.",
            "status": "triggered",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=8)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=8)).isoformat()
        },
        {
            "event_id": str(uuid4()),
            "tenant_id": "aurem_platform",
            "conversation_id": f"conv_{uuid4().hex[:8]}",
            "customer": {
                "name": "李明 (Li Ming)",
                "email": "liming@example.cn",
                "phone": "+86-10-1234-5678"
            },
            "trigger_reason": "Product defect + anger",
            "sentiment_score": -0.79,
            "sentiment_label": "panic",
            "detected_language": "zh",
            "detected_keywords": ["坏了", "不满意", "退款"],
            "original_message": "产品完全坏了！这太让人失望了。我非常不满意，要求立即退款！",
            "english_translation": "The product is completely broken! This is so disappointing. I am very dissatisfied and demand an immediate refund!",
            "last_message": "The product is completely broken! This is so disappointing. I am very dissatisfied and demand an immediate refund!",
            "status": "triggered",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        },
        {
            "event_id": str(uuid4()),
            "tenant_id": "aurem_platform",
            "conversation_id": f"conv_{uuid4().hex[:8]}",
            "customer": {
                "name": "أحمد العلي (Ahmad Al-Ali)",
                "email": "ahmad.alali@example.sa",
                "phone": "+966-11-123-4567"
            },
            "trigger_reason": "Service complaint + human request",
            "sentiment_score": -0.83,
            "sentiment_label": "panic",
            "detected_language": "ar",
            "detected_keywords": ["سيء", "شكوى", "مدير"],
            "original_message": "الخدمة سيئة جداً! أريد التحدث مع المدير فوراً. سأقدم شكوى رسمية!",
            "english_translation": "The service is very bad! I want to speak with the manager immediately. I will file an official complaint!",
            "last_message": "The service is very bad! I want to speak with the manager immediately. I will file an official complaint!",
            "status": "triggered",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
        }
    ]
    
    # Insert all events
    result = db.panic_events.insert_many(panic_events)
    
    print(f"✅ Created {len(result.inserted_ids)} multilingual panic events:")
    print("   🇺🇸 English (Sarah - Frustrated order delay)")
    print("   🇫🇷 French (Pierre - Service catastrophe)")
    print("   🇪🇸 Spanish (María - Legal threat)")
    print("   🇨🇳 Mandarin (李明 - Product defect)")
    print("   🇸🇦 Arabic (أحمد - Manager escalation)")
    
    print(f"\n📊 Total panic_events in database: {db.panic_events.count_documents({})}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_panic_events())
