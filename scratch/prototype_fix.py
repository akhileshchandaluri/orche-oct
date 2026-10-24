import sys
import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Let's inspect the candidate accounts and exclude other users
from code.evidence_indexer import EvidenceIndexer
from code.identity_resolver import IdentityResolver

# Let's see what accounts belong to other users by building an excluded account set
dataset_dir = PROJECT_ROOT / "dataset"
other_user_accounts = {}

# 1. From trace logs: profile_lookup_started resource_id=account_XXXX lookup_key=someone@...
trace_log = dataset_dir / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "resource_id=" in line and "lookup_key=" in line:
                import re
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    other_user_accounts[res.group(1)] = key.group(1)

# 2. From customer_account_handover_20261001.txt
handover_txt = dataset_dir / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                other_user_accounts[parts[2]] = parts[5]

print(f"Discovered {len(other_user_accounts)} accounts with explicit user mappings:")
for acc, email in other_user_accounts.items():
    print(f"  {acc} -> {email}")
