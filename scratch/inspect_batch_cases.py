import csv, json

truth = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}
sample_reqs = {r["case_id"]: r for r in csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8"))}

for cid in ["case_25", "case_26", "case_27", "case_28"]:
    print(f"\n--- {cid} ---")
    print("Request:", sample_reqs[cid])
    print("Truth Steps:")
    for s in truth[cid]:
        print(f"  {s}")
