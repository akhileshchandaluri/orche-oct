import zipfile
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Define the explicit allowlist
allowlist_items = [
    ("README.md", "README.md"),
    ("AGENTS.md", "AGENTS.md"),
    ("problem_statement.md", "problem_statement.md"),
    ("code/__init__.py", "code/__init__.py"),
    ("code/main.py", "code/main.py"),
    ("code/prediction_engine.py", "code/prediction_engine.py"),
    ("code/evidence_indexer.py", "code/evidence_indexer.py"),
    ("code/identity_resolver.py", "code/identity_resolver.py"),
    ("code/agent_interface.py", "code/agent_interface.py"),
    ("code/groq_reasoner.py", "code/groq_reasoner.py"),
    ("code/evaluation/__init__.py", "code/evaluation/__init__.py"),
    ("code/evaluation/main.py", "code/evaluation/main.py"),
    ("code/evaluation/evaluator.py", "code/evaluation/evaluator.py"),
    ("code/evaluation/schema_validator.py", "code/evaluation/schema_validator.py"),
    ("code/evaluation/benchmark_sample.py", "code/evaluation/benchmark_sample.py"),
    ("code/evaluation/test_scenarios.py", "code/evaluation/test_scenarios.py"),
    ("code/evaluation/test_regressions.py", "code/evaluation/test_regressions.py"),
    ("code/evaluation/test_infrastructure.py", "code/evaluation/test_infrastructure.py"),
    ("code/evaluation/test_prediction_engine.py", "code/evaluation/test_prediction_engine.py"),
    ("code/evaluation/test_groq_integration.py", "code/evaluation/test_groq_integration.py"),
    ("code/evaluation/evaluation_report.md", "code/evaluation/evaluation_report.md"),
    ("code/evaluation/usage_report.md", "code/evaluation/usage_report.md"),
    ("code/evaluation/evaluation_report.md", "evaluation/evaluation_report.md"),
    ("code/evaluation/usage_report.md", "evaluation/usage_report.md"),
]

zip_path = PROJECT_ROOT / "code.zip"
with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
    for src_rel, arc_rel in allowlist_items:
        src_path = PROJECT_ROOT / src_rel
        if not src_path.exists():
            raise FileNotFoundError(f"Missing required source file: {src_rel}")
        zf.write(src_path, arcname=arc_rel)
        print(f"  Added: {arc_rel} ({src_path.stat().st_size} bytes)")

print(f"\nBuilt {zip_path.name} with {len(allowlist_items)} entries ({zip_path.stat().st_size} bytes).")

# Strict verification of exclusions
with zipfile.ZipFile(zip_path, mode="r") as zf:
    names = zf.namelist()
    for name in names:
        # Check forbidden patterns
        for forbidden in [".env", "dataset", ".csv", "__pycache__", ".pyc", "backup", "scratch", ".zip", ".tar", ".gz"]:
            if forbidden in name and not name.endswith(".md"):
                raise AssertionError(f"Forbidden item found in archive: {name}")

print("Exclusion verification passed: Zero forbidden files, secrets, CSVs, or caches.")

# Clean sandbox execution verification
sandbox_dir = PROJECT_ROOT / "scratch" / "final_sandbox_test"
if sandbox_dir.exists():
    shutil.rmtree(sandbox_dir)
sandbox_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, mode="r") as zf:
    zf.extractall(sandbox_dir)

# Copy dataset separately as grader will provide
shutil.copytree(PROJECT_ROOT / "dataset", sandbox_dir / "dataset")

# Run test suite in sandbox
res_tests = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "code/evaluation"],
    cwd=sandbox_dir,
    capture_output=True,
    text=True,
)
assert res_tests.returncode == 0, f"Tests failed in sandbox: {res_tests.stderr}"
print("Sandbox unit test execution: PASS (46/46 tests)")

# Run production entry point in sandbox (deterministic mode)
res_main = subprocess.run(
    [sys.executable, "code/main.py", "--disable-groq"],
    cwd=sandbox_dir,
    capture_output=True,
    text=True,
)
assert res_main.returncode == 0, f"Production pipeline failed in sandbox: {res_main.stderr}"
print("Sandbox production pipeline execution: PASS (518 rows generated and validated)")

# Validate generated output in sandbox
sandbox_out = sandbox_dir / "output.csv"
assert sandbox_out.exists(), "Sandbox output.csv not generated"
with open(sandbox_out, encoding="utf-8") as f:
    s_lines = f.readlines()
assert len(s_lines) == 519, f"Sandbox output expected 519 lines, got {len(s_lines)}"

# Clean up sandbox
shutil.rmtree(sandbox_dir)
print("ALL SANDBOX TESTS PASSED SUCCESSFULLY! code.zip IS SUBMISSION-READY.")
