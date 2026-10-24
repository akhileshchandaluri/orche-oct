import sys
sys.path.insert(0, ".")
import csv
from code.identity_resolver import IdentityResolver

resolver = IdentityResolver("dataset")

with open("dataset/sample_deletion_requests.csv", "r", encoding="utf-8") as f:
    sample_reqs = list(csv.DictReader(f))

with open("dataset/system_activity.csv", "r", encoding="utf-8") as f:
    acts = list(csv.DictReader(f))

for case in sample_reqs:
    cid = case["case_id"]
    if cid in ["case_03", "case_04", "case_21", "case_25", "case_26", "case_27", "case_28"]:
        email = case["email"]
        req_at = case["requested_at"]
        audit_at = case["audit_at"]
        profile = resolver.resolve_by_email(email)
        uid = profile.user_id if profile else "unknown"
        all_emails = list(profile.all_emails) if profile else [email]
        print(f"\n*** {cid}: user_id={uid}, emails={all_emails}, req={req_at}, audit={audit_at} ***")
        for a in acts:
            et = a["event_time"]
            det = a.get("details", "")
            if (req_at <= et <= audit_at):
                # check if related
                if any(e in det.lower() for e in all_emails) or (uid and uid in det) or a["resource_id"] in ["analytics_9406", "analytics_901", "analytics_5335", "analytics_1895", "analytics_4566", "analytics_4574", "analytics_6077"]:
                    print(f"  {a['activity_id']} | {et} | {a['source_system']} -> {a['target_system']} | {a['event_type']} | {a['resource_id']} | {det}")
