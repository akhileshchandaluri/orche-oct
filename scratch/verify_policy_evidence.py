import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
DATASET_DIR = PROJECT_ROOT / "dataset"

sys.path.insert(0, str(PROJECT_ROOT))
from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir=DATASET_DIR)

# Valid operations and states according to official problem_statement.md
OFFICIAL_OPS = {
    "FINDING": {
        "REPORT_REMAINING_RECORD": "PRESENT",
        "REPORT_EXPOSED_PII": "PRESENT",
        "REPORT_ACTIVE_DATA_FLOW": "ACTIVE",
        "REPORT_RESTORE_RISK": "ACTIVE",
    },
    "REMEDIATION": {
        "DISABLE_DATA_FLOW": "DISABLED",
        "BLOCK_RESTORE": "BLOCKED",
        "DELETE_RECORD": "ABSENT",
        "REDACT_RECORD": "REDACTED",
        "ANONYMIZE_RECORD": "ANONYMIZED",
    },
    "VERIFICATION": {
        "VERIFY_RECORD_ABSENT": "ABSENT",
        "VERIFY_RECORD_PRESENT": "PRESENT",
        "VERIFY_RECORD_REDACTED": "REDACTED",
        "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED",
        "VERIFY_DATA_FLOW_DISABLED": "DISABLED",
        "VERIFY_RESTORE_BLOCKED": "BLOCKED",
    },
}

# Collect all valid evidence IDs from evidence_files.csv, system_activity, and user_audit_log
valid_evidence_ids = set()
with open(DATASET_DIR / "evidence_files.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        valid_evidence_ids.add(r["file_id"].strip())

with open(DATASET_DIR / "system_activity.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        valid_evidence_ids.add(r["activity_id"].strip())

with open(DATASET_DIR / "user_audit_log.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        valid_evidence_ids.add(r["audit_id"].strip())

print(f"Total valid evidence/activity/audit IDs in dataset: {len(valid_evidence_ids)}")

# Audit all 518 official cases
with open(DATASET_DIR / "deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_requests = list(csv.DictReader(f))

errors = []
warnings = []

for req in sample_requests:
    cid = req["case_id"]
    res = engine.audit_case(req)
    status = res["deletion_status"]
    steps = json.loads(res["steps_json"])

    if status == "NOT_APPLICABLE":
        if len(steps) != 0:
            errors.append(f"{cid}: NOT_APPLICABLE must have empty steps array, got {len(steps)}")
        continue

    for s in steps:
        phase = s.get("phase")
        op = s.get("operation")
        state = s.get("state")
        ev_id = s.get("evidence_id")
        res_id = s.get("resource_id")
        sys_id = s.get("system_id")

        # 1. Check phase
        if phase not in OFFICIAL_OPS:
            errors.append(f"{cid}: Invalid phase '{phase}' in step {s}")
            continue

        # 2. Check operation and state match
        expected_state = OFFICIAL_OPS[phase].get(op)
        if expected_state is None:
            errors.append(f"{cid}: Invalid op '{op}' for phase '{phase}'")
        elif state != expected_state:
            errors.append(f"{cid}: State mismatch for {op}: expected {expected_state}, got {state}")

        # 3. Check evidence ID rules
        if phase == "FINDING":
            if not ev_id:
                errors.append(f"{cid}: FINDING step missing evidence_id: {s}")
            elif ev_id not in valid_evidence_ids:
                errors.append(f"{cid}: FINDING cites unknown evidence_id '{ev_id}'")

        elif phase == "REMEDIATION":
            if ev_id != "":
                errors.append(f"{cid}: REMEDIATION step must have empty evidence_id, got '{ev_id}'")

        elif phase == "VERIFICATION":
            if status == "COMPLETE":
                if not ev_id:
                    errors.append(f"{cid}: COMPLETE case verification step missing evidence_id: {s}")
                elif ev_id not in valid_evidence_ids:
                    errors.append(f"{cid}: COMPLETE verification cites unknown evidence_id '{ev_id}'")
            elif status == "INCOMPLETE":
                if ev_id != "":
                    errors.append(f"{cid}: INCOMPLETE future verification step must have empty evidence_id, got '{ev_id}'")

print(f"\nAudit complete for {len(sample_requests)} sample cases.")
print(f"Total Errors Found: {len(errors)}")
print(f"Total Warnings:     {len(warnings)}")
if errors:
    for e in errors[:10]:
        print("  ERROR:", e)
else:
    print("ALL POLICY, OPERATION, STATE, AND EVIDENCE ID RULES STRICTLY COMPLIANT!")
