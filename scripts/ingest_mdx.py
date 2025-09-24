# scripts/ingest_mdx.py - Dev-only MDX ingestion script

import os
import json
import re
from pathlib import Path
import yaml

ACADEMY_CONTENT_PATH = os.getenv("ACADEMY_CONTENT_PATH", "content/academy")

# YAML frontmatter parser (between --- markers)
FRONTMATTER_RE = re.compile(r"^---\s*([\s\S]+?)---", re.MULTILINE)

lessons = []

# Recursively find all .mdx files in content/academy/*/*
mdx_files = list(Path(ACADEMY_CONTENT_PATH).rglob("*.mdx"))
if not mdx_files:
    print(f"No .mdx files found in {ACADEMY_CONTENT_PATH} or its subfolders.")
else:
    for fname in mdx_files:
        with open(fname, "r", encoding="utf-8") as f:
            content = f.read()
            m = FRONTMATTER_RE.search(content)
            if not m:
                print(f"Missing YAML frontmatter in {fname}")
                continue
            try:
                frontmatter = yaml.safe_load(m.group(1))
                if not isinstance(frontmatter, dict):
                    print(f"YAML frontmatter is not a dict in {fname}, skipping.")
                    continue
            except Exception as e:
                print(f"YAML frontmatter parse error in {fname}: {e}")
                continue
            lesson_id = frontmatter.get("id") or fname.stem
            lesson_json = {
                "id": lesson_id,
                "frontmatter": frontmatter,
                "html": "<compiled-html-here>"  # TODO: compile MDX to HTML
            }
            # Output all lesson JSONs as flat files in content/academy/
            out_path = os.path.join(ACADEMY_CONTENT_PATH, f"{lesson_id}.json")
            try:
                with open(out_path, "w", encoding="utf-8") as out:
                    json.dump(lesson_json, out, indent=2)
                lessons.append(lesson_id)
            except Exception as e:
                print(f"Failed to write lesson JSON for {fname}: {e}")
    print(f"Ingested {len(lessons)} lessons from {len(mdx_files)} .mdx files. Skipped writing curriculum.json as it is user-provided.")
