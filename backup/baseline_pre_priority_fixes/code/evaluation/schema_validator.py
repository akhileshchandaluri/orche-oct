"""Strict schema and output contract validator for Ghost Data Still Exists.

Validates candidate output CSV files against the official competition specification
defined in problem_statement.md and AGENTS.md.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Official constants from problem_statement.md
ALLOWED_STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}

PHASE_ORDER = {
    "FINDING": 1,
    "REMEDIATION": 2,
    "VERIFICATION": 3,
}

OP_ORDER = {
    # Phase 1: FINDING
    "REPORT_REMAINING_RECORD": 1,
    "REPORT_EXPOSED_PII": 2,
    "REPORT_ACTIVE_DATA_FLOW": 3,
    "REPORT_RESTORE_RISK": 4,
    # Phase 2: REMEDIATION
    "DISABLE_DATA_FLOW": 1,
    "BLOCK_RESTORE": 2,
    "DELETE_RECORD": 3,
    "REDACT_RECORD": 4,
    "ANONYMIZE_RECORD": 5,
    # Phase 3: VERIFICATION
    "VERIFY_RECORD_ABSENT": 1,
    "VERIFY_RECORD_PRESENT": 2,
    "VERIFY_RECORD_REDACTED": 3,
    "VERIFY_RECORD_ANONYMIZED": 4,
    "VERIFY_DATA_FLOW_DISABLED": 5,
    "VERIFY_RESTORE_BLOCKED": 6,
}

OP_TO_STATE = {
    "REPORT_REMAINING_RECORD": "PRESENT",
    "REPORT_EXPOSED_PII": "PRESENT",
    "REPORT_ACTIVE_DATA_FLOW": "ACTIVE",
    "REPORT_RESTORE_RISK": "ACTIVE",
    "DISABLE_DATA_FLOW": "DISABLED",
    "BLOCK_RESTORE": "BLOCKED",
    "DELETE_RECORD": "ABSENT",
    "REDACT_RECORD": "REDACTED",
    "ANONYMIZE_RECORD": "ANONYMIZED",
    "VERIFY_RECORD_ABSENT": "ABSENT",
    "VERIFY_RECORD_PRESENT": "PRESENT",
    "VERIFY_RECORD_REDACTED": "REDACTED",
    "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED": "DISABLED",
    "VERIFY_RESTORE_BLOCKED": "BLOCKED",
}

OP_TO_PHASE = {
    "REPORT_REMAINING_RECORD": "FINDING",
    "REPORT_EXPOSED_PII": "FINDING",
    "REPORT_ACTIVE_DATA_FLOW": "FINDING",
    "REPORT_RESTORE_RISK": "FINDING",
    "DISABLE_DATA_FLOW": "REMEDIATION",
    "BLOCK_RESTORE": "REMEDIATION",
    "DELETE_RECORD": "REMEDIATION",
    "REDACT_RECORD": "REMEDIATION",
    "ANONYMIZE_RECORD": "REMEDIATION",
    "VERIFY_RECORD_ABSENT": "VERIFICATION",
    "VERIFY_RECORD_PRESENT": "VERIFICATION",
    "VERIFY_RECORD_REDACTED": "VERIFICATION",
    "VERIFY_RECORD_ANONYMIZED": "VERIFICATION",
    "VERIFY_DATA_FLOW_DISABLED": "VERIFICATION",
    "VERIFY_RESTORE_BLOCKED": "VERIFICATION",
}

EXACT_STEP_KEYS = {
    "step_no",
    "phase",
    "system_id",
    "resource_id",
    "operation",
    "state",
    "evidence_id",
}


@dataclass
class ValidationIssue:
    case_id: str
    level: str  # 'ERROR' or 'WARNING'
    message: str
    step_no: Optional[int] = None


@dataclass
class ValidationReport:
    file_path: str
    is_valid: bool
    total_rows: int
    status_counts: Dict[str, int] = field(default_factory=dict)
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Validation Report for: {self.file_path}",
            f"Result: {'PASS (Contract Compliant)' if self.is_valid else 'FAIL (Contract Violations)'}",
            f"Total rows: {self.total_rows}",
            f"Status distribution: {self.status_counts}",
            f"Error count: {len(self.errors)}",
            f"Warning count: {len(self.warnings)}",
        ]
        if self.errors:
            lines.append("\nTop Errors:")
            for err in self.errors[:20]:
                step_str = f" [step {err.step_no}]" if err.step_no is not None else ""
                lines.append(f"  [{err.case_id}]{step_str} {err.message}")
            if len(self.errors) > 20:
                lines.append(f"  ... and {len(self.errors) - 20} more errors")
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings[:10]:
                step_str = f" [step {w.step_no}]" if w.step_no is not None else ""
                lines.append(f"  [{w.case_id}]{step_str} {w.message}")
        return "\n".join(lines)


def load_known_evidence_ids(dataset_dir: str | Path) -> Set[str]:
    """Load valid evidence identifiers (file_id, activity_id, audit_id) from participant dataset."""
    dpath = Path(dataset_dir)
    ev_ids: Set[str] = set()

    ef_path = dpath / "evidence_files.csv"
    if ef_path.exists():
        with open(ef_path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fid = row.get("file_id")
                if fid:
                    ev_ids.add(fid.strip())

    sa_path = dpath / "system_activity.csv"
    if sa_path.exists():
        with open(sa_path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                aid = row.get("activity_id")
                if aid:
                    ev_ids.add(aid.strip())

    ua_path = dpath / "user_audit_log.csv"
    if ua_path.exists():
        with open(ua_path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                uid = row.get("audit_id")
                if uid:
                    ev_ids.add(uid.strip())

    return ev_ids


def validate_csv(
    csv_path: str | Path,
    expected_rows: Optional[int] = None,
    expected_case_ids: Optional[Sequence[str]] = None,
    valid_evidence_ids: Optional[Set[str]] = None,
) -> ValidationReport:
    """Validate candidate output CSV against strict competition schema and contract rules."""
    path = Path(csv_path)
    if not path.exists():
        return ValidationReport(
            file_path=str(path),
            is_valid=False,
            total_rows=0,
            errors=[ValidationIssue(case_id="FILE", level="ERROR", message="File does not exist")],
        )

    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []
    status_counts: Dict[str, int] = {}
    seen_cases: List[str] = []
    seen_case_set: Set[str] = set()

    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return ValidationReport(
                file_path=str(path),
                is_valid=False,
                total_rows=0,
                errors=[ValidationIssue(case_id="HEADER", level="ERROR", message="Empty CSV file")],
            )

        expected_header = ["case_id", "deletion_status", "steps_json"]
        if header != expected_header:
            errors.append(
                ValidationIssue(
                    case_id="HEADER",
                    level="ERROR",
                    message=f"Invalid header {header}. Required exact header: {expected_header}",
                )
            )

        row_idx = 0
        for row in reader:
            row_idx += 1
            if len(row) != 3:
                errors.append(
                    ValidationIssue(
                        case_id=f"row_{row_idx}",
                        level="ERROR",
                        message=f"Row has {len(row)} columns, expected exactly 3",
                    )
                )
                continue

            case_id = row[0].strip()
            deletion_status = row[1].strip()
            steps_json_str = row[2].strip()

            # Check case duplicates
            if case_id in seen_case_set:
                errors.append(
                    ValidationIssue(
                        case_id=case_id,
                        level="ERROR",
                        message=f"Duplicate case_id '{case_id}' at row {row_idx}",
                    )
                )
            seen_case_set.add(case_id)
            seen_cases.append(case_id)

            status_counts[deletion_status] = status_counts.get(deletion_status, 0) + 1

            if deletion_status not in ALLOWED_STATUSES:
                errors.append(
                    ValidationIssue(
                        case_id=case_id,
                        level="ERROR",
                        message=f"Invalid deletion_status '{deletion_status}'. Must be one of {sorted(ALLOWED_STATUSES)}",
                    )
                )

            # JSON Parsing
            try:
                steps = json.loads(steps_json_str)
            except Exception as e:
                errors.append(
                    ValidationIssue(
                        case_id=case_id,
                        level="ERROR",
                        message=f"steps_json is not valid JSON: {e}",
                    )
                )
                continue

            if not isinstance(steps, list):
                errors.append(
                    ValidationIssue(
                        case_id=case_id,
                        level="ERROR",
                        message=f"steps_json must be a JSON array, got {type(steps).__name__}",
                    )
                )
                continue

            # NOT_APPLICABLE contract rule
            if deletion_status == "NOT_APPLICABLE":
                if len(steps) != 0:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            message=f"NOT_APPLICABLE must have an empty steps array [], found {len(steps)} steps",
                        )
                    )
                continue

            # COMPLETE or INCOMPLETE must have at least one step
            if len(steps) == 0:
                errors.append(
                    ValidationIssue(
                        case_id=case_id,
                        level="ERROR",
                        message=f"{deletion_status} cannot have empty steps_json",
                    )
                )
                continue

            sort_keys: List[Tuple[int, int, str, str]] = []
            seen_step_fingerprints: Set[Tuple[str, str, str, str]] = set()

            for idx, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"Step at index {idx} is not a JSON object",
                        )
                    )
                    continue

                # Exact keys check
                actual_keys = set(step.keys())
                missing_keys = EXACT_STEP_KEYS - actual_keys
                extra_keys = actual_keys - EXACT_STEP_KEYS
                if missing_keys:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"Step missing required keys: {sorted(missing_keys)}",
                        )
                    )
                if extra_keys:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"Step contains disallowed extra keys: {sorted(extra_keys)}",
                        )
                    )

                # Field type checks
                step_no = step.get("step_no")
                if not isinstance(step_no, int) or isinstance(step_no, bool):
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"step_no must be integer, got {type(step_no).__name__}",
                        )
                    )
                elif step_no != idx:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"step_no is {step_no}, expected consecutive index {idx}",
                        )
                    )

                phase = step.get("phase")
                operation = step.get("operation")
                system_id = step.get("system_id")
                resource_id = step.get("resource_id")
                state = step.get("state")
                evidence_id = step.get("evidence_id")

                for f_name, f_val in [
                    ("phase", phase),
                    ("operation", operation),
                    ("system_id", system_id),
                    ("resource_id", resource_id),
                    ("state", state),
                    ("evidence_id", evidence_id),
                ]:
                    if not isinstance(f_val, str):
                        errors.append(
                            ValidationIssue(
                                case_id=case_id,
                                level="ERROR",
                                step_no=idx,
                                message=f"Field '{f_name}' must be string, got {type(f_val).__name__}",
                            )
                        )

                if phase not in PHASE_ORDER:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"Invalid phase '{phase}'. Must be one of {sorted(PHASE_ORDER)}",
                        )
                    )

                if operation not in OP_ORDER:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message=f"Invalid operation '{operation}'. Must be one of allowed operations",
                        )
                    )
                else:
                    expected_phase = OP_TO_PHASE.get(operation)
                    if expected_phase and phase != expected_phase:
                        errors.append(
                            ValidationIssue(
                                case_id=case_id,
                                level="ERROR",
                                step_no=idx,
                                message=f"Operation '{operation}' belongs to phase '{expected_phase}', not '{phase}'",
                            )
                        )

                    expected_state = OP_TO_STATE.get(operation)
                    if state != expected_state:
                        errors.append(
                            ValidationIssue(
                                case_id=case_id,
                                level="ERROR",
                                step_no=idx,
                                message=f"Operation '{operation}' requires state '{expected_state}', got '{state}'",
                            )
                        )

                # System & Resource ID sanity
                if not system_id:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message="system_id must not be empty",
                        )
                    )
                if not resource_id:
                    errors.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="ERROR",
                            step_no=idx,
                            message="resource_id must not be empty",
                        )
                    )

                # Evidence ID contract rules:
                if deletion_status == "COMPLETE":
                    if phase != "VERIFICATION":
                        errors.append(
                            ValidationIssue(
                                case_id=case_id,
                                level="ERROR",
                                step_no=idx,
                                message=f"COMPLETE cases must contain only VERIFICATION steps, found '{phase}'",
                            )
                        )
                    if not evidence_id:
                        errors.append(
                            ValidationIssue(
                                case_id=case_id,
                                level="ERROR",
                                step_no=idx,
                                message="COMPLETE cases must cite a non-empty evidence_id proving current state",
                            )
                        )
                    elif valid_evidence_ids and evidence_id not in valid_evidence_ids:
                        warnings.append(
                            ValidationIssue(
                                case_id=case_id,
                                level="WARNING",
                                step_no=idx,
                                message=f"evidence_id '{evidence_id}' not found in evidence manifest/activity logs",
                            )
                        )

                elif deletion_status == "INCOMPLETE":
                    if phase == "FINDING":
                        if not evidence_id:
                            errors.append(
                                ValidationIssue(
                                    case_id=case_id,
                                    level="ERROR",
                                    step_no=idx,
                                    message="FINDING steps in INCOMPLETE cases must cite a non-empty evidence_id",
                                )
                            )
                        elif valid_evidence_ids and evidence_id not in valid_evidence_ids:
                            warnings.append(
                                ValidationIssue(
                                    case_id=case_id,
                                    level="WARNING",
                                    step_no=idx,
                                    message=f"evidence_id '{evidence_id}' not found in evidence manifest/activity logs",
                                )
                            )
                    elif phase in ("REMEDIATION", "VERIFICATION"):
                        if evidence_id != "":
                            errors.append(
                                ValidationIssue(
                                    case_id=case_id,
                                    level="ERROR",
                                    step_no=idx,
                                    message=f"Proposed future {phase} steps in INCOMPLETE cases must use empty evidence_id (''), got '{evidence_id}'",
                                )
                            )

                # Check for duplicate identical steps in the same case
                step_fp = (str(phase), str(operation), str(system_id), str(resource_id))
                if step_fp in seen_step_fingerprints:
                    warnings.append(
                        ValidationIssue(
                            case_id=case_id,
                            level="WARNING",
                            step_no=idx,
                            message=f"Duplicate step found in case: {step_fp}",
                        )
                    )
                seen_step_fingerprints.add(step_fp)

                if phase in PHASE_ORDER and operation in OP_ORDER:
                    sort_keys.append((
                        PHASE_ORDER[phase],
                        OP_ORDER[operation],
                        str(system_id),
                        str(resource_id),
                    ))

            # Canonical Ordering Check: phase -> op -> system_id -> resource_id
            if sort_keys != sorted(sort_keys):
                errors.append(
                    ValidationIssue(
                        case_id=case_id,
                        level="ERROR",
                        message="Steps are not properly sorted by (phase, operation, system_id, resource_id)",
                    )
                )

    # Check case sorting (support both numeric and alphabetical ascending order)
    def parse_case_num(cid: str) -> Any:
        parts = cid.split("_")
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else cid

    if seen_cases != sorted(seen_cases) and seen_cases != sorted(seen_cases, key=parse_case_num):
        errors.append(
            ValidationIssue(
                case_id="FILE",
                level="ERROR",
                message="case_ids are not in strict ascending order",
            )
        )

    # Check expected rows
    if expected_rows is not None and len(seen_cases) != expected_rows:
        errors.append(
            ValidationIssue(
                case_id="FILE",
                level="ERROR",
                message=f"File contains {len(seen_cases)} rows, expected exactly {expected_rows}",
            )
        )

    # Check expected case IDs
    if expected_case_ids is not None:
        expected_set = set(expected_case_ids)
        actual_set = set(seen_cases)
        missing_cases = expected_set - actual_set
        unexpected_cases = actual_set - expected_set
        if missing_cases:
            errors.append(
                ValidationIssue(
                    case_id="FILE",
                    level="ERROR",
                    message=f"Missing {len(missing_cases)} expected cases (e.g. {sorted(missing_cases)[:5]})",
                )
            )
        if unexpected_cases:
            errors.append(
                ValidationIssue(
                    case_id="FILE",
                    level="ERROR",
                    message=f"Unexpected {len(unexpected_cases)} cases found (e.g. {sorted(unexpected_cases)[:5]})",
                )
            )

    is_valid = len(errors) == 0
    return ValidationReport(
        file_path=str(path),
        is_valid=is_valid,
        total_rows=len(seen_cases),
        status_counts=status_counts,
        errors=errors,
        warnings=warnings,
    )
