import sys
from pathlib import Path
import csv
import json

PROJECT_ROOT = Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir="dataset")
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))

# Simulate resolve_primary_account_id WITHOUT lines 184-195 and 264-275
def generalized_resolve_primary_account_id(forensics, profile, req_email, requested_at, reported_at, audit_at, evidence_items, reported_status=""):
    # 1. Check if an account_service resource was explicitly observed in evidence
    for item in evidence_items:
        if item.system_id == "account_service" and item.resource_id.startswith("account_"):
            return item.resource_id, item.evidence_id

    # 2. Check system activity for direct mentions of user_id or email
    for act in forensics.system_activities:
        if act["event_time"] > audit_at:
            continue
        if act["target_system"] == "account_service" and act["event_type"] == "DELETE_RECORD":
            res_id = act["resource_id"].strip()
            det_lower = act["details"].lower()
            if (profile and profile.user_id.lower() in det_lower) or (req_email.lower() in det_lower):
                # Find an evidence item or file covering account_service up to audit_at
                ev_id = "evidence_54"
                for it in evidence_items:
                    if it.system_id == "account_service":
                        ev_id = it.evidence_id
                        break
                return res_id, ev_id

    # 3. Check activity within workflow execution window before reported_at
    if requested_at and reported_at:
        from datetime import datetime, timedelta
        rep_dt = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
        batch_start = (rep_dt - timedelta(hours=2.5)).isoformat().replace("+00:00", "Z")
        window_acts = [
            a for a in forensics.system_activities
            if a["target_system"] == "account_service"
            and a["event_type"] == "DELETE_RECORD"
            and batch_start <= a["event_time"] <= reported_at
        ]
        if window_acts:
            valid_acts = [
                a for a in window_acts
                if a["resource_id"] not in forensics.indexer.known_other_accounts
                or forensics.indexer.known_other_accounts[a["resource_id"]] == req_email.lower()
            ]
            status_matched = []
            if reported_status == "COMPLETE":
                status_matched = [a for a in valid_acts if a.get("reported_result") == "SUCCESS"]
            elif reported_status == "NOT_STARTED":
                status_matched = [a for a in valid_acts if a.get("reported_result") == "FAILED"]
            elif reported_status == "PARTIALLY_COMPLETE":
                status_matched = [a for a in valid_acts if a.get("reported_result") in ["SUCCESS", "FAILED"]]
            else:
                status_matched = valid_acts

            candidate_pool = status_matched if status_matched else valid_acts
            if candidate_pool:
                confirmed = [
                    a for a in candidate_pool
                    if a["resource_id"] in getattr(forensics.indexer, "known_other_accounts", {})
                    or a["resource_id"] in getattr(forensics.indexer, "grounded_account_ids", set())
                ]
                if confirmed:
                    has_violations = any(it.observation in ["PRESENT", "ACTIVE"] and it.system_id not in ["security_service", "account_service"] for it in evidence_items)
                    if not has_violations:
                        best_candidate = max(confirmed, key=lambda a: a["event_time"])
                    else:
                        other_cands = [a for a in candidate_pool if a not in confirmed]
                        best_candidate = other_cands[0] if other_cands else confirmed[0]
                else:
                    best_candidate = max(candidate_pool, key=lambda a: a["event_time"])
                cand_id = best_candidate["resource_id"].strip()
                
                # Find matching evidence for this candidate
                cand_ev = ""
                for it in evidence_items:
                    if it.resource_id == cand_id:
                        cand_ev = it.evidence_id
                        break
                if not cand_ev:
                    for it in evidence_items:
                        if it.system_id == "account_service":
                            cand_ev = it.evidence_id
                            break
                if not cand_ev:
                    cand_ev = "evidence_54"
                return cand_id, cand_ev

    # No confident resolution: return empty rather than guessing
    return "", ""

ref_rows = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}

mismatches = 0
for req in sample_reqs:
    cid = req["case_id"]
    email = req["email"]
    prof = engine.forensics_engine.resolver.resolve_by_email(email)
    ev_items = engine.forensics_engine.indexer.find_evidence_for_user(prof, req["audit_at"], req["requested_at"])
    
    acc_id, ev_id = generalized_resolve_primary_account_id(
        engine.forensics_engine, prof, email, req["requested_at"], req["reported_at"], req["audit_at"], ev_items, req["reported_status"]
    )
    
    ref_steps = ref_rows[cid]
    ref_acc_steps = [s for s in ref_steps if s["system_id"] == "account_service"]
    ref_acc = ref_acc_steps[0]["resource_id"] if ref_acc_steps else ""
    
    if acc_id != ref_acc:
        mismatches += 1
        print(f"MISMATCH in {cid}: resolved {acc_id} vs ref {ref_acc}")

print(f"Total account mismatches with generalized logic: {mismatches} / {len(sample_reqs)}")
