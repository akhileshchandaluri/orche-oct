import sys, os, csv, json, re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine
from code.evidence_indexer import EvidenceIndexer, EvidenceItem

indexer = EvidenceIndexer("dataset")

# Find all anonymized records across evidence files
anonymized_evidence = {} # resource_id -> (evidence_id, captured_at)

for fid, info in indexer.manifest.items():
    fpath = Path("dataset") / info["file_path"]
    if not fpath.exists():
        continue
    rel = info["file_path"]
    cap = info["captured_at"]

    if rel.endswith(".json"):
        try:
            d = json.load(open(fpath, encoding="utf-8"))
            if isinstance(d, dict) and "service_exports" in d:
                profiles = d["service_exports"].get("analytics_platform", {}).get("profiles", [])
                for rec in profiles:
                    if rec.get("email") is None and rec.get("customer_reference") is None:
                        rid = rec.get("resource_id")
                        if rid:
                            anonymized_evidence[rid] = (fid, cap)
            if isinstance(d, dict) and "snapshots" in d:
                for s in d.get("snapshots", []):
                    if s.get("data_store") == "analytics_platform":
                        for rec in s.get("records", []):
                            if rec.get("email") is None and rec.get("user_id") is None and rec.get("phone") is None:
                                rid = rec.get("resource_id")
                                if rid:
                                    anonymized_evidence[rid] = (fid, cap)
            for rec in d.get("analytics_profiles", []) or d.get("records", []):
                if rec.get("email") is None and rec.get("user_id") is None:
                    rid = rec.get("resource_id")
                    if rid:
                        anonymized_evidence[rid] = (fid, cap)
        except Exception:
            pass

    elif rel.endswith(".log"):
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    if "service=analytics_platform" in line and ("event=analytics_profile_read_completed" in line or "analytics_profile" in line):
                        m_res = re.search(r"resource_id=(analytics_[0-9]+)", line)
                        if m_res and "customer_reference=null" in line and "email=null" in line:
                            anonymized_evidence[m_res.group(1)] = (fid, cap)
        except Exception:
            pass

print(f"Grounded anonymized analytics profiles in evidence ({len(anonymized_evidence)}):")
for r, (ev, cap) in sorted(anonymized_evidence.items()):
    print(f"  {r} -> {ev} (captured {cap})")
