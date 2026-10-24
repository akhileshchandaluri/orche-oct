import csv, json, re, sys
from pathlib import Path

PROJECT_ROOT = Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from code.evidence_indexer import EvidenceIndexer
from code.identity_resolver import IdentityResolver
from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions

# Patch EvidenceIndexer._parse_log_file to extract leading ISO timestamp
orig_parse_log = EvidenceIndexer._parse_log_file

def improved_parse_log(self, fpath, fid, captured_at, origin, emails, phones, hashes, uid, audit_at=None, requested_at=None, candidate_resources=None):
    results = []
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        matched_cand = any(r in content for r in candidate_resources) if candidate_resources else False
        matched_em = [e for e in emails if e in content.lower()]
        matched_ph = [p for p in phones if p in content]
        matched_h = [h for h in hashes if h in content.lower()]
        matched_u = uid.lower() in content.lower()

        if not (matched_em or matched_ph or matched_h or matched_u or matched_cand):
            return results

        lines_by_trace = {}
        untraced_lines = []

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            event_dict = {}
            # Extract line timestamp if present at beginning of log line
            ts_m = re.search(r"^\s*([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z)", line_str)
            line_ts = ts_m.group(1) if ts_m else None

            json_match = re.search(r"(\{.*\})", line_str)
            if json_match:
                try:
                    event_dict = json.loads(json_match.group(1))
                except Exception:
                    pass
            else:
                for m in re.finditer(r'([a-zA-Z0-9_\-]+)=(?:"([^"]*)"|([^\s]+))', line_str):
                    k = m.group(1)
                    v = m.group(2) if m.group(2) is not None else m.group(3)
                    event_dict[k] = v

            if not event_dict:
                continue

            if line_ts and "timestamp" not in event_dict and "event_time" not in event_dict:
                event_dict["event_time"] = line_ts

            tid = event_dict.get("trace_id")
            if tid:
                if tid not in lines_by_trace:
                    lines_by_trace[tid] = []
                lines_by_trace[tid].append(event_dict)
            else:
                untraced_lines.append(event_dict)

        # Process traced groups
        for tid, events in lines_by_trace.items():
            trace_str = json.dumps(events).lower()
            trace_matches = (
                any(e in trace_str for e in emails)
                or any(p in trace_str for p in phones)
                or any(h in trace_str for h in hashes)
                or (uid.lower() in trace_str)
            )

            if not trace_matches:
                continue

            for ev in events:
                res_id = ev.get("resource_id", "")
                if not res_id:
                    continue

                event_name = ev.get("event", "")
                if event_name.endswith("_started"):
                    continue

                # Filter by event timestamp if present; for untimed log entries, use defensible file-level captured_at
                ev_time = ev.get("timestamp") or ev.get("event_time") or ev.get("time")
                if not ev_time:
                    ev_time = captured_at
                if not ev_time:
                    continue
                if audit_at and ev_time > audit_at:
                    continue
                if requested_at and ev_time < requested_at:
                    continue

                sys_id = ev.get("service") or ev.get("logger") or "account_service"
                if sys_id == "support_replica":
                    sys_id = "support_platform"

                obs = "PRESENT"
                if "404" in str(ev.get("http_status", "")) or str(ev.get("rows")) == "0":
                    obs = "ABSENT"
                elif ev.get("enabled") in ["true", True, "1", 1]:
                    obs = "ACTIVE"
                elif ev.get("enabled") in ["false", False, "0", 0]:
                    obs = "DISABLED"
                elif ev.get("restore_allowed") in ["true", True, "1", 1]:
                    obs = "ACTIVE"
                elif ev.get("restore_allowed") in ["false", False, "0", 0]:
                    obs = "BLOCKED"
                elif sys_id == "analytics_platform":
                    if str(ev.get("rows")) == "1" or ev.get("email_opt_in") is not None or ev.get("correlation_key") is not None:
                        obs = "PRESENT"
                    elif ev.get("customer_reference") is None and ev.get("email") is None:
                        obs = "ANONYMIZED"
                elif sys_id == "support_platform":
                    if str(ev.get("rows")) == "1" or str(ev.get("marker_found")).lower() == "false":
                        obs = "PRESENT"
                    elif str(ev.get("marker_found")).lower() == "true":
                        obs = "ABSENT"
                    elif ev.get("requester_email") is None and ev.get("requester_name") is None and "message" in ev:
                        obs = "REDACTED"
                elif sys_id == "security_service":
                    obs = "PRESENT"

                if sys_id == "integration_service" or "data_flow" in res_id:
                    if obs == "PRESENT": obs = "ACTIVE"
                elif sys_id == "backup_service" or "backup_" in res_id:
                    if obs == "PRESENT": obs = "ACTIVE"

                cat = "USER_PROFILE"
                if sys_id == "integration_service" or "data_flow" in res_id:
                    cat = "DATA_FLOW"
                elif sys_id == "backup_service" or "backup_" in res_id:
                    cat = "BACKUP_ARCHIVE"
                elif sys_id == "security_service" or "audit_record_" in res_id:
                    cat = "SECURITY_AUDIT_LOG"
                elif sys_id == "support_platform" or "support_" in res_id:
                    cat = "SUPPORT_MESSAGE"
                elif sys_id == "analytics_platform" or "analytics_" in res_id:
                    cat = "ANALYTICS_PROFILE"

                matched_val = uid
                for e in emails:
                    if e in str(ev).lower():
                        matched_val = e
                        break

                results.append(
                    EvidenceItem(
                        evidence_id=fid,
                        captured_at=captured_at,
                        system_id=sys_id,
                        resource_id=res_id,
                        data_category=cat,
                        observation=obs,
                        matched_key=matched_val,
                        raw_details=json.dumps(ev),
                        origin=origin,
                    )
                )
    except Exception:
        pass
    return results

EvidenceIndexer._parse_log_file = improved_parse_log

engine = PredictionEngine(dataset_dir="dataset")
sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))

preds = []
for r in sample_reqs:
    res = engine.audit_case(r)
    preds.append({
        "case_id": res["case_id"],
        "deletion_status": res["deletion_status"],
        "steps_json": res["steps_json"],
    })

tmp_p = PROJECT_ROOT / "scratch" / "test_improved_parse.csv"
with open(tmp_p, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
    w.writeheader()
    w.writerows(preds)

metrics = evaluate_predictions(PROJECT_ROOT / "dataset" / "sample_output.csv", tmp_p)
matches = int(round(metrics.row_level_accuracy * 32))
print(f"Results with line timestamp extraction:")
print(f"Status Accuracy:    {metrics.case_status_accuracy * 100:.2f}%")
print(f"Exact Row Accuracy: {metrics.row_level_accuracy * 100:.2f}% ({matches} / 32)")
print(f"Step Precision:     {metrics.step_precision * 100:.2f}%")
print(f"Step Recall:        {metrics.step_recall * 100:.2f}%")
print(f"Step F1 Score:      {metrics.step_f1 * 100:.2f}%")
print(f"Sequence Accuracy:  {metrics.sequence_accuracy * 100:.2f}%")
