import json

with open("dataset/evidence/records/service_resource_export_20260915_120000.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("Keys:", d.keys())
sexp = d.get("service_exports", {})
for k in sexp.keys():
    print("service:", k, "subkeys:", sexp[k].keys() if isinstance(sexp[k], dict) else type(sexp[k]))
    if isinstance(sexp[k], dict):
        for subk, items in sexp[k].items():
            if isinstance(items, list):
                print(f"  {k}.{subk} len={len(items)}")
                for item in items[:5]:
                    print("   ", item)
