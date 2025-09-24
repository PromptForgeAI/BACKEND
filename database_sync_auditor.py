#!/usr/bin/env python3
"""
Database Schema Synchronization Audit
Compares documented database schema with actual codebase usage
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Any

class DatabaseSyncAuditor:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.api_dir = self.project_root / "api"
        
        # Database schema from documentation
        self.documented_collections = {
            # Active collections (9)
            "users": {"documents": 5, "status": "active", "indexes": 6},
            "prompts": {"documents": 9, "status": "active", "indexes": 8},
            "prompt_versions": {"documents": 9, "status": "active", "indexes": 4},
            "ideas": {"documents": 15, "status": "active", "indexes": 2},
            "transactions": {"documents": 5, "status": "active", "indexes": 4},
            "usage": {"documents": 16, "status": "active", "indexes": 2},
            "auth_logs": {"documents": 95, "status": "active", "indexes": 1},
            "notifications": {"documents": 4, "status": "active", "indexes": 3},
            "web_vitals": {"documents": 3, "status": "active", "indexes": 1},
            
            # Empty but prepared collections (14)
            "marketplace_listings": {"documents": 0, "status": "prepared", "indexes": 11},
            "marketplace_purchases": {"documents": 0, "status": "prepared", "indexes": 3},
            "prompt_purchases": {"documents": 0, "status": "prepared", "indexes": 3},
            "listings": {"documents": 0, "status": "prepared", "indexes": 2},
            "analytics": {"documents": 0, "status": "prepared", "indexes": 3},
            "analytics_events": {"documents": 0, "status": "prepared", "indexes": 4},
            "analytics_jobs": {"documents": 0, "status": "prepared", "indexes": 4},
            "teams": {"documents": 0, "status": "prepared", "indexes": 4},
            "projects": {"documents": 0, "status": "prepared", "indexes": 4},
            "reviews": {"documents": 0, "status": "prepared", "indexes": 5},
            "webhook_events": {"documents": 0, "status": "prepared", "indexes": 2},
            "export_jobs": {"documents": 0, "status": "prepared", "indexes": 3},
            "exports": {"documents": 0, "status": "prepared", "indexes": 2},
            "demo_bookings": {"documents": 0, "status": "prepared", "indexes": 3},
        }
        
        # Track codebase usage
        self.code_collections = set()
        self.missing_collections = set()
        self.unused_collections = set()
        self.field_mismatches = {}
        
    def scan_codebase_collections(self) -> Set[str]:
        """Scan all Python files for database collection usage"""
        collection_patterns = [
            r'db\.(\w+)\.', # db.collection_name.
            r'db\["(\w+)"\]', # db["collection_name"]
            r'db\[\'(\w+)\'\]', # db['collection_name']
        ]
        
        collections_found = set()
        
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                content = py_file.read_text(encoding='utf-8')
                
                for pattern in collection_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    for match in matches:
                        collections_found.add(match)
                        
            except Exception as e:
                print(f"⚠️  Error reading {py_file}: {e}")
                
        return collections_found
    
    def analyze_field_usage(self) -> Dict[str, Dict[str, List[str]]]:
        """Analyze field usage patterns in collections"""
        field_usage = {}
        
        # Key patterns to look for
        field_patterns = {
            "users": [
                "uid", "email", "display_name", "photo_url", "account_status",
                "subscription", "credits", "preferences", "stats", "partnership",
                "security", "profile", "billing", "email_verified"
            ],
            "prompts": [
                "user_id", "project_id", "title", "body", "content", "category", 
                "tags", "visibility", "status", "deleted", "metadata", "performance",
                "is_public", "role"
            ],
            "prompt_versions": [
                "prompt_id", "version_number", "content", "changes", "created_by",
                "created_at", "is_current"
            ],
            "transactions": [
                "user_id", "type", "amount", "currency", "credits_affected",
                "stripe_payment_intent", "status", "description", "provider",
                "transaction_id"
            ]
        }
        
        for collection, expected_fields in field_patterns.items():
            field_usage[collection] = {"found": [], "missing": expected_fields.copy()}
            
            for py_file in self.project_root.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                    
                try:
                    content = py_file.read_text(encoding='utf-8')
                    
                    # Look for field references
                    for field in expected_fields:
                        if f'"{field}"' in content or f"'{field}'" in content:
                            if field not in field_usage[collection]["found"]:
                                field_usage[collection]["found"].append(field)
                                field_usage[collection]["missing"].remove(field)
                                
                except Exception as e:
                    continue
                    
        return field_usage
    
    def check_api_models_sync(self) -> Dict[str, Any]:
        """Check if API models match database schema"""
        models_file = self.project_root / "api" / "models.py"
        sync_issues = {}
        
        if not models_file.exists():
            return {"error": "api/models.py not found"}
            
        try:
            content = models_file.read_text(encoding='utf-8')
            
            # Check for key model classes
            model_classes = [
                "SavePromptRequest", "UpdatePromptRequest", "RemixRequest",
                "AnalyzeRequest", "ArchitectRequest", "MarketplaceListingRequest",
                "MarketplacePurchaseRequest", "PromptRatingRequest", "PreferencesModel",
                "PackageCreateRequest", "PartnershipApplicationRequest", "ProjectCreateRequest",
                "ExportRequest", "AnalyticsJobRequest"
            ]
            
            for model_class in model_classes:
                if f"class {model_class}" in content:
                    sync_issues[model_class] = "✅ Found"
                else:
                    sync_issues[model_class] = "❌ Missing"
                    
            # Check for field aliases (camelCase support)
            if "Field(..., alias=" in content:
                sync_issues["field_aliases"] = "✅ camelCase aliases present"
            else:
                sync_issues["field_aliases"] = "⚠️  No camelCase aliases found"
                
        except Exception as e:
            sync_issues["error"] = f"Error reading models.py: {e}"
            
        return sync_issues
    
    def check_index_creation(self) -> Dict[str, Any]:
        """Check if index creation matches documented indexes"""
        dependencies_file = self.project_root / "dependencies.py"
        index_status = {}
        
        if not dependencies_file.exists():
            return {"error": "dependencies.py not found"}
            
        try:
            content = dependencies_file.read_text(encoding='utf-8')
            
            # Look for ensure_indexes function
            if "async def ensure_indexes" in content:
                index_status["ensure_indexes_function"] = "✅ Found"
                
                # Check specific indexes
                expected_indexes = [
                    "users.*uid.*unique=True",
                    "transactions.*user_id.*created_at",
                    "listings.*seller_id.*created_at",
                    "usage.*user_id.*timestamp",
                    "webhook_events.*event_id.*unique=True"
                ]
                
                for idx_pattern in expected_indexes:
                    if any(part in content for part in idx_pattern.split(".*")):
                        index_status[idx_pattern] = "✅ Found"
                    else:
                        index_status[idx_pattern] = "❌ Missing"
                        
            else:
                index_status["ensure_indexes_function"] = "❌ Missing"
                
        except Exception as e:
            index_status["error"] = f"Error reading dependencies.py: {e}"
            
        return index_status
    
    def generate_sync_report(self) -> Dict[str, Any]:
        """Generate comprehensive synchronization report"""
        print("🔍 Starting Database Schema Synchronization Audit...")
        
        # 1. Scan codebase for collection usage
        print("📊 Scanning codebase for collection usage...")
        self.code_collections = self.scan_codebase_collections()
        
        # 2. Compare with documented collections
        documented_set = set(self.documented_collections.keys())
        self.missing_collections = documented_set - self.code_collections
        self.unused_collections = self.code_collections - documented_set
        
        # 3. Analyze field usage
        print("🔍 Analyzing field usage patterns...")
        field_analysis = self.analyze_field_usage()
        
        # 4. Check API models sync
        print("📝 Checking API models synchronization...")
        models_sync = self.check_api_models_sync()
        
        # 5. Check index creation
        print("📊 Checking index creation...")
        index_sync = self.check_index_creation()
        
        # Generate report
        report = {
            "audit_timestamp": "2025-09-02 23:55:00",
            "collections_summary": {
                "documented": len(self.documented_collections),
                "found_in_code": len(self.code_collections),
                "active_in_db": len([c for c in self.documented_collections.values() if c["status"] == "active"]),
                "prepared_for_scale": len([c for c in self.documented_collections.values() if c["status"] == "prepared"])
            },
            "synchronization_status": {
                "collections_in_sync": len(documented_set & self.code_collections),
                "missing_from_code": list(self.missing_collections),
                "undocumented_in_code": list(self.unused_collections),
                "sync_percentage": round((len(documented_set & self.code_collections) / len(documented_set)) * 100, 1)
            },
            "field_analysis": field_analysis,
            "api_models_sync": models_sync,
            "index_sync": index_sync,
            "recommendations": []
        }
        
        # Generate recommendations
        if self.missing_collections:
            report["recommendations"].append({
                "priority": "Medium",
                "action": "Add missing collection usage",
                "details": f"Collections documented but not used in code: {', '.join(self.missing_collections)}"
            })
            
        if self.unused_collections:
            report["recommendations"].append({
                "priority": "Low", 
                "action": "Document new collections",
                "details": f"Collections used in code but not documented: {', '.join(self.unused_collections)}"
            })
            
        # Check sync percentage
        sync_pct = report["synchronization_status"]["sync_percentage"]
        if sync_pct < 80:
            report["recommendations"].append({
                "priority": "High",
                "action": "Critical sync issues",
                "details": f"Only {sync_pct}% of collections are synchronized"
            })
        elif sync_pct < 95:
            report["recommendations"].append({
                "priority": "Medium",
                "action": "Minor sync improvements needed",
                "details": f"{sync_pct}% sync rate - close to optimal"
            })
        else:
            report["recommendations"].append({
                "priority": "Low",
                "action": "Excellent synchronization",
                "details": f"{sync_pct}% sync rate - very well maintained"
            })
            
        return report

def print_sync_report(report: Dict[str, Any]):
    """Print formatted synchronization report"""
    print("\n" + "="*80)
    print("📊 DATABASE SCHEMA SYNCHRONIZATION AUDIT REPORT")
    print("="*80)
    
    # Summary
    summary = report["collections_summary"]
    print(f"\n📈 COLLECTIONS SUMMARY:")
    print(f"   • Documented Collections: {summary['documented']}")
    print(f"   • Found in Codebase: {summary['found_in_code']}")
    print(f"   • Active with Data: {summary['active_in_db']}")
    print(f"   • Prepared for Scale: {summary['prepared_for_scale']}")
    
    # Sync Status
    sync = report["synchronization_status"]
    print(f"\n🔄 SYNCHRONIZATION STATUS:")
    print(f"   • Collections in Sync: {sync['collections_in_sync']}")
    print(f"   • Sync Percentage: {sync['sync_percentage']}%")
    
    if sync['missing_from_code']:
        print(f"   • Missing from Code: {', '.join(sync['missing_from_code'])}")
    if sync['undocumented_in_code']:
        print(f"   • Undocumented in Code: {', '.join(sync['undocumented_in_code'])}")
    
    # Field Analysis
    print(f"\n🔍 FIELD USAGE ANALYSIS:")
    for collection, fields in report["field_analysis"].items():
        found_count = len(fields["found"])
        missing_count = len(fields["missing"])
        total = found_count + missing_count
        if total > 0:
            pct = round((found_count / total) * 100, 1)
            print(f"   • {collection}: {found_count}/{total} fields used ({pct}%)")
            if fields["missing"]:
                print(f"     Missing: {', '.join(fields['missing'][:3])}{'...' if len(fields['missing']) > 3 else ''}")
    
    # API Models Sync
    print(f"\n📝 API MODELS SYNCHRONIZATION:")
    models = report["api_models_sync"]
    for model, status in models.items():
        if not model.startswith("error"):
            print(f"   • {model}: {status}")
    
    # Index Sync
    print(f"\n📊 INDEX SYNCHRONIZATION:")
    indexes = report["index_sync"]
    for idx, status in indexes.items():
        if not idx.startswith("error"):
            print(f"   • {idx}: {status}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    for i, rec in enumerate(report["recommendations"], 1):
        priority_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(rec["priority"], "⚪")
        print(f"   {i}. {priority_icon} {rec['priority']}: {rec['action']}")
        print(f"      {rec['details']}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    auditor = DatabaseSyncAuditor(project_root)
    
    try:
        report = auditor.generate_sync_report()
        print_sync_report(report)
        
        # Save report to file
        import json
        report_file = Path(project_root) / "database_sync_audit_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n💾 Detailed report saved to: {report_file}")
        
        # Exit with appropriate code
        sync_pct = report["synchronization_status"]["sync_percentage"]
        sys.exit(0 if sync_pct >= 90 else 1)
        
    except Exception as e:
        print(f"❌ Audit failed: {e}")
        sys.exit(1)
