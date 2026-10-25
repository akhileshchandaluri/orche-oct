import sys
import csv
import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir=Path('dataset'), enable_groq=False)
with open('dataset/sample_deletion_requests.csv', encoding='utf-8') as f:
    sample_reqs = list(csv.DictReader(f))
with open('dataset/sample_output.csv', encoding='utf-8') as f:
    sample_outs = {r['case_id']: r for r in csv.DictReader(f)}

for req in sample_reqs:
    cid = req['case_id']
    engine.forensics_engine.register_request(req)
    prof = engine.forensics_engine.resolver.resolve_by_email(req['email'])
    ev_items = engine.forensics_engine.indexer.find_evidence_for_user(prof, req['audit_at'], req['requested_at'])
    res_id, ev_id = engine.forensics_engine.resolve_primary_account_id(
        profile=prof,
        req_email=req['email'],
        requested_at=req['requested_at'],
        reported_at=req['reported_at'],
        audit_at=req['audit_at'],
        evidence_items=ev_items,
        reported_status=req['reported_status']
    )
    truth_steps = json.loads(sample_outs[cid]['steps_json'])
    truth_acc = [s['resource_id'] for s in truth_steps if s['system_id'] == 'account_service']
    is_match = (res_id in truth_acc) if truth_acc else (res_id == '')
    mark = 'MATCH' if is_match else 'MISMATCH'
    print(f'{cid}: pred={res_id} truth={truth_acc} [{mark}]')
