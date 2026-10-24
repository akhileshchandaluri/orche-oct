import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.evidence_indexer import EvidenceIndexer, EvidenceItem
from code.identity_resolver import IdentityResolver, UserProfile
from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv

# Let's inspect PredictionEngine
engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")

# Load known account mappings
known_accounts = {}
trace_log = PROJECT_ROOT / "dataset" / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "lookup_key=" in line:
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    known_accounts[res.group(1)] = key.group(1).lower()

handover_txt = PROJECT_ROOT / "dataset" / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                known_accounts[parts[2]] = parts[5].lower()

for snap_path in (PROJECT_ROOT / "dataset" / "evidence" / "records").glob("*.json"):
    try:
        with open(snap_path, "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict) and "snapshots" in d:
                for s in d["snapshots"]:
                    if s.get("data_store") == "account_service":
                        for rec in s.get("records", []):
                            aid = rec.get("resource_id")
                            em = rec.get("email")
                            if aid and em:
                                known_accounts[aid] = em.lower()
    except Exception:
        pass

print(f"Known accounts loaded: {len(known_accounts)}")
