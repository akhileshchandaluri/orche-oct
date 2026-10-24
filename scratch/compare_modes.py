import sys, os, time, csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions

dataset_dir = Path("dataset")
sample_reqs_path = dataset_dir / "sample_deletion_requests.csv"
sample_truth_path = dataset_dir / "sample_output.csv"

with open(sample_reqs_path, "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

# ----------------------------------------------------
# Mode 1: Deterministic (Groq Disabled)
# ----------------------------------------------------
print("====================================================")
print("RUNNING BENCHMARK: MODE 1 (GROQ DISABLED - DETERMINISTIC)")
print("====================================================")
engine_det = PredictionEngine(dataset_dir=dataset_dir, enable_groq=False)
t0 = time.time()
det_rows = []
for req in sample_reqs:
    res = engine_det.audit_case(req)
    det_rows.append({
        "case_id": res["case_id"],
        "deletion_status": res["deletion_status"],
        "steps_json": res["steps_json"],
    })
elapsed_det = time.time() - t0

det_csv_path = Path("scratch/pred_deterministic.csv")
with open(det_csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
    writer.writeheader()
    writer.writerows(det_rows)

eval_det = evaluate_predictions(det_csv_path, sample_truth_path)
det_metrics = engine_det.groq_reasoner.get_metrics_summary()

print(f"Elapsed: {elapsed_det:.2f}s")
print(f"Status Accuracy:   {eval_det.case_status_accuracy * 100:.2f}%")
print(f"Exact-Row Accuracy:{eval_det.row_level_accuracy * 100:.2f}% ({eval_det.evaluated_cases - len([c for c in eval_det.case_results if not c.exact_row_match])}/{eval_det.total_truth_cases})")
print(f"Step Precision:    {eval_det.step_precision * 100:.2f}%")
print(f"Step Recall:       {eval_det.step_recall * 100:.2f}%")
print(f"Step F1:           {eval_det.step_f1 * 100:.2f}%")
print(f"Sequence Accuracy: {eval_det.sequence_accuracy * 100:.2f}%")
print(f"Groq Calls:        {det_metrics['total_calls']}")

# ----------------------------------------------------
# Mode 2: Groq Enabled (Selective Reasoning)
# ----------------------------------------------------
print("\n====================================================")
print("RUNNING BENCHMARK: MODE 2 (GROQ ENABLED)")
print("====================================================")
engine_groq = PredictionEngine(dataset_dir=dataset_dir, enable_groq=True)
t0 = time.time()
groq_rows = []
for req in sample_reqs:
    res = engine_groq.audit_case(req)
    groq_rows.append({
        "case_id": res["case_id"],
        "deletion_status": res["deletion_status"],
        "steps_json": res["steps_json"],
    })
elapsed_groq = time.time() - t0

groq_csv_path = Path("scratch/pred_groq_enabled.csv")
with open(groq_csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
    writer.writeheader()
    writer.writerows(groq_rows)

eval_groq = evaluate_predictions(groq_csv_path, sample_truth_path)
groq_metrics = engine_groq.groq_reasoner.get_metrics_summary()

print(f"Elapsed: {elapsed_groq:.2f}s")
print(f"Status Accuracy:   {eval_groq.case_status_accuracy * 100:.2f}%")
print(f"Exact-Row Accuracy:{eval_groq.row_level_accuracy * 100:.2f}% ({eval_groq.evaluated_cases - len([c for c in eval_groq.case_results if not c.exact_row_match])}/{eval_groq.total_truth_cases})")
print(f"Step Precision:    {eval_groq.step_precision * 100:.2f}%")
print(f"Step Recall:       {eval_groq.step_recall * 100:.2f}%")
print(f"Step F1:           {eval_groq.step_f1 * 100:.2f}%")
print(f"Sequence Accuracy: {eval_groq.sequence_accuracy * 100:.2f}%")
print(f"Groq Calls:        {groq_metrics['total_calls']} (Successful: {groq_metrics['successful_calls']}, Tokens: {groq_metrics['total_tokens']})")
