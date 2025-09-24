# scripts/unify_techniques.py - Merge brain.json into compendium.json
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class TechniqueUnifier:
    """Unifies brain.json and compendium.json into single source of truth"""
    
    def __init__(self, brain_path: str = "brain.json", compendium_path: str = "compendium.json"):
        self.brain_path = Path(brain_path)
        self.compendium_path = Path(compendium_path)
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    def load_files(self) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Load both JSON files"""
        # Load brain.json
        with open(self.brain_path, 'r', encoding='utf-8') as f:
            brain_data = json.load(f)
        
        # Load compendium.json
        with open(self.compendium_path, 'r', encoding='utf-8') as f:
            compendium_data = json.load(f)
        
        return brain_data, compendium_data
    
    def create_backup(self):
        """Create timestamped backups of both files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Backup brain.json
        brain_backup = self.backup_dir / f"brain_{timestamp}.json"
        brain_backup.write_text(self.brain_path.read_text(encoding='utf-8'), encoding='utf-8')
        
        # Backup compendium.json
        compendium_backup = self.backup_dir / f"compendium_{timestamp}.json"
        compendium_backup.write_text(self.compendium_path.read_text(encoding='utf-8'), encoding='utf-8')
        
        logger.info(f"Backups created: {brain_backup}, {compendium_backup}")
        return brain_backup, compendium_backup
    
    def unify_techniques(self) -> Dict[str, Any]:
        """Merge techniques from brain.json into compendium.json structure"""
        brain_data, compendium_data = self.load_files()
        
        # Create backup before modification
        self.create_backup()
        
        # Extract techniques from brain.json
        brain_techniques = brain_data.get("techniques", {})
        
        # Build unified technique database
        unified_techniques = {}
        existing_ids = set()
        
        # First, add all existing compendium techniques
        for technique in compendium_data:
            technique_id = technique.get("id")
            if technique_id:
                unified_techniques[technique_id] = technique
                existing_ids.add(technique_id)
        
        # Then add brain.json techniques, avoiding duplicates
        added_count = 0
        updated_count = 0
        
        # Handle both array and dict formats for brain_techniques
        if isinstance(brain_techniques, list):
            brain_techniques_dict = {t.get('id', t.get('name', f'technique_{i}')): t 
                                   for i, t in enumerate(brain_techniques)}
        else:
            brain_techniques_dict = brain_techniques
        
        for technique_id, brain_technique in brain_techniques_dict.items():
            if technique_id in existing_ids:
                # Technique exists, merge additional fields
                existing = unified_techniques[technique_id]
                updated = self._merge_technique_data(existing, brain_technique)
                if updated != existing:
                    unified_techniques[technique_id] = updated
                    updated_count += 1
            else:
                # New technique, convert brain format to compendium format
                compendium_technique = self._convert_brain_to_compendium(technique_id, brain_technique)
                unified_techniques[technique_id] = compendium_technique
                added_count += 1
        
        # Convert back to list format for compendium
        unified_list = list(unified_techniques.values())
        
        # Add metadata
        metadata = {
            "version": "2.1",
            "last_updated": datetime.now().isoformat(),
            "total_techniques": len(unified_list),
            "merge_stats": {
                "brain_techniques_added": added_count,
                "techniques_updated": updated_count,
                "total_brain_techniques": len(brain_techniques),
                "total_compendium_techniques": len(compendium_data)
            }
        }
        
        logger.info(f"Unification complete: {added_count} added, {updated_count} updated")
        
        return {
            "metadata": metadata,
            "techniques": unified_list
        }
    
    def _merge_technique_data(self, compendium_tech: Dict, brain_tech: Dict) -> Dict:
        """Merge data from brain technique into compendium technique"""
        merged = compendium_tech.copy()
        
        # Fields to merge from brain.json if missing in compendium
        brain_fields = {
            "description": "description",
            "example": "example", 
            "use_cases": "use_cases",
            "aliases": "aliases",
            "surfaces": "surfaces",
            "tiers": "tiers",
            "cost_estimate": "cost_estimate",
            "conflicts_with": "conflicts_with",
            "complements": "complements"
        }
        
        for compendium_field, brain_field in brain_fields.items():
            if not merged.get(compendium_field) and brain_tech.get(brain_field):
                merged[compendium_field] = brain_tech[brain_field]
        
        # Special handling for template fragments
        if brain_tech.get("template_fragments") and not merged.get("template_fragments"):
            merged["template_fragments"] = brain_tech["template_fragments"]
        
        # Update last_modified
        merged["last_modified"] = datetime.now().isoformat()
        
        return merged
    
    def _convert_brain_to_compendium(self, technique_id: str, brain_technique: Dict) -> Dict:
        """Convert brain.json format to compendium.json format"""
        return {
            "id": technique_id,
            "name": brain_technique.get("name", technique_id.replace("_", " ").title()),
            "description": brain_technique.get("description", ""),
            "category": brain_technique.get("category", "general"),
            "tags": brain_technique.get("tags", []),
            "use_cases": brain_technique.get("use_cases", []),
            "example": brain_technique.get("example", ""),
            "evaluation": brain_technique.get("evaluation", {}),
            "complexity": brain_technique.get("complexity", "medium"),
            "surfaces": brain_technique.get("surfaces", ["web", "vscode", "chrome"]),
            "tiers": brain_technique.get("tiers", ["free", "pro"]),
            "aliases": brain_technique.get("aliases", []),
            "template_fragments": brain_technique.get("template_fragments", {}),
            "cost_estimate": brain_technique.get("cost_estimate", {"tokens": 1.0}),
            "conflicts_with": brain_technique.get("conflicts_with", []),
            "complements": brain_technique.get("complements", []),
            "matcher_rules": brain_technique.get("matcher_rules", {}),
            "phase": brain_technique.get("phase", ["intra"]),
            "created": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "source": "brain_migration"
        }
    
    def save_unified(self, unified_data: Dict[str, Any], output_path: str = None):
        """Save unified data to compendium.json"""
        if output_path is None:
            output_path = self.compendium_path
        
        # Save techniques array (compendium format)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unified_data["techniques"], f, indent=2, ensure_ascii=False)
        
        # Save metadata separately
        metadata_path = Path(output_path).parent / "compendium_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(unified_data["metadata"], f, indent=2, ensure_ascii=False)
        
        logger.info(f"Unified data saved to {output_path}")
        logger.info(f"Metadata saved to {metadata_path}")
    
    def validate_unified(self, unified_techniques: List[Dict]) -> Dict[str, Any]:
        """Validate the unified technique database"""
        issues = []
        stats = {"total": len(unified_techniques), "valid": 0, "issues": 0}
        
        seen_ids = set()
        for i, technique in enumerate(unified_techniques):
            technique_issues = []
            
            # Check required fields
            required_fields = ["id", "name", "description", "category"]
            for field in required_fields:
                if not technique.get(field):
                    technique_issues.append(f"Missing required field: {field}")
            
            # Check for duplicate IDs
            tech_id = technique.get("id")
            if tech_id in seen_ids:
                technique_issues.append(f"Duplicate ID: {tech_id}")
            else:
                seen_ids.add(tech_id)
            
            # Check data types
            if technique.get("tags") and not isinstance(technique["tags"], list):
                technique_issues.append("tags must be a list")
            
            if technique.get("use_cases") and not isinstance(technique["use_cases"], list):
                technique_issues.append("use_cases must be a list")
            
            if technique_issues:
                issues.append({"index": i, "id": tech_id, "issues": technique_issues})
                stats["issues"] += 1
            else:
                stats["valid"] += 1
        
        return {"stats": stats, "issues": issues}

def main():
    """Main function to run the unification process"""
    logging.basicConfig(level=logging.INFO)
    
    unifier = TechniqueUnifier()
    
    try:
        # Unify the techniques
        unified_data = unifier.unify_techniques()
        
        # Validate the result
        validation = unifier.validate_unified(unified_data["techniques"])
        
        if validation["issues"]:
            logger.warning(f"Found {len(validation['issues'])} validation issues")
            for issue in validation["issues"][:5]:  # Show first 5 issues
                logger.warning(f"Technique {issue['id']}: {issue['issues']}")
        
        # Save if validation passes or user confirms
        if not validation["issues"] or input("Validation issues found. Continue? (y/N): ").lower() == 'y':
            unifier.save_unified(unified_data)
            print(f"✅ Unification complete!")
            print(f"📊 Stats: {unified_data['metadata']['merge_stats']}")
            print(f"📁 Total techniques: {unified_data['metadata']['total_techniques']}")
        else:
            print("❌ Unification cancelled due to validation issues")
            
    except Exception as e:
        logger.error(f"Unification failed: {e}")
        raise

if __name__ == "__main__":
    main()
