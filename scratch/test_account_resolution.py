import csv
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
DATASET_DIR = PROJECT_ROOT / "dataset"

with open(DATASET_DIR / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

with open(DATASET_DIR / "system_activity.csv", "r", encoding="utf-8") as f:
    all_acts = list(csv.DictReader(f))

with open(DATASET_DIR / "sample_output.csv", "r", encoding="utf-8") as f:
    gt = {}
    for r in csv.DictReader(f):
        for s in json.loads(r["steps_json"]):
            if s["system_id"] == "account_service":
                gt[r["case_id"]] = s["resource_id"]

dw_acc_acts = [
    a for a in all_acts 
    if a["source_system"] == "deletion_worker" and a["target_system"] == "account_service"
]

print(f"Total deletion worker account actions: {len(dw_acc_acts)}")
print(f"Ground truth accounts count: {len(gt)}")

# Let's inspect the matching for cases where our previous logic failed:
failed_cases = ['case_18', 'case_20', 'case_21', 'case_22', 'case_23', 'case_25', 'case_26', 'case_27', 'case_28', 'case_29', 'case_30', 'case_31', 'case_32']

for req in sample_reqs:
    cid = req["case_id"]
    if cid not in failed_cases:
        continue
    req_t = req["requested_at"]
    rep_t = req["reported_at"]
    rep_stat = req["reported_status"]
    gt_acc = gt.get(cid)
    
    # Candidate acts in window: within 2 hours before reported_at
    cands = [
        a for a in dw_acc_acts
        if req_t <= a["event_time"] <= rep_t
    ]
    print(f"\n{cid} (req={req_t}, rep={rep_t}, stat={rep_stat}, GT={gt_acc}):")
    for c in cands:
        is_match = (c["resource_id"] == gt_acc)
        print(f"   {'[MATCH]' if is_match else '       '} {c['event_time']} {c['resource_id']} {c['reported_result']}")
