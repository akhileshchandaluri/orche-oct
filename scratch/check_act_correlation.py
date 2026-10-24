import csv
from datetime import datetime, timedelta

sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
activities = list(csv.DictReader(open("dataset/system_activity.csv", encoding="utf-8")))

acc_acts = [a for a in activities if a["target_system"] == "account_service" and a["event_type"] == "DELETE_RECORD"]

for req in sample_reqs:
    cid = req["case_id"]
    req_at = req["requested_at"]
    rep_at = req["reported_at"]
    stat = req["reported_status"]
    
    # Let's find deletion_worker activity around reported_at
    rep_dt = datetime.fromisoformat(rep_at.replace("Z", "+00:00"))
    w_start = (rep_dt - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    w_end = (rep_dt + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    
    matches = [a for a in acc_acts if w_start <= a["event_time"] <= w_end]
    print(f"{cid} (rep={rep_at}, stat={stat}): {[(a['resource_id'], a['event_time'], a['reported_result']) for a in matches]}")
