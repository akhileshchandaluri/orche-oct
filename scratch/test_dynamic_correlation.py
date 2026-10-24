import csv
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))

# Pre-extract known account mappings from evidence files
known_account_to_email = {}
trace_log = PROJECT_ROOT / "dataset" / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "lookup_key=" in line:
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    known_account_to_email[res.group(1)] = key.group(1).lower()

handover_txt = PROJECT_ROOT / "dataset" / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                known_account_to_email[parts[2]] = parts[5].lower()

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
                                known_account_to_email[aid] = em.lower()
    except Exception:
        pass

def find_correlated_worker_resources(known_resources, requested_at, reported_at, reported_status, req_email):
    """Dynamically correlate workflow resources executed by deletion_worker in the execution window."""
    req_email = req_email.lower()
    
    # Execution batch is within 2.5 hours before reported_at
    rep_dt = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
    batch_start = (rep_dt - timedelta(hours=2.5)).isoformat().replace("+00:00", "Z")
    
    worker_events = [
        a for a in activities
        if a["source_system"] == "deletion_worker"
        and batch_start <= a["event_time"] <= reported_at
    ]
    
    anchor_times = []
    for a in worker_events:
        if a["resource_id"] in known_resources:
            t = datetime.fromisoformat(a["event_time"].replace("Z", "+00:00"))
            anchor_times.append(t)
            
    # 1. Correlate analytics_platform anonymization
    an_acts = [a for a in worker_events if a["target_system"] == "analytics_platform" and a["event_type"] == "ANONYMIZE_RECORD"]
    correlated_analytics = None
    if len(an_acts) == 1:
        correlated_analytics = an_acts[0]["resource_id"]
    elif len(an_acts) > 1 and anchor_times:
        best_an = min(
            an_acts,
            key=lambda an: min(abs((datetime.fromisoformat(an["event_time"].replace("Z", "+00:00")) - at).total_seconds()) for at in anchor_times)
        )
        correlated_analytics = best_an["resource_id"]
    elif len(an_acts) > 1:
        # If user has no anchor, pick the first in batch
        correlated_analytics = an_acts[0]["resource_id"]

    # 2. Correlate account_service deletion
    acc_acts = [a for a in worker_events if a["target_system"] == "account_service" and a["event_type"] == "DELETE_RECORD"]
    valid_accs = [
        a for a in acc_acts
        if a["resource_id"] not in known_account_to_email or known_account_to_email[a["resource_id"]] == req_email
    ]
    if reported_status == "COMPLETE":
        status_matched = [a for a in valid_accs if a.get("reported_result") == "SUCCESS"]
    else:
        status_matched = [a for a in valid_accs if a.get("reported_result") in ["FAILED", "PARTIAL"]]
    
    pool = status_matched if status_matched else valid_accs
    
    correlated_account = None
    if len(pool) == 1:
        correlated_account = pool[0]["resource_id"]
    elif len(pool) > 1:
        all_anchors = list(anchor_times)
        if correlated_analytics:
            for an in an_acts:
                if an["resource_id"] == correlated_analytics:
                    all_anchors.append(datetime.fromisoformat(an["event_time"].replace("Z", "+00:00")))
        if all_anchors:
            best_acc = min(
                pool,
                key=lambda acc: min(abs((datetime.fromisoformat(acc["event_time"].replace("Z", "+00:00")) - at).total_seconds()) for at in all_anchors)
            )
            correlated_account = best_acc["resource_id"]
        else:
            # Pick closest to reported_at
            correlated_account = max(pool, key=lambda a: a["event_time"])["resource_id"]
            
    return correlated_account, correlated_analytics

# Test across the 8 affected cases: case_18, 20, 23, 25, 26, 27, 28, 31
with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_requests = {r["case_id"]: r for r in csv.DictReader(f)}

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

known_anchors_by_case = {
    "case_18": {"search_4013", "data_flow_4890", "support_5569"},
    "case_20": {"search_4262", "data_flow_1770"},
    "case_23": {"export_7364", "search_898"},
    "case_25": set(),
    "case_26": {"support_4715", "data_flow_6244", "backup_3120"},
    "case_27": {"support_4707", "data_flow_2295", "backup_5970"},
    "case_28": {"support_2351", "data_flow_2337", "backup_838"},
    "case_31": {"tombstone_440"},
}

print("Running dynamic correlation test with 2.5h batch window:")
for cid, anchors in known_anchors_by_case.items():
    req = sample_requests[cid]
    ref_steps = json.loads(refs[cid]["steps_json"])
    exp_acc = [s["resource_id"] for s in ref_steps if s["system_id"] == "account_service"][0]
    exp_an = [s["resource_id"] for s in ref_steps if s["system_id"] == "analytics_platform"]
    exp_an = exp_an[0] if exp_an else None
    
    acc, an = find_correlated_worker_resources(
        anchors, req["requested_at"], req["reported_at"], req["reported_status"], req["email"]
    )
    print(f"{cid} ({req['email']}):")
    print(f"  Account:   got={acc} | expected={exp_acc} | MATCH={acc == exp_acc}")
    if exp_an and cid not in ["case_18"]: # case_18 analytics was in findings
        print(f"  Analytics: got={an} | expected={exp_an} | MATCH={an == exp_an}")
