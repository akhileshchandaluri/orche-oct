import csv
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
DATASET_DIR = PROJECT_ROOT / "dataset"

with open(DATASET_DIR / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

with open(DATASET_DIR / "system_activity.csv", "r", encoding="utf-8") as f:
    system_activities = list(csv.DictReader(f))

dw_acts = [a for a in system_activities if a["source_system"] == "deletion_worker"]

with open(DATASET_DIR / "sample_output.csv", "r", encoding="utf-8") as f:
    ground_truth = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(f)}

print("=== Checking Ground Truth Verification Steps vs Worker Activities ===")
for req in sample_reqs:
    cid = req["case_id"]
    req_t = req["requested_at"]
    rep_t = req["reported_at"]
    gt_steps = ground_truth.get(cid, [])
    gt_verifs = [s for s in gt_steps if s["phase"] == "VERIFICATION"]
    
    # Worker acts in window
    window_acts = [a for a in dw_acts if req_t <= a["event_time"] <= rep_t]
    
    print(f"\n{cid} ({req['email']}) reported_status={req['reported_status']}:")
    print(f"  GT Verifs ({len(gt_verifs)}): {[(v['system_id'], v['resource_id'], v['state'], v['evidence_id']) for v in gt_verifs]}")
    print(f"  Worker Acts in Window ({len(window_acts)}): {[(a['target_system'], a['resource_id'], a['event_type'], a['reported_result']) for a in window_acts]}")
