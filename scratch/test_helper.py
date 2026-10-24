import csv
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))

# Pre-extract known account mappings from evidence files
known_account_to_email = {}
# 1. From trace logs:
trace_log = PROJECT_ROOT / "dataset" / "evidence" / "logs" / "resource_lookup_trace_20260926_103856.log"
if trace_log.exists():
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if "service=account_service" in line and "lookup_key=" in line:
                import re
                res = re.search(r"resource_id=(account_[0-9]+)", line)
                key = re.search(r"lookup_key=([^\s]+)", line)
                if res and key and key.group(1) != "null":
                    known_account_to_email[res.group(1)] = key.group(1).lower()

# 2. From handover txt:
handover_txt = PROJECT_ROOT / "dataset" / "evidence" / "records" / "customer_account_handover_20261001.txt"
if handover_txt.exists():
    with open(handover_txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1] == "account_service":
                known_account_to_email[parts[2]] = parts[5].lower()

# 3. From snapshot bundles:
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

def resolve_workflow_resources(req_email, uid, requested_at, reported_at, reported_status, known_user_resources):
    """Generalizable workflow resource resolution from system_activity."""
    req_email = req_email.lower()
    
    # Window worker events
    w_acts = [
        a for a in activities
        if a["source_system"] == "deletion_worker"
        and requested_at <= a["event_time"] <= reported_at
    ]
    
    resolved_account = None
    resolved_analytics = None
    
    # 1. Analytics
    an_acts = [a for a in w_acts if a["target_system"] == "analytics_platform" and a["event_type"] == "ANONYMIZE_RECORD"]
    if len(an_acts) == 1:
        resolved_analytics = an_acts[0]["resource_id"]
    elif len(an_acts) > 1:
        # Check if one of them is in the same thread as known_user_resources
        # Thread distance: within 15 minutes of a known user resource
        best_an = None
        min_dist = float("inf")
        for an in an_acts:
            an_t = datetime.fromisoformat(an["event_time"].replace("Z", "+00:00"))
            for r_res in known_user_resources:
                # Find event for this known resource
                for a in w_acts:
                    if a["resource_id"] == r_res:
                        r_t = datetime.fromisoformat(a["event_time"].replace("Z", "+00:00"))
                        dist = abs((an_t - r_t).total_seconds())
                        if dist < min_dist:
                            min_dist = dist
                            best_an = an["resource_id"]
        if best_an and min_dist <= 1800: # within 30 min
            resolved_analytics = best_an
        else:
            # Fallback: if user is earlier in the window
            resolved_analytics = an_acts[0]["resource_id"]

    # 2. Account
    acc_acts = [a for a in w_acts if a["target_system"] == "account_service" and a["event_type"] == "DELETE_RECORD"]
    valid_accs = [
        a for a in acc_acts
        if a["resource_id"] not in known_account_to_email or known_account_to_email[a["resource_id"]] == req_email
    ]
    
    # Status match
    if reported_status == "COMPLETE":
        matched = [a for a in valid_accs if a.get("reported_result") == "SUCCESS"]
    else:
        matched = [a for a in valid_accs if a.get("reported_result") in ["FAILED", "PARTIAL"]]
    
    pool = matched if matched else valid_accs
    
    if len(pool) == 1:
        resolved_account = pool[0]["resource_id"]
    elif len(pool) > 1:
        # Check thread proximity with known resources or resolved analytics
        anchor_resources = list(known_user_resources)
        if resolved_analytics:
            anchor_resources.append(resolved_analytics)
            
        best_acc = None
        min_dist = float("inf")
        for acc in pool:
            acc_t = datetime.fromisoformat(acc["event_time"].replace("Z", "+00:00"))
            for r_res in anchor_resources:
                for a in w_acts:
                    if a["resource_id"] == r_res:
                        r_t = datetime.fromisoformat(a["event_time"].replace("Z", "+00:00"))
                        dist = abs((acc_t - r_t).total_seconds())
                        if dist < min_dist:
                            min_dist = dist
                            best_acc = acc["resource_id"]
        if best_acc and min_dist <= 3600:
            resolved_account = best_acc
        else:
            resolved_account = max(pool, key=lambda a: a["event_time"])["resource_id"]

    return resolved_account, resolved_analytics

# Test across all 32 sample requests
with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

with open(PROJECT_ROOT / "dataset" / "sample_output.csv", "r", encoding="utf-8") as f:
    refs = {r["case_id"]: r for r in csv.DictReader(f)}

print("\n--- Evaluating Workflow Resolution on Sample Cases ---")
correct_accounts = 0
correct_analytics = 0
total_tested = 0

for req in sample_requests:
    cid = req["case_id"]
    email = req["email"]
    req_at = req["requested_at"]
    rep_at = req.get("reported_at", "")
    rep_status = req.get("reported_status", "")
    
    ref_steps = json.loads(refs[cid]["steps_json"])
    ref_acc = [s["resource_id"] for s in ref_steps if s["system_id"] == "account_service"]
    ref_an = [s["resource_id"] for s in ref_steps if s["system_id"] == "analytics_platform"]
    
    # User's other known resources from non-account, non-analytics steps
    known_user_res = [s["resource_id"] for s in ref_steps if s["system_id"] not in ["account_service", "analytics_platform"]]
    
    res_acc, res_an = resolve_workflow_resources(email, "", req_at, rep_at, rep_status, known_user_res)
    
    if ref_acc:
        exp_a = ref_acc[0]
        if res_acc == exp_a:
            correct_accounts += 1
        else:
            print(f"  {cid} Account mismatch: res={res_acc} vs exp={exp_a}")
    
    if ref_an:
        exp_an = ref_an[0]
        if res_an == exp_an:
            correct_analytics += 1
        else:
            print(f"  {cid} Analytics mismatch: res={res_an} vs exp={exp_an}")

print(f"\nAccount accuracy on tested cases: {correct_accounts} correct")
print(f"Analytics accuracy on tested cases: {correct_analytics} correct")
