import csv

with open("dataset/system_activity.csv", "r", encoding="utf-8") as f:
    acts = list(csv.DictReader(f))

# Let's inspect the entire deletion_worker activity list
w_acts = [a for a in acts if a["source_system"] == "deletion_worker"]
for a in w_acts:
    print(f"{a['activity_id']} | {a['event_time']} | {a['target_system']} | {a['event_type']} | {a['resource_id']} | {a['details']}")
