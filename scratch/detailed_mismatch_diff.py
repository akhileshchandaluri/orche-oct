import csv
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
sys_path = PROJECT_ROOT
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")

with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    truth_rows = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}

print(f"Loaded {len(sample_requests)} sample requests and {len(truth_rows)} reference rows.\n")

mismatches = []

for req in sample_requests:
    cid = req["case_id"]
    res = engine.audit_case(req)
    p_status = res["deletion_status"]
    p_steps = json.loads(res["steps_json"])
    
    t_status, t_steps = truth_rows[cid]
    
    p_fps = [(s.get("phase"), s.get("system_id"), s.get("resource_id"), s.get("operation"), s.get("state"), s.get("evidence_id")) for s in p_steps]
    t_fps = [(s.get("phase"), s.get("system_id"), s.get("resource_id"), s.get("operation"), s.get("state"), s.get("evidence_id")) for s in t_steps]
    
    if p_status != t_status or p_fps != t_fps:
        mismatches.append({
            "case_id": cid,
            "email": req["email"],
            "requested_at": req["requested_at"],
            "reported_at": req["reported_at"],
            "audit_at": req["audit_at"],
            "reported_status": req["reported_status"],
            "pred_status": p_status,
            "truth_status": t_status,
            "pred_steps": p_steps,
            "truth_steps": t_steps,
            "pred_fps": p_fps,
            "truth_fps": t_fps,
        })

print(f"Total Mismatched Cases: {len(mismatches)} / {len(sample_requests)}\n")

for m in mismatches:
    cid = m["case_id"]
    print("=" * 80)
    print(f"CASE: {cid} | Email: {m['email']} | Req: {m['requested_at']} | Rep: {m['reported_at']} | Audit: {m['audit_at']}")
    print(f"Reported Status: {m['reported_status']} | Pred Status: {m['pred_status']} | Truth Status: {m['truth_status']}")
    print("-" * 80)
    
    p_set = set(m["pred_fps"])
    t_set = set(m["truth_fps"])
    
    missing = [s for s in m["truth_fps"] if s not in p_set]
    extra = [s for s in m["pred_fps"] if s not in t_set]
    
    print(f"Expected Steps Count: {len(m['truth_steps'])} | Predicted Steps Count: {len(m['pred_steps'])}")
    
    if missing:
        print("\n  [MISSING STEPS] (in Truth, not in Prediction):")
        for s in missing:
            print(f"    - phase={s[0]}, sys={s[1]}, res={s[2]}, op={s[3]}, state={s[4]}, ev={s[5]}")
            
    if extra:
        print("\n  [EXTRA STEPS] (in Prediction, not in Truth):")
        for s in extra:
            print(f"    + phase={s[0]}, sys={s[1]}, res={s[2]}, op={s[3]}, state={s[4]}, ev={s[5]}")
            
    print("\n  [EXPECTED STEPS SEQUENCE]:")
    for i, s in enumerate(m["truth_steps"], 1):
        print(f"    {i}. {s['phase']} | {s['system_id']} | {s['resource_id']} | {s['operation']} | {s['state']} | ev='{s['evidence_id']}'")
        
    print("\n  [PREDICTED STEPS SEQUENCE]:")
    for i, s in enumerate(m["pred_steps"], 1):
        print(f"    {i}. {s['phase']} | {s['system_id']} | {s['resource_id']} | {s['operation']} | {s['state']} | ev='{s['evidence_id']}'")
    print()
