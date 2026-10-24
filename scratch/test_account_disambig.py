import sys
sys.path.insert(0, ".")
import csv
from datetime import datetime, timedelta
from code.identity_resolver import IdentityResolver

resolver = IdentityResolver("dataset")
with open("dataset/evidence_files.csv", "r", encoding="utf-8") as f:
    manifest = list(csv.DictReader(f))
with open("dataset/system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))
with open("dataset/sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

# Build known accounts map
known_account_to_email = {}
trace_log = "dataset/evidence/logs/resource_lookup_trace_20260926_103856.log"
import re
with open(trace_log, "r", encoding="utf-8") as f:
    for line in f:
        if "service=account_service" in line and "lookup_key=" in line:
            res = re.search(r"resource_id=(account_[0-9]+)", line)
            key = re.search(r"lookup_key=([^\s]+)", line)
            if res and key and key.group(1) != "null":
                known_account_to_email[res.group(1)] = key.group(1).lower()

with open("dataset/evidence/records/customer_account_handover_20261001.txt", "r", encoding="utf-8") as f:
    for line in f:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 6 and parts[1] == "account_service":
            known_account_to_email[parts[2]] = parts[5].lower()

import json
for snap_path in ["dataset/evidence/records/customer_data_snapshot_bundle_20260917.json"]:
    with open(snap_path, "r", encoding="utf-8") as f:
        d = json.load(f)
        for s in d.get("snapshots", []):
            if s.get("data_store") == "account_service":
                for rec in s.get("records", []):
                    aid = rec.get("resource_id")
                    em = rec.get("email")
                    if aid and em:
                        known_account_to_email[aid] = em.lower()

with open("dataset/user_identities.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if "9155" in row.get("phone", ""):
            known_account_to_email["account_9155"] = row["email"].lower()

for cid in ["case_18", "case_20", "case_23", "case_25", "case_28", "case_31"]:
    req = [r for r in sample_reqs if r["case_id"] == cid][0]
    email = req["email"].lower()
    reported_at = req["reported_at"]
    reported_status = req["reported_status"]
    
    rep_dt = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
    batch_start = (rep_dt - timedelta(hours=2.5)).isoformat().replace("+00:00", "Z")
    
    w_acts = [
        a for a in activities
        if a["source_system"] == "deletion_worker"
        and a["target_system"] == "account_service"
        and a["event_type"] == "DELETE_RECORD"
        and batch_start <= a["event_time"] <= reported_at
    ]
    
    valid_accs = [
        a for a in w_acts
        if a["resource_id"] not in known_account_to_email or known_account_to_email[a["resource_id"]] == email
    ]
    
    if reported_status == "COMPLETE":
        matched = [a for a in valid_accs if a.get("reported_result") == "SUCCESS"]
    elif reported_status == "NOT_STARTED":
        matched = [a for a in valid_accs if a.get("reported_result") == "FAILED"]
    elif reported_status == "PARTIALLY_COMPLETE":
        matched = [a for a in valid_accs if a.get("reported_result") == "PARTIAL"]
    else:
        matched = [a for a in valid_accs if a.get("reported_result") in ["FAILED", "PARTIAL"]]
        
    pool = matched if matched else valid_accs
    print(f"{cid} ({email}): {len(pool)} candidates -> {[a['resource_id'] for a in pool]}")
