#!/usr/bin/env python3
import os, re, ast, json, textwrap
from pathlib import Path

ROOT = Path("BRAIN_ENGINE")

def read_first_comment_block(text: str):
    # grab top comment/docstring chunk
    # python: module docstring; others: leading // or /* */ block
    # try python first
    try:
        mod = ast.parse(text)
        ds = ast.get_docstring(mod)
        if ds: return ds.strip()
    except Exception:
        pass
    # fallback: leading comment lines
    lines = text.splitlines()
    block = []
    for i, line in enumerate(lines[:60]):
        if re.match(r'^\s*(#|//|/\*|\*)', line):
            block.append(line.strip("/*# /"))
        elif block:
            break
    return "\n".join(block).strip() if block else ""

def list_py_symbols(text: str):
    out = {"classes": [], "functions": []}
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                out["classes"].append({
                    "name": node.name,
                    "doc": (ast.get_docstring(node) or "").strip()
                })
            elif isinstance(node, ast.FunctionDef):
                out["functions"].append({
                    "name": node.name,
                    "doc": (ast.get_docstring(node) or "").strip()
                })
    except Exception:
        pass
    return out

def detect_lang(path: Path):
    ext = path.suffix.lower()
    if ext == ".py": return "python"
    if ext in (".ts", ".tsx"): return "typescript"
    if ext in (".js", ".jsx", ".mjs", ".cjs"): return "javascript"
    if ext in (".json", ".yml", ".yaml", ".toml"): return "config"
    return "other"

def summarize_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    lang = detect_lang(path)
    header = read_first_comment_block(text)
    symbols = list_py_symbols(text) if lang == "python" else {"classes": [], "functions": []}
    # quick heuristics: pipeline/registry/adapter/feature/route words
    tags = []
    name = path.name.lower()
    for key, tag in [
        ("router", "router"),
        ("registry", "registry"),
        ("pipeline", "pipeline"),
        ("adapter", "adapter"),
        ("feature", "feature-flags"),
        ("flag", "feature-flags"),
        ("error", "errors"),
        ("util", "utils"),
        ("config", "config"),
        ("client", "client"),
        ("schema", "schema"),
        ("model", "model"),
        ("service", "service"),
        ("worker", "worker"),
        ("task", "task"),
    ]:
        if key in name: tags.append(tag)
    return {
        "path": str(path),
        "lang": lang,
        "comment_header": header,
        "classes": symbols["classes"],
        "functions": symbols["functions"],
        "tags": sorted(set(tags)),
        "lines": text.count("\n")+1
    }

def main():
    if not ROOT.exists():
        print(f"Missing {ROOT}/ — run from repo root.")
        return
    files = []
    for p in ROOT.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml", ".toml", ".md"}:
                files.append(p)
    records = []
    for f in sorted(files):
        rec = summarize_file(f)
        if rec: records.append(rec)

    out = ["# BRAIN_ENGINE – File Inventory\n"]
    out.append(f"Total files: **{len(records)}**\n")
    out.append("---\n")
    for r in records:
        out.append(f"## `{r['path']}`")
        out.append(f"- Language: **{r['lang']}**, Lines: **{r['lines']}**, Tags: `{', '.join(r['tags']) or '—'}`")
        if r["comment_header"]:
            out.append(f"- Top comment/docstring:\n\n> {textwrap.fill(r['comment_header'], width=100)}\n")
        if r["classes"]:
            out.append("- Classes:")
            for c in r["classes"]:
                doc = (" — " + c["doc"]) if c["doc"] else ""
                out.append(f"  - `{c['name']}`{doc}")
        if r["functions"]:
            out.append("- Functions:")
            for fn in r["functions"]:
                doc = (" — " + fn["doc"]) if fn["doc"] else ""
                out.append(f"  - `{fn['name']}`{doc}")
        out.append("")
    Path("BRAIN_ENGINE_REPORT.md").write_text("\n".join(out), encoding="utf-8")
    print("Wrote BRAIN_ENGINE_REPORT.md ✅")

if __name__ == "__main__":
    main()
