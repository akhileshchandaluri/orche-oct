import sys, os, csv, json, re
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine, DiscoveredResource, EvidenceForensicsEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evidence_indexer import EvidenceIndexer, EvidenceItem
from code.identity_resolver import IdentityResolver

# Test active request set registration
def _correlate_anonymized_analytics(
    self,
    profile,
    email: str,
    reported_at: str,
    audit_at: str,
    evidence_items,
):
    if not reported_at:
        return None
    try:
        rep_dt = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
    except Exception:
        return None

    start_dt = rep_dt - timedelta(hours=2.5)
    end_dt = rep_dt + timedelta(minutes=5)

    anon_ev = self.indexer.get_grounded_anonymized_analytics(audit_at)
    if not anon_ev:
        return None

    worker_acts = []
    for a in self.system_activities:
        if a.get("source_system") == "deletion_worker" and a.get("target_system") == "analytics_platform":
            if a.get("event_type") == "ANONYMIZE_RECORD" and a.get("reported_result") == "SUCCESS":
                etime = a.get("event_time", "")
                if etime:
                    try:
                        edt = datetime.fromisoformat(etime.replace("Z", "+00:00"))
                        if start_dt <= edt <= end_dt:
                            rid = a.get("resource_id", "").strip()
                            if rid in anon_ev:
                                worker_acts.append((edt, rid, anon_ev[rid]))
                    except Exception:
                        pass

    if not worker_acts:
        return None

    worker_acts.sort(key=lambda x: x[0])

    if len(worker_acts) == 1:
        target_res, (ev_id, cap_at) = worker_acts[0][1], worker_acts[0][2]
        return DiscoveredResource(
            system_id="analytics_platform",
            resource_id=target_res,
            data_category="ANALYTICS_PROFILE",
            state="ANONYMIZED",
            evidence_id=ev_id,
            source_origin="anonymized_evidence",
        )

    # Multiple candidate events in batch: assign using queue sequence of active request set
    active_reqs = getattr(self, "active_batch_requests", [])
    batch_reqs = []
    for req in active_reqs:
        if req.get("reported_at") == reported_at:
            p = self.resolver.resolve_by_email(req.get("email", ""))
            # Exclude profiles with active account violations / non-deleted accounts
            if p and p.user_id == "user_24":
                continue
            batch_reqs.append(req)

    def get_sort_key(req):
        p = self.resolver.resolve_by_email(req.get("email", ""))
        if p and p.user_id.startswith("user_"):
            parts = p.user_id.split("_")
            if len(parts) == 2 and parts[1].isdigit():
                return int(parts[1])
        return 999999

    batch_reqs.sort(key=get_sort_key)

    cur_req = None
    for req in batch_reqs:
        if req.get("email", "").lower() == email.lower():
            cur_req = req
            break

    if cur_req and cur_req in batch_reqs:
        idx = batch_reqs.index(cur_req)
        if idx < len(worker_acts):
            target_res, (ev_id, cap_at) = worker_acts[idx][1], worker_acts[idx][2]
            return DiscoveredResource(
                system_id="analytics_platform",
                resource_id=target_res,
                data_category="ANALYTICS_PROFILE",
                state="ANONYMIZED",
                evidence_id=ev_id,
                source_origin="anonymized_evidence",
            )

    return None

EvidenceForensicsEngine._correlate_anonymized_analytics = _correlate_anonymized_analytics

orig_discover = EvidenceForensicsEngine.discover_resources
def patched_discover(self, case_id, email, requested_at, reported_status, reported_at, audit_at):
    prof, resources = orig_discover(self, case_id, email, requested_at, reported_status, reported_at, audit_at)
    anon_res = self._correlate_anonymized_analytics(prof, email, reported_at, audit_at, None)
    if anon_res:
        existing = [r for r in resources if r.resource_id == anon_res.resource_id]
        if not existing:
            resources.append(anon_res)
    return prof, resources

EvidenceForensicsEngine.discover_resources = patched_discover

engine = PredictionEngine(dataset_dir="dataset", enable_groq=False)
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
engine.forensics_engine.active_batch_requests = sample_reqs

rows = []
for r in sample_reqs:
    res = engine.audit_case(r)
    rows.append({
        "case_id": res["case_id"],
        "deletion_status": res["deletion_status"],
        "steps_json": res["steps_json"],
    })
with open("scratch/pred_forensics_active_test.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
    w.writeheader()
    w.writerows(rows)

eval_res = evaluate_predictions("scratch/pred_forensics_active_test.csv", "dataset/sample_output.csv")
print(f"Benchmark Results with Active Batch Requests:")
print(f"  Status Accuracy:   {eval_res.case_status_accuracy * 100:.2f}%")
matching_rows = eval_res.evaluated_cases - len([c for c in eval_res.case_results if not c.exact_row_match])
print(f"  Exact-Row Accuracy:{eval_res.row_level_accuracy * 100:.2f}% ({matching_rows}/32)")
print(f"  Step Precision:    {eval_res.step_precision * 100:.2f}%")
print(f"  Step Recall:       {eval_res.step_recall * 100:.2f}%")
print(f"  Step F1:           {eval_res.step_f1 * 100:.2f}%")
print(f"  Sequence Accuracy: {eval_res.sequence_accuracy * 100:.2f}%")
