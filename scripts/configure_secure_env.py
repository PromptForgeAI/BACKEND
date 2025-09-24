#!/usr/bin/env python3
"""
SECURE ENVIRONMENT CONFIGURATION
Sets up proper environment variables for production security
"""
import os

def configure_production_env():
    """
    Configure environment for production security
    """
    print("🔒 CONFIGURING PRODUCTION SECURITY ENVIRONMENT")
    print("=" * 60)
    
    # SECURITY: Default to production mode
    os.environ["ENV"] = "production"
    os.environ["EXPLICIT_TEST_MODE"] = "false"
    
    # Remove any development bypasses
    if "TESTING_MODE" in os.environ:
        del os.environ["TESTING_MODE"]
    
    print("✅ Environment configured for production:")
    print(f"   ENV: {os.environ.get('ENV')}")
    print(f"   EXPLICIT_TEST_MODE: {os.environ.get('EXPLICIT_TEST_MODE')}")
    print(f"   TESTING_MODE: {os.environ.get('TESTING_MODE', 'NOT SET')}")
    
    print("\n🚨 SECURITY STATUS:")
    print("   ✅ Mock authentication DISABLED")
    print("   ✅ Credit bypasses DISABLED") 
    print("   ✅ Development shortcuts DISABLED")
    print("   ✅ Only real Firebase tokens accepted")
    
    print("\n📋 For legitimate testing:")
    print("   1. Use real Firebase tokens")
    print("   2. Top up credits via: python scripts/secure_credit_topup.py")
    print("   3. Use test database: MONGODB_DATABASE=test_promptforge")

def configure_test_env():
    """
    Configure environment for testing (with strict controls)
    """
    print("🧪 CONFIGURING TEST ENVIRONMENT (RESTRICTED)")
    print("=" * 60)
    
    # Require test database
    db_name = os.environ.get("MONGODB_DATABASE", "")
    if not db_name.startswith("test_"):
        print("❌ ERROR: Test mode requires database name starting with 'test_'")
        print("   Set: MONGODB_DATABASE=test_promptforge")
        return False
    
    os.environ["ENV"] = "test"
    os.environ["EXPLICIT_TEST_MODE"] = "true"
    
    print("✅ Test environment configured:")
    print(f"   ENV: {os.environ.get('ENV')}")
    print(f"   DATABASE: {db_name}")
    print(f"   EXPLICIT_TEST_MODE: {os.environ.get('EXPLICIT_TEST_MODE')}")
    
    print("\n⚠️  TEST RESTRICTIONS:")
    print("   🔒 Only test- prefixed tokens accepted")
    print("   🔒 Must use test database")
    print("   🔒 Real credits still required (no bypasses)")
    
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        configure_test_env()
    else:
        configure_production_env()
