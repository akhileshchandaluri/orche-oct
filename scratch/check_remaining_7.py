import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "code" / "evaluation" / "test_pred_improved.csv", "r", encoding="utf-8") as f:
    preds = {r["case_id"]: r for r in csv.DictReader(f)}

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

for cid, pred in preds.items():
    ref = refs[cid]
    p_steps = json.loads(pred["steps_json"])
    r_steps = json.loads(ref["steps_json"])
    p_tuples = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in p_steps]
    r_tuples = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in r_steps]
    if p_tuples != r_tuples:
        print(f"\n--- {cid} ---")
        missing = [s for s in r_tuples if s not in p_tuples]
        extra = [s for s in p_tuples if s not in r_tuples]
        print(f"Missing: {missing}")
        print(f"Extra:   {extra}")
        if set(p_tuples) == set(r_tuples):
            print("Set match but ORDER difference!")
            print("Pred order:", [s[2] + ':' + s[3] for s in p_tuples])
            print("Ref order: ", [s[2] + ':' + s[3] for s in r_tuples])
