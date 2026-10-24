import sys, os, csv, json, re, textwrap
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine, EvidenceForensicsEngine
from code.evaluation.evaluator import evaluate_predictions

def test_candidate_selection(use_min=False):
    import inspect
    lines = inspect.getsource(EvidenceForensicsEngine.resolve_primary_account_id)
    dedented = textwrap.dedent(lines)
    if use_min:
        patched_code = dedented.replace('best_candidate = max(candidate_pool, key=lambda a: a["event_time"])',
                                        'best_candidate = min(candidate_pool, key=lambda a: a["event_time"])')
    else:
        patched_code = dedented

    sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
    truth = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}

    from unittest.mock import patch
    loc = {}
    exec(patched_code, EvidenceForensicsEngine.resolve_primary_account_id.__globals__, loc)
    
    with patch.object(EvidenceForensicsEngine, "resolve_primary_account_id", new=loc["resolve_primary_account_id"]):
        eng = PredictionEngine(dataset_dir="dataset", enable_groq=False)
        mismatches = []
        for r in sample_reqs:
            cid = r["case_id"]
            res = eng.audit_case(r)
            pred = (res["deletion_status"], json.loads(res["steps_json"]))
            if pred != truth[cid]:
                mismatches.append(cid)
        print(f"Use min: {use_min} -> Mismatches ({len(mismatches)}): {mismatches}")

test_candidate_selection(use_min=False)
test_candidate_selection(use_min=True)
