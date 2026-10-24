import sys
sys.path.insert(0, '.')
from code.prediction_engine import PredictionEngine
import json

engine = PredictionEngine(dataset_dir='dataset')

cases = [
    {
        'id': 'case_01_non_deletion',
        'name': 'GDPR Article 20 Portability vs Erasure',
        'input': {
            'case_id': 'part_01',
            'email': 'amina.elmasri@gmail.com',
            'requested_at': '2026-09-01T10:00:00Z',
            'reported_status': 'COMPLETE',
            'reported_at': '2026-09-02T10:00:00Z',
            'audit_at': '2026-09-10T10:00:00Z',
            'request_text': 'I want a copy of all my data under GDPR Article 20 (Right to Data Portability). Please provide the export file. Do NOT delete my account; keep the account active.',
        },
        'exp_status': 'NOT_APPLICABLE',
        'exp_steps_empty': True
    },
    {
        'id': 'case_02_active_data_flow',
        'name': 'Active Synchronization Data Flow Hazard',
        'input': {
            'case_id': 'part_02',
            'email': 'mori.ren@gmail.com',
            'requested_at': '2026-09-06T11:00:00Z',
            'reported_status': 'COMPLETE',
            'reported_at': '2026-09-09T11:00:00Z',
            'audit_at': '2026-09-26T11:00:00Z',
            'request_text': 'Please permanently delete my account and personal data across all services.',
        },
        'exp_status': 'INCOMPLETE',
        'req_op': 'REPORT_ACTIVE_DATA_FLOW',
        'req_res': 'data_flow_4890'
    },
    {
        'id': 'case_03_backup_restore_risk',
        'name': 'Unblocked Backup Archive Restoration Hazard',
        'input': {
            'case_id': 'part_03',
            'email': 'y.tanaka32@gmail.com',
            'requested_at': '2026-09-04T12:00:00Z',
            'reported_status': 'COMPLETE',
            'reported_at': '2026-09-06T12:00:00Z',
            'audit_at': '2026-10-01T12:00:00Z',
            'request_text': 'Please delete my account and all personal information.',
        },
        'exp_status': 'INCOMPLETE',
        'req_op': 'REPORT_RESTORE_RISK',
        'req_res': 'backup_3870'
    },
    {
        'id': 'case_04_multilingual_german',
        'name': 'German Language Deletion Authorization',
        'input': {
            'case_id': 'part_04',
            'email': 'diego.m@zoho.com',
            'requested_at': '2026-08-28T10:00:00Z',
            'reported_status': 'COMPLETE',
            'reported_at': '2026-08-30T10:00:00Z',
            'audit_at': '2026-09-12T10:00:00Z',
            'request_text': 'Bitte löschen Sie mein Konto und alle damit verbundenen Daten unwiderruflich.',
        },
        'exp_status': 'COMPLETE',
        'exp_steps_empty': True
    },
    {
        'id': 'case_05_historical_identity',
        'name': 'Historical Email Alias Resolution',
        'input': {
            'case_id': 'part_05',
            'email': 'nadia.ionescu@yahoo.com',
            'requested_at': '2026-09-03T14:00:00Z',
            'reported_status': 'COMPLETE',
            'reported_at': '2026-09-05T14:00:00Z',
            'audit_at': '2026-09-20T14:00:00Z',
            'request_text': 'Please delete my account and all personal data.',
        },
        'exp_status': 'INCOMPLETE',
        'req_res': 'account_010'
    }
]

for c in cases:
    res = engine.audit_case(c['input'])
    stat = res['deletion_status']
    steps = json.loads(res['steps_json'])
    stat_pass = (stat == c['exp_status'])
    steps_pass = True
    if c.get('exp_steps_empty'):
        steps_pass = (len(steps) == 0)
    if c.get('req_op'):
        steps_pass = steps_pass and any(s.get('operation') == c['req_op'] for s in steps)
    if c.get('req_res'):
        steps_pass = steps_pass and any(s.get('resource_id') == c['req_res'] for s in steps)
    
    total_pass = stat_pass and steps_pass
    res_str = 'PASS' if total_pass else 'FAIL'
    print(f"{c['id']}: status_pass={stat_pass}, steps_pass={steps_pass} -> {res_str}")
