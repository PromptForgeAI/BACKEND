import json
from pathlib import Path

def load_compendium_from_file(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Optionally, add MongoDB loader here if needed
