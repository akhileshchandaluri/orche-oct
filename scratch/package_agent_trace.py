import os
import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_BRAIN = Path("C:/Users/Akhilesh Chandaluri/.gemini/antigravity-ide/brain/df503d39-04c0-4ed6-ab0e-fd87f9ede001")
STAGING_DIR = PROJECT_ROOT / "agent-trace"
DEST_DIR = STAGING_DIR / "antigravity" / "df503d39-04c0-4ed6-ab0e-fd87f9ede001"
ZIP_OUTPUT = PROJECT_ROOT / "agent-trace.zip"

print(f"--- Step 1: Staging Agent Trace ---")
if STAGING_DIR.exists():
    shutil.rmtree(STAGING_DIR)

DEST_DIR.parent.mkdir(parents=True, exist_ok=True)

# Find secret API key from .env to redact if present
secret_key = None
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    with open(env_path, mode="r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                secret_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if secret_key:
    print(f"Secret key found in .env (length: {len(secret_key)}). Redaction will be applied.")
else:
    print("No secret key found in .env.")

# Copy conversation folder
print(f"Copying {SOURCE_BRAIN} -> {DEST_DIR}...")
shutil.copytree(SOURCE_BRAIN, DEST_DIR)

# Scan and redact any occurrence of secret_key or credential tokens
redaction_count = 0
for root, dirs, files in os.walk(DEST_DIR):
    for f in files:
        fpath = Path(root) / f
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            modified = False
            if secret_key and secret_key in content:
                content = content.replace(secret_key, "[REDACTED_API_KEY]")
                modified = True
                redaction_count += 1
            if modified:
                fpath.write_text(content, encoding="utf-8")
                print(f"  Redacted secret in: {fpath.relative_to(STAGING_DIR)}")
        except Exception as e:
            print(f"  Warning checking {fpath}: {e}")

print(f"Redaction complete ({redaction_count} occurrences redacted).")

# Step 2: Package into agent-trace.zip
print(f"\n--- Step 2: Packaging agent-trace.zip ---")
if ZIP_OUTPUT.exists():
    ZIP_OUTPUT.unlink()

file_count = 0
total_uncompressed_bytes = 0

with zipfile.ZipFile(ZIP_OUTPUT, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(STAGING_DIR):
        for f in files:
            full_path = Path(root) / f
            rel_path = full_path.relative_to(PROJECT_ROOT)
            zf.write(full_path, arcname=str(rel_path).replace("\\", "/"))
            file_count += 1
            total_uncompressed_bytes += full_path.stat().st_size

zip_size = ZIP_OUTPUT.stat().st_size
print(f"Created {ZIP_OUTPUT.name}:")
print(f"  Entries: {file_count} files")
print(f"  Uncompressed Size: {total_uncompressed_bytes:,} bytes")
print(f"  Compressed Size: {zip_size:,} bytes ({zip_size / (1024 * 1024):.2f} MB)")

# Step 3: Validate contents of agent-trace.zip
print(f"\n--- Step 3: Validating agent-trace.zip ---")
with zipfile.ZipFile(ZIP_OUTPUT, mode="r") as zf:
    names = zf.namelist()
    print(f"Archive verified: {len(names)} entries.")
    
    # Check for forbidden files
    for n in names:
        assert not n.endswith(".env"), f"Found .env in archive: {n}"
        assert "auth.json" not in n, f"Found auth.json in archive: {n}"
        assert "credentials" not in n.lower(), f"Found credentials in archive: {n}"

    # Confirm key files exist
    assert any("transcript.jsonl" in n for n in names), "Missing transcript.jsonl in agent-trace.zip"
    print("Found transcript.jsonl in archive.")
    if any("transcript_full.jsonl" in n for n in names):
        print("Found transcript_full.jsonl in archive.")

    # Verify no raw secret key in zipped contents
    if secret_key:
        for info in zf.infolist():
            raw_data = zf.read(info).decode("utf-8", errors="ignore")
            assert secret_key not in raw_data, f"Secret key leaked in {info.filename}!"
        print("Zero API keys or secrets detected in archive contents.")

print("\nagent-trace.zip successfully generated, validated, and ready for submission!")

# Copy to Desktop for direct submission
desktop = Path(os.path.expanduser("~/Desktop"))
if desktop.exists():
    dest_desktop = desktop / "agent-trace.zip"
    shutil.copy2(ZIP_OUTPUT, dest_desktop)
    print(f"Copied updated agent-trace.zip to {dest_desktop}")

