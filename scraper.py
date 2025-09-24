import os, re, json, hashlib, time
IGNORE = re.compile(r'(^\.git($|/))|/node_modules/|/dist/|/build/|/\.venv/|/venv/|/__pycache__/|/\.mypy_cache/|/coverage/|/\.pytest_cache/')
root = os.getcwd()
manifest = []
for base, dirs, files in os.walk(root):
    # prune ignored dirs fast
    dirs[:] = [d for d in dirs if not IGNORE.search(os.path.join(base, d).replace("\\","/") + "/")]
    for fn in files:
        p = os.path.join(base, fn)
        rp = p[len(root)+1:]
        if IGNORE.search(rp.replace("\\","/")): 
            continue
        try:
            st = os.stat(p)
            h = hashlib.sha1()
            with open(p, 'rb') as f:
                while True:
                    b = f.read(1<<20)
                    if not b: break
                    h.update(b)
            manifest.append({
                "path": rp.replace("\\","/"),
                "size": st.st_size,
                "modified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
                "sha1": h.hexdigest()
            })
        except Exception as e:
            manifest.append({"path": rp, "error": str(e)})
with open("project-structure.json","w",encoding="utf-8") as f:
    json.dump(manifest,f,ensure_ascii=False,indent=2)
print("Wrote project-structure.json")
