#!/usr/bin/env python3
"""
🔧 PROMPTFORGE.AI - DEVELOPMENT CONFIGURATION SCRIPT
Sets environment variables for testing and development mode
"""

import os
import sys

def setup_testing_environment():
    """Configure environment for comprehensive testing"""
    
    print("🔧 Setting up PromptForge.ai testing environment...")
    
    # Core environment settings
    os.environ['ENV'] = 'development'
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['TESTING_MODE'] = 'true'
    
    # Debug flags for comprehensive logging
    os.environ['DEBUG_BRAIN_ENGINE'] = '1'
    os.environ['DEBUG_DEMON_ENGINE'] = '1'
    os.environ['DEBUG_AUTH'] = '1'
    os.environ['DEBUG_RATE_LIMITING'] = '1'
    os.environ['DEBUG_VALIDATION'] = '1'
    os.environ['DEBUG_INJECTION_PROTECTION'] = '1'
    os.environ['DEBUG_SECURITY'] = '1'
    
    # Mock authentication
    os.environ['MOCK_AUTH_ENABLED'] = 'true'
    os.environ['ENABLE_DESTRUCTIVE_TESTS'] = '0'  # Safety first
    
    # Database settings for testing
    os.environ['MONGO_URL'] = os.getenv('MONGO_URL', 'mongodb+srv://shivadeepakdev_db_user:IazHjfnuOfLEnw40@testpfai.uoiqsww.mongodb.net/?retryWrites=true&w=majority&appName=testpfai')
    os.environ['MONGO_DB'] = os.getenv('MONGO_DB', 'promptforge_test')
    
    # Log level
    os.environ['LOG_LEVEL'] = 'DEBUG'
    
    print("✅ Testing environment configured!")
    print(f"   ENV: {os.environ['ENV']}")
    print(f"   TESTING_MODE: {os.environ['TESTING_MODE']}")
    print(f"   MOCK_AUTH_ENABLED: {os.environ['MOCK_AUTH_ENABLED']}")
    print(f"   DATABASE: {os.environ['MONGO_DB']}")
    print(f"   DEBUG FLAGS: All enabled")
    
    return True

def setup_production_environment():
    """Configure environment for production"""
    
    print("🚀 Setting up PromptForge.ai production environment...")
    
    # Core environment settings
    os.environ['ENV'] = 'production'
    os.environ['ENVIRONMENT'] = 'production'
    os.environ['TESTING_MODE'] = 'false'
    
    # Disable debug flags
    debug_flags = [
        'DEBUG_BRAIN_ENGINE', 'DEBUG_DEMON_ENGINE', 'DEBUG_AUTH',
        'DEBUG_RATE_LIMITING', 'DEBUG_VALIDATION', 'DEBUG_INJECTION_PROTECTION',
        'DEBUG_SECURITY'
    ]
    
    for flag in debug_flags:
        os.environ[flag] = '0'
    
    # Disable mock authentication
    os.environ['MOCK_AUTH_ENABLED'] = 'false'
    os.environ['ENABLE_DESTRUCTIVE_TESTS'] = '0'
    
    # Production database
    os.environ['MONGO_DB'] = os.getenv('MONGO_DB', 'promptforge')
    
    # Log level
    os.environ['LOG_LEVEL'] = 'INFO'
    
    print("✅ Production environment configured!")
    print(f"   ENV: {os.environ['ENV']}")
    print(f"   TESTING_MODE: {os.environ['TESTING_MODE']}")
    print(f"   MOCK_AUTH_ENABLED: {os.environ['MOCK_AUTH_ENABLED']}")
    print(f"   DATABASE: {os.environ['MONGO_DB']}")
    print(f"   DEBUG FLAGS: All disabled")
    
    return True

def validate_configuration():
    """Validate the current configuration"""
    
    print("\n🔍 Validating configuration...")
    
    required_vars = ['ENV', 'MONGO_URL', 'MONGO_DB']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    # Check testing mode consistency
    env = os.getenv('ENV')
    testing_mode = os.getenv('TESTING_MODE', 'false').lower() == 'true'
    mock_auth = os.getenv('MOCK_AUTH_ENABLED', 'false').lower() == 'true'
    
    if env == 'production' and (testing_mode or mock_auth):
        print("⚠️  WARNING: Production environment with testing features enabled!")
        print("   This could be a security risk.")
        return False
    
    if env == 'development' and not testing_mode:
        print("💡 INFO: Development environment without testing mode.")
    
    print("✅ Configuration validation passed!")
    return True

def main():
    """Main configuration script"""
    
    if len(sys.argv) < 2:
        print("Usage: python configure_env.py [testing|production|validate]")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == 'testing':
        setup_testing_environment()
        validate_configuration()
    elif mode == 'production':
        setup_production_environment()
        validate_configuration()
    elif mode == 'validate':
        validate_configuration()
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: testing, production, validate")
        sys.exit(1)

if __name__ == "__main__":
    main()
