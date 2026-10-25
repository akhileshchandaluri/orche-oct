"""Agent Tools for Ghost Data Still Exists.

Exposes read-only forensic retrieval and inspection tools that an AI agent or LLM
can call during deletion audit investigation.

Hard constraints enforced by every tool:
1. Strict Temporal Cutoff: Evidence captured after audit_at is NEVER returned.
   Evidence captured before requested_at is flagged "pre_request".
2. Provenance Ledger: Every file_id, activity_id, audit_id, and resource_id returned
   is recorded in a per-case ProvenanceLedger.
3. Read-Only Safety: No side effects on datasets or system state.
4. Structured Errors: Any failure returns {"error": ...} rather than crashing.
"""

from __future__ import annotations

import csv
import datetime
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Attempt safe import of pypdfium2
try:
    import pypdfium2 as pdfium
    _PDFIUM_AVAILABLE = True
except ImportError:
    pdfium = None
    _PDFIUM_AVAILABLE = False

from code.identity_resolver import IdentityResolver, UserProfile


@dataclass
class ProvenanceLedger:
    """Per-case audit ledger recording every grounded identifier accessed."""

    case_id: str = ""
    file_ids: Set[str] = field(default_factory=set)
    activity_ids: Set[str] = field(default_factory=set)
    audit_ids: Set[str] = field(default_factory=set)
    resource_ids: Set[str] = field(default_factory=set)
    access_events: List[Dict[str, Any]] = field(default_factory=list)

    def record_access(
        self,
        tool_name: str,
        file_id: Optional[str] = None,
        activity_id: Optional[str] = None,
        audit_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record evidence or identifier citation in the ledger."""
        if file_id:
            self.file_ids.add(file_id.strip())
        if activity_id:
            self.activity_ids.add(activity_id.strip())
        if audit_id:
            self.audit_ids.add(audit_id.strip())
        if resource_id:
            self.resource_ids.add(resource_id.strip())

        self.access_events.append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "tool_name": tool_name,
            "file_id": file_id,
            "activity_id": activity_id,
            "audit_id": audit_id,
            "resource_id": resource_id,
            "details": details or {},
        })

    def reset(self, new_case_id: str = "") -> None:
        """Clear ledger for a new case."""
        self.case_id = new_case_id
        self.file_ids.clear()
        self.activity_ids.clear()
        self.audit_ids.clear()
        self.resource_ids.clear()
        self.access_events.clear()

    def summary(self) -> Dict[str, Any]:
        """Return serializable summary of all grounded evidence citations."""
        return {
            "case_id": self.case_id,
            "total_file_ids": len(self.file_ids),
            "file_ids": sorted(self.file_ids),
            "total_activity_ids": len(self.activity_ids),
            "activity_ids": sorted(self.activity_ids),
            "total_audit_ids": len(self.audit_ids),
            "audit_ids": sorted(self.audit_ids),
            "total_resource_ids": len(self.resource_ids),
            "resource_ids": sorted(self.resource_ids),
            "total_access_events": len(self.access_events),
        }


# Regex pattern to detect canonical Northstar Shop resource IDs
RESOURCE_ID_REGEX = re.compile(
    r"\b(?:account|search|analytics|support|email_delivery|audit_record|export|data_flow|backup)_[a-zA-Z0-9_]+\b"
)


class AgentTools:
    """Read-only forensic inspection tools for the LLM deletion-audit agent."""

    def __init__(
        self,
        dataset_dir: str | Path,
        ledger: Optional[ProvenanceLedger] = None,
        current_case_row: Optional[Dict[str, str]] = None,
        engine: Optional[Any] = None,
    ):
        self.dataset_dir = Path(dataset_dir)
        self.ledger = ledger if ledger is not None else ProvenanceLedger()
        self.current_case_row = current_case_row
        self.engine = engine

        # Shared component indexers
        self.resolver = IdentityResolver(self.dataset_dir)
        self.manifest: Dict[str, Dict[str, str]] = {}
        self.manifest_by_path: Dict[str, str] = {}
        self.ocr_cache: Dict[str, List[str]] = {}
        self.system_activities: List[Dict[str, str]] = []
        self.user_audit_logs: List[Dict[str, str]] = []
        self.deletion_rules: List[Dict[str, str]] = []

        self._load_all_metadata()

    def _load_all_metadata(self) -> None:
        """Load manifest, activities, audit logs, OCR cache, and deletion rules."""
        # 1. Manifest
        mf_path = self.dataset_dir / "evidence_files.csv"
        if mf_path.exists():
            with open(mf_path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    fid = row["file_id"].strip()
                    fpath = row["file_path"].strip()
                    self.manifest[fid] = {
                        "file_id": fid,
                        "file_path": fpath,
                        "origin": row.get("origin", "").strip(),
                        "captured_at": row.get("captured_at", "").strip(),
                    }
                    self.manifest_by_path[fpath] = fid
                    self.manifest_by_path[Path(fpath).name] = fid

        # 2. OCR Cache
        ocr_path = self.dataset_dir / "evidence" / "images" / "ocr_cache.json"
        if ocr_path.exists():
            try:
                with open(ocr_path, mode="r", encoding="utf-8") as f:
                    self.ocr_cache = json.load(f)
            except Exception:
                self.ocr_cache = {}

        # 3. System Activity
        act_path = self.dataset_dir / "system_activity.csv"
        if act_path.exists():
            with open(act_path, mode="r", encoding="utf-8") as f:
                self.system_activities = list(csv.DictReader(f))

        # 4. User Audit Log
        audit_path = self.dataset_dir / "user_audit_log.csv"
        if audit_path.exists():
            with open(audit_path, mode="r", encoding="utf-8") as f:
                self.user_audit_logs = list(csv.DictReader(f))

        # 5. Deletion Rules
        rules_path = self.dataset_dir / "deletion_rules.csv"
        if rules_path.exists():
            with open(rules_path, mode="r", encoding="utf-8") as f:
                self.deletion_rules = list(csv.DictReader(f))

    # -------------------------------------------------------------------------
    # Tool 1: resolve_identity
    # -------------------------------------------------------------------------
    def resolve_identity(self, identifier: str) -> Dict[str, Any]:
        """Resolve current and historical identity profiles via IdentityResolver.
        
        Accepts email, phone number, user_id, or email_hash.
        """
        try:
            if not identifier or not isinstance(identifier, str):
                return {"error": "Invalid identifier: must be a non-empty string"}

            clean_id = identifier.strip()

            # Attempt resolution across supported identity keys
            profile: Optional[UserProfile] = None
            if "@" in clean_id:
                profile = self.resolver.resolve_by_email(clean_id)
            elif clean_id.startswith("user_"):
                profile = self.resolver.resolve_by_user_id(clean_id)
            elif clean_id.startswith("+") or clean_id.replace(" ", "").isdigit():
                profile = self.resolver.resolve_by_phone(clean_id)
            elif len(clean_id) == 64:  # SHA-256 hash length
                profile = self.resolver.resolve_by_hash(clean_id)

            # Fallback cascade
            if not profile:
                profile = (
                    self.resolver.resolve_by_email(clean_id)
                    or self.resolver.resolve_by_user_id(clean_id)
                    or self.resolver.resolve_by_phone(clean_id)
                    or self.resolver.resolve_by_hash(clean_id)
                )

            if not profile:
                return {
                    "found": False,
                    "identifier": identifier,
                    "message": "No matching user profile found in identities or audit log",
                }

            # Record provenance
            self.ledger.record_access("resolve_identity", resource_id=profile.user_id)
            for link in profile.audit_links:
                self.ledger.record_access("resolve_identity", audit_id=link.audit_id, resource_id=profile.user_id)

            return {
                "found": True,
                "user_id": profile.user_id,
                "current_name": profile.current_name,
                "current_email": profile.current_email,
                "current_phone": profile.current_phone,
                "current_email_hash": profile.current_email_hash,
                "all_emails": sorted(profile.all_emails),
                "all_phones": sorted(profile.all_phones),
                "all_hashes": sorted(profile.all_hashes),
                "audit_links": [
                    {
                        "audit_id": link.audit_id,
                        "field_name": link.field_name,
                        "old_value": link.old_value,
                        "new_value": link.new_value,
                        "event_time": link.event_time,
                    }
                    for link in profile.audit_links
                ],
            }
        except Exception as e:
            return {"error": f"Failed to resolve identity: {str(e)}"}

    # -------------------------------------------------------------------------
    # Tool 2: list_evidence_manifest
    # -------------------------------------------------------------------------
    def list_evidence_manifest(
        self,
        system_id: Optional[str] = None,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List rows from evidence_files.csv filtered by system_id and temporal cutoff.
        
        Strict cutoff: rows captured after audit_at are NEVER returned.
        """
        try:
            results = []
            for fid, row in self.manifest.items():
                captured_at = row["captured_at"]

                # 1. Enforce strict post-audit cutoff
                if audit_at and captured_at and captured_at > audit_at:
                    continue

                # 2. Optional system_id filter
                if system_id:
                    sys_lower = system_id.lower()
                    if sys_lower not in row["origin"].lower() and sys_lower not in row["file_path"].lower():
                        continue

                # 3. Pre-request tagging
                temporal_status = "in_window"
                if requested_at and captured_at and captured_at < requested_at:
                    temporal_status = "pre_request"

                # Record provenance
                self.ledger.record_access("list_evidence_manifest", file_id=fid)

                results.append({
                    "file_id": fid,
                    "file_path": row["file_path"],
                    "origin": row["origin"],
                    "captured_at": captured_at,
                    "temporal_status": temporal_status,
                })

            return results
        except Exception as e:
            return [{"error": f"Failed to list evidence manifest: {str(e)}"}]

    # -------------------------------------------------------------------------
    # Tool 3: search_evidence
    # -------------------------------------------------------------------------
    def search_evidence(
        self,
        query: str,
        system_id: Optional[str] = None,
        max_results: int = 20,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search across SQL dumps, logs, JSON/JSONL, PDF text (pypdfium2), and ocr_cache.json.
        
        Strict cutoff: evidence captured after audit_at is NEVER searched or returned.
        """
        try:
            if not query or not isinstance(query, str):
                return [{"error": "Invalid search query: must be non-empty string"}]

            q_lower = query.strip().lower()
            results: List[Dict[str, Any]] = []

            for fid, info in self.manifest.items():
                if len(results) >= max_results:
                    break

                captured_at = info["captured_at"]

                # 1. Enforce strict post-audit cutoff
                if audit_at and captured_at and captured_at > audit_at:
                    continue

                # 2. System filter
                if system_id:
                    sys_lower = system_id.lower()
                    if sys_lower not in info["origin"].lower() and sys_lower not in info["file_path"].lower():
                        continue

                rel_path = info["file_path"]
                full_path = self.dataset_dir / rel_path
                if not full_path.exists():
                    continue

                temporal_status = "pre_request" if (requested_at and captured_at < requested_at) else "in_window"

                # Search by file type
                ext = full_path.suffix.lower()

                # A. SQL Dumps, Text Logs, JSON / JSONL
                if ext in [".sql", ".log", ".txt", ".json", ".jsonl"]:
                    try:
                        with open(full_path, mode="r", encoding="utf-8", errors="ignore") as f:
                            for line_idx, line in enumerate(f, start=1):
                                if q_lower in line.lower():
                                    snippet = line.strip()[:200]
                                    res_ids = RESOURCE_ID_REGEX.findall(snippet)

                                    self.ledger.record_access("search_evidence", file_id=fid)
                                    for r in res_ids:
                                        self.ledger.record_access("search_evidence", file_id=fid, resource_id=r)

                                    results.append({
                                        "file_id": fid,
                                        "file_path": rel_path,
                                        "captured_at": captured_at,
                                        "temporal_status": temporal_status,
                                        "line_ref": f"line:{line_idx}",
                                        "snippet": snippet,
                                        "resource_ids": sorted(set(res_ids)),
                                    })
                                    if len(results) >= max_results:
                                        break
                    except Exception:
                        pass

                # B. PDF Documents (pypdfium2)
                elif ext == ".pdf":
                    if _PDFIUM_AVAILABLE and pdfium is not None:
                        try:
                            doc = pdfium.PdfDocument(full_path)
                            for page_idx, page in enumerate(doc, start=1):
                                textpage = page.get_textpage()
                                text = textpage.get_text_range()
                                for line_idx, line in enumerate(text.splitlines(), start=1):
                                    if q_lower in line.lower():
                                        snippet = line.strip()[:200]
                                        res_ids = RESOURCE_ID_REGEX.findall(snippet)

                                        self.ledger.record_access("search_evidence", file_id=fid)
                                        for r in res_ids:
                                            self.ledger.record_access("search_evidence", file_id=fid, resource_id=r)

                                        results.append({
                                            "file_id": fid,
                                            "file_path": rel_path,
                                            "captured_at": captured_at,
                                            "temporal_status": temporal_status,
                                            "line_ref": f"page:{page_idx}:line:{line_idx}",
                                            "snippet": snippet,
                                            "resource_ids": sorted(set(res_ids)),
                                        })
                                        if len(results) >= max_results:
                                            break
                                if len(results) >= max_results:
                                    break
                        except Exception:
                            pass

                # C. PNG Image OCR Text
                elif ext == ".png":
                    fname = full_path.name
                    ocr_tokens = self.ocr_cache.get(fname, [])
                    full_ocr_str = " ".join(ocr_tokens)
                    if q_lower in full_ocr_str.lower():
                        # Find matching window in tokens
                        matching_sub = [tok for tok in ocr_tokens if q_lower in tok.lower()]
                        snippet = f"OCR Tokens matching '{query}': {', '.join(matching_sub[:5])}"
                        res_ids = RESOURCE_ID_REGEX.findall(full_ocr_str)

                        self.ledger.record_access("search_evidence", file_id=fid)
                        for r in res_ids:
                            self.ledger.record_access("search_evidence", file_id=fid, resource_id=r)

                        results.append({
                            "file_id": fid,
                            "file_path": rel_path,
                            "captured_at": captured_at,
                            "temporal_status": temporal_status,
                            "line_ref": f"image_ocr:{fname}",
                            "snippet": snippet[:200],
                            "resource_ids": sorted(set(res_ids)),
                        })

            return results
        except Exception as e:
            return [{"error": f"Search failed: {str(e)}"}]

    # -------------------------------------------------------------------------
    # Tool 4: read_evidence
    # -------------------------------------------------------------------------
    def read_evidence(
        self,
        file_id: str,
        locator: Optional[str] = None,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
        max_chars: int = 4000,
    ) -> Dict[str, Any]:
        """Return bounded content for a file_id.
        
        Strict cutoff: if captured_at > audit_at, content is withheld and an error returned.
        """
        try:
            fid = file_id.strip()
            if fid not in self.manifest:
                return {"error": f"file_id '{fid}' not found in evidence manifest"}

            info = self.manifest[fid]
            captured_at = info["captured_at"]

            # 1. Enforce strict post-audit cutoff
            if audit_at and captured_at and captured_at > audit_at:
                return {
                    "error": f"Evidence {fid} was captured at {captured_at}, which is after audit cutoff {audit_at}. Access denied.",
                    "cutoff_enforced": True,
                    "file_id": fid,
                    "captured_at": captured_at,
                    "audit_at": audit_at,
                }

            full_path = self.dataset_dir / info["file_path"]
            if not full_path.exists():
                return {"error": f"Evidence file not found on disk: {info['file_path']}"}

            ext = full_path.suffix.lower()
            content = ""

            # Extract content based on format
            if ext == ".pdf":
                if _PDFIUM_AVAILABLE and pdfium is not None:
                    doc = pdfium.PdfDocument(full_path)
                    pages = []
                    for i, page in enumerate(doc, start=1):
                        txt = page.get_textpage().get_text_range()
                        pages.append(f"--- Page {i} ---\n{txt}")
                    content = "\n".join(pages)
                else:
                    content = "[pypdfium2 not installed: unable to parse PDF binary]"
            elif ext == ".png":
                fname = full_path.name
                tokens = self.ocr_cache.get(fname, [])
                content = f"--- OCR Content for {fname} ---\n" + "\n".join(tokens)
            else:
                with open(full_path, mode="r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

            # Handle locator filter if provided
            if locator and locator.startswith("line:"):
                # locator format e.g. "line:10-40"
                range_part = locator.split("line:", 1)[1]
                lines = content.splitlines()
                if "-" in range_part:
                    p1, p2 = range_part.split("-", 1)
                    start_l = max(1, int(p1)) if p1.isdigit() else 1
                    end_l = min(len(lines), int(p2)) if p2.isdigit() else len(lines)
                else:
                    start_l = max(1, int(range_part)) if range_part.isdigit() else 1
                    end_l = min(len(lines), start_l + 50)
                content = "\n".join(lines[start_l - 1:end_l])

            # Enforce bounded size cap
            orig_len = len(content)
            truncated = False
            if orig_len > max_chars:
                content = content[:max_chars]
                truncated = True

            # Record provenance
            self.ledger.record_access("read_evidence", file_id=fid)
            res_ids = RESOURCE_ID_REGEX.findall(content)
            for r in res_ids:
                self.ledger.record_access("read_evidence", file_id=fid, resource_id=r)

            temporal_status = "pre_request" if (requested_at and captured_at < requested_at) else "in_window"

            return {
                "file_id": fid,
                "file_path": info["file_path"],
                "origin": info["origin"],
                "captured_at": captured_at,
                "temporal_status": temporal_status,
                "content": content,
                "truncated": truncated,
                "returned_chars": len(content),
                "total_chars": orig_len,
                "discovered_resource_ids": sorted(set(res_ids)),
            }
        except Exception as e:
            return {"error": f"Failed to read evidence: {str(e)}"}

    # -------------------------------------------------------------------------
    # Tool 5: query_sql_snapshot
    # -------------------------------------------------------------------------
    def query_sql_snapshot(
        self,
        file_id: str,
        table: str,
        where_column: str,
        where_value: str,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parameterized read-only query against a point-in-time SQLite SQL dump.
        
        Strict cutoff: SQL snapshots captured after audit_at are rejected.
        """
        try:
            fid = file_id.strip()
            if fid not in self.manifest:
                return {"error": f"file_id '{fid}' not found in evidence manifest"}

            info = self.manifest[fid]
            captured_at = info["captured_at"]

            # 1. Enforce strict post-audit cutoff
            if audit_at and captured_at and captured_at > audit_at:
                return {
                    "error": f"SQL snapshot {fid} was captured at {captured_at}, which is after audit cutoff {audit_at}.",
                    "cutoff_enforced": True,
                }

            full_path = self.dataset_dir / info["file_path"]
            if not full_path.exists():
                return {"error": f"SQL snapshot file missing on disk: {info['file_path']}"}

            if not full_path.suffix.lower() == ".sql":
                return {"error": f"file_id '{fid}' ({full_path.name}) is not a SQL snapshot"}

            # Parameterized safety: ensure table and where_column are valid identifiers
            if not re.match(r"^[a-zA-Z0-9_]+$", table):
                return {"error": f"Invalid table identifier '{table}'"}
            if not re.match(r"^[a-zA-Z0-9_]+$", where_column):
                return {"error": f"Invalid column identifier '{where_column}'"}

            # Read script and execute in temporary in-memory SQLite database
            with open(full_path, mode="r", encoding="utf-8", errors="ignore") as f:
                sql_text = f.read()

            conn = sqlite3.connect(":memory:")
            try:
                conn.executescript(sql_text)
                cursor = conn.cursor()

                # Verify table exists in snapshot
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                avail_tables = [row[0] for row in cursor.fetchall()]
                if table not in avail_tables:
                    return {
                        "error": f"Table '{table}' not found in snapshot",
                        "available_tables": avail_tables,
                    }

                query = f"SELECT * FROM {table} WHERE {where_column} = ?"
                cursor.execute(query, (where_value,))
                cols = [desc[0] for desc in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

                # Record provenance
                self.ledger.record_access("query_sql_snapshot", file_id=fid)
                for r in rows:
                    for k, v in r.items():
                        if isinstance(v, str):
                            if k == "resource_id" or RESOURCE_ID_REGEX.match(v):
                                self.ledger.record_access("query_sql_snapshot", file_id=fid, resource_id=v)
                            elif k == "user_id" or v.startswith("user_"):
                                self.ledger.record_access("query_sql_snapshot", file_id=fid, resource_id=v)

                temporal_status = "pre_request" if (requested_at and captured_at < requested_at) else "in_window"

                return {
                    "file_id": fid,
                    "table": table,
                    "where_clause": f"{where_column} = '{where_value}'",
                    "captured_at": captured_at,
                    "temporal_status": temporal_status,
                    "row_count": len(rows),
                    "rows": rows,
                }
            finally:
                conn.close()

        except Exception as e:
            return {"error": f"SQL query failed: {str(e)}"}

    # -------------------------------------------------------------------------
    # Tool 6: search_activity
    # -------------------------------------------------------------------------
    def search_activity(
        self,
        identifier: str,
        system_id: Optional[str] = None,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Search system_activity.csv and user_audit_log.csv for events.
        
        Strict cutoff: activity and audit events timestamped after audit_at are omitted.
        """
        try:
            if not identifier or not isinstance(identifier, str):
                return {"error": "Invalid identifier: must be non-empty string"}

            q_lower = identifier.strip().lower()
            matched_activities: List[Dict[str, Any]] = []
            matched_audits: List[Dict[str, Any]] = []

            # 1. Search system_activity.csv
            for act in self.system_activities:
                if len(matched_activities) >= max_results:
                    break
                etime = act.get("event_time", "")

                # Cutoff check
                if audit_at and etime and etime > audit_at:
                    continue

                # System filter
                if system_id:
                    s_lower = system_id.lower()
                    src = act.get("source_system", "").lower()
                    tgt = act.get("target_system", "").lower()
                    if s_lower not in src and s_lower not in tgt:
                        continue

                # Match against fields
                res_id = act.get("resource_id", "")
                details = act.get("details", "")
                if q_lower in res_id.lower() or q_lower in details.lower():
                    aid = act.get("activity_id", "")
                    self.ledger.record_access("search_activity", activity_id=aid, resource_id=res_id)

                    temporal_status = "pre_request" if (requested_at and etime < requested_at) else "in_window"
                    matched_activities.append({
                        "activity_id": aid,
                        "event_time": etime,
                        "event_type": act.get("event_type", ""),
                        "source_system": act.get("source_system", ""),
                        "target_system": act.get("target_system", ""),
                        "resource_id": res_id,
                        "reported_result": act.get("reported_result", ""),
                        "details": details,
                        "temporal_status": temporal_status,
                    })

            # 2. Search user_audit_log.csv
            for aud in self.user_audit_logs:
                if len(matched_audits) >= max_results:
                    break
                etime = aud.get("event_time", "")

                # Cutoff check
                if audit_at and etime and etime > audit_at:
                    continue

                uid = aud.get("user_id", "")
                old_val = aud.get("old_value", "")
                new_val = aud.get("new_value", "")
                audit_id = aud.get("audit_id", "")

                if (
                    q_lower in uid.lower()
                    or q_lower in old_val.lower()
                    or q_lower in new_val.lower()
                    or q_lower in audit_id.lower()
                ):
                    self.ledger.record_access("search_activity", audit_id=audit_id, resource_id=uid)
                    temporal_status = "pre_request" if (requested_at and etime < requested_at) else "in_window"
                    matched_audits.append({
                        "audit_id": audit_id,
                        "user_id": uid,
                        "event_time": etime,
                        "field_name": aud.get("field_name", ""),
                        "old_value": old_val,
                        "new_value": new_val,
                        "temporal_status": temporal_status,
                    })

            return {
                "identifier": identifier,
                "total_matches": len(matched_activities) + len(matched_audits),
                "system_activity_matches": matched_activities,
                "user_audit_matches": matched_audits,
            }
        except Exception as e:
            return {"error": f"Failed to search activity logs: {str(e)}"}

    # -------------------------------------------------------------------------
    # Tool 7: get_deletion_rules
    # -------------------------------------------------------------------------
    def get_deletion_rules(self, data_category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return official policy rules from deletion_rules.csv."""
        try:
            if not data_category:
                return self.deletion_rules

            cat_lower = data_category.strip().lower()
            return [
                rule for rule in self.deletion_rules
                if rule.get("data_category", "").strip().lower() == cat_lower
            ]
        except Exception as e:
            return [{"error": f"Failed to retrieve deletion rules: {str(e)}"}]

    # -------------------------------------------------------------------------
    # Tool 8: check_temporal_window
    # -------------------------------------------------------------------------
    def check_temporal_window(
        self,
        file_id: str,
        requested_at: str,
        audit_at: str,
    ) -> Dict[str, Any]:
        """Check whether evidence item falls in/out of the audit window and explain why."""
        try:
            fid = file_id.strip()
            if fid not in self.manifest:
                return {"error": f"file_id '{fid}' not found in evidence manifest"}

            info = self.manifest[fid]
            captured_at = info["captured_at"]

            self.ledger.record_access("check_temporal_window", file_id=fid)

            if captured_at > audit_at:
                return {
                    "file_id": fid,
                    "captured_at": captured_at,
                    "requested_at": requested_at,
                    "audit_at": audit_at,
                    "in_window": False,
                    "temporal_status": "post_audit",
                    "reason": f"Captured at {captured_at}, which is strictly after audit cutoff {audit_at}. Prohibited from use.",
                }
            elif captured_at < requested_at:
                return {
                    "file_id": fid,
                    "captured_at": captured_at,
                    "requested_at": requested_at,
                    "audit_at": audit_at,
                    "in_window": False,
                    "temporal_status": "pre_request",
                    "reason": f"Captured at {captured_at}, which is before the deletion request time {requested_at}.",
                }
            else:
                return {
                    "file_id": fid,
                    "captured_at": captured_at,
                    "requested_at": requested_at,
                    "audit_at": audit_at,
                    "in_window": True,
                    "temporal_status": "in_window",
                    "reason": f"Captured at {captured_at}, which falls cleanly within [{requested_at}, {audit_at}].",
                }
        except Exception as e:
            return {"error": f"Temporal window check failed: {str(e)}"}

    # -------------------------------------------------------------------------
    # Tool 9: get_baseline_analysis
    # -------------------------------------------------------------------------
    def get_baseline_analysis(
        self,
        audit_at: Optional[str] = None,
        requested_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns the existing prediction engine's draft analysis and steps for the current case.
        
        Enforces the case temporal cutoff and records all generated resource_ids and evidence_ids into the ledger.
        """
        if not self.current_case_row:
            return {"error": "No current_case_row configured for baseline analysis."}

        if not self.engine:
            from code.prediction_engine import PredictionEngine
            self.engine = PredictionEngine(dataset_dir=self.dataset_dir, enable_groq=False)

        row = dict(self.current_case_row)
        if audit_at:
            row["audit_at"] = audit_at
        if requested_at:
            row["requested_at"] = requested_at

        try:
            draft_result = self.engine.audit_case(row)
            draft_status = draft_result.get("deletion_status", "INCOMPLETE")
            raw_steps_json = draft_result.get("steps_json", "[]")
            draft_steps = json.loads(raw_steps_json) if isinstance(raw_steps_json, str) else (raw_steps_json or [])

            for st in draft_steps:
                fid = st.get("evidence_id", "").strip()
                rid = st.get("resource_id", "").strip()
                if fid:
                    self.ledger.record_access("get_baseline_analysis", file_id=fid)
                if rid:
                    self.ledger.record_access("get_baseline_analysis", resource_id=rid)

            return {
                "draft_status": draft_status,
                "draft_steps": draft_steps,
                "draft_summary": f"Baseline engine draft: status={draft_status}, {len(draft_steps)} steps proposed.",
            }
        except Exception as e:
            return {"error": f"Failed to compute baseline analysis: {str(e)}"}

    # -------------------------------------------------------------------------
    # Dispatcher
    # -------------------------------------------------------------------------
    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Dynamically dispatch tool execution by name with error trapping."""
        dispatch_map = {
            "get_baseline_analysis": lambda args: self.get_baseline_analysis(
                audit_at=args.get("audit_at"),
                requested_at=args.get("requested_at"),
            ),
            "resolve_identity": lambda args: self.resolve_identity(args.get("identifier", "")),
            "list_evidence_manifest": lambda args: self.list_evidence_manifest(
                system_id=args.get("system_id"),
                audit_at=args.get("audit_at"),
                requested_at=args.get("requested_at"),
            ),
            "search_evidence": lambda args: self.search_evidence(
                query=args.get("query", ""),
                system_id=args.get("system_id"),
                max_results=int(args.get("max_results", 20)),
                audit_at=args.get("audit_at"),
                requested_at=args.get("requested_at"),
            ),
            "read_evidence": lambda args: self.read_evidence(
                file_id=args.get("file_id", ""),
                locator=args.get("locator"),
                audit_at=args.get("audit_at"),
                requested_at=args.get("requested_at"),
                max_chars=int(args.get("max_chars", 4000)),
            ),
            "query_sql_snapshot": lambda args: self.query_sql_snapshot(
                file_id=args.get("file_id", ""),
                table=args.get("table", ""),
                where_column=args.get("where_column", ""),
                where_value=args.get("where_value", ""),
                audit_at=args.get("audit_at"),
                requested_at=args.get("requested_at"),
            ),
            "search_activity": lambda args: self.search_activity(
                identifier=args.get("identifier", ""),
                system_id=args.get("system_id"),
                audit_at=args.get("audit_at"),
                requested_at=args.get("requested_at"),
                max_results=int(args.get("max_results", 50)),
            ),
            "get_deletion_rules": lambda args: self.get_deletion_rules(
                data_category=args.get("data_category")
            ),
            "check_temporal_window": lambda args: self.check_temporal_window(
                file_id=args.get("file_id", ""),
                requested_at=args.get("requested_at", ""),
                audit_at=args.get("audit_at", ""),
            ),
        }

        func = dispatch_map.get(name)
        if not func:
            return {
                "error": f"Unknown tool '{name}'",
                "available_tools": list(dispatch_map.keys()),
            }

        try:
            return func(arguments)
        except Exception as e:
            return {"error": f"Tool '{name}' execution failed: {str(e)}"}


# =============================================================================
# JSON Schema Definitions for LLM Tool Calling (OpenAI / Groq Standard)
# =============================================================================
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_baseline_analysis",
            "description": "Retrieves the deterministic baseline engine's draft analysis, proposed status, and steps for the current case. Use this as an initial hypothesis to verify, refine, or dispute.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_identity",
            "description": "Resolves all current and historical emails, phones, names, email_hash, and user_id using the identity graph. Accepts email, phone, user_id, or email_hash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "The user identifier to resolve (email, phone, user_id, or SHA-256 email hash).",
                    }
                },
                "required": ["identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_evidence_manifest",
            "description": "Lists rows from evidence_files.csv with origin and capture time. Automatically excludes any evidence captured after audit_at.",
            "parameters": {
                "type": "object",
                "properties": {
                    "system_id": {
                        "type": "string",
                        "description": "Optional filter by system domain (e.g., account_service, search_service).",
                    },
                    "audit_at": {
                        "type": "string",
                        "description": "ISO timestamp cutoff. Evidence captured after this time is never returned.",
                    },
                    "requested_at": {
                        "type": "string",
                        "description": "Optional ISO timestamp of deletion request to flag pre-request evidence.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_evidence",
            "description": "Searches across SQL dumps, structured logs, JSON/JSONL records, PDF documents (via pypdfium2), and OCR screenshot text. Returns snippets with file_id and location references.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., user_id, email, phone, hash, or account_id).",
                    },
                    "system_id": {
                        "type": "string",
                        "description": "Optional filter by system or service name.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of snippet results to return (default 20).",
                    },
                    "audit_at": {
                        "type": "string",
                        "description": "ISO timestamp cutoff. Files captured after this time are excluded from search.",
                    },
                    "requested_at": {
                        "type": "string",
                        "description": "Optional ISO timestamp to tag pre-request evidence.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_evidence",
            "description": "Reads bounded content from an evidence file. Strictly refuses to return content if captured after audit_at. Supports locators to narrow down lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The evidence file identifier (e.g., evidence_01).",
                    },
                    "locator": {
                        "type": "string",
                        "description": "Optional locator to restrict content (e.g., 'line:1-50').",
                    },
                    "audit_at": {
                        "type": "string",
                        "description": "ISO timestamp cutoff. If file was captured after this, access is denied.",
                    },
                    "requested_at": {
                        "type": "string",
                        "description": "Optional ISO timestamp to tag pre-request evidence.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default 4000). Truncation is indicated.",
                    },
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_sql_snapshot",
            "description": "Executes a parameterized read-only SELECT query against an SQLite-compatible point-in-time SQL snapshot dump.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The SQL evidence file identifier (e.g., evidence_05).",
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name to query (must be alphanumeric/underscore).",
                    },
                    "where_column": {
                        "type": "string",
                        "description": "Column name to filter on (e.g., user_id or resource_id).",
                    },
                    "where_value": {
                        "type": "string",
                        "description": "Value to match exactly in the filter column.",
                    },
                    "audit_at": {
                        "type": "string",
                        "description": "ISO timestamp cutoff. Rejects query if snapshot was captured after cutoff.",
                    },
                    "requested_at": {
                        "type": "string",
                        "description": "Optional ISO timestamp to tag pre-request status.",
                    },
                },
                "required": ["file_id", "table", "where_column", "where_value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_activity",
            "description": "Searches global operational logs in system_activity.csv and user_audit_log.csv for operations involving a user_id, resource_id, or email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "The user_id, resource_id, or email to search for.",
                    },
                    "system_id": {
                        "type": "string",
                        "description": "Optional filter by source or target system.",
                    },
                    "audit_at": {
                        "type": "string",
                        "description": "ISO timestamp cutoff. Events after this time are excluded.",
                    },
                    "requested_at": {
                        "type": "string",
                        "description": "Optional ISO timestamp to tag pre-request events.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum activity records to return (default 50).",
                    },
                },
                "required": ["identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deletion_rules",
            "description": "Returns official policy treatment rules from deletion_rules.csv, optionally filtered by data category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_category": {
                        "type": "string",
                        "description": "Optional category filter (e.g., USER_PROFILE, ACCOUNT_TOMBSTONE, SECURITY_AUDIT_LOG).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_temporal_window",
            "description": "Evaluates whether an evidence file falls within the valid audit window [requested_at, audit_at] and provides an explanatory diagnosis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The evidence file identifier to check.",
                    },
                    "requested_at": {
                        "type": "string",
                        "description": "ISO timestamp when deletion was requested.",
                    },
                    "audit_at": {
                        "type": "string",
                        "description": "ISO timestamp cutoff for the audit.",
                    },
                },
                "required": ["file_id", "requested_at", "audit_at"],
            },
        },
    },
]


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return tool schemas in standard LLM function-calling format."""
    return TOOL_SCHEMAS
