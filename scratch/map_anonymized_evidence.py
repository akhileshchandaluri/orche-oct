import sys, os, csv, json, re
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evidence_indexer import EvidenceIndexer, EvidenceItem

# Load sample requests and system activity
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
acts = list(csv.DictReader(open("dataset/system_activity.csv", encoding="utf-8")))
truth = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}

# Map all anonymized records in evidence files
# evidence_94: resource_lookup_trace_20260926_103856.log
# evidence_56: customer_analytics_report_20260907.json
# evidence_92: service_resource_export_20260915_114455.json

anonymized_evidence = {}
# Check evidence_94
with open("dataset/evidence/logs/resource_lookup_trace_20260926_103856.log", "r", encoding="utf-8") as f:
    for line in f:
        if "service=analytics_platform" in line and "event=analytics_profile_read_completed" in line:
            m_res = re.search(r"resource_id=(analytics_[0-9]+)", line)
            if m_res and "customer_reference=null" in line and "email=null" in line:
                anonymized_evidence[m_res.group(1)] = "evidence_94"

# Check evidence_56
with open("dataset/evidence/records/customer_analytics_report_20260907.json", "r", encoding="utf-8") as f:
    d = json.load(f)
    for rec in d.get("analytics_profiles", []) or d.get("records", []):
        if rec.get("email") is None and rec.get("user_id") is None:
            anonymized_evidence[rec.get("resource_id")] = "evidence_56"

# Check evidence_92
with open("dataset/evidence/records/service_resource_export_20260915_114455.json", "r", encoding="utf-8") as f:
    d = json.load(f)
    profiles = d.get("service_exports", {}).get("analytics_platform", {}).get("profiles", [])
    for rec in profiles:
        if rec.get("email") is None and rec.get("customer_reference") is None:
            anonymized_evidence[rec.get("resource_id")] = "evidence_92"

print(f"Known grounded anonymized analytics resources in evidence: {len(anonymized_evidence)}")
for k, v in anonymized_evidence.items():
    print(f"  {k} -> {v}")
