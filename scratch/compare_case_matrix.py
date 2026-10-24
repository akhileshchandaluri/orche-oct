import csv, json
from pathlib import Path

truth = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}
base_18 = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/base_pred.csv", encoding="utf-8"))}
scratch_23 = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("backup/baseline_pre_priority_fixes/code/evaluation/scratch_pred_sample.csv", encoding="utf-8"))}
current_21 = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/pred_current_prompt3.csv", encoding="utf-8"))}
pre_fix_engine_21 = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/pred_baseline_pre_priority_fixes.csv", encoding="utf-8"))}

print(f"{'Case ID':<10} | {'base_pred (18/32)':<18} | {'scratch_23 (23/32)':<18} | {'pre_fix_engine (21/32)':<22} | {'current_prompt3 (21/32)':<22}")
print("-" * 105)

for cid in sorted(truth.keys(), key=lambda x: int(x.split("_")[1])):
    t_stat, t_steps = truth[cid]
    
    b_stat, b_steps = base_18[cid]
    b_match = (b_stat == t_stat and b_steps == t_steps)
    
    s_stat, s_steps = scratch_23[cid]
    s_match = (s_stat == t_stat and s_steps == t_steps)
    
    p_stat, p_steps = pre_fix_engine_21[cid]
    p_match = (p_stat == t_stat and p_steps == t_steps)

    c_stat, c_steps = current_21[cid]
    c_match = (c_stat == t_stat and c_steps == t_steps)

    print(f"{cid:<10} | {'MATCH' if b_match else 'DIFF':<18} | {'MATCH' if s_match else 'DIFF':<18} | {'MATCH' if p_match else 'DIFF':<22} | {'MATCH' if c_match else 'DIFF':<22}")
