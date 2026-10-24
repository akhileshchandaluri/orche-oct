import json
import csv
import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")

with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    requests = list(csv.DictReader(f))

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

mismatches = []
for req in requests:
    cid = req["case_id"]
    res = engine.audit_case(req)
    ref = refs[cid]
    p_steps = json.loads(res["steps_json"])
    r_steps = json.loads(ref["steps_json"])
    p_stat = res["deletion_status"]
    r_stat = ref["deletion_status"]
    if p_stat != r_stat or p_steps != r_steps:
        mismatches.append((cid, req, p_stat, r_stat, p_steps, r_steps))

print(f"Total mismatches: {len(mismatches)} / {len(requests)}")
for cid, req, p_stat, r_stat, p_steps, r_steps in mismatches:
    email = req["email"]
    print(f"\n=======================================================")
    print(f"CASE: {cid} | Email: {email} | Status: pred={p_stat}, ref={r_stat}")
    print(f"Requested: {req['requested_at']} | Reported: {req.get('reported_at', '')}")
    p_tuples = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in p_steps]
    r_tuples = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in r_steps]
    missing = [s for s in r_tuples if s not in p_tuples]
    extra = [s for s in p_tuples if s not in r_tuples]
    print(f"Missing from pred ({len(missing)}):")
    for m in missing:
        print(f"  - {m}")
    print(f"Extra in pred ({len(extra)}):")
    for e in extra:
        print(f"  + {e}")
    # Also check ordering differences if sets are identical
    if set(p_tuples) == set(r_tuples) and p_tuples != r_tuples:
        print("  * Set match but order difference!")
