"""Evaluation engine for Ghost Data Still Exists.

Computes multi-dimensional benchmark metrics between predictions and ground-truth reference:
1. Case-Level Status Accuracy
2. Full-Row Exact Match Accuracy
3. Step Precision, Recall, and F1 (multiset alignment)
4. Sequence Ordering Accuracy (conditional on step set equivalence)
5. Field-Level Accuracies (phase, operation, system_id, resource_id, state, evidence_id)
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


@dataclass
class CaseEvaluation:
    case_id: str
    pred_status: Optional[str]
    truth_status: str
    status_match: bool
    pred_steps_count: int
    truth_steps_count: int
    exact_row_match: bool
    step_precision: float
    step_recall: float
    step_f1: float
    sequence_match: bool
    notes: List[str] = field(default_factory=list)


@dataclass
class EvaluationSummary:
    evaluation_mode: str  # 'SANITY_CHECK', 'SAMPLE_BENCHMARK', 'INDEPENDENT_EVAL'
    total_truth_cases: int
    total_pred_cases: int
    evaluated_cases: int
    missing_pred_cases: int
    unexpected_pred_cases: int
    case_status_accuracy: float
    row_level_accuracy: float
    step_precision: float
    step_recall: float
    step_f1: float
    sequence_accuracy: float
    field_accuracies: Dict[str, float] = field(default_factory=dict)
    case_results: List[CaseEvaluation] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"### Benchmark Results ({self.evaluation_mode})",
            "",
            "> [!NOTE]",
            "> **Metric Semantics & Disclaimer**:" if self.evaluation_mode != "SANITY_CHECK" else "> **EVALUATOR HARNESS SELF-CHECK**:",
            f"> - Mode: `{self.evaluation_mode}`",
            f"> - Truth Cases: {self.total_truth_cases} | Predicted Cases: {self.total_pred_cases}",
            f"> - Missing Cases Penalized: {self.missing_pred_cases} | Unexpected Cases: {self.unexpected_pred_cases}",
        ]
        if self.evaluation_mode == "SANITY_CHECK":
            lines.append(
                "> - **IMPORTANT**: This run compares identical reference files as a self-test of evaluator mechanics. It does NOT represent prediction or model accuracy."
            )
        lines.extend([
            "",
            "| Metric | Score | Definition |",
            "| --- | --- | --- |",
            f"| **Evaluated Reference Cases** | {self.total_truth_cases} | Total cases in reference ground-truth |",
            f"| **Case-Level Status Accuracy** | {self.case_status_accuracy * 100:.2f}% | Exact match of `deletion_status` across all truth cases |",
            f"| **Full Row-Level Exact Accuracy** | {self.row_level_accuracy * 100:.2f}% | Exact match of status AND entire ordered `steps_json` |",
            f"| **Step Precision** | {self.step_precision * 100:.2f}% | Correct predicted steps / total predicted steps |",
            f"| **Step Recall** | {self.step_recall * 100:.2f}% | Correct predicted steps / total reference steps |",
            f"| **Step F1-Score** | {self.step_f1 * 100:.2f}% | Harmonic mean of step precision and recall |",
            f"| **Sequence Accuracy** | {self.sequence_accuracy * 100:.2f}% | Correct array ordering among cases with matching step sets |",
            "",
            "#### Field-Level Accuracies",
            "",
            "| Field | Accuracy | Description |",
            "| --- | --- | --- |",
        ])
        for f_name, f_acc in sorted(self.field_accuracies.items()):
            lines.append(f"| `{f_name}` | {f_acc * 100:.2f}% | Correct assignment of `{f_name}` across aligned steps |")

        lines.extend([
            "",
            "#### Case-by-Case Breakdown",
            "",
            "| Case ID | Truth Status | Pred Status | Status Match | Row Match | Step F1 | Seq Match | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for c in self.case_results:
            p_stat = c.pred_status if c.pred_status is not None else "MISSING"
            status_ico = "PASS" if c.status_match else "FAIL"
            row_ico = "PASS" if c.exact_row_match else "FAIL"
            seq_ico = "PASS" if c.sequence_match else "FAIL"
            notes_str = "; ".join(c.notes) if c.notes else "-"
            lines.append(
                f"| `{c.case_id}` | {c.truth_status} | {p_stat} | {status_ico} | {row_ico} | {c.step_f1 * 100:.1f}% | {seq_ico} | {notes_str} |"
            )

        return "\n".join(lines)


def _step_fingerprint(s: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
    return (
        str(s.get("phase", "")),
        str(s.get("system_id", "")),
        str(s.get("resource_id", "")),
        str(s.get("operation", "")),
        str(s.get("state", "")),
        str(s.get("evidence_id", "")),
    )


def evaluate_predictions(
    pred_path: str | Path,
    truth_path: str | Path,
    is_sanity_check: bool = False,
) -> EvaluationSummary:
    """Evaluate candidate predictions against a ground-truth reference CSV.
    
    Handles:
    - Missing cases (penalized as failures)
    - Extra unexpected cases (penalized as false positives)
    - Empty step arrays (NOT_APPLICABLE vs NOT_APPLICABLE = 1.0; mismatch = 0.0)
    - Duplicate steps (penalized in precision)
    - Ordering verification
    """
    preds: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}
    with open(pred_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        _ = next(reader, None)
        for row in reader:
            if len(row) >= 3:
                cid, status, steps_str = row[0].strip(), row[1].strip(), row[2].strip()
                try:
                    steps = json.loads(steps_str)
                    if not isinstance(steps, list):
                        steps = []
                except Exception:
                    steps = []
                preds[cid] = (status, steps)

    truth: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}
    with open(truth_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        _ = next(reader, None)
        for row in reader:
            if len(row) >= 3:
                cid, status, steps_str = row[0].strip(), row[1].strip(), row[2].strip()
                try:
                    steps = json.loads(steps_str)
                    if not isinstance(steps, list):
                        steps = []
                except Exception:
                    steps = []
                truth[cid] = (status, steps)

    all_truth_cases = list(truth.keys())
    pred_case_set = set(preds.keys())
    truth_case_set = set(all_truth_cases)

    missing_cases = truth_case_set - pred_case_set
    unexpected_cases = pred_case_set - truth_case_set

    case_evals: List[CaseEvaluation] = []
    status_matches = 0
    row_matches = 0
    total_tp = 0
    total_fp = 0
    total_fn = 0
    seq_eligible = 0
    seq_matches = 0

    field_correct: Dict[str, int] = {
        "deletion_status": 0,
        "phase": 0,
        "system_id": 0,
        "resource_id": 0,
        "operation": 0,
        "state": 0,
        "evidence_id": 0,
    }
    field_total: Dict[str, int] = {k: 0 for k in field_correct}

    for cid in all_truth_cases:
        t_status, t_steps = truth[cid]
        field_total["deletion_status"] += 1

        if cid not in preds:
            # Missing case penalty
            total_fn += len(t_steps)
            case_evals.append(
                CaseEvaluation(
                    case_id=cid,
                    pred_status=None,
                    truth_status=t_status,
                    status_match=False,
                    pred_steps_count=0,
                    truth_steps_count=len(t_steps),
                    exact_row_match=False,
                    step_precision=0.0,
                    step_recall=0.0,
                    step_f1=0.0,
                    sequence_match=False,
                    notes=["Case missing from predictions"],
                )
            )
            continue

        p_status, p_steps = preds[cid]

        # Status check
        s_match = (p_status == t_status)
        if s_match:
            status_matches += 1
            field_correct["deletion_status"] += 1

        p_fps = [_step_fingerprint(s) for s in p_steps]
        t_fps = [_step_fingerprint(s) for s in t_steps]

        # Exact row match (status + entire steps sequence)
        exact_row = s_match and (p_fps == t_fps)
        if exact_row:
            row_matches += 1

        # Multiset step matching
        # When both step lists are empty (e.g. NOT_APPLICABLE):
        if len(p_fps) == 0 and len(t_fps) == 0:
            prec = 1.0
            rec = 1.0
            f1 = 1.0
            seq_match = True
            seq_eligible += 1
            seq_matches += 1
        elif len(p_fps) == 0 or len(t_fps) == 0:
            prec = 0.0
            rec = 0.0
            f1 = 0.0
            seq_match = False
            total_fp += len(p_fps)
            total_fn += len(t_fps)
        else:
            t_matched: Set[int] = set()
            p_matched: Set[int] = set()

            for pi, pf in enumerate(p_fps):
                for ti, tf in enumerate(t_fps):
                    if ti not in t_matched and pf == tf:
                        t_matched.add(ti)
                        p_matched.add(pi)
                        break

            tp = len(p_matched)
            fp = len(p_fps) - tp
            fn = len(t_fps) - len(t_matched)

            total_tp += tp
            total_fp += fp
            total_fn += fn

            prec = tp / len(p_fps) if p_fps else 0.0
            rec = tp / len(t_fps) if t_fps else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            # Sequence match: eligible if all steps match as a multiset
            if len(p_fps) == len(t_fps) and tp == len(t_fps):
                seq_eligible += 1
                seq_match = (p_fps == t_fps)
                if seq_match:
                    seq_matches += 1
            else:
                seq_match = False

        # Field-level tracking on aligned steps
        min_len = min(len(p_steps), len(t_steps))
        for i in range(min_len):
            ps, ts = p_steps[i], t_steps[i]
            for fld in ["phase", "system_id", "resource_id", "operation", "state", "evidence_id"]:
                field_total[fld] += 1
                if ps.get(fld) == ts.get(fld):
                    field_correct[fld] += 1

        notes = []
        if not s_match:
            notes.append(f"Status mismatch: expected {t_status}, got {p_status}")
        if len(p_steps) != len(t_steps):
            notes.append(f"Step count mismatch: expected {len(t_steps)}, got {len(p_steps)}")

        case_evals.append(
            CaseEvaluation(
                case_id=cid,
                pred_status=p_status,
                truth_status=t_status,
                status_match=s_match,
                pred_steps_count=len(p_steps),
                truth_steps_count=len(t_steps),
                exact_row_match=exact_row,
                step_precision=prec,
                step_recall=rec,
                step_f1=f1,
                sequence_match=seq_match,
                notes=notes,
            )
        )

    # Penalize unexpected cases
    for ucid in unexpected_cases:
        _, u_steps = preds[ucid]
        total_fp += len(u_steps)

    n = len(all_truth_cases)
    global_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    global_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    global_f1 = (
        (2 * global_prec * global_rec) / (global_prec + global_rec)
        if (global_prec + global_rec) > 0
        else 0.0
    )
    seq_acc = (seq_matches / seq_eligible) if seq_eligible > 0 else 0.0

    field_accs = {
        k: (field_correct[k] / field_total[k] if field_total[k] > 0 else 0.0)
        for k in field_correct
    }

    mode = "SANITY_CHECK" if is_sanity_check else "BENCHMARK_EVALUATION"

    return EvaluationSummary(
        evaluation_mode=mode,
        total_truth_cases=n,
        total_pred_cases=len(preds),
        evaluated_cases=len(truth_case_set.intersection(pred_case_set)),
        missing_pred_cases=len(missing_cases),
        unexpected_pred_cases=len(unexpected_cases),
        case_status_accuracy=status_matches / n if n > 0 else 0.0,
        row_level_accuracy=row_matches / n if n > 0 else 0.0,
        step_precision=global_prec,
        step_recall=global_rec,
        step_f1=global_f1,
        sequence_accuracy=seq_acc,
        field_accuracies=field_accs,
        case_results=case_evals,
    )
