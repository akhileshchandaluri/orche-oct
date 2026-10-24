import os
import shutil
import subprocess
import zipfile
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
TEMP_DIR = PROJECT_ROOT / "scratch" / "test_submission_env"

print("--- Step 1: Packaging clean code.zip ---")
code_zip_path = PROJECT_ROOT / "code.zip"

# Include README inside code/ for completeness if not present
readme_path = PROJECT_ROOT / "README.md"

with zipfile.ZipFile(code_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    # Walk through code directory
    for root, dirs, files in os.walk(PROJECT_ROOT / "code"):
        # Exclude pycache and scratch files
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".pyc") or f.startswith("scratch_"):
                continue
            full_path = Path(root) / f
            rel_path = full_path.relative_to(PROJECT_ROOT)
            zf.write(full_path, arcname=str(rel_path).replace("\\", "/"))
            print(f"  Added to code.zip: {rel_path}")
            
    # Also include README.md at root of zip or in code/
    zf.write(readme_path, arcname="README.md")

print(f"\nCreated {code_zip_path.name} ({code_zip_path.stat().st_size} bytes)")

print("\n--- Step 2: Setting up clean test environment ---")
if TEMP_DIR.exists():
    shutil.rmtree(TEMP_DIR)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Extract code.zip into TEMP_DIR
with zipfile.ZipFile(code_zip_path, "r") as zf:
    zf.extractall(TEMP_DIR)

# Copy dataset/ into TEMP_DIR (as the grader will provide)
shutil.copytree(PROJECT_ROOT / "dataset", TEMP_DIR / "dataset")

print(f"Extracted files to: {TEMP_DIR}")
print("Contents of TEMP_DIR:", [p.name for p in TEMP_DIR.iterdir()])

print("\n--- Step 3: Running python code/main.py in isolated environment ---")
cmd = ["python", "code/main.py"]
res = subprocess.run(cmd, cwd=str(TEMP_DIR), capture_output=True, text=True)

print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)

print("\n--- Step 4: Validating generated output.csv in isolated environment ---")
out_csv = TEMP_DIR / "output.csv"
if out_csv.exists():
    print(f"output.csv exists! Size: {out_csv.stat().st_size} bytes")
    # Run schema validator
    val_cmd = ["python", "code/evaluation/schema_validator.py"]
    val_res = subprocess.run(val_cmd, cwd=str(TEMP_DIR), capture_output=True, text=True)
    print("Schema Validator Exit code:", val_res.returncode)
    print("Validator Output:\n", val_res.stdout)
    if val_res.stderr:
        print("Validator STDERR:\n", val_res.stderr)
else:
    print("ERROR: output.csv was not generated!")
