import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["case_id"] in ["case_14", "case_31", "case_32"]:
            print(f"=== {r['case_id']} ({r['deletion_status']}) ===")
            for s in json.loads(r["steps_json"]):
                print(" ", s["system_id"], s["resource_id"], s["operation"], s["state"])
