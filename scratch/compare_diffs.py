import os, filecmp, difflib
from pathlib import Path

def compare_dirs(dir1, dir2):
    print(f"\n=======================================================")
    print(f"COMPARING: {dir1} vs {dir2}")
    print(f"=======================================================")
    
    files1 = set()
    for root, _, fs in os.walk(dir1):
        if any(p in root for p in ["__pycache__", ".git"]): continue
        for f in fs:
            rel = os.path.relpath(os.path.join(root, f), dir1)
            files1.add(rel)

    files2 = set()
    for root, _, fs in os.walk(dir2):
        if any(p in root for p in ["__pycache__", ".git"]): continue
        for f in fs:
            rel = os.path.relpath(os.path.join(root, f), dir2)
            files2.add(rel)

    common = sorted(files1.intersection(files2))
    only1 = sorted(files1 - files2)
    only2 = sorted(files2 - files1)

    print(f"Files only in {dir1}: {only1}")
    print(f"Files only in {dir2}: {only2}")
    
    differing = []
    for rel in common:
        p1 = Path(dir1) / rel
        p2 = Path(dir2) / rel
        if p1.read_bytes() != p2.read_bytes():
            differing.append(rel)
    
    print(f"Differing files ({len(differing)}): {differing}")
    for d in differing:
        print(f"\n--- DIFF: {d} ---")
        lines1 = (Path(dir1) / d).read_text(encoding="utf-8", errors="ignore").splitlines()
        lines2 = (Path(dir2) / d).read_text(encoding="utf-8", errors="ignore").splitlines()
        diff = list(difflib.unified_diff(lines1, lines2, fromfile=f"{dir1}/{d}", tofile=f"{dir2}/{d}", lineterm=""))
        for l in diff[:40]: # show first 40 lines
            print(l)
        if len(diff) > 40:
            print(f"... ({len(diff) - 40} more diff lines)")

compare_dirs("backup/baseline_pre_eval_repair", "backup/baseline_pre_priority_fixes")
compare_dirs("backup/baseline_pre_priority_fixes", ".")
