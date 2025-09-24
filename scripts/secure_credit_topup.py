#!/usr/bin/env python3
"""
Secure Credit Management for Test User
Properly tops up test user credits in database instead of using mock bypasses
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

async def top_up_test_user_credits():
    """
    Securely add credits to test user in database
    """
    # Connect to database
    mongo_uri = os.getenv("MONGODB_URI", "mongodb+srv://shivadeepakdev_db_user:IazHjfnuOfLEnw40@testpfai.uoiqsww.mongodb.net/?retryWrites=true&w=majority&appName=testpfai")
    db_name = os.getenv("MONGODB_DATABASE", "promptforge")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    
    try:
        # Update test user credits in database
        result = await db.users.update_one(
            {"_id": "test-user-123"},
            {
                "$set": {
                    "credits.balance": 10000,  # Give substantial testing credits
                    "credits.total_purchased": 10000,
                    "credits.last_purchase_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            print("✅ Test user credits updated successfully")
            print("   Balance: 10,000 credits")
            print("   User ID: test-user-123")
        else:
            print("❌ Failed to update test user credits")
            print("   User may not exist or no changes needed")
            
        # Verify the update
        user = await db.users.find_one({"_id": "test-user-123"})
        if user:
            credits = user.get("credits", {})
            print(f"📊 Current credits: {credits.get('balance', 0)}")
        
    except Exception as e:
        print(f"❌ Error updating credits: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    print("🔧 Secure Test User Credit Top-up")
    print("=" * 50)
    asyncio.run(top_up_test_user_credits())
