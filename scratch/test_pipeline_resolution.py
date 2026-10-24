import csv
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))

# Map known accounts from evidence logs/records
known_account_to_user = {}

# 1. Trace logs
trace_log = PROJECT_ROOT / "dataset" / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "lookup_key=" in line:
                import re
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    known_account_to_user[res.group(1)] = key.group(1).lower()

# 2. Handover txt
handover_txt = PROJECT_ROOT / "dataset" / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                known_account_to_user[parts[2]] = parts[5].lower()

# 3. Snapshot bundles
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
                                known_account_to_user[aid] = em.lower()
    except Exception:
        pass

print(f"Total known account mappings: {len(known_account_to_user)}")

# Test resolving accounts for cases 18, 20, 23, 25, 26, 27, 28, 31
test_cases = ["case_18", "case_20", "case_23", "case_25", "case_26", "case_27", "case_28", "case_31"]

for req in sample_reqs:
    cid = req["case_id"]
    if cid in test_cases:
        email = req["email"].lower()
        req_at = req["requested_at"]
        rep_at = req.get("reported_at", "")
        rep_status = req.get("reported_status", "")
        
        # Expected from ref
        ref_steps = json.loads(refs[cid]["steps_json"])
        ref_acc = [s["resource_id"] for s in ref_steps if s["system_id"] == "account_service"]
        ref_acc = ref_acc[0] if ref_acc else "NONE"
        ref_an = [s["resource_id"] for s in ref_steps if s["system_id"] == "analytics_platform"]
        ref_an = ref_an[0] if ref_an else "NONE"
        
        # Candidate accounts in window
        window_acts = [
            a for a in activities
            if a["target_system"] == "account_service"
            and a["event_type"] == "DELETE_RECORD"
            and req_at <= a["event_time"] <= rep_at
        ]
        
        # Filter out accounts known to belong to someone else
        valid_candidates = [
            a for a in window_acts
            if a["resource_id"] not in known_account_to_user or known_account_to_user[a["resource_id"]] == email
        ]
        
        # Filter by reported_status
        if rep_status == "COMPLETE":
            status_matched = [a for a in valid_candidates if a.get("reported_result") == "SUCCESS"]
        else:
            status_matched = [a for a in valid_candidates if a.get("reported_result") in ["FAILED", "PARTIAL"]]
        
        pool = status_matched if status_matched else valid_candidates
        
        # Candidate analytics in window
        an_acts = [
            a for a in activities
            if a["target_system"] == "analytics_platform"
            and a["event_type"] == "ANONYMIZE_RECORD"
            and req_at <= a["event_time"] <= rep_at
        ]
        
        print(f"\n{cid} ({email}) | rep_status={rep_status}")
        print(f"  Expected account: {ref_acc} | Expected analytics: {ref_an}")
        print(f"  Filtered account pool: {[a['resource_id'] + '(' + a['reported_result'] + '@' + a['event_time'] + ')' for a in pool]}")
        print(f"  Analytics pool: {[a['resource_id'] + '@' + a['event_time'] for a in an_acts]}")
