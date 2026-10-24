import sys
from pathlib import Path
import csv
import json

PROJECT_ROOT = Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir="dataset")
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
ref_rows = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}

print("Checking resolve_primary_account_id without step 2 (num <= 10):")
for req in sample_reqs:
    cid = req["case_id"]
    email = req["email"]
    prof = engine.forensics_engine.resolver.resolve_by_email(email)
    ev_items = engine.forensics_engine.indexer.find_evidence_for_user(prof, req["audit_at"], req["requested_at"])
    
    # Check current resolution
    curr_acc, curr_ev = engine.forensics_engine.resolve_primary_account_id(
        prof, email, req["requested_at"], req["reported_at"], req["audit_at"], ev_items, req["reported_status"]
    )
    
    # Check reference account
    ref_steps = ref_rows[cid]
    ref_acc_steps = [s for s in ref_steps if s["system_id"] == "account_service"]
    ref_acc = ref_acc_steps[0]["resource_id"] if ref_acc_steps else "NONE"
    ref_ev = ref_acc_steps[0]["evidence_id"] if ref_acc_steps else "NONE"
    
    match = (curr_acc == ref_acc)
    ev_match = (curr_ev == ref_ev)
    if not match or not ev_match:
        print(f"  {cid} ({email}): resolved ({curr_acc}, {curr_ev}) vs ref ({ref_acc}, {ref_ev}) -> acc_match={match}, ev_match={ev_match}")
