#!/usr/bin/env python3
"""
Quick fix verification test
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_fixes():
    headers = {
        "Authorization": "Bearer mock-test-token",
        "Content-Type": "application/json"
    }
    
    print("🔧 Testing Critical Fixes...")
    
    # Test 1: Marketplace List Prompt (500 -> should be fixed)
    print("\n1. Testing marketplace list-prompt (was 500 error)...")
    marketplace_data = {
        "prompt_id": "batch-test-prompt-123",
        "price_credits": 10,
        "description": "Test listing",
        "tags": ["test"]
    }
    try:
        response = requests.post(
            f"{BASE_URL}/marketplace/list-prompt",
            json=marketplace_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   ✅ Fixed! Marketplace listing works")
    except Exception as e:
        print(f"   Connection Error: {e}")
    
    # Test 2: AI Architect (402 -> should be fixed with more credits)
    print("\n2. Testing AI architect (was 402 insufficient credits)...")
    architect_data = {
        "description": "Build a REST API",
        "techStack": ["python", "fastapi"],
        "architectureStyle": "microservices"
    }
    try:
        response = requests.post(
            f"{BASE_URL}/ai/architect-prompt",
            json=architect_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   ✅ Fixed! AI Architect works")
    except Exception as e:
        print(f"   Connection Error: {e}")
    
    # Test 3: Generate Enhanced Prompt (422 -> should be fixed with correct format)
    print("\n3. Testing generate enhanced prompt (was 422 validation error)...")
    enhanced_data = {
        "prompt_a": "Help me write emails",
        "prompt_b": "Make it professional and engaging"
    }
    try:
        response = requests.post(
            f"{BASE_URL}/ai/generate-enhanced-prompt",
            json=enhanced_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   ✅ Fixed! Enhanced prompt generation works")
    except Exception as e:
        print(f"   Connection Error: {e}")

if __name__ == "__main__":
    test_fixes()
