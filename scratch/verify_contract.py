import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.schema_validator import validate_csv, load_known_evidence_ids

out_path = Path("output.csv")
dataset_dir = Path("dataset")
known_ev_ids = load_known_evidence_ids(dataset_dir)

# 1. Run schema validator
rep = validate_csv(out_path, expected_rows=518, valid_evidence_ids=known_ev_ids)
print("Schema Validator Report:")
print(rep.summary())
assert rep.is_valid, f"Schema validation failed: {rep.errors}"

# 2. Detailed invariant verification
with open(out_path, mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    assert reader.fieldnames == ["case_id", "deletion_status", "steps_json"], f"Header mismatch: {reader.fieldnames}"
    rows = list(reader)

assert len(rows) == 518, f"Expected 518 rows, got {len(rows)}"

# Check case_id ordering and completeness against deletion_requests.csv
with open(dataset_dir / "deletion_requests.csv", mode="r", encoding="utf-8") as f:
    req_cids = [r["case_id"].strip() for r in csv.DictReader(f)]

out_cids = [r["case_id"] for r in rows]
assert out_cids == req_cids, "Output case IDs do not match deletion_requests.csv exactly in sequence!"
assert len(set(out_cids)) == 518, "Duplicate case IDs found!"

# Check status distribution and step rules
status_counts = {}
for r in rows:
    cid = r["case_id"]
    st = r["deletion_status"]
    status_counts[st] = status_counts.get(st, 0) + 1
    steps = json.loads(r["steps_json"])
    
    if st == "NOT_APPLICABLE":
        assert len(steps) == 0, f"NOT_APPLICABLE case {cid} has non-empty steps"
    elif st == "COMPLETE":
        assert all(s["phase"] == "VERIFICATION" for s in steps), f"COMPLETE case {cid} has non-VERIFICATION steps"
        assert all(s["evidence_id"] != "" for s in steps), f"COMPLETE case {cid} has empty evidence_id"
    elif st == "INCOMPLETE":
        findings = [s for s in steps if s["phase"] == "FINDING"]
        rem_ver = [s for s in steps if s["phase"] in ("REMEDIATION", "VERIFICATION")]
        assert len(findings) > 0, f"INCOMPLETE case {cid} has no findings"
        assert all(s["evidence_id"] != "" for s in findings), f"INCOMPLETE finding in {cid} has empty evidence_id"
        assert all(s["evidence_id"] == "" for s in rem_ver), f"INCOMPLETE rem/ver in {cid} has non-empty evidence_id"

print("Status distribution:", status_counts)
print("ALL 13 INVARIANTS STRICTLY VERIFIED ON output.csv!")
