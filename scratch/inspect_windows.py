import csv

with open("dataset/system_activity.csv", "r", encoding="utf-8") as f:
    acts = list(csv.DictReader(f))

for window in [("2026-08-30T11:30:00Z", "2026-08-30T11:33:00Z"), ("2026-09-02T11:30:00Z", "2026-09-02T11:33:00Z")]:
    print(f"=== Window {window} ===")
    for a in acts:
        if window[0] <= a["event_time"] <= window[1]:
            print(f"  {a['activity_id']} | {a['event_time']} | {a['source_system']} -> {a['target_system']} | {a['event_type']} | {a['resource_id']} | {a['details']}")
