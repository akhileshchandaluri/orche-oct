"""Evidence indexing and retrieval engine for Ghost Data Still Exists.

Parses, indexes, and normalizes evidence files (SQL snapshots, JSON exports,
structured logs, system activity) respecting strict temporal cutoffs:
requested_at <= captured_at <= audit_at.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from code.identity_resolver import UserProfile


@dataclass
class EvidenceItem:
    evidence_id: str  # file_id or activity_id
    captured_at: str
    system_id: str
    resource_id: str
    data_category: str
    observation: str  # 'PRESENT', 'ABSENT', 'EXPOSED_PII', 'ANONYMIZED', 'REDACTED', 'ACTIVE', 'DISABLED', 'BLOCKED'
    matched_key: str
    raw_details: str
    origin: str


class EvidenceIndexer:
    """Discovers and retrieves grounded evidence items for a user within temporal cutoffs."""

    def __init__(self, dataset_dir: str | Path):
        self.dataset_dir = Path(dataset_dir)
        self.manifest: Dict[str, Dict[str, str]] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        mf_path = self.dataset_dir / "evidence_files.csv"
        if not mf_path.exists():
            return
        with open(mf_path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fid = row["file_id"].strip()
                self.manifest[fid] = {
                    "file_path": row["file_path"].strip(),
                    "origin": row.get("origin", "").strip(),
                    "captured_at": row.get("captured_at", "").strip(),
                }

    def find_evidence_for_user(
        self,
        profile: UserProfile,
        audit_at: str,
        requested_at: Optional[str] = None,
    ) -> List[EvidenceItem]:
        """Find all grounded evidence items for a given user up to audit_at."""
        items: List[EvidenceItem] = []

        # Target search identifiers
        emails_lower = {e.lower() for e in profile.all_emails if e}
        phones = {p for p in profile.all_phones if p}
        hashes_lower = {h.lower() for h in profile.all_hashes if h}
        uid = profile.user_id

        # 1. Scan evidence files captured in the audit window [requested_at, audit_at]
        for fid, finfo in self.manifest.items():
            captured_at = finfo["captured_at"]
            rel_path = finfo["file_path"]

            # Files captured before request cannot contain post-request evidence
            if requested_at and captured_at and captured_at < requested_at:
                continue

            # For non-log files, captured_at must also be within audit_at
            if not rel_path.endswith(".log"):
                if captured_at and captured_at > audit_at:
                    continue

            fpath = self.dataset_dir / rel_path
            if not fpath.exists():
                continue

            origin = finfo["origin"]

            if rel_path.endswith(".txt"):
                items.extend(self._parse_handover_txt(fpath, fid, captured_at, origin, emails_lower, uid))
            elif rel_path.endswith(".json"):
                items.extend(self._parse_json_record(fpath, fid, captured_at, origin, emails_lower, phones, hashes_lower, uid))
            elif rel_path.endswith(".sql"):
                items.extend(self._parse_sql_snapshot(fpath, fid, captured_at, origin, emails_lower, phones, uid))
            elif rel_path.endswith(".log"):
                items.extend(self._parse_log_file(fpath, fid, captured_at, origin, emails_lower, phones, hashes_lower, uid, audit_at, requested_at))
            elif rel_path.endswith(".pdf"):
                items.extend(self._parse_pdf_document(fpath, fid, captured_at, origin, emails_lower, phones, uid))

        # 2. Scan system activity stream up to audit_at
        items.extend(self._parse_system_activity(emails_lower, uid, audit_at, requested_at))

        return items

    def _parse_handover_txt(
        self,
        fpath: Path,
        fid: str,
        captured_at: str,
        origin: str,
        emails: Set[str],
        uid: str,
    ) -> List[EvidenceItem]:
        results: List[EvidenceItem] = []
        try:
            with open(fpath, mode="r", encoding="utf-8") as f:
                for line in f:
                    line_clean = line.strip()
                    if not line_clean.startswith("- "):
                        continue

                    parts = [p.strip() for p in line_clean[2:].split("|")]
                    if len(parts) >= 6:
                        ts, sys_id, res_id, cat, status, id_val = parts[:6]
                        id_lower = id_val.lower()

                        matched = (id_lower in emails) or (id_val == uid)
                        if matched:
                            obs = "PRESENT"
                            if status in ["NOT_FOUND", "ABSENT"]:
                                obs = "ABSENT"
                            elif status in ["IDENTIFIABLE", "EXPOSED"]:
                                obs = "PRESENT"
                            elif status == "ANONYMIZED":
                                obs = "ANONYMIZED"
                            elif status == "ACTIVE":
                                obs = "ACTIVE"
                            elif status == "DISABLED":
                                obs = "DISABLED"
                            elif status == "BLOCKED":
                                obs = "BLOCKED"
                            elif status == "REDACTED":
                                obs = "REDACTED"
                            elif status == "FOUND":
                                obs = "PRESENT"

                            results.append(
                                EvidenceItem(
                                    evidence_id=fid,
                                    captured_at=captured_at,
                                    system_id=sys_id,
                                    resource_id=res_id,
                                    data_category=cat,
                                    observation=obs,
                                    matched_key=id_val,
                                    raw_details=line_clean,
                                    origin=origin,
                                )
                            )
        except Exception:
            pass
        return results

    def _parse_json_record(
        self,
        fpath: Path,
        fid: str,
        captured_at: str,
        origin: str,
        emails: Set[str],
        phones: Set[str],
        hashes: Set[str],
        uid: str,
    ) -> List[EvidenceItem]:
        results: List[EvidenceItem] = []
        try:
            with open(fpath, mode="r", encoding="utf-8") as f:
                data = json.load(f)

            # Snapshots bundle format
            if isinstance(data, dict) and "snapshots" in data:
                for snap in data.get("snapshots", []):
                    sys_id = snap.get("data_store", "")
                    coll = snap.get("collection", "")
                    for rec in snap.get("records", []):
                        sub_ref = str(rec.get("subject_reference") or rec.get("customer_reference") or rec.get("user_id") or "")
                        res_id = str(rec.get("resource_id", ""))
                        rec_email = str(rec.get("email") or "").lower()
                        rec_phone = str(rec.get("phone") or "")

                        if sub_ref == uid or (rec_email and rec_email in emails) or (rec_phone and rec_phone in phones):
                            if "tombstone" in res_id or coll == "deleted_customer_references":
                                cat = "ACCOUNT_TOMBSTONE"
                                if rec_email or rec_phone or rec.get("name"):
                                    obs = "EXPOSED_PII"
                                else:
                                    obs = "REDACTED"
                            elif "audit" in res_id or coll == "security_audit_events":
                                cat = "SECURITY_AUDIT_LOG"
                                obs = "PRESENT"
                            elif "analytics" in res_id or coll == "customer_analytics_reports":
                                cat = "ANALYTICS_PROFILE"
                                if rec_email or rec_phone or sub_ref:
                                    obs = "PRESENT"
                                else:
                                    obs = "ANONYMIZED"
                            else:
                                cat = "USER_PROFILE"
                                obs = "PRESENT"

                            results.append(
                                EvidenceItem(
                                    evidence_id=fid,
                                    captured_at=captured_at,
                                    system_id=sys_id,
                                    resource_id=res_id,
                                    data_category=cat,
                                    observation=obs,
                                    matched_key=sub_ref or rec_email,
                                    raw_details=json.dumps(rec),
                                    origin=origin,
                                )
                            )

            # Service resource export format
            elif isinstance(data, dict) and "service_exports" in data:
                sexp = data.get("service_exports", {})
                for sys_id, sys_val in sexp.items():
                    if isinstance(sys_val, dict):
                        for group_name, items_list in sys_val.items():
                            if isinstance(items_list, list):
                                for item in items_list:
                                    res_id = item.get("resource_id", "")
                                    cust_ref = item.get("customer_reference") or item.get("subject_reference") or ""
                                    c_email = str(item.get("customer_email") or item.get("requester_email") or item.get("email") or "").lower()
                                    item_str = json.dumps(item).lower()

                                    matched = (
                                        (cust_ref == uid)
                                        or (c_email and c_email in emails)
                                        or any(e in item_str for e in emails)
                                        or (uid.lower() in item_str)
                                    )

                                    if matched:
                                        if sys_id == "account_service":
                                            status_code = item.get("status_code", 200)
                                            prof = item.get("profile")
                                            obs = "ABSENT" if (status_code == 404 or prof is None) else "PRESENT"
                                            cat = "USER_PROFILE"
                                        elif sys_id == "integration_service":
                                            enabled = item.get("enabled", True)
                                            obs = "ACTIVE" if enabled else "DISABLED"
                                            cat = "DATA_FLOW"
                                        elif sys_id == "backup_service":
                                            restore_allowed = item.get("restore_allowed", True)
                                            obs = "ACTIVE" if restore_allowed else "BLOCKED"
                                            cat = "BACKUP_ARCHIVE"
                                        elif sys_id == "security_service":
                                            obs = "PRESENT"
                                            cat = "SECURITY_AUDIT_LOG"
                                        elif sys_id == "support_platform":
                                            r_em = item.get("requester_email")
                                            r_nm = item.get("requester_name")
                                            obs = "REDACTED" if (r_em is None and r_nm is None) else "PRESENT"
                                            cat = "SUPPORT_MESSAGE"
                                        elif sys_id == "analytics_platform":
                                            em = item.get("email")
                                            cref = item.get("customer_reference")
                                            obs = "ANONYMIZED" if (em is None and cref is None) else "PRESENT"
                                            cat = "ANALYTICS_PROFILE"
                                        else:
                                            obs = "PRESENT"
                                            cat = "USER_PROFILE"

                                        results.append(
                                            EvidenceItem(
                                                evidence_id=fid,
                                                captured_at=captured_at,
                                                system_id=sys_id,
                                                resource_id=res_id,
                                                data_category=cat,
                                                observation=obs,
                                                matched_key=cust_ref or c_email or uid,
                                                raw_details=json.dumps(item),
                                                origin=origin,
                                            )
                                        )

            # Export jobs / connector formats
            elif isinstance(data, dict) and "records" in data:
                coll = data.get("collection", "")
                src = data.get("source", "")
                for rec in data.get("records", []):
                    rec_str = json.dumps(rec).lower()
                    if any(e in rec_str for e in emails) or (uid.lower() in rec_str):
                        res_id = rec.get("job_id") or rec.get("resource_id") or rec.get("connector_id", "")
                        status = str(rec.get("status") or rec.get("state", "PRESENT")).upper()
                        
                        sys_mapped = "export_service" if "export" in src.lower() or "export" in coll.lower() else src
                        cat_mapped = "USER_EXPORT" if "export" in coll.lower() else coll

                        obs = "PRESENT"
                        if rec.get("download_available") in [True, "true"]:
                            obs = "PRESENT"
                        elif "ACTIVE" in status:
                            obs = "ACTIVE"
                        elif "DISABLE" in status:
                            obs = "DISABLED"
                        elif "ANONYMIZED" in status:
                            obs = "ANONYMIZED"
                        elif rec.get("user_id") is None and rec.get("email") is None and rec.get("owner_email") is None:
                            obs = "ANONYMIZED"
                        else:
                            obs = "PRESENT"

                        results.append(
                            EvidenceItem(
                                evidence_id=fid,
                                captured_at=captured_at,
                                system_id=sys_mapped or "export_service",
                                resource_id=res_id,
                                data_category=cat_mapped or "USER_EXPORT",
                                observation=obs,
                                matched_key=uid,
                                raw_details=json.dumps(rec),
                                origin=origin,
                            )
                        )
        except Exception:
            pass
        return results

    def _parse_sql_snapshot(
        self,
        fpath: Path,
        fid: str,
        captured_at: str,
        origin: str,
        emails: Set[str],
        phones: Set[str],
        uid: str,
    ) -> List[EvidenceItem]:
        results: List[EvidenceItem] = []
        try:
            sql_text = fpath.read_text(encoding="utf-8")
            matches = [e for e in emails if e in sql_text.lower()]
            if not matches and uid.lower() not in sql_text.lower():
                return results

            con = sqlite3.connect(":memory:")
            cur = con.cursor()
            cur.executescript(sql_text)

            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]

            for t in tables:
                cur.execute(f"PRAGMA table_info({t});")
                cols = [c[1] for c in cur.fetchall()]
                cur.execute(f"SELECT * FROM {t};")
                rows = cur.fetchall()

                for r in rows:
                    row_dict = dict(zip(cols, r))
                    if "record_json" in row_dict:
                        try:
                            rec_data = json.loads(row_dict["record_json"])
                            for k, v in rec_data.items():
                                if k not in row_dict or not row_dict[k]:
                                    row_dict[k] = v
                            if isinstance(rec_data.get("document"), dict):
                                for dk, dv in rec_data["document"].items():
                                    if dk not in row_dict or not row_dict[dk]:
                                        row_dict[dk] = dv
                        except Exception:
                            pass

                    origin_sys = row_dict.get("origin_system")
                    r_uid = str(row_dict.get("user_id") or row_dict.get("customer_reference") or row_dict.get("subject_reference") or "")
                    r_em = str(row_dict.get("email") or row_dict.get("customer_email") or row_dict.get("owner_email") or row_dict.get("requester_email") or "").lower()
                    r_ph = str(row_dict.get("phone") or row_dict.get("owner_phone") or row_dict.get("requester_phone") or "")
                    res_id = str(row_dict.get("resource_id", ""))

                    if (r_uid == uid) or (r_em and r_em in emails) or (r_ph and r_ph in phones):
                        t_lower = t.lower()
                        if origin_sys:
                            sys_id = origin_sys
                            if sys_id == "analytics_platform":
                                cat = "ANALYTICS_PROFILE"
                                obs = "PRESENT" if (r_em or (r_uid and r_uid != "None")) else "ANONYMIZED"
                            elif sys_id == "security_service":
                                cat = "SECURITY_AUDIT_LOG"
                                obs = "PRESENT"
                            elif sys_id == "search_service":
                                cat = "SEARCH_INDEX_ENTRY"
                                obs = "PRESENT"
                            elif sys_id == "account_service":
                                cat = "USER_PROFILE"
                                obs = "PRESENT"
                            else:
                                cat = "USER_PROFILE"
                                obs = "PRESENT"
                        elif "backup" in t_lower:
                            sys_id = "backup_service"
                            cat = "BACKUP_ARCHIVE"
                            restore_allowed = row_dict.get("restore_allowed")
                            obs = "ACTIVE" if restore_allowed in [1, "1", True] else "BLOCKED"
                        elif "connector" in t_lower:
                            sys_id = "integration_service"
                            cat = "DATA_FLOW"
                            enabled = row_dict.get("enabled")
                            obs = "ACTIVE" if enabled in [1, "1", True] else "DISABLED"
                        elif "search" in t_lower:
                            sys_id = "search_service"
                            cat = "SEARCH_INDEX_ENTRY"
                            obs = "PRESENT"
                        elif "export" in t_lower:
                            sys_id = "export_service"
                            cat = "USER_EXPORT"
                            obs = "PRESENT"
                        elif "support" in t_lower:
                            sys_id = "support_platform"
                            cat = "SUPPORT_MESSAGE"
                            obs = "PRESENT" if r_em else "REDACTED"
                        elif "analytics" in t_lower:
                            sys_id = "analytics_platform"
                            cat = "ANALYTICS_PROFILE"
                            obs = "PRESENT" if r_em else "ANONYMIZED"
                        elif "security" in t_lower or "audit" in t_lower:
                            sys_id = "security_service"
                            cat = "SECURITY_AUDIT_LOG"
                            obs = "PRESENT"
                        else:
                            sys_id = "account_service"
                            cat = "USER_PROFILE"
                            status_val = str(row_dict.get("account_status", "")).upper()
                            obs = "ABSENT" if "DELETE" in status_val else "PRESENT"

                        results.append(
                            EvidenceItem(
                                evidence_id=fid,
                                captured_at=captured_at,
                                system_id=sys_id,
                                resource_id=res_id,
                                data_category=cat,
                                observation=obs,
                                matched_key=r_em or r_uid,
                                raw_details=f"Table {t}: {json.dumps(row_dict)}",
                                origin=origin,
                            )
                        )
            con.close()
        except Exception:
            pass
        return results

    def _parse_pdf_document(
        self,
        fpath: Path,
        fid: str,
        captured_at: str,
        origin: str,
        emails: Set[str],
        phones: Set[str],
        uid: str,
    ) -> List[EvidenceItem]:
        results: List[EvidenceItem] = []
        try:
            import pypdfium2
            pdf = pypdfium2.PdfDocument(fpath)
            full_text = ""
            for page in pdf:
                full_text += page.get_textpage().get_text_range() + "\n"

            text_lower = full_text.lower()
            matched_em = [e for e in emails if e in text_lower]
            matched_ph = [p for p in phones if p in full_text]
            matched_uid = uid.lower() in text_lower

            if matched_em or matched_ph or matched_uid:
                res_match = re.search(r"\b(support_[0-9]+)\b", full_text)
                res_id = res_match.group(1) if res_match else fid

                sys_id = "support_platform" if "support" in origin.lower() else "security_service"
                cat = "SUPPORT_ATTACHMENT" if "support" in origin.lower() else "LEGAL_HOLD_RECORD"

                matched_val = matched_em[0] if matched_em else (matched_ph[0] if matched_ph else uid)
                results.append(
                    EvidenceItem(
                        evidence_id=fid,
                        captured_at=captured_at,
                        system_id=sys_id,
                        resource_id=res_id,
                        data_category=cat,
                        observation="PRESENT",
                        matched_key=matched_val,
                        raw_details=full_text[:300],
                        origin=origin,
                    )
                )
        except Exception:
            pass
        return results

    def _parse_log_file(
        self,
        fpath: Path,
        fid: str,
        captured_at: str,
        origin: str,
        emails: Set[str],
        phones: Set[str],
        hashes: Set[str],
        uid: str,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
    ) -> List[EvidenceItem]:
        """Parse structured logs grouping events by trace_id."""
        results: List[EvidenceItem] = []
        try:
            # Check fast filter
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            matched_em = [e for e in emails if e in content.lower()]
            matched_ph = [p for p in phones if p in content]
            matched_h = [h for h in hashes if h in content.lower()]
            matched_u = uid.lower() in content.lower()

            if not (matched_em or matched_ph or matched_h or matched_u):
                return results

            # Group lines by trace_id
            lines_by_trace: Dict[str, List[Dict[str, Any]]] = {}
            untraced_lines: List[Dict[str, Any]] = []

            for line in content.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue

                event_dict: Dict[str, Any] = {}
                json_match = re.search(r"(\{.*\})", line_str)
                if json_match:
                    try:
                        event_dict = json.loads(json_match.group(1))
                    except Exception:
                        pass
                else:
                    # Key-value line: e.g. service=xxx trace_id=xxx
                    for m in re.finditer(r'([a-zA-Z0-9_\-]+)=(?:"([^"]*)"|([^\s]+))', line_str):
                        k = m.group(1)
                        v = m.group(2) if m.group(2) is not None else m.group(3)
                        event_dict[k] = v

                if not event_dict:
                    continue

                tid = event_dict.get("trace_id")
                if tid:
                    if tid not in lines_by_trace:
                        lines_by_trace[tid] = []
                    lines_by_trace[tid].append(event_dict)
                else:
                    untraced_lines.append(event_dict)

            # Process traced groups
            for tid, events in lines_by_trace.items():
                # Check if this trace belongs to target user
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
                    # *_started events only initiate queries; results are in *_completed
                    if event_name.endswith("_started"):
                        continue

                    # Filter by event timestamp if present
                    ev_time = ev.get("timestamp") or ev.get("event_time") or ev.get("time")
                    if ev_time:
                        if audit_at and ev_time > audit_at:
                            continue
                        if requested_at and ev_time < requested_at:
                            continue

                    sys_id = ev.get("service") or ev.get("logger") or "account_service"
                    if sys_id == "support_replica":
                        sys_id = "support_platform"

                    # Observation inference
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

                    # Canonical system states
                    if sys_id == "integration_service" or "data_flow" in res_id:
                        if obs == "PRESENT":
                            obs = "ACTIVE"
                    elif sys_id == "backup_service" or "backup_" in res_id:
                        if obs == "PRESENT":
                            obs = "ACTIVE"

                    cat = "USER_PROFILE"
                    if sys_id == "integration_service" or "data_flow" in res_id:
                        cat = "DATA_FLOW"
                    elif sys_id == "backup_service" or "backup_" in res_id:
                        cat = "BACKUP_ARCHIVE"
                    elif sys_id == "security_service" or "audit_record_" in res_id:
                        cat = "SECURITY_AUDIT_LOG"
                    elif sys_id == "analytics_platform" or "analytics_" in res_id:
                        cat = "ANALYTICS_PROFILE"
                    elif sys_id == "support_platform" or "support_" in res_id:
                        cat = "SUPPORT_MESSAGE"
                    elif sys_id == "search_service" or "search_" in res_id:
                        cat = "SEARCH_INDEX_ENTRY"

                    results.append(
                        EvidenceItem(
                            evidence_id=fid,
                            captured_at=captured_at,
                            system_id=sys_id,
                            resource_id=res_id,
                            data_category=cat,
                            observation=obs,
                            matched_key=uid,
                            raw_details=json.dumps(ev),
                            origin=origin,
                        )
                    )

        except Exception:
            pass
        return results

    def _parse_system_activity(
        self,
        emails: Set[str],
        uid: str,
        audit_at: str,
        requested_at: Optional[str] = None,
    ) -> List[EvidenceItem]:
        results: List[EvidenceItem] = []
        act_file = self.dataset_dir / "system_activity.csv"
        if not act_file.exists():
            return results

        try:
            with open(act_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    etime = row["event_time"].strip()
                    if etime > audit_at:
                        continue
                    if requested_at and etime < requested_at:
                        continue

                    details = row.get("details", "")
                    details_lower = details.lower()
                    res_id = row.get("resource_id", "").strip()
                    etype = row.get("event_type", "").strip()

                    # Only inspect operational deletion events
                    if etype not in [
                        "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD",
                        "DISABLE_DATA_FLOW", "BLOCK_RESTORE", "CHECK_DATA_FLOW",
                        "CHECK_RESTORE_ACCESS",
                    ]:
                        continue

                    matched = any(e in details_lower for e in emails) or (uid.lower() in details_lower)
                    if matched:
                        aid = row.get("activity_id", "").strip()
                        tgt = row.get("target_system", "").strip()
                        res = row.get("reported_result", "").strip()

                        obs = "PRESENT"
                        if res == "SUCCESS" and etype == "DELETE_RECORD":
                            obs = "ABSENT"
                        elif res == "FAILED" or res == "PARTIAL":
                            obs = "PRESENT"
                        elif etype == "CHECK_DATA_FLOW" and "remains enabled" in details_lower:
                            obs = "ACTIVE"
                        elif etype == "CHECK_RESTORE_ACCESS" and "can still be restored" in details_lower:
                            obs = "ACTIVE"
                        elif res == "SUCCESS" and etype == "DISABLE_DATA_FLOW":
                            obs = "DISABLED"
                        elif res == "SUCCESS" and etype == "BLOCK_RESTORE":
                            obs = "BLOCKED"
                        elif res == "SUCCESS" and etype == "REDACT_RECORD":
                            obs = "REDACTED"
                        elif res == "SUCCESS" and etype == "ANONYMIZE_RECORD":
                            obs = "ANONYMIZED"

                        results.append(
                            EvidenceItem(
                                evidence_id=aid,
                                captured_at=etime,
                                system_id=tgt,
                                resource_id=res_id,
                                data_category=etype,
                                observation=obs,
                                matched_key=uid,
                                raw_details=details,
                                origin="system_activity",
                            )
                        )
        except Exception:
            pass
        return results
