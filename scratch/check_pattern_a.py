import csv, json
from datetime import datetime, timezone, timedelta

pattern_a_cases = ['case_03', 'case_04', 'case_21', 'case_25', 'case_26', 'case_27', 'case_28']
sample_reqs = {r['case_id']: r for r in csv.DictReader(open('dataset/sample_deletion_requests.csv', encoding='utf-8'))}
truth = {r['case_id']: json.loads(r['steps_json']) for r in csv.DictReader(open('dataset/sample_output.csv', encoding='utf-8'))}
acts = list(csv.DictReader(open('dataset/system_activity.csv', encoding='utf-8')))

for cid in pattern_a_cases:
    req = sample_reqs[cid]
    rep_at = req['reported_at']
    rep_dt = datetime.fromisoformat(rep_at.replace('Z', '+00:00'))
    start_dt = rep_dt - timedelta(hours=2.5)
    end_dt = rep_dt + timedelta(minutes=15)
    
    missing_analytics_step = [s for s in truth[cid] if s['system_id'] == 'analytics_platform' and s['operation'] == 'VERIFY_RECORD_ANONYMIZED']
    target_res = missing_analytics_step[0]['resource_id'] if missing_analytics_step else 'NONE'
    
    matching_worker_acts = [
        a for a in acts
        if a['target_system'] == 'analytics_platform'
        and a['event_type'] == 'ANONYMIZE_RECORD'
        and start_dt <= datetime.fromisoformat(a['event_time'].replace('Z', '+00:00')) <= end_dt
    ]
    
    print(f"Case: {cid} | Rep: {rep_at} | Target Analytics Res: {target_res}")
    print(f"  Worker ANONYMIZE_RECORD in window: {len(matching_worker_acts)}")
    for ma in matching_worker_acts:
        print(f"    {ma['event_time']} {ma['resource_id']} {ma['reported_result']} (Matches target? {ma['resource_id'] == target_res})")
