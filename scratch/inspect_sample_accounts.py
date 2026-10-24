import csv
import json

ref_rows = list(csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8")))
sample_reqs = {r["case_id"]: r for r in csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8"))}

for r in ref_rows:
    cid = r["case_id"]
    stat = r["deletion_status"]
    req = sample_reqs[cid]
    steps = json.loads(r["steps_json"])
    acc_steps = [s for s in steps if s["system_id"] == "account_service"]
    acc_info = [(s["resource_id"], s["operation"], s["evidence_id"]) for s in acc_steps]
    print(f"{cid} ({req['email']}): status={stat} -> {acc_info}")
