import csv, json
from datetime import datetime, timedelta
from collections import defaultdict

requests = list(csv.DictReader(open("dataset/deletion_requests.csv", encoding="utf-8")))
acts = list(csv.DictReader(open("dataset/system_activity.csv", encoding="utf-8")))

# Find all worker ANONYMIZE_RECORD events
worker_anonymize_acts = [
    a for a in acts
    if a["source_system"] == "deletion_worker" and a["event_type"] == "ANONYMIZE_RECORD"
]

print(f"Total deletion worker ANONYMIZE_RECORD events: {len(worker_anonymize_acts)}")
for a in worker_anonymize_acts:
    print(f"  {a['event_time']} | {a['resource_id']} | details: {a.get('details')}")
