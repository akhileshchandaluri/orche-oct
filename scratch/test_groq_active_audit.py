import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir="dataset", enable_groq=True)

ambiguous_req = {
    "case_id": "case_ambig_02",
    "email": "h.mori78@yahoo.com",
    "requested_at": "2026-09-15T12:00:00Z",
    "reported_status": "COMPLETE",
    "reported_at": "2026-09-18T12:00:00Z",
    "audit_at": "2026-09-28T12:00:00Z",
    "request_text": "I demand you forget me and scrub away everything associated with my identity across all company platforms.",
}

print("Auditing un-keyed request with Groq enabled...")
res = engine.audit_case(ambiguous_req)
metrics = engine.groq_reasoner.get_metrics_summary()

print("Result status:", res["deletion_status"])
print("Groq metrics:", metrics)
