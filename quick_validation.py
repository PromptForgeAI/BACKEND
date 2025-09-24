#!/usr/bin/env python3
"""
🚀 PROMPTFORGE.AI - Quick Validation Test
Tests the critical fixes we just implemented
"""

import requests
import json
import time
import os
from datetime import datetime

# Configure environment for testing
os.environ['ENV'] = 'development'
os.environ['TESTING_MODE'] = 'true'
os.environ['MOCK_AUTH_ENABLED'] = 'true'

class QuickValidationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': 'Bearer mock-test-token',
            'User-Agent': 'PromptForge-QuickValidation/1.0'
        })
        
    def test_endpoint(self, method: str, endpoint: str, data=None, expected_status=200):
        """Test an endpoint and return results"""
        start_time = time.time()
        
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method.upper() == "GET":
                response = self.session.get(url, params=data)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url)
                
            response_time = (time.time() - start_time) * 1000
            success = response.status_code == expected_status
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
                
            result = {
                "endpoint": endpoint,
                "method": method,
                "status_code": response.status_code,
                "expected_status": expected_status,
                "success": success,
                "response_time_ms": int(response_time),
                "response_data": response_data
            }
            
            status_icon = "✅" if success else "❌"
            print(f"{status_icon} {method} {endpoint} [{response.status_code}] - {response_time:.0f}ms")
            
            if not success:
                print(f"   Expected: {expected_status}, Got: {response.status_code}")
                if response_data.get("detail"):
                    print(f"   Error: {response_data['detail']}")
                    
            return result
            
        except Exception as e:
            result = {
                "endpoint": endpoint,
                "method": method,
                "status_code": 0,
                "expected_status": expected_status,
                "success": False,
                "response_time_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }
            print(f"❌ {method} {endpoint} - FAILED: {str(e)}")
            return result

    def run_validation_tests(self):
        """Run the critical validation tests"""
        
        print("🚀 PROMPTFORGE.AI - QUICK VALIDATION TEST")
        print("=" * 60)
        print(f"🔗 Base URL: {self.base_url}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🎯 Testing critical fixes...")
        print()
        
        results = []
        
        # Test 1: Health check
        print("1️⃣ HEALTH CHECK")
        result = self.test_endpoint("GET", "/api/v1/health", expected_status=200)
        results.append(result)
        print()
        
        # Test 2: Authentication with mock token
        print("2️⃣ MOCK AUTHENTICATION")
        result = self.test_endpoint("GET", "/api/v1/users/me", expected_status=200)
        results.append(result)
        print()
        
        # Test 3: Prompt creation with correct field names
        print("3️⃣ PROMPT CREATION (Fixed Schema)")
        prompt_data = {
            "title": "Test Validation Prompt",
            "body": "Write a professional email about {topic}",  # ✅ Correct field name
            "role": "assistant"
        }
        result = self.test_endpoint("POST", "/api/v1/prompts/prompts/", prompt_data, expected_status=200)
        results.append(result)
        print()
        
        # Test 4: AI Remix with correct field names  
        print("4️⃣ AI REMIX (Fixed Schema)")
        remix_data = {
            "prompt_body": "Write an email"  # ✅ Correct field name
        }
        result = self.test_endpoint("POST", "/api/v1/ai/remix-prompt", remix_data, expected_status=200)
        results.append(result)
        print()
        
        # Test 5: AI Architect with correct field names
        print("5️⃣ AI ARCHITECT (Fixed Schema)")
        architect_data = {
            "description": "Create a web application",  # ✅ Correct field name
            "techStack": ["React", "Node.js"],  # ✅ Use camelCase as expected by API
            "architectureStyle": "microservices"  # ✅ Use camelCase as expected by API
        }
        result = self.test_endpoint("POST", "/api/v1/ai/architect-prompt", architect_data, expected_status=200)
        results.append(result)
        print()
        
        # Test 6: Public prompts (empty state handling)
        print("6️⃣ PUBLIC PROMPTS (Empty State)")
        result = self.test_endpoint("GET", "/api/v1/prompts/prompts/public", expected_status=200)
        results.append(result)
        print()
        
        # Test 7: Bulk action with supported action
        print("7️⃣ BULK ACTIONS (Supported Actions)")
        bulk_data = {
            "prompt_ids": ["test-id-1", "test-id-2"],
            "action": "tag",  # ✅ Now supported
            "action_data": {"tags": ["test", "validation"]}
        }
        result = self.test_endpoint("POST", "/api/v1/prompts/prompts/bulk-action", bulk_data, expected_status=200)
        results.append(result)
        print()
        
        # Test 8: Packaging (should have proper imports now)
        print("8️⃣ PACKAGING (Fixed Imports)")
        # Try debug endpoint first to test if module loads properly
        result = self.test_endpoint("GET", "/api/v1/packaging/debug", expected_status=200)
        results.append(result)
        print()
        
        # Generate summary
        total_tests = len(results)
        passed_tests = len([r for r in results if r["success"]])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print("=" * 60)
        print("📊 VALIDATION RESULTS SUMMARY")
        print("=" * 60)
        print(f"🎯 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in results:
                if not result["success"]:
                    print(f"   • {result['method']} {result['endpoint']} [{result['status_code']}]")
                    if result.get("error"):
                        print(f"     Error: {result['error']}")
                    elif result.get("response_data", {}).get("detail"):
                        print(f"     Detail: {result['response_data']['detail']}")
        
        print(f"\n🎉 VALIDATION {'COMPLETE' if success_rate >= 80 else 'NEEDS WORK'}!")
        
        if success_rate >= 80:
            print("🚀 Most critical fixes are working! Ready for comprehensive testing.")
        else:
            print("⚠️  Some critical issues remain. Check the failed tests above.")
            
        return results, success_rate

def main():
    """Run the quick validation"""
    tester = QuickValidationTester()
    results, success_rate = tester.run_validation_tests()
    
    # Exit with appropriate code
    exit_code = 0 if success_rate >= 80 else 1
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
