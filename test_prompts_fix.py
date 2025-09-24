#!/usr/bin/env python3
"""
Quick test script to validate prompts endpoints with proper payloads
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# Test data
test_prompt_data = {
    "title": "Test Email Assistant",
    "body": "You are a helpful assistant. Write a {type} email about {topic}.",
    "role": "assistant",
    "category": "email",
    "tags": ["email", "assistant"],
    "is_public": False
}

test_drive_data = {
    "prompt_id": "test-123",
    "inputs": {
        "type": "professional",
        "topic": "project updates"
    }
}

ai_remix_data = {
    "prompt_body": "Write an email about project updates",
    "style": "professional",
    "target_audience": "team members",
    "enhancement_level": "medium"
}

ai_architect_data = {
    "description": "Build a REST API for user management",
    "techStack": ["python", "fastapi", "mongodb"],
    "architectureStyle": "microservices"
}

def test_endpoints():
    print("🧪 Testing PromptForge API Endpoints...")
    
    # Get a valid auth token (mock development token)
    headers = {
        "Authorization": "Bearer mock-test-token",  # This should work in development
        "Content-Type": "application/json"
    }
    
    # Test 1: Create Prompt (should work with proper payload)
    print("\n1. Testing POST /prompts/ with valid payload...")
    try:
        response = requests.post(
            f"{BASE_URL}/prompts/",
            json=test_prompt_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   Success: Prompt created")
    except Exception as e:
        print(f"   Connection Error: {e}")
    
    # Test 2: Get Public Prompts (should work)
    print("\n2. Testing GET /prompts/public...")
    try:
        response = requests.get(f"{BASE_URL}/prompts/public")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data.get('data', {}).get('prompts', []))} public prompts")
    except Exception as e:
        print(f"   Connection Error: {e}")
    
    # Test 3: Test Drive (with proper payload)
    print("\n3. Testing POST /prompts/test-drive-by-id with proper payload...")
    try:
        response = requests.post(
            f"{BASE_URL}/prompts/test-drive-by-id",
            json=test_drive_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   Success: Test drive completed")
    except Exception as e:
        print(f"   Connection Error: {e}")
    
    # Test 4: AI Remix with correct format
    print("\n4. Testing POST /ai/remix-prompt with correct payload...")
    try:
        response = requests.post(
            f"{BASE_URL}/ai/remix-prompt",
            json=ai_remix_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   Success: Prompt remixed")
    except Exception as e:
        print(f"   Connection Error: {e}")
    
    # Test 5: AI Architect with correct format
    print("\n5. Testing POST /ai/architect-prompt with correct payload...")
    try:
        response = requests.post(
            f"{BASE_URL}/ai/architect-prompt",
            json=ai_architect_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
        else:
            print(f"   Success: Prompt architected")
    except Exception as e:
        print(f"   Connection Error: {e}")

if __name__ == "__main__":
    test_endpoints()
