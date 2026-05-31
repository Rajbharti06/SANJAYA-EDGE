"""Create submission ZIP — excludes node_modules, __pycache__, .git, dist."""
import os, zipfile

BASE   = os.path.dirname(os.path.abspath(__file__))
OUT    = os.path.join(BASE, "SANJAYA_EDGE_Code.zip")

SKIP_DIRS  = {"node_modules", "__pycache__", ".git", "dist", ".venv", "venv",
              ".idea", ".vscode", "env"}
SKIP_FILES = {".pyc", ".pyo", ".DS_Store"}

def should_skip(path):
    parts = path.replace("\\", "/").split("/")
    for p in parts:
        if p in SKIP_DIRS:
            return True
    _, ext = os.path.splitext(path)
    return ext in SKIP_FILES

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(BASE):
        # Prune skip dirs in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, BASE)
            if should_skip(rel):
                continue
            # Skip the zip itself and the output doc/pptx
            if fname in {"SANJAYA_EDGE_Code.zip", "make_zip.py",
                         "make_docx.py", "make_ppt.py"}:
                continue
            zf.write(full, rel)
            count += 1
            print(f"  + {rel}")

sz = os.path.getsize(OUT) / (1024*1024)
print(f"\n[zip] {count} files  |  {sz:.1f} MB  ->  {OUT}")
