import csv, json
from pathlib import Path

truth = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}
current = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/pred_current_prompt3.csv", encoding="utf-8"))}
pre_fix = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/pred_baseline_pre_priority_fixes.csv", encoding="utf-8"))}
sample_reqs = {r["case_id"]: r for r in csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8"))}

mismatched = []
for cid in sorted(truth.keys(), key=lambda x: int(x.split("_")[1])):
    t_stat, t_steps = truth[cid]
    c_stat, c_steps = current[cid]
    if t_stat != c_stat or t_steps != c_steps:
        mismatched.append(cid)

print(f"Total mismatched cases in current_prompt3: {len(mismatched)}")
print("Cases:", mismatched)

def step_fp(s):
    return (s.get("phase"), s.get("system_id"), s.get("resource_id"), s.get("operation"), s.get("state"), s.get("evidence_id"))

for cid in mismatched:
    t_stat, t_steps = truth[cid]
    c_stat, c_steps = current[cid]
    p_stat, p_steps = pre_fix[cid]
    req = sample_reqs[cid]
    
    t_fps = [step_fp(s) for s in t_steps]
    c_fps = [step_fp(s) for s in c_steps]
    p_fps = [step_fp(s) for s in p_steps]
    
    missing_in_current = [f for f in t_fps if f not in c_fps]
    extra_in_current = [f for f in c_fps if f not in t_fps]
    diff_from_prefix = (c_fps != p_fps)

    print(f"\n=======================================================")
    print(f"CASE: {cid} | User: {req['email']} | Req: {req['requested_at']} | Rep: {req['reported_at']} ({req['reported_status']}) | Audit: {req['audit_at']}")
    print(f"Status: Truth={t_stat}, Current={c_stat} (Match: {t_stat == c_stat})")
    print(f"Diff between pre_priority_fixes and current_prompt3? {diff_from_prefix}")
    if diff_from_prefix:
        print("  Pre-fix FPS:", p_fps)
        print("  Current FPS:", c_fps)
    print(f"Missing from current ({len(missing_in_current)}):")
    for m in missing_in_current:
        print(f"  - {m}")
    print(f"Extra in current ({len(extra_in_current)}):")
    for e in extra_in_current:
        print(f"  + {e}")
