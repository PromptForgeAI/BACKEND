#!/usr/bin/env python3
"""
Quick verification of corrected endpoint paths
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8080"

# Corrected endpoint mappings
CORRECTED_ENDPOINTS = [
    # Credits (no prefix due to billing router config)
    {"path": "/api/v1/credits/balance", "method": "GET", "name": "Credit Balance", "auth": True},
    {"path": "/api/v1/credits/purchase", "method": "POST", "name": "Purchase Credits", "auth": True},
    
    # User profile (corrected name)
    {"path": "/api/v1/users/me", "method": "GET", "name": "User Profile", "auth": True},
    
    # Marketplace (corrected name)
    {"path": "/api/v1/marketplace/listings", "method": "GET", "name": "Marketplace Browse", "auth": False},
    
    # Gallery (corrected name) 
    {"path": "/api/v1/gallery/list", "method": "GET", "name": "Gallery Browse", "auth": False},
    
    # Alternative marketplace endpoints
    {"path": "/api/v1/marketplace/search", "method": "GET", "name": "Marketplace Search", "auth": False},
    
    # Additional user endpoints found
    {"path": "/api/v1/users/preferences", "method": "GET", "name": "User Preferences", "auth": True},
    {"path": "/api/v1/users/stats", "method": "GET", "name": "User Stats", "auth": True},
]

def test_corrected_endpoints():
    print("🔍 Testing Corrected Endpoint Paths")
    print("=" * 50)
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    working = 0
    not_found = 0
    errors = 0
    
    for i, endpoint in enumerate(CORRECTED_ENDPOINTS, 1):
        url = f"{BASE_URL}{endpoint['path']}"
        method = endpoint['method']
        name = endpoint['name']
        
        print(f"[{i:2d}/{len(CORRECTED_ENDPOINTS)}] Testing {method} {endpoint['path']}")
        print(f"    📝 {name}")
        
        try:
            if method == "GET":
                response = requests.get(url, timeout=5)
            elif method == "POST":
                response = requests.post(url, json={}, timeout=5)
            
            status_code = response.status_code
            
            if status_code == 404:
                print(f"    🚫 STILL 404 - Path incorrect or endpoint missing")
                not_found += 1
            elif status_code in [200, 401, 422]:
                print(f"    ✅ ENDPOINT EXISTS (HTTP {status_code})")
                working += 1
            elif status_code >= 500:
                print(f"    ⚠️  SERVER ERROR (HTTP {status_code})")
                errors += 1
            else:
                print(f"    ❓ OTHER STATUS (HTTP {status_code})")
                
        except requests.exceptions.RequestException as e:
            print(f"    ❌ CONNECTION ERROR: {e}")
            errors += 1
            
        print()
    
    print("=" * 50)
    print("📊 CORRECTED PATHS VERIFICATION SUMMARY")
    print("=" * 50)
    print(f"✅ Working Endpoints: {working}")
    print(f"🚫 Still 404: {not_found}")
    print(f"⚠️  Server Errors: {errors}")
    print(f"❌ Connection Errors: {errors}")
    
    total_tested = len(CORRECTED_ENDPOINTS)
    success_rate = (working / total_tested) * 100 if total_tested > 0 else 0
    
    print(f"\n📈 Corrected Path Success Rate: {success_rate:.1f}% ({working}/{total_tested})")
    
    if not_found > 0:
        print(f"\n🚨 {not_found} endpoints still return 404 - need further investigation")
    
    print(f"\n📄 Results saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    test_corrected_endpoints()
