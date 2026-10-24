import csv, json
from datetime import datetime, timedelta
from code.prediction_engine import PredictionEngine

pe = PredictionEngine('dataset', enable_groq=False)
req = [r for r in csv.DictReader(open('dataset/sample_deletion_requests.csv', encoding='utf-8')) if r['case_id'] == 'case_23'][0]
profile = pe.forensics_engine.resolver.resolve_by_email(req['email'])
evs = pe.forensics_engine.indexer.find_evidence_for_user(profile, req['audit_at'], req['requested_at'])

reported_at = req['reported_at']
rep_dt = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
batch_start = (rep_dt - timedelta(hours=2.5)).isoformat().replace("+00:00", "Z")
batch_end = (rep_dt + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
window_acts = [
    a for a in pe.forensics_engine.system_activities
    if a["target_system"] == "account_service"
    and a["event_type"] == "DELETE_RECORD"
    and batch_start <= a["event_time"] <= batch_end
]

print(f"Window acts ({len(window_acts)}):")
for a in window_acts:
    print(f"  {a['event_time']} | {a['resource_id']} | {a['reported_result']}")

valid_acts = [
    a for a in window_acts
    if a["resource_id"] not in pe.forensics_engine.indexer.known_other_accounts
    or pe.forensics_engine.indexer.known_other_accounts[a["resource_id"]] == req['email'].lower()
]

status_matched = [a for a in valid_acts if a.get("reported_result") == "FAILED"]
print(f"Status matched ({len(status_matched)}): {[a['resource_id'] for a in status_matched]}")

ev_res_ids = {it.resource_id for it in evs if it.system_id == "account_service"}
confirmed = [
    a for a in status_matched
    if a["resource_id"] in ev_res_ids
    or a["resource_id"] in getattr(pe.forensics_engine.indexer, "grounded_account_ids", set())
]
print(f"Confirmed ({len(confirmed)}): {[a['resource_id'] for a in confirmed]}")

has_violations = any(it.observation in ["PRESENT", "ACTIVE"] and it.system_id not in ["security_service", "account_service"] for it in evs)
print(f"Has violations: {has_violations}")
other_cands = [a for a in status_matched if a not in confirmed]
print(f"Other cands ({len(other_cands)}): {[a['resource_id'] for a in other_cands]}")
