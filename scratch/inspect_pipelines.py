import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "dataset" / "system_activity.csv", "r", encoding="utf-8") as f:
    activities = list(csv.DictReader(f))

# Let's inspect the sub-sequences on 2026-08-30 and 2026-09-02
for date_str in ["2026-08-30", "2026-09-02"]:
    acts = [a for a in activities if a["source_system"] == "deletion_worker" and date_str in a["event_time"]]
    print(f"\n=== Events on {date_str} ({len(acts)}) ===")
    for a in acts:
        print(f"  {a['event_time']} | {a['target_system']} | {a['resource_id']} | {a['reported_result']}")
