#!/usr/bin/env python3
"""
Verify the merged compendium.json
"""
import json

with open('compendium.json', 'r', encoding='utf-8') as f:
    compendium = json.load(f)

print(f'Total entries: {len(compendium)}')

# Count entries with IDs
entries_with_ids = [c for c in compendium if isinstance(c, dict) and 'id' in c]
print(f'Entries with IDs: {len(entries_with_ids)}')

# Show last 5 technique IDs (the newly added ones)
print(f'Last 5 technique IDs (newly added):')
for c in compendium[-5:]:
    if isinstance(c, dict) and 'id' in c:
        print(f'  {c["id"]}: {c.get("name", "No name")}')

# Verify structure - should be array of objects
print(f'Structure check: compendium is list = {isinstance(compendium, list)}')

# Check for proper JSON
try:
    json.dumps(compendium)
    print('✅ JSON serialization successful')
except:
    print('❌ JSON serialization failed')

# Show some key fields from a newly added technique
print('\nSample newly added technique (oracle_constraint_enrichment):')
for technique in compendium:
    if isinstance(technique, dict) and technique.get('id') == 'oracle_constraint_enrichment':
        print(f'  ID: {technique.get("id")}')
        print(f'  Name: {technique.get("name")}')
        print(f'  Category: {technique.get("category")}')
        print(f'  Has aliases: {"aliases" in technique}')
        print(f'  Has phase: {"phase" in technique}')
        print(f'  Has cost_estimate: {"cost_estimate" in technique}')
        break
