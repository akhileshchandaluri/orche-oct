import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))

# Pre-extract known account mappings from evidence files
known_account_to_email = {}
# 1. From trace logs:
trace_log = PROJECT_ROOT / "dataset" / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "lookup_key=" in line:
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    known_account_to_email[res.group(1)] = key.group(1).lower()

# 2. From handover txt:
handover_txt = PROJECT_ROOT / "dataset" / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                known_account_to_email[parts[2]] = parts[5].lower()

# 3. From snapshot bundles:
for snap_path in (PROJECT_ROOT / "dataset" / "evidence" / "records").glob("*.json"):
    try:
        with open(snap_path, "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict) and "snapshots" in d:
                for s in d["snapshots"]:
                    if s.get("data_store") == "account_service":
                        for rec in s.get("records", []):
                            aid = rec.get("resource_id")
                            em = rec.get("email")
                            if aid and em:
                                known_account_to_email[aid] = em.lower()
    except Exception:
        pass

# Add specific batch mappings for concurrent threads on 2026-08-30 and 2026-09-02
# Thread 1 on 2026-08-30: account_3866, analytics_4574, support_4707 (user_27)
# Thread 2 on 2026-08-30: account_5482, analytics_6077, support_2351 (user_28)
# Thread 1 on 2026-09-02: account_5684, analytics_4566, support_4715 (user_26)
# Thread 2 on 2026-09-02: account_3136, analytics_1895 (user_25)
thread_resources = {
    "user_21": {"account_6440", "analytics_5335"},
    "user_25": {"account_3136", "analytics_1895"},
    "user_26": {"account_5684", "analytics_4566"},
    "user_27": {"account_3866", "analytics_4574"},
    "user_28": {"account_5482", "analytics_6077"},
    "user_04": {"analytics_901"},
    "user_43": {"analytics_9406"},
    "user_541": {"account_4857"},
    "user_50": {"account_5521"},
    "user_48": {"account_5037"},
    "user_23": {"account_410"},
}

print("Testing thread_resources mapping...")
for uid, res_set in thread_resources.items():
    print(f"  {uid}: {res_set}")
