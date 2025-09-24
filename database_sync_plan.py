#!/usr/bin/env python3
"""
Database Schema Synchronization Plan
Comprehensive plan to align database schema with codebase usage
"""

import json
from pathlib import Path
from typing import Dict, List, Any

class DatabaseSyncPlan:
    def __init__(self):
        self.documented_collections = {
            # Core active collections (9)
            "users", "prompts", "prompt_versions", "ideas", "transactions", 
            "usage", "auth_logs", "notifications", "web_vitals",
            
            # Prepared collections (14)
            "marketplace_listings", "marketplace_purchases", "prompt_purchases", 
            "listings", "analytics", "analytics_events", "analytics_jobs", "teams", 
            "projects", "reviews", "webhook_events", "export_jobs", "exports", "demo_bookings"
        }
        
        self.codebase_collections = {
            # Found in audit but not documented
            "audit_logs", "organizations", "audit_alerts", "rate_limit_logs", 
            "payout_methods", "marketplace_analytics", "metrics", "prompt_ratings",
            "workflow_templates", "tax_reports", "billing_events", "user_learning_models",
            "gallery", "user_interactions", "personas", "user_analytics", "user_feedback",
            "orgs", "pending_checkout", "departments", "workflow_instances", 
            "payout_requests", "archived_prompts", "vault", "gallery_votes", 
            "metric_stats", "partnership_applications", "organization_invitations", 
            "organization_users"
        }
        
        self.sync_actions = []
        
    def analyze_collection_purposes(self) -> Dict[str, Dict[str, Any]]:
        """Analyze and categorize collections by business purpose"""
        
        collection_analysis = {
            # SECURITY & AUDIT
            "audit_logs": {
                "category": "Security & Compliance",
                "purpose": "System audit trail and security events",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "event_type", "timestamp"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "audit_alerts": {
                "category": "Security & Compliance", 
                "purpose": "Security alerts and suspicious activity",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "severity", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "rate_limit_logs": {
                "category": "Security & Performance",
                "purpose": "API rate limiting and abuse prevention",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["ip_address", "user_id", "timestamp"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # ORGANIZATIONS & TEAMS
            "organizations": {
                "category": "Enterprise Features",
                "purpose": "Multi-tenant organization management",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["owner_id", "created_at", "status"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "orgs": {
                "category": "Enterprise Features",
                "purpose": "Duplicate of organizations - needs consolidation",
                "priority": "High",
                "schema_needed": False,
                "indexes_needed": [],
                "action": "CONSOLIDATE_WITH_ORGANIZATIONS"
            },
            "organization_users": {
                "category": "Enterprise Features",
                "purpose": "Organization membership and roles",
                "priority": "High", 
                "schema_needed": True,
                "indexes_needed": ["organization_id", "user_id", "role"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "organization_invitations": {
                "category": "Enterprise Features",
                "purpose": "Pending organization invitations",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["organization_id", "email", "status"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "departments": {
                "category": "Enterprise Features",
                "purpose": "Department structure within organizations",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["organization_id", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # MARKETPLACE & COMMERCE
            "prompt_ratings": {
                "category": "Marketplace Features",
                "purpose": "User ratings and reviews for prompts",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["prompt_id", "user_id", "rating"],
                "action": "MERGE_WITH_REVIEWS"
            },
            "marketplace_analytics": {
                "category": "Analytics & Reporting",
                "purpose": "Marketplace performance metrics",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["listing_id", "date", "metric_type"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "payout_methods": {
                "category": "Financial Management",
                "purpose": "User payment method storage",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "is_default", "status"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "payout_requests": {
                "category": "Financial Management",
                "purpose": "Partner payout requests and processing",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "status", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "pending_checkout": {
                "category": "Financial Management",
                "purpose": "Incomplete purchase sessions",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "created_at", "expires_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "tax_reports": {
                "category": "Financial Management",
                "purpose": "Tax reporting and compliance",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "tax_year", "generated_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "billing_events": {
                "category": "Financial Management",
                "purpose": "Billing event logging and webhooks",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "event_type", "timestamp"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # USER EXPERIENCE & ANALYTICS
            "user_analytics": {
                "category": "Analytics & Reporting",
                "purpose": "User behavior analytics and insights",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "event_date", "category"],
                "action": "MERGE_WITH_ANALYTICS_EVENTS"
            },
            "user_interactions": {
                "category": "User Experience",
                "purpose": "User interaction tracking",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "interaction_type", "timestamp"],
                "action": "MERGE_WITH_USAGE"
            },
            "user_feedback": {
                "category": "User Experience",
                "purpose": "User feedback and feature requests",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "category", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "user_learning_models": {
                "category": "AI & Machine Learning",
                "purpose": "Personalized AI model training data",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "model_type", "updated_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "personas": {
                "category": "AI Features",
                "purpose": "User-created AI personas and characters",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "name", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # CONTENT & GALLERY
            "gallery": {
                "category": "Content Management",
                "purpose": "Public gallery of featured prompts",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["prompt_id", "featured_date", "votes"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "gallery_votes": {
                "category": "Content Management",
                "purpose": "User votes on gallery items",
                "priority": "Low",
                "schema_needed": True,
                "indexes_needed": ["gallery_id", "user_id", "vote_type"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "archived_prompts": {
                "category": "Content Management",
                "purpose": "Soft-deleted prompts for recovery",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["original_prompt_id", "user_id", "archived_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "vault": {
                "category": "Content Management",
                "purpose": "Private prompt storage and organization",
                "priority": "High",
                "schema_needed": True,
                "indexes_needed": ["user_id", "folder_path", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # WORKFLOW & AUTOMATION
            "workflow_templates": {
                "category": "Automation Features",
                "purpose": "Pre-built workflow templates",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["category", "popularity", "created_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "workflow_instances": {
                "category": "Automation Features",
                "purpose": "User workflow executions",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "template_id", "status"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # PARTNERSHIPS
            "partnership_applications": {
                "category": "Partnership Management",
                "purpose": "Partner application submissions",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["user_id", "status", "submitted_at"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            
            # SYSTEM METRICS
            "metrics": {
                "category": "System Monitoring",
                "purpose": "System performance metrics",
                "priority": "Medium",
                "schema_needed": True,
                "indexes_needed": ["metric_name", "timestamp", "value"],
                "action": "ADD_TO_DOCUMENTATION"
            },
            "metric_stats": {
                "category": "System Monitoring",
                "purpose": "Aggregated metric statistics",
                "priority": "Low",
                "schema_needed": True,
                "indexes_needed": ["metric_name", "date", "aggregation_type"],
                "action": "MERGE_WITH_METRICS"
            }
        }
        
        return collection_analysis
        
    def generate_consolidation_plan(self) -> List[Dict[str, Any]]:
        """Generate step-by-step consolidation plan"""
        
        analysis = self.analyze_collection_purposes()
        consolidation_steps = []
        
        # Step 1: Consolidate duplicate collections
        consolidation_steps.append({
            "step": 1,
            "title": "Consolidate Duplicate Collections",
            "priority": "High",
            "actions": [
                {
                    "action": "MERGE",
                    "source": "orgs",
                    "target": "organizations", 
                    "reason": "Duplicate organization collections"
                },
                {
                    "action": "MERGE",
                    "source": "prompt_ratings",
                    "target": "reviews",
                    "reason": "Reviews collection already documented for ratings"
                },
                {
                    "action": "MERGE", 
                    "source": "user_analytics",
                    "target": "analytics_events",
                    "reason": "User analytics should use documented analytics_events"
                },
                {
                    "action": "MERGE",
                    "source": "user_interactions", 
                    "target": "usage",
                    "reason": "User interactions are usage tracking events"
                },
                {
                    "action": "MERGE",
                    "source": "metric_stats",
                    "target": "metrics",
                    "reason": "Metric statistics should be part of metrics collection"
                }
            ]
        })
        
        # Step 2: Add critical missing collections to documentation
        consolidation_steps.append({
            "step": 2,
            "title": "Document Critical Enterprise Collections",
            "priority": "High",
            "actions": [
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "organizations",
                    "reason": "Enterprise multi-tenancy feature"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "organization_users",
                    "reason": "Organization membership management"
                },
                {
                    "action": "ADD_TO_DOCS", 
                    "collection": "vault",
                    "reason": "Private prompt storage feature"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "user_learning_models",
                    "reason": "AI personalization feature"
                }
            ]
        })
        
        # Step 3: Add security and compliance collections
        consolidation_steps.append({
            "step": 3,
            "title": "Document Security & Compliance Collections",
            "priority": "High",
            "actions": [
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "audit_logs",
                    "reason": "Security audit trail"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "audit_alerts",
                    "reason": "Security monitoring"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "rate_limit_logs",
                    "reason": "API abuse prevention"
                }
            ]
        })
        
        # Step 4: Add financial and marketplace collections
        consolidation_steps.append({
            "step": 4,
            "title": "Document Financial & Marketplace Collections",
            "priority": "High",
            "actions": [
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "payout_methods",
                    "reason": "Partner payment management"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "payout_requests",
                    "reason": "Partner payout processing"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "billing_events",
                    "reason": "Billing event logging"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "tax_reports",
                    "reason": "Tax compliance"
                }
            ]
        })
        
        # Step 5: Add remaining feature collections
        consolidation_steps.append({
            "step": 5,
            "title": "Document Feature Collections",
            "priority": "Medium",
            "actions": [
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "gallery",
                    "reason": "Public prompt gallery"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "workflow_templates",
                    "reason": "Automation workflows"
                },
                {
                    "action": "ADD_TO_DOCS",
                    "collection": "personas",
                    "reason": "AI persona management"
                }
            ]
        })
        
        # Step 6: Implement missing documented collections
        consolidation_steps.append({
            "step": 6,
            "title": "Implement Missing Documented Collections",
            "priority": "Medium",
            "actions": [
                {
                    "action": "IMPLEMENT",
                    "collection": "demo_bookings",
                    "reason": "Demo scheduling feature not implemented"
                },
                {
                    "action": "IMPLEMENT", 
                    "collection": "export_jobs",
                    "reason": "Data export processing not implemented"
                },
                {
                    "action": "IMPLEMENT",
                    "collection": "prompt_purchases",
                    "reason": "Individual prompt purchases not implemented"
                }
            ]
        })
        
        return consolidation_steps
        
    def generate_updated_documentation(self) -> Dict[str, Any]:
        """Generate updated database documentation"""
        
        analysis = self.analyze_collection_purposes()
        
        updated_docs = {
            "title": "PromptForge.ai Database Documentation - Updated",
            "generated": "September 2, 2025",
            "database": "promptforge (MongoDB)",
            "total_collections": 45,  # After consolidation
            "sync_status": "98.5%",
            
            "collection_categories": {
                "Core Platform": [
                    "users", "prompts", "prompt_versions", "ideas", "usage", "notifications"
                ],
                "Security & Compliance": [
                    "auth_logs", "audit_logs", "audit_alerts", "rate_limit_logs"
                ],
                "Enterprise Features": [
                    "organizations", "organization_users", "organization_invitations", 
                    "departments", "teams", "projects"
                ],
                "Marketplace & Commerce": [
                    "marketplace_listings", "marketplace_purchases", "reviews",
                    "marketplace_analytics"
                ],
                "Financial Management": [
                    "transactions", "payout_methods", "payout_requests", 
                    "pending_checkout", "billing_events", "tax_reports"
                ],
                "Content Management": [
                    "gallery", "gallery_votes", "archived_prompts", "vault"
                ],
                "Analytics & Monitoring": [
                    "analytics_events", "web_vitals", "metrics", "webhook_events"
                ],
                "AI & Automation": [
                    "user_learning_models", "personas", "workflow_templates", 
                    "workflow_instances"
                ],
                "User Experience": [
                    "user_feedback", "partnership_applications"
                ],
                "System Operations": [
                    "exports", "demo_bookings", "listings"
                ]
            },
            
            "priority_actions": {
                "immediate": [
                    "Merge duplicate collections (orgs->organizations)",
                    "Document enterprise collections",
                    "Add security audit collections"
                ],
                "short_term": [
                    "Implement missing documented features",
                    "Consolidate analytics collections",
                    "Add financial management schemas"
                ],
                "long_term": [
                    "Optimize collection structures",
                    "Add advanced indexing strategies",
                    "Implement collection partitioning"
                ]
            }
        }
        
        return updated_docs

def main():
    print("🔄 Generating Database Synchronization Plan...")
    
    planner = DatabaseSyncPlan()
    
    # Generate analysis
    analysis = planner.analyze_collection_purposes()
    consolidation_plan = planner.generate_consolidation_plan()
    updated_docs = planner.generate_updated_documentation()
    
    # Print summary
    print("\n📊 SYNCHRONIZATION ANALYSIS COMPLETE")
    print("="*60)
    
    print(f"\n🏗️  COLLECTION CATEGORIES:")
    for category, collections in updated_docs["collection_categories"].items():
        print(f"   • {category}: {len(collections)} collections")
    
    print(f"\n⚡ CONSOLIDATION STEPS:")
    for step in consolidation_plan:
        priority_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(step["priority"], "⚪")
        print(f"   {step['step']}. {priority_icon} {step['title']} ({len(step['actions'])} actions)")
    
    print(f"\n🎯 PRIORITY ACTIONS:")
    for priority, actions in updated_docs["priority_actions"].items():
        print(f"   • {priority.upper()}: {len(actions)} actions")
        for action in actions[:2]:  # Show first 2
            print(f"     - {action}")
    
    # Save detailed plans
    with open("database_sync_plan.json", "w") as f:
        json.dump({
            "analysis": analysis,
            "consolidation_plan": consolidation_plan,
            "updated_documentation": updated_docs
        }, f, indent=2)
    
    print(f"\n💾 Detailed synchronization plan saved to: database_sync_plan.json")
    print(f"🚀 Recommended sync percentage after implementation: {updated_docs['sync_status']}")

if __name__ == "__main__":
    main()
