import csv
import json
import sys
import importlib
from pathlib import Path

PROJECT_ROOT = Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.evaluator import evaluate_predictions

truth_path = PROJECT_ROOT / "dataset" / "sample_output.csv"
sample_requests = list(csv.DictReader(open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", encoding="utf-8")))

print("=== 1. Evaluating pre-saved CSVs against sample_output.csv ===")
csv_candidates = [
    ("baseline_pre_eval_repair/test_pred_improved.csv", "backup/baseline_pre_eval_repair/code/evaluation/test_pred_improved.csv"),
    ("baseline_pre_eval_repair/scratch_pred_sample.csv", "backup/baseline_pre_eval_repair/code/evaluation/scratch_pred_sample.csv"),
    ("baseline_pre_priority_fixes/test_pred_improved.csv", "backup/baseline_pre_priority_fixes/code/evaluation/test_pred_improved.csv"),
    ("baseline_pre_priority_fixes/scratch_pred_sample.csv", "backup/baseline_pre_priority_fixes/code/evaluation/scratch_pred_sample.csv"),
]

for label, cpath in csv_candidates:
    p = PROJECT_ROOT / cpath
    if not p.exists():
        print(f"[{label}] NOT FOUND: {cpath}")
        continue
    try:
        metrics = evaluate_predictions(truth_path, p)
        matches = int(round(metrics.row_level_accuracy * metrics.total_truth_cases))
        print(f"[{label}] -> Cases: {metrics.total_truth_cases}, Status: {metrics.case_status_accuracy*100:.2f}%, Exact Row: {metrics.row_level_accuracy*100:.2f}% ({matches}/32), Prec: {metrics.step_precision*100:.2f}%, Rec: {metrics.step_recall*100:.2f}%, F1: {metrics.step_f1*100:.2f}%, Seq: {metrics.sequence_accuracy*100:.2f}%")
    except Exception as e:
        print(f"[{label}] Error: {e}")

print("\n=== 2. Running PredictionEngine directly from each codebase ===")

def run_and_eval_engine(label, code_dir):
    tmp_out = PROJECT_ROOT / "scratch" / f"pred_{label}.csv"
    
    import subprocess
    cmd = [
        sys.executable,
        "-c",
        f"""
import sys, csv, json
from pathlib import Path
root = Path(r'{PROJECT_ROOT}')
sys.path.insert(0, str(root / r'{code_dir}'))
sys.path.insert(0, str(root))

for m in list(sys.modules.keys()):
    if m.startswith('code'):
        del sys.modules[m]

from code.prediction_engine import PredictionEngine
engine = PredictionEngine(dataset_dir=root / 'dataset')
reqs = list(csv.DictReader(open(root / 'dataset' / 'sample_deletion_requests.csv', encoding='utf-8')))

rows = []
for r in reqs:
    res = engine.audit_case(r)
    rows.append({{
        'case_id': res['case_id'],
        'deletion_status': res['deletion_status'],
        'steps_json': res['steps_json'],
    }})

with open(r'{tmp_out}', 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['case_id', 'deletion_status', 'steps_json'])
    w.writeheader()
    w.writerows(rows)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[{label}] Generation failed: {res.stderr}")
        return

    metrics = evaluate_predictions(truth_path, tmp_out)
    matches = int(round(metrics.row_level_accuracy * metrics.total_truth_cases))
    print(f"[{label}] -> Cases: {metrics.total_truth_cases}, Status: {metrics.case_status_accuracy*100:.2f}%, Exact Row: {metrics.row_level_accuracy*100:.2f}% ({matches}/32), Prec: {metrics.step_precision*100:.2f}%, Rec: {metrics.step_recall*100:.2f}%, F1: {metrics.step_f1*100:.2f}%, Seq: {metrics.sequence_accuracy*100:.2f}%")
    return tmp_out, metrics

run_and_eval_engine("baseline_pre_eval_repair", "backup/baseline_pre_eval_repair")
run_and_eval_engine("baseline_pre_priority_fixes", "backup/baseline_pre_priority_fixes")
run_and_eval_engine("current_prompt3", ".")
