import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Let's inspect the sample benchmark with improved logic
from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv

engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")

# Load sample requests and reference output
req_file = PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv"
ref_file = PROJECT_ROOT / "dataset" / "sample_output.csv"

with open(req_file, mode="r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

with open(ref_file, mode="r", encoding="utf-8") as f:
    ref_rows = list(csv.DictReader(f))

print(f"Loaded {len(sample_requests)} requests.")
