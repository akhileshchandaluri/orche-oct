import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    reqs = {r["case_id"]: r for r in csv.DictReader(f)}

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    acts = list(csv.DictReader(f))

for cid in ["case_18", "case_20", "case_23", "case_31"]:
    req = reqs[cid]
    ref = refs[cid]
    email = req["email"]
    print(f"\n=======================================================")
    print(f"=== {cid} ({email}) requested={req['requested_at']} reported={req.get('reported_at')} ===")
    steps = json.loads(ref["steps_json"])
    print("Ref steps:", [(s.get("system_id"), s.get("resource_id"), s.get("state"), s.get("evidence_id")) for s in steps])
    w = [a for a in acts if req["requested_at"] <= a["event_time"] <= req["reported_at"] and a["target_system"] == "account_service"]
    for a in w:
        print("  account act:", a["event_time"], a["resource_id"], a["reported_result"], a["details"])
