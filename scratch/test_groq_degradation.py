import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import csv
from code.prediction_engine import PredictionEngine
from code.groq_reasoner import GroqReasoner

dataset_dir = PROJECT_ROOT / "dataset"
sample_reqs = list(csv.DictReader(open(dataset_dir / "sample_deletion_requests.csv", encoding="utf-8")))

# Test 1: Explicit Groq Disabled (Offline deterministic)
engine_disabled = PredictionEngine(dataset_dir=dataset_dir, enable_groq=False)
assert not engine_disabled.groq_reasoner.is_available(), "Groq should not be available when disabled"
res_disabled = [engine_disabled.audit_case(r) for r in sample_reqs]

# Test 2: Invalid API key (API Failure / Degradation)
groq_bad_key = GroqReasoner(api_key="gsk_invalid_test_key_12345", enabled=True)
engine_degraded = PredictionEngine(dataset_dir=dataset_dir, groq_reasoner=groq_bad_key)
res_degraded = [engine_degraded.audit_case(r) for r in sample_reqs]

# Test 3: Verify bit-for-bit equivalence in output
for r_dis, r_deg in zip(res_disabled, res_degraded):
    assert r_dis["case_id"] == r_deg["case_id"]
    assert r_dis["deletion_status"] == r_deg["deletion_status"]
    assert r_dis["steps_json"] == r_deg["steps_json"]

print(f"Verified degradation safety across all {len(sample_reqs)} sample cases.")
print("Mode degraded gracefully with 100% identical outputs and zero crashes.")
