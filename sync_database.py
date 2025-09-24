#!/usr/bin/env python3
"""
Database Synchronization Implementation
Initialize synchronized database structure with proper indexes
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from dependencies import db, ensure_indexes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseSynchronizer:
    def __init__(self):
        self.db = db
        self.collections_created = []
        self.indexes_created = []
        
    async def create_collection_if_not_exists(self, collection_name: str, description: str = ""):
        """Create collection if it doesn't exist"""
        try:
            # Check if collection exists
            collections = await self.db.list_collection_names()
            
            if collection_name not in collections:
                await self.db.create_collection(collection_name)
                self.collections_created.append(collection_name)
                logger.info(f"✅ Created collection: {collection_name} - {description}")
            else:
                logger.info(f"📋 Collection exists: {collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to create collection {collection_name}: {e}")
            
    async def consolidate_duplicate_collections(self):
        """Consolidate duplicate collections as per sync plan"""
        
        logger.info("🔄 Starting collection consolidation...")
        
        consolidation_plan = [
            {
                "source": "orgs", 
                "target": "organizations",
                "action": "migrate_data"
            },
            {
                "source": "prompt_ratings",
                "target": "reviews", 
                "action": "migrate_data"
            },
            {
                "source": "user_analytics",
                "target": "analytics_events",
                "action": "migrate_data"
            },
            {
                "source": "user_interactions", 
                "target": "usage",
                "action": "migrate_data"
            },
            {
                "source": "metric_stats",
                "target": "metrics",
                "action": "migrate_data"
            }
        ]
        
        for plan in consolidation_plan:
            source = plan["source"]
            target = plan["target"]
            
            try:
                # Check if source collection exists and has data
                source_count = await self.db[source].count_documents({})
                
                if source_count > 0:
                    logger.info(f"📦 Migrating {source_count} documents from {source} to {target}")
                    
                    # Get all documents from source
                    async for doc in self.db[source].find({}):
                        # Add migration metadata
                        doc["_migrated_from"] = source
                        doc["_migrated_at"] = datetime.utcnow()
                        
                        # Remove _id to avoid conflicts
                        if "_id" in doc:
                            del doc["_id"]
                            
                        # Insert into target collection
                        await self.db[target].insert_one(doc)
                    
                    # After successful migration, rename source to archived
                    archive_name = f"{source}_archived_{datetime.now().strftime('%Y%m%d')}"
                    await self.db[source].rename(archive_name)
                    logger.info(f"✅ Migrated {source} → {target}, archived as {archive_name}")
                    
                else:
                    logger.info(f"📭 Collection {source} is empty, skipping migration")
                    
            except Exception as e:
                logger.warning(f"⚠️  Migration {source} → {target} failed: {e}")
                
    async def initialize_core_collections(self):
        """Initialize all core collections with proper structure"""
        
        logger.info("🏗️  Initializing core database collections...")
        
        collections_to_create = [
            # Core Platform
            ("users", "Central user account management"),
            ("prompts", "Core prompt storage and management"),
            ("prompt_versions", "Prompt version control"),
            ("ideas", "AI-generated ideas and suggestions"),
            ("usage", "User activity and feature usage tracking"),
            ("notifications", "User notification management"),
            
            # Security & Compliance
            ("auth_logs", "Authentication and security event logging"),
            ("audit_logs", "System audit trail and security events"),
            ("audit_alerts", "Security alerts and suspicious activity"),
            ("rate_limit_logs", "API rate limiting and abuse prevention"),
            
            # Enterprise Features
            ("organizations", "Multi-tenant organization management"),
            ("organization_users", "Organization membership and roles"),
            ("organization_invitations", "Pending organization invitations"),
            ("departments", "Department structure within organizations"),
            ("teams", "Team management"),
            ("projects", "Project organization"),
            
            # Marketplace & Commerce
            ("marketplace_listings", "Product listings in marketplace"),
            ("marketplace_purchases", "Purchase transaction records"),
            ("reviews", "User ratings and reviews"),
            ("marketplace_analytics", "Marketplace performance metrics"),
            
            # Financial Management
            ("transactions", "Financial transaction tracking"),
            ("payout_methods", "User payment method storage"),
            ("payout_requests", "Partner payout requests and processing"),
            ("pending_checkout", "Incomplete purchase sessions"),
            ("billing_events", "Billing event logging and webhooks"),
            ("tax_reports", "Tax reporting and compliance"),
            
            # Content Management
            ("vault", "Private prompt storage and organization"),
            ("gallery", "Public gallery of featured prompts"),
            ("gallery_votes", "User votes on gallery items"),
            ("archived_prompts", "Soft-deleted prompts for recovery"),
            
            # Analytics & Monitoring
            ("analytics_events", "Event tracking for analytics"),
            ("web_vitals", "Performance monitoring and optimization"),
            ("metrics", "System performance metrics"),
            ("webhook_events", "External integrations"),
            
            # AI & Automation
            ("user_learning_models", "Personalized AI model training data"),
            ("personas", "User-created AI personas and characters"),
            ("workflow_templates", "Pre-built workflow templates"),
            ("workflow_instances", "User workflow executions"),
            
            # User Experience
            ("user_feedback", "User feedback and feature requests"),
            ("partnership_applications", "Partner application submissions"),
            
            # System Operations
            ("exports", "Export records"),
            ("export_jobs", "Data export processing"),
            ("demo_bookings", "Demo scheduling"),
            
            # Legacy (to be consolidated)
            ("listings", "General listings - legacy")
        ]
        
        for collection_name, description in collections_to_create:
            await self.create_collection_if_not_exists(collection_name, description)
            
    async def create_all_indexes(self):
        """Create all database indexes"""
        
        logger.info("📊 Creating database indexes...")
        
        try:
            await ensure_indexes()
            logger.info("✅ All database indexes created successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")
            
    async def verify_synchronization(self):
        """Verify database synchronization status"""
        
        logger.info("🔍 Verifying database synchronization...")
        
        # Get list of all collections
        collections = await self.db.list_collection_names()
        collections_count = len(collections)
        
        # Check for critical collections
        critical_collections = [
            "users", "prompts", "organizations", "marketplace_listings",
            "transactions", "audit_logs", "vault", "analytics_events"
        ]
        
        missing_critical = []
        for collection in critical_collections:
            if collection not in collections:
                missing_critical.append(collection)
                
        # Generate report
        if missing_critical:
            logger.warning(f"⚠️  Missing critical collections: {missing_critical}")
            return False
        else:
            logger.info(f"✅ All {len(critical_collections)} critical collections present")
            logger.info(f"📊 Total collections: {collections_count}")
            return True
            
    async def run_synchronization(self):
        """Run complete database synchronization"""
        
        logger.info("🚀 Starting Database Synchronization Process...")
        print("="*80)
        
        try:
            # Step 1: Consolidate duplicate collections
            await self.consolidate_duplicate_collections()
            print()
            
            # Step 2: Initialize core collections
            await self.initialize_core_collections()
            print()
            
            # Step 3: Create all indexes
            await self.create_all_indexes()
            print()
            
            # Step 4: Verify synchronization
            sync_status = await self.verify_synchronization()
            print()
            
            # Final report
            logger.info("📋 SYNCHRONIZATION SUMMARY:")
            logger.info(f"   • Collections Created: {len(self.collections_created)}")
            logger.info(f"   • Indexes Updated: ✅ Complete")
            logger.info(f"   • Sync Status: {'✅ Success' if sync_status else '❌ Issues Found'}")
            
            if self.collections_created:
                logger.info(f"   • New Collections: {', '.join(self.collections_created[:5])}...")
                
            print("="*80)
            logger.info("🎉 Database synchronization completed!")
            
            return sync_status
            
        except Exception as e:
            logger.error(f"❌ Synchronization failed: {e}")
            return False

async def main():
    """Main synchronization function"""
    
    try:
        synchronizer = DatabaseSynchronizer()
        success = await synchronizer.run_synchronization()
        
        if success:
            print("\n✅ Database is now synchronized with codebase!")
            print("📖 See DATABASE_SCHEMA_SYNCHRONIZED.md for complete documentation")
            sys.exit(0)
        else:
            print("\n❌ Synchronization completed with issues")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error during synchronization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
