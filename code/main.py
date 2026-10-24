"""Main production pipeline entry point for Ghost Data Still Exists.

Executes offline hybrid prediction engine on all 518 deletion requests in
dataset/deletion_requests.csv and compiles the verified output.csv adhering
strictly to the competition schema and canonical constraints.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from code.evaluation.schema_validator import validate_csv
from code.prediction_engine import PredictionEngine


def run_full_pipeline(
    dataset_dir: Path,
    output_file: Path,
    enable_groq: Optional[bool] = None,
) -> None:
    start_time = time.time()
    print("================================================================================")
    print("ORCHESTRATE: GHOST DATA STILL EXISTS - FULL AUDIT PIPELINE")
    print("================================================================================")
    print(f"Dataset root:  {dataset_dir}")
    print(f"Output target: {output_file}")

    # Load deletion requests
    requests_path = dataset_dir / "deletion_requests.csv"
    if not requests_path.exists():
        raise FileNotFoundError(f"Missing deletion requests file at {requests_path}")

    with open(requests_path, mode="r", encoding="utf-8") as f:
        requests = list(csv.DictReader(f))

    print(f"Loaded {len(requests)} deletion requests to audit.")

    # Initialize modular hybrid engine
    engine = PredictionEngine(dataset_dir=dataset_dir, enable_groq=enable_groq)
    groq_status = "ENABLED (Selective Reasoning)" if engine.groq_reasoner.is_available() else "DISABLED / OFFLINE FALLBACK"
    print(f"Groq Reasoning Assistant: {groq_status} (Model: {engine.groq_reasoner.model})")

    results = []
    status_counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}

    for idx, req in enumerate(requests, start=1):
        case_id = req["case_id"]
        audit_res = engine.audit_case(req)

        results.append({
            "case_id": audit_res["case_id"],
            "deletion_status": audit_res["deletion_status"],
            "steps_json": audit_res["steps_json"],
        })
        status_counts[audit_res["deletion_status"]] = status_counts.get(audit_res["deletion_status"], 0) + 1

        if idx % 100 == 0 or idx == len(requests):
            print(f"Processed {idx:3d} / {len(requests)} requests...")

    # Sort results canonically by case_id number
    def parse_case_num(cid: str) -> int:
        parts = cid.split("_")
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 999999

    results.sort(key=lambda r: parse_case_num(r["case_id"]))

    # Write output.csv
    with open(output_file, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        writer.writerows(results)

    elapsed = time.time() - start_time
    print(f"\nWrote {len(results)} rows to {output_file} in {elapsed:.2f} seconds.")
    print("\nSummary Status Distribution:")
    for status, count in status_counts.items():
        pct = (count / len(results)) * 100
        print(f"  {status:15s}: {count:4d} ({pct:5.1f}%)")

    # Report Groq reasoning metrics
    metrics = engine.groq_reasoner.get_metrics_summary()
    print("\nGroq Reasoning Assistant Metrics:")
    print(f"  Calls: {metrics['total_calls']} (Successful: {metrics['successful_calls']}, Failed: {metrics['failed_calls']}, Fallbacks: {metrics['fallback_calls']})")
    print(f"  Tokens: {metrics['total_tokens']} (Prompt: {metrics['total_prompt_tokens']}, Completion: {metrics['total_completion_tokens']})")
    print(f"  Latency: {metrics['total_latency_seconds']}s total ({metrics['average_latency_seconds']}s avg)")

    # Validate output schema
    print("\nExecuting strict schema and policy validation on output.csv...")
    report = validate_csv(output_file, expected_rows=518)
    print(report.summary())
    if not report.is_valid:
        print(f"Errors detected ({len(report.errors)}):")
        for err in report.errors[:10]:
            print(f"  - Case {err.case_id} [Step {err.step_no}]: {err.message}")
        sys.exit(1)
    else:
        print("ALL 518 ROWS PASSED STRICT SCHEMA AND POLICY VALIDATION WITH ZERO ERRORS.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Prediction Pipeline")
    parser.add_argument("--disable-groq", action="store_true", help="Force disable Groq reasoning (100% offline deterministic)")
    parser.add_argument("--groq", action="store_true", help="Enable Groq reasoning assistant")
    args = parser.parse_args()

    enable_groq = False if args.disable_groq else (True if args.groq else None)

    dataset_dir = PROJECT_ROOT / "dataset"
    output_file = PROJECT_ROOT / "output.csv"
    run_full_pipeline(dataset_dir, output_file, enable_groq=enable_groq)

