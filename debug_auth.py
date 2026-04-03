#!/usr/bin/env python3
"""
Debug script to test AUREM platform authentication
"""
import hashlib
import sys
import os
sys.path.append('/app/backend')

# Import the platform auth router
from routers.platform_auth_router import ADMIN_USERS, hash_password

def test_auth():
    print("=== AUREM Platform Auth Debug ===")
    
    # Test credentials
    test_email = "admin@aurem.live"
    test_password = "AuremAdmin2024!"
    
    print(f"Test email: {test_email}")
    print(f"Test password: {test_password}")
    
    # Check what's in ADMIN_USERS
    print(f"\nStored admin users: {len(ADMIN_USERS)}")
    for email, user in ADMIN_USERS.items():
        print(f"  Email: {email}")
        print(f"  Stored hash: {user['password_hash']}")
        print(f"  Full name: {user['full_name']}")
        print(f"  Role: {user['role']}")
    
    # Test the hash function
    test_hash = hash_password(test_password)
    print(f"\nGenerated hash for test password: {test_hash}")
    
    # Check if email exists (case sensitive)
    email_lower = test_email.lower()
    print(f"\nEmail (lowercase): {email_lower}")
    print(f"Email exists in ADMIN_USERS: {email_lower in ADMIN_USERS}")
    
    if email_lower in ADMIN_USERS:
        stored_user = ADMIN_USERS[email_lower]
        stored_hash = stored_user["password_hash"]
        print(f"Stored hash: {stored_hash}")
        print(f"Generated hash: {test_hash}")
        print(f"Hashes match: {stored_hash == test_hash}")
        
        if stored_hash == test_hash:
            print("✅ Authentication should work!")
        else:
            print("❌ Hash mismatch - authentication will fail")
    else:
        print("❌ Email not found in ADMIN_USERS")
    
    # Test direct hash comparison
    direct_hash = hashlib.sha256(test_password.encode()).hexdigest()
    print(f"\nDirect SHA256 hash: {direct_hash}")
    print(f"Function hash: {test_hash}")
    print(f"Direct vs function match: {direct_hash == test_hash}")

if __name__ == "__main__":
    test_auth()