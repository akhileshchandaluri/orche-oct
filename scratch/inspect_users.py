import csv

with open("dataset/system_activity.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

for u in ["user_03", "user_04", "user_21", "user_25", "user_26", "user_27", "user_28"]:
    print(f"=== {u} ===")
    matches = [r for r in rows if u in r.get("details", "") or u == r.get("resource_id")]
    for m in matches:
        aid = m["activity_id"]
        et = m["event_time"]
        src = m["source_system"]
        tgt = m["target_system"]
        ev = m["event_type"]
        res = m["resource_id"]
        det = m["details"]
        print(f"  {aid} | {et} | {src} -> {tgt} | {ev} | {res} | {det}")
