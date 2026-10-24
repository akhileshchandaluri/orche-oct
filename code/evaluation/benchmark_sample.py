"""Representative benchmark runner comparing PredictionEngine against sample_output.csv.

Evaluates:
- Deletion-status accuracy
- Exact row accuracy
- Step-level precision, recall, F1
- Sequence accuracy
- Detailed breakdown of mismatches and root causes
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv
from code.prediction_engine import PredictionEngine


def run_benchmark():
    engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")

    # Load sample requests and reference output
    req_file = PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv"
    ref_file = PROJECT_ROOT / "dataset" / "sample_output.csv"

    with open(req_file, mode="r", encoding="utf-8") as f:
        sample_requests = list(csv.DictReader(f))

    with open(ref_file, mode="r", encoding="utf-8") as f:
        ref_rows = list(csv.DictReader(f))

    print(f"Loaded {len(sample_requests)} sample requests and {len(ref_rows)} reference answers.")

    # Generate predictions
    pred_rows = []
    agent_outputs = {}

    for req in sample_requests:
        res = engine.audit_case(req)
        pred_rows.append({
            "case_id": res["case_id"],
            "deletion_status": res["deletion_status"],
            "steps_json": res["steps_json"],
        })
        agent_outputs[res["case_id"]] = res["agent_output"]

    # Write temporary prediction CSV for evaluator
    pred_csv_path = PROJECT_ROOT / "code" / "evaluation" / "scratch_pred_sample.csv"
    with open(pred_csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        writer.writerows(pred_rows)

    # Validate schema
    valid_res = validate_csv(pred_csv_path, expected_rows=len(sample_requests))
    print(f"Prediction Schema Validity: {valid_res.is_valid} (errors: {len(valid_res.errors)})")

    # Evaluate against reference
    metrics = evaluate_predictions(
        pred_path=pred_csv_path,
        truth_path=ref_file,
        is_sanity_check=False,
    )

    print("\n" + "=" * 60)
    print("REPRESENTATIVE SAMPLE BENCHMARK METRICS:")
    print("=" * 60)
    print(f"Total Cases:              {metrics.total_truth_cases}")
    print(f"Status Accuracy:          {metrics.case_status_accuracy:.4f} ({metrics.case_status_accuracy * 100:.1f}%)")
    print(f"Exact Row Accuracy:       {metrics.row_level_accuracy:.4f} ({metrics.row_level_accuracy * 100:.1f}%)")
    print(f"Step Precision:           {metrics.step_precision:.4f}")
    print(f"Step Recall:              {metrics.step_recall:.4f}")
    print(f"Step F1 Score:            {metrics.step_f1:.4f}")
    print(f"Sequence Accuracy:        {metrics.sequence_accuracy:.4f} ({metrics.sequence_accuracy * 100:.1f}%)")
    print(f"Schema Compliant:         {valid_res.is_valid}")
    print("=" * 60)

    # Detailed Mismatch Analysis
    print("\n" + "=" * 60)
    print("DETAILED MISMATCH ANALYSIS:")
    print("=" * 60)

    ref_map = {r["case_id"]: r for r in ref_rows}
    status_mismatches = []
    step_mismatches = []

    for pred in pred_rows:
        cid = pred["case_id"]
        ref = ref_map.get(cid)
        if not ref:
            continue

        p_stat = pred["deletion_status"]
        r_stat = ref["deletion_status"]
        if p_stat != r_stat:
            status_mismatches.append((cid, p_stat, r_stat))

        p_steps = json.loads(pred["steps_json"])
        r_steps = json.loads(ref["steps_json"])

        # Compare step details
        p_tuples = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in p_steps]
        r_tuples = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in r_steps]

        if p_tuples != r_tuples:
            step_mismatches.append((cid, p_tuples, r_tuples))

    print(f"Status Mismatches ({len(status_mismatches)} / {len(sample_requests)}):")
    for cid, p_stat, r_stat in status_mismatches:
        print(f"  {cid}: Predicted {p_stat} vs Reference {r_stat}")

    print(f"\nStep Mismatches ({len(step_mismatches)} / {len(sample_requests)}):")
    for cid, p_t, r_t in step_mismatches[:10]:
        print(f"\n--- {cid} ---")
        p_set = set(p_t)
        r_set = set(r_t)
        missing_in_pred = r_set - p_set
        extra_in_pred = p_set - r_set
        if missing_in_pred:
            print(f"  Missing from prediction ({len(missing_in_pred)}):")
            for item in missing_in_pred:
                print(f"    - {item}")
        if extra_in_pred:
            print(f"  Extra in prediction ({len(extra_in_pred)}):")
            for item in extra_in_pred:
                print(f"    + {item}")


if __name__ == "__main__":
    run_benchmark()
