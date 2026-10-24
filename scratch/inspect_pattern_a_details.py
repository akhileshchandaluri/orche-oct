import csv, json
from datetime import datetime, timedelta

sample_reqs = {r["case_id"]: r for r in csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8"))}
truth = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}
acts = list(csv.DictReader(open("dataset/system_activity.csv", encoding="utf-8")))

pattern_a_cases = ["case_03", "case_04", "case_21", "case_25", "case_26", "case_27", "case_28"]

for cid in pattern_a_cases:
    req = sample_reqs[cid]
    rep_at = req["reported_at"]
    rep_dt = datetime.fromisoformat(rep_at.replace("Z", "+00:00"))
    
    # Truth analytics step
    t_steps = [s for s in truth[cid] if s["system_id"] == "analytics_platform"]
    t_analytics_step = t_steps[0] if t_steps else None
    
    # Worker acts in window [reported_at - 2.5h, reported_at + 15m]
    start_dt = rep_dt - timedelta(hours=2.5)
    end_dt = rep_dt + timedelta(minutes=15)
    
    window_worker_acts = [
        a for a in acts
        if a["source_system"] == "deletion_worker"
        and start_dt <= datetime.fromisoformat(a["event_time"].replace("Z", "+00:00")) <= end_dt
    ]
    
    # Filter worker acts for analytics
    analytics_worker_acts = [a for a in window_worker_acts if a["target_system"] == "analytics_platform"]
    
    print(f"\n=======================================================")
    print(f"Case: {cid} | Email: {req['email']} | ReqAt: {req['requested_at']} | RepAt: {req['reported_at']}")
    print(f"Truth Analytics Step: {t_analytics_step}")
    print(f"Analytics Worker Events in Window ({len(analytics_worker_acts)}):")
    for a in analytics_worker_acts:
        print(f"  {a['event_time']} | op: {a['event_type']} | res: {a['resource_id']} | res: {a['reported_result']}")
