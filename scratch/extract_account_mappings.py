import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
dataset_dir = PROJECT_ROOT / "dataset"
mappings = {}

for p in (dataset_dir / "evidence").rglob("*"):
    if p.is_file() and p.suffix in [".log", ".txt", ".json"]:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'resource_id=[\"\']?(account_[0-9]+)[\"\']?.*?correlation_key=[\"\']?([^\s\"\'\,]+)[\"\']?', content):
                acc, key = m.group(1), m.group(2)
                if "@" in key:
                    mappings[acc] = key.lower()
            for m in re.finditer(r'lookup_key=[\"\']?([^\s\"\'\,]+)[\"\']?.*?resource_id=[\"\']?(account_[0-9]+)[\"\']?', content):
                key, acc = m.group(1), m.group(2)
                if "@" in key:
                    mappings[acc] = key.lower()
        except Exception:
            pass

print(f"Total account-email mappings found: {len(mappings)}")
for acc, email in sorted(mappings.items())[:20]:
    print(f"  {acc} -> {email}")
