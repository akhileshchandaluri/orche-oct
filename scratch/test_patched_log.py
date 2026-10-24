import sys, os, csv, json, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evidence_indexer import EvidenceIndexer, EvidenceItem

def patched_parse_log_file(self, fpath, fid, captured_at, origin, emails, phones, hashes, uid, audit_at=None, requested_at=None, candidate_resources=None):
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
            line_time_match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)", line_str)
            line_ts = line_time_match.group(1) if line_time_match else None

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
                event_dict["line_timestamp"] = line_ts

            tid = event_dict.get("trace_id")
            if tid:
                if tid not in lines_by_trace:
                    lines_by_trace[tid] = []
                lines_by_trace[tid].append(event_dict)
            else:
                untraced_lines.append(event_dict)

        for tid, events in lines_by_trace.items():
            trace_str = json.dumps(events).lower()
            trace_matches = (
                any(e in trace_str for e in emails)
                or any(p in trace_str for p in phones)
                or any(h in trace_str for h in hashes)
                or (uid.lower() in trace_str)
                or any(r in trace_str for r in (candidate_resources or []))
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

                ev_time = ev.get("timestamp") or ev.get("event_time") or ev.get("time") or ev.get("line_timestamp")
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
                    if obs == "PRESENT":
                        obs = "ACTIVE"

                results.append(EvidenceItem(
                    evidence_id=fid,
                    captured_at=ev_time,
                    system_id=sys_id,
                    resource_id=res_id,
                    data_category="LOG_TRACE",
                    observation=obs,
                    matched_key=f"trace:{tid}",
                    raw_details=json.dumps(ev),
                    origin=origin,
                ))
    except Exception:
        pass
    return results

from unittest.mock import patch
with patch.object(EvidenceIndexer, "_parse_log_file", new=patched_parse_log_file):
    engine = PredictionEngine(dataset_dir="dataset", enable_groq=False)
    sample_reqs = list(csv.DictReader(open("dataset/sample_deletion_requests.csv", encoding="utf-8")))
    rows = []
    for r in sample_reqs:
        res = engine.audit_case(r)
        rows.append({
            "case_id": res["case_id"],
            "deletion_status": res["deletion_status"],
            "steps_json": res["steps_json"],
        })
    with open("scratch/pred_patched_log.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
        w.writeheader()
        w.writerows(rows)

eval_res = evaluate_predictions("scratch/pred_patched_log.csv", "dataset/sample_output.csv")
print(f"Patched Log Parsing Benchmark:")
print(f"  Status Accuracy:   {eval_res.case_status_accuracy * 100:.2f}%")
matching_rows = eval_res.evaluated_cases - len([c for c in eval_res.case_results if not c.exact_row_match])
print(f"  Exact-Row Accuracy:{eval_res.row_level_accuracy * 100:.2f}% ({matching_rows}/32)")
print(f"  Step Precision:    {eval_res.step_precision * 100:.2f}%")
print(f"  Step Recall:       {eval_res.step_recall * 100:.2f}%")
print(f"  Step F1:           {eval_res.step_f1 * 100:.2f}%")
print(f"  Sequence Accuracy: {eval_res.sequence_accuracy * 100:.2f}%")

# Print which cases changed!
truth = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("dataset/sample_output.csv", encoding="utf-8"))}
patched = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/pred_patched_log.csv", encoding="utf-8"))}
current = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(open("scratch/pred_current_prompt3.csv", encoding="utf-8"))}

for cid in sorted(truth.keys()):
    c_m = (current[cid] == truth[cid])
    p_m = (patched[cid] == truth[cid])
    if c_m != p_m:
        print(f"Case {cid} changed! Current match: {c_m} -> Patched match: {p_m}")
