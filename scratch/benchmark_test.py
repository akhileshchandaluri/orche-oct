import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv
from code.identity_resolver import IdentityResolver, UserProfile
from code.evidence_indexer import EvidenceIndexer, EvidenceItem
from code.prediction_engine import PredictionEngine

# Let's run a test benchmark
engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")

req_file = PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv"
ref_file = PROJECT_ROOT / "dataset" / "sample_output.csv"

with open(req_file, mode="r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

pred_rows = []
for req in sample_requests:
    res = engine.audit_case(req)
    pred_rows.append({
        "case_id": res["case_id"],
        "deletion_status": res["deletion_status"],
        "steps_json": res["steps_json"],
    })

pred_csv_path = PROJECT_ROOT / "code" / "evaluation" / "scratch_pred_sample.csv"
with open(pred_csv_path, mode="w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
    writer.writeheader()
    writer.writerows(pred_rows)

metrics = evaluate_predictions(
    pred_path=pred_csv_path,
    truth_path=ref_file,
    is_sanity_check=False,
)

print(f"Current Baseline:")
print(f"Status Accuracy:    {metrics.case_status_accuracy * 100:.2f}%")
print(f"Exact Row Accuracy: {metrics.row_level_accuracy * 100:.2f}%")
print(f"Step Precision:     {metrics.step_precision * 100:.2f}%")
print(f"Step Recall:        {metrics.step_recall * 100:.2f}%")
print(f"Step F1 Score:      {metrics.step_f1 * 100:.2f}%")
