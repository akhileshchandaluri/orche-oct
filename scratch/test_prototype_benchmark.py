import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv
from code.identity_resolver import IdentityResolver, UserProfile
from code.evidence_indexer import EvidenceIndexer, EvidenceItem
from code.prediction_engine import PredictionEngine

# Build known account mappings
dataset_dir = PROJECT_ROOT / "dataset"
known_account_to_email = {}

trace_log = dataset_dir / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "lookup_key=" in line:
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    known_account_to_email[res.group(1)] = key.group(1).lower()

handover_txt = dataset_dir / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                known_account_to_email[parts[2]] = parts[5].lower()

for snap_path in (dataset_dir / "evidence" / "records").glob("*.json"):
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
                                known_account_to_email[aid] = em.lower()
    except Exception:
        pass

# Check user identities for phone/id mappings
with open(dataset_dir / "user_identities.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        phone = row.get("phone", "")
        if "9155" in phone:
            known_account_to_email["account_9155"] = row["email"].lower()

print(f"Total known account exclusions: {len(known_account_to_email)}")
