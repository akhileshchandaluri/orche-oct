import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))

target_cids = ['case_03', 'case_04', 'case_21', 'case_25', 'case_26', 'case_27', 'case_28']

for req in sample_reqs:
    cid = req['case_id']
    if cid in target_cids:
        req_at = req['requested_at']
        rep_at = req.get('reported_at', '')
        email = req['email']
        print(f"\n=======================================================")
        print(f"{cid} | email: {email} | requested: {req_at} | reported: {rep_at}")
        # Find all deletion_worker events around reported_at (e.g. within 2 hours before reported_at)
        batch = [a for a in activities if a['source_system'] == 'deletion_worker' and req_at <= a['event_time'] <= rep_at]
        print(f"deletion_worker events in window ({len(batch)}):")
        for b in batch:
            print(f"  {b['event_time']} | {b['event_type']} | {b['target_system']} | {b['resource_id']} | {b['reported_result']}")
