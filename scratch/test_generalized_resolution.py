import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine
import csv

engine = PredictionEngine(dataset_dir="dataset")
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))

for req in sample_reqs:
    res = engine.audit_case(req)
    print(f"{req['case_id']} ({req['email']}): {res['deletion_status']}")
