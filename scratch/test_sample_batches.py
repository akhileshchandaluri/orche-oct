import sys, os, csv, json, re
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions

# Test FIFO queue assignment
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
acts = list(csv.DictReader(open("dataset/system_activity.csv", encoding="utf-8")))

# For each request, find candidate pool of account_service DELETE_RECORD events
# Group requests by reported_at and reported_status
from collections import defaultdict
reqs_by_batch = defaultdict(list)
for r in sample_reqs:
    rep_at = r.get("reported_at", "").strip()
    status = r.get("reported_status", "").strip()
    reqs_by_batch[(rep_at, status)].append(r)

print(f"Batches in sample_deletion_requests:")
for (rep_at, status), rlist in reqs_by_batch.items():
    if len(rlist) > 1:
        print(f"  Batch {rep_at} | {status} | count={len(rlist)}: {[r['case_id'] for r in rlist]}")
