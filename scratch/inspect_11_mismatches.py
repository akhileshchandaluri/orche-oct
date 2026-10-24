import sys, os, csv, json, re
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.identity_resolver import IdentityResolver, UserProfile
from code.evidence_indexer import EvidenceIndexer, EvidenceItem
from code.prediction_engine import PredictionEngine, EvidenceForensicsEngine, PolicyMapper
from code.evaluation.evaluator import evaluate_predictions

# Let's inspect the 11 mismatched cases from Prompt 4 baseline:
truth = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))

engine_base = PredictionEngine(dataset_dir="dataset", enable_groq=False)
base_preds = {}
for r in sample_reqs:
    res = engine_base.audit_case(r)
    base_preds[res["case_id"]] = (res["deletion_status"], json.loads(res["steps_json"]))

mismatched = [cid for cid in sorted(truth.keys()) if base_preds[cid] != truth[cid]]
print(f"Mismatched in baseline ({len(mismatched)}): {mismatched}")

# For each mismatched case, print what's different:
for cid in mismatched:
    pred_status, pred_steps = base_preds[cid]
    true_status, true_steps = truth[cid]
    print(f"\n--- {cid} ---")
    if pred_status != true_status:
        print(f"  Status diff: pred={pred_status} vs true={true_status}")
    print(f"  Pred steps ({len(pred_steps)}):")
    for s in pred_steps:
        print(f"    {s}")
    print(f"  True steps ({len(true_steps)}):")
    for s in true_steps:
        print(f"    {s}")
