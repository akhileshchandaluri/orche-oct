import sys
sys.path.insert(0, ".")
import csv
import json
from pathlib import Path
from code.evaluation.evaluator import evaluate_predictions

dataset_dir = Path("dataset")
req_file = dataset_dir / "sample_deletion_requests.csv"
ref_file = dataset_dir / "sample_output.csv"

with open(req_file, mode="r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

from code.prediction_engine import PredictionEngine
engine = PredictionEngine(dataset_dir=dataset_dir)

# 1. Baseline run
base_rows = []
for req in sample_requests:
    res = engine.audit_case(req)
    base_rows.append({
        "case_id": res["case_id"],
        "deletion_status": res["deletion_status"],
        "steps_json": res["steps_json"]
    })

with open("scratch/base_pred.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
    writer.writeheader()
    writer.writerows(base_rows)

res_base = evaluate_predictions("scratch/base_pred.csv", str(ref_file))
print("=== BASELINE ===")
for k, v in vars(res_base).items():
    if not isinstance(v, (list, dict)):
        print(f"  {k}: {v}")
