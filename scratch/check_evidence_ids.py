import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        cid = r["case_id"]
        status = r["deletion_status"]
        steps = json.loads(r["steps_json"])
        verifs = [s for s in steps if s["phase"] == "VERIFICATION"]
        non_empty_ev = [s for s in verifs if s.get("evidence_id") != ""]
        empty_ev = [s for s in verifs if s.get("evidence_id") == ""]
        if status == "INCOMPLETE":
            if non_empty_ev:
                print(f"{cid} INCOMPLETE has non-empty verif evidence: {len(non_empty_ev)} steps")
        elif status == "COMPLETE":
            if empty_ev:
                print(f"{cid} COMPLETE has empty verif evidence: {len(empty_ev)} steps")

print("Check finished.")
