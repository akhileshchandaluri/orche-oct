import json

d = json.load(open('dataset/evidence/records/service_resource_export_20260915_114455.json', encoding='utf-8'))
se = d['service_exports']

for cid, uid, email in [
    ("case_25", "user_1167", "s.yoon04@gmail.com"),
    ("case_26", "user_1168", "almeida.mariana@gmail.com"),
    ("case_27", "user_1169", "ananya-nair@gmail.com"),
    ("case_28", "user_1170", "smartinez6461@gmail.com"),
]:
    print(f"\n=== {cid} ({uid}, {email}) ===")
    for sname, sdata in se.items():
        # find in sdata
        sdata_str = json.dumps(sdata)
        if uid in sdata_str or email in sdata_str:
            print(f"  Found in {sname}!")
            # inspect which items in sdata matched
            if isinstance(sdata, dict):
                for k, v in sdata.items():
                    v_str = json.dumps(v)
                    if uid in v_str or email in v_str:
                        print(f"    Key {k}: {v_str[:200]}...")
            elif isinstance(sdata, list):
                for item in sdata:
                    item_str = json.dumps(item)
                    if uid in item_str or email in item_str:
                        print(f"    Item: {item_str[:200]}...")
