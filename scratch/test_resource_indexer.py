import json
import csv
from pathlib import Path

ds = Path("dataset")
ev_files = {}
with open(ds / "evidence_files.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        ev_files[r["file_path"]] = (r["file_id"], r["captured_at"])

res_map = {}

# Check JSON files
for jf in (ds / "evidence" / "records").glob("*.json"):
    rel = f"evidence/records/{jf.name}"
    ev_id, cap = ev_files.get(rel, ("", ""))
    try:
        with open(jf, "r", encoding="utf-8") as f:
            d = json.load(f)
            if "service_exports" in d:
                for sname, sval in d["service_exports"].items():
                    if isinstance(sval, dict):
                        for grp, lst in sval.items():
                            if isinstance(lst, list):
                                for item in lst:
                                    rid = item.get("resource_id")
                                    if rid:
                                        res_map[rid] = (ev_id, cap, sname)
            if "snapshots" in d:
                for s in d["snapshots"]:
                    sname = s.get("data_store", "")
                    for rec in s.get("records", []):
                        rid = rec.get("resource_id")
                        if rid:
                            res_map[rid] = (ev_id, cap, sname)
    except Exception:
        pass

# Check SQL files
for sf in (ds / "evidence" / "databases").glob("*.sql"):
    rel = f"evidence/databases/{sf.name}"
    ev_id, cap = ev_files.get(rel, ("", ""))
    with open(sf, "r", encoding="utf-8") as f:
        for line in f:
            if "account_" in line:
                for part in line.split():
                    if part.startswith("account_"):
                        rid = part.strip("\"',;) ")
                        if rid not in res_map:
                            res_map[rid] = (ev_id, cap, "account_service")

# Check logs
for lf in (ds / "evidence" / "logs").glob("*.log"):
    rel = f"evidence/logs/{lf.name}"
    ev_id, cap = ev_files.get(rel, ("", ""))
    with open(lf, "r", encoding="utf-8") as f:
        for line in f:
            if "resource_id=" in line:
                for part in line.split():
                    if part.startswith("resource_id="):
                        rid = part.split("=", 1)[1].strip("\"',;) ")
                        if rid.startswith("account_") and rid not in res_map:
                            res_map[rid] = (ev_id, cap, "account_service")

print("Indexed resources in evidence files:", len(res_map))
for acc in ["account_6440", "account_3136", "account_5684", "account_3866", "account_5482", "account_4857", "account_7566"]:
    print(acc, "->", res_map.get(acc))
