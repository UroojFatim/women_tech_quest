"""Build the competition submission ZIP with Python (guaranteed forward-slash
paths, so the portal finds output/, source/ and demo/ correctly).

Includes: output/level1.csv, output/level2.csv, all of source/, demo/demo.mp4
Excludes: source/.env, any __pycache__, *.pyc, cache/
"""
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ZIP = ROOT / "submission.zip"

# ---- diagnose the old zip first (if present) ----
if ZIP.exists():
    try:
        with zipfile.ZipFile(ZIP) as z:
            back = [n for n in z.namelist() if "\\" in n]
            print(f"OLD zip entries with backslash separators: {len(back)}")
            if back:
                print("  -> that was the bug (portal could not see folders)")
    except Exception as e:
        print("could not read old zip:", e)
    os.remove(ZIP)


def should_skip(p: Path) -> bool:
    if p.name == ".env" or p.suffix == ".pyc":
        return True
    if "__pycache__" in p.parts:
        return True
    return False


# Gather the file list (arcname -> source path) first.
files = {}
for name in ("level1.csv", "level2.csv"):
    src = ROOT / "output" / name
    if not src.exists():
        raise SystemExit(f"MISSING: output/{name} — run the solution first.")
    files[f"output/{name}"] = src
for p in sorted((ROOT / "source").rglob("*")):
    if p.is_file() and not should_skip(p):
        files[p.relative_to(ROOT).as_posix()] = p
demo = ROOT / "demo" / "demo.mp4"
if demo.exists():
    files["demo/demo.mp4"] = demo

# Derive every folder that should exist, so strict validators find the folders.
dirs = set()
for arc in files:
    parts = arc.split("/")[:-1]
    for i in range(1, len(parts) + 1):
        dirs.add("/".join(parts[:i]) + "/")

count = 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    # explicit directory entries first (output/, source/, source/wtq/, demo/, ...)
    for d in sorted(dirs):
        z.writestr(d, "")
    # then the files, with forward-slash paths
    for arc, src in files.items():
        z.write(src, arc)
        count += 1

size_mb = ZIP.stat().st_size / 1024 / 1024
print(f"\nBuilt {ZIP.name}: {count} files, {size_mb:.2f} MB")

# ---- verify the new zip ----
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
    back = [n for n in names if "\\" in n]
    checks = {
        "output/level1.csv": "output/level1.csv" in names,
        "output/level2.csv": "output/level2.csv" in names,
        "source/README.md": "source/README.md" in names,
        "source/ code (run.py)": "source/run.py" in names,
        "demo/demo.mp4": "demo/demo.mp4" in names,
        "forward-slash paths": len(back) == 0,
        "no real .env": not any(n.split("/")[-1] == ".env" for n in names),
        "no cache": not any("cache" in n for n in names),
        "size <= 15 MB": size_mb <= 15,
    }
    print("\n=== VERIFY ===")
    for k, v in checks.items():
        print(f"  [{'OK' if v else 'FAIL'}] {k}")
    print("\nALL GOOD" if all(checks.values()) else "\nSOMETHING IS WRONG")
