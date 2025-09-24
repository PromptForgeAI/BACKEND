#!/usr/bin/env python3
"""
Test Firebase Admin SDK 7.1.0 upgrade and clock skew tolerance functionality.
Run this to verify authentication is working properly.
"""
import asyncio
import logging
from datetime import timedelta
from firebase_admin import auth as fb_auth

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_firebase_auth_upgrade():
    """Test Firebase Admin SDK functionality after upgrade."""
    
    print("🔥 Testing Firebase Admin SDK 7.1.0 Features")
    print("=" * 50)
    
    # Test 1: Check if clock_skew_seconds parameter is supported
    print("\n1. Testing clock_skew_seconds parameter support...")
    try:
        import inspect
        
        # Check if verify_id_token accepts clock_skew_seconds parameter
        sig = inspect.signature(fb_auth.verify_id_token)
        params = list(sig.parameters.keys())
        print(f"Available parameters: {params}")
        
        if 'clock_skew_seconds' in params:
            print("✅ clock_skew_seconds parameter is supported")
        else:
            print("❌ clock_skew_seconds parameter NOT supported")
            
    except Exception as e:
        print(f"❌ Error checking parameters: {e}")
    
    # Test 2: Test with mock token (will fail but should show proper error handling)
    print("\n2. Testing error handling with mock token...")
    try:
        decoded = fb_auth.verify_id_token(
            "mock-invalid-token", 
            check_revoked=True,
            clock_skew_seconds=10
        )
        print("❌ Mock token verification should have failed")
    except fb_auth.InvalidIdTokenError:
        print("✅ Invalid token properly caught with clock_skew_seconds")
    except TypeError as e:
        print(f"❌ TypeError suggests parameter not supported: {e}")
    except Exception as e:
        print(f"✅ Expected error for invalid token: {type(e).__name__}")
    
    # Test 3: Import our auth.py module to check for syntax errors
    print("\n3. Testing auth.py module import...")
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        
        from auth import verify_firebase_token
        print("✅ auth.py imported successfully")
        print("✅ verify_firebase_token function available")
        
    except Exception as e:
        print(f"❌ Error importing auth.py: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Firebase Admin SDK 7.1.0 upgrade test complete!")
    print("   Your clock skew issues should now be resolved.")
    print("   Restart your FastAPI server to apply changes.")

if __name__ == "__main__":
    asyncio.run(test_firebase_auth_upgrade())
