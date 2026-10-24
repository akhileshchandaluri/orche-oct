import csv
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
DATASET_DIR = PROJECT_ROOT / "dataset"

with open(DATASET_DIR / "system_activity.csv", "r", encoding="utf-8") as f:
    acts = list(csv.DictReader(f))

with open(DATASET_DIR / "sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

# Test for cases 03, 04, 21, 26, 27
test_cids = ['case_03', 'case_04', 'case_21', 'case_26', 'case_27']

for req in sample_reqs:
    cid = req['case_id']
    if cid not in test_cids:
        continue
    req_t = req['requested_at']
    rep_t = req['reported_at']
    # Worker acts in window
    w = [a for a in acts if a['source_system'] == 'deletion_worker' and req_t <= a['event_time'] <= rep_t]
    analytics_acts = [a for a in w if a['target_system'] == 'analytics_platform']
    print(f"{cid} ({req['email']}): analytics_acts={[a['resource_id'] for a in analytics_acts]}")
