"""Main evaluation harness entry point for Ghost Data Still Exists.

Provides:
- Schema and contract validation against problem_statement.md & AGENTS.md rules.
- Ground-truth benchmark evaluation (with explicit separation between evaluator sanity checks and actual prediction benchmarks).
- Comprehensive 10-category edge-case test scenario management.
- Self-diagnostic fault injection tests proving that malformed outputs are detected.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

# Add project root to path for reliable imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.schema_validator import (
    load_known_evidence_ids,
    validate_csv,
)
from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.test_scenarios import (
    execute_scenarios_against_engine,
    get_all_scenarios,
    verify_scenario_spec_conformance,
)


def run_fault_injection_tests(dataset_dir: Path) -> bool:
    """Deliberately inject contract violations to verify that the validator and evaluator catch them."""
    print("\n" + "=" * 60)
    print("Executing Deliberate Fault-Injection Tests (Validator & Evaluator Hardening)")
    print("=" * 60)

    known_ev_ids = load_known_evidence_ids(dataset_dir)
    fault_cases = [
        (
            "Invalid Header",
            [["wrong_id", "wrong_status", "steps"], ["case_01", "COMPLETE", "[]"]],
            "Invalid header",
        ),
        (
            "Invalid Deletion Status",
            [["case_id", "deletion_status", "steps_json"], ["case_01", "MAYBE", "[]"]],
            "Invalid deletion_status",
        ),
        (
            "NOT_APPLICABLE with non-empty steps",
            [
                ["case_id", "deletion_status", "steps_json"],
                ["case_01", "NOT_APPLICABLE", json.dumps([{"step_no": 1, "phase": "FINDING", "system_id": "acc", "resource_id": "r1", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_01"}])],
            ],
            "NOT_APPLICABLE must have an empty steps array",
        ),
        (
            "State mismatch with operation",
            [
                ["case_id", "deletion_status", "steps_json"],
                ["case_01", "INCOMPLETE", json.dumps([{"step_no": 1, "phase": "FINDING", "system_id": "acc", "resource_id": "r1", "operation": "REPORT_REMAINING_RECORD", "state": "ABSENT", "evidence_id": "evidence_01"}])],
            ],
            "requires state 'PRESENT'",
        ),
        (
            "Inverted step ordering (Verification before Finding)",
            [
                ["case_id", "deletion_status", "steps_json"],
                ["case_01", "INCOMPLETE", json.dumps([
                    {"step_no": 1, "phase": "VERIFICATION", "system_id": "acc", "resource_id": "r1", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
                    {"step_no": 2, "phase": "FINDING", "system_id": "acc", "resource_id": "r1", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_01"},
                ])],
            ],
            "Steps are not properly sorted",
        ),
        (
            "INCOMPLETE proposed remediation with non-empty evidence_id",
            [
                ["case_id", "deletion_status", "steps_json"],
                ["case_01", "INCOMPLETE", json.dumps([
                    {"step_no": 1, "phase": "FINDING", "system_id": "acc", "resource_id": "r1", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_01"},
                    {"step_no": 2, "phase": "REMEDIATION", "system_id": "acc", "resource_id": "r1", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": "evidence_01"},
                ])],
            ],
            "must use empty evidence_id",
        ),
        (
            "Duplicate case IDs",
            [
                ["case_id", "deletion_status", "steps_json"],
                ["case_01", "NOT_APPLICABLE", "[]"],
                ["case_01", "NOT_APPLICABLE", "[]"],
            ],
            "Duplicate case_id",
        ),
        (
            "Non-integer step_no",
            [
                ["case_id", "deletion_status", "steps_json"],
                ["case_01", "COMPLETE", json.dumps([{"step_no": "1", "phase": "VERIFICATION", "system_id": "acc", "resource_id": "r1", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_01"}])],
            ],
            "step_no must be integer",
        ),
    ]

    all_caught = True
    with tempfile.TemporaryDirectory() as tmp_dir:
        for name, rows, expected_err_substr in fault_cases:
            fpath = Path(tmp_dir) / f"{name.replace(' ', '_')}.csv"
            with open(fpath, mode="w", newline="", encoding="utf-8") as tf:
                writer = csv.writer(tf)
                writer.writerows(rows)
            rep = validate_csv(fpath, valid_evidence_ids=known_ev_ids)

            if rep.is_valid:
                print(f"  [FAIL] Did NOT catch deliberate violation: {name}")
                all_caught = False
            else:
                err_texts = " ".join(e.message for e in rep.errors)
                if expected_err_substr.lower() in err_texts.lower():
                    print(f"  [PASS] Correctly caught: {name} (Error: {rep.errors[0].message})")
                else:
                    print(f"  [WARN] Caught failure but error message differed for {name}: {err_texts}")

    print(f"Fault Injection Test Result: {'ALL FAULTS CAUGHT (100% PASS)' if all_caught else 'FAILED'}")
    return all_caught


def generate_evaluation_report(
    sample_val_rep,
    sample_sanity_rep,
    scenario_spec_res,
    scenario_exec_res,
    report_output_path: Path,
) -> None:
    """Generate or update code/evaluation/evaluation_report.md with transparent separation of concerns."""
    scenarios = get_all_scenarios()

    lines = [
        "# Ghost Data Still Exists — Evaluation Foundation & Verification Report",
        "",
        "## 1. Executive Summary & Verification Methodology",
        "",
        "This report documents the evaluation framework, schema validation checks, test scenario specifications, and evaluator sanity verifications.",
        "",
        "> [!IMPORTANT]",
        "> **Transparency & Distinction of Checks**:",
        "> 1. **Schema & Output Contract Validation**: Verifies candidate CSV structure, field types, and ordering against the rules in `problem_statement.md` and `AGENTS.md`.",
        "> 2. **Evaluator Harness Sanity Check**: Tests that the evaluator correctly scores identical reference files as a mechanics verification. This is **NOT** a prediction score.",
        "> 3. **Custom Test Scenarios**: Formal specification of 10 edge-case failure modes with inputs, expected behavior, and rule citations. End-to-end execution is staged and pending prediction engine implementation.",
        "> 4. **No Premature Accuracy Claims**: Prediction accuracy on the 518 evaluation cases is strictly pending actual model generation.",
        "",
        "## 2. Official Output Contract & Specification Rules",
        "",
        "| Requirement | Specification | Enforcement Mechanism |",
        "| --- | --- | --- |",
        "| **Exact Header** | `case_id,deletion_status,steps_json` | Strict CSV header validation in `schema_validator.py` |",
        "| **Row Count** | Exactly 518 data rows for submission | Exact row count and missing/extra case checks |",
        "| **Case Ordering** | Monotonically ascending order by `case_id` | Full sequence ordering validation |",
        "| **Permitted Statuses** | `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE` | Exact enum membership |",
        "| **`NOT_APPLICABLE` Rule** | Must have empty steps array `[]` | Fails if `len(steps) != 0` |",
        "| **Exact Step Fields** | `step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id` | Strict key set match (no missing, no extra keys) |",
        "| **Step Numbering** | 1-indexed, strictly consecutive (`1, 2, ...`) | Enforced integer progression |",
        "| **Phase Ordering** | `FINDING` -> `REMEDIATION` -> `VERIFICATION` | Enforced phase ordering |",
        "| **Operation Ordering** | Canonical precedence defined in `problem_statement.md` | Enforced operation sort order |",
        "| **Tie-Breaker Rule** | `system_id` ascending, then `resource_id` ascending | Multi-key sort validation |",
        "| **Evidence ID (`COMPLETE`)** | Non-empty evidence ID proving current compliant state | Must cite participant evidence |",
        "| **Evidence ID (`INCOMPLETE`)** | Non-empty for `FINDING`; empty string `\"\"` for `REMEDIATION` and `VERIFICATION` | Enforced future-step evidence clearing |",
        "",
        "## 3. Sample Reference Dataset Schema Validation",
        "",
        f"- **File Validated**: `dataset/sample_output.csv` (32 gold-standard cases).",
        f"- **Contract Conformance**: {'100% PASS' if sample_val_rep.is_valid else 'FAIL'}",
        f"- **Total Rows**: {sample_val_rep.total_rows}",
        f"- **Status Distribution**: {sample_val_rep.status_counts}",
        f"- **Contract Violations / Errors**: {len(sample_val_rep.errors)}",
        f"- **Warnings**: {len(sample_val_rep.warnings)}",
        "",
        "## 4. Evaluator Mechanics Sanity Check (Self-Comparison)",
        "",
        "> [!NOTE]",
        "> The table below records an automated verification of evaluator comparison mechanics by comparing `sample_output.csv` with itself. This verifies that multiset matching, sequence checks, and field alignment function correctly without inflating scores.",
        "",
        sample_sanity_rep.to_markdown(),
        "",
        "## 5. Ten Comprehensive Edge-Case Scenarios",
        "",
        "To rigorously test deletion audit logic against adversarial and operational failure modes, 10 distinct test scenarios have been constructed:",
        "",
    ]

    for idx, sc in enumerate(scenarios, start=1):
        lines.extend([
            f"### Scenario {idx}: {sc.category_name}",
            f"- **Scenario ID**: `{sc.scenario_id}`",
            f"- **Description**: {sc.description}",
            f"- **Supporting Task Rule**: *{sc.supporting_rule}*",
            f"- **Input Facts**: `{json.dumps(sc.input_facts)}`",
            f"- **Expected Deletion Status**: `{sc.expected_status}`",
            f"- **Expected Steps Count**: {len(sc.expected_steps)}",
            "- **Expected Canonical Steps**:",
            "```json",
            f"{json.dumps(sc.expected_steps, indent=2)}",
            "```",
            "",
        ])

    lines.extend([
        "## 6. Scenario Test Suite Status",
        "",
        f"- **Total Scenarios Defined**: {scenario_spec_res['total_scenarios']}",
        f"- **Scenario Schema & Contract Conformance**: {'100% PASS' if scenario_spec_res['spec_valid'] else 'FAIL'}",
        f"- **Execution Engine Status**: `{scenario_exec_res['status']}`",
        f"- **Engine Message**: {scenario_exec_res['message']}",
        "",
        "| Scenario ID | Category | Expected Status | Execution Status |",
        "| --- | --- | --- | --- |",
    ])
    for r in scenario_exec_res["results"]:
        lines.append(f"| `{r['scenario_id']}` | {r['category']} | `{r['expected_status']}` | `{r['execution_result']}` |")

    lines.extend([
        "",
        "## 7. Known Contract Ambiguities & Defensive Interpretations",
        "",
        "1. **Tombstone Classification**:",
        "   - *Ambiguity*: Is a tombstone record reported as `account_service` or `identity_service`?",
        "   - *Grounding*: Sample case 31 and 32 cite `system_id: identity_service` and `resource_id: tombstone_xxx`. We adopt `identity_service` for explicit tombstone resources while account profiles use `account_service`.",
        "",
        "2. **Primary vs Secondary Absences in Verification**:",
        "   - *Ambiguity*: When a secondary record (e.g. search entry) is deleted during remediation, which records must be verified?",
        "   - *Grounding*: Sample cases (e.g., case 06, case 07, case 11) show that the verification phase must include `VERIFY_RECORD_ABSENT` for the primary account record as well as the remediated secondary record.",
        "",
        "3. **Tie-Breaker String Comparison**:",
        "   - *Ambiguity*: Are resource IDs sorted alphabetically (e.g. `account_10` before `account_2`) or numerically?",
        "   - *Grounding*: String comparison is the universal standard for system and resource identifiers in Python and SQL (`'account_10' < 'account_2'`). Verified consistent with all sample outputs.",
        "",
    ])

    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nUpdated comprehensive evaluation report at: {report_output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Evaluation Harness")
    parser.add_argument("--validate", type=str, help="Validate candidate CSV against contract")
    parser.add_argument("--expected-rows", type=int, default=None, help="Expected row count")
    parser.add_argument("--eval", nargs=2, metavar=("PRED_CSV", "TRUTH_CSV"), help="Evaluate predictions against truth")
    parser.add_argument("--fault-tests", action="store_true", help="Run deliberate fault-injection tests")

    args = parser.parse_args()
    dataset_dir = PROJECT_ROOT / "dataset"
    known_ev_ids = load_known_evidence_ids(dataset_dir)

    if args.validate:
        rep = validate_csv(args.validate, expected_rows=args.expected_rows, valid_evidence_ids=known_ev_ids)
        print(rep.summary())
        return 0 if rep.is_valid else 1

    if args.eval:
        pred_path, truth_path = args.eval
        val_rep = validate_csv(pred_path, valid_evidence_ids=known_ev_ids)
        print(val_rep.summary())
        print("\n" + "=" * 60 + "\n")
        eval_summary = evaluate_predictions(pred_path, truth_path, is_sanity_check=(pred_path == truth_path))
        print(eval_summary.to_markdown())
        return 0 if val_rep.is_valid else 1

    if args.fault_tests:
        ok = run_fault_injection_tests(dataset_dir)
        return 0 if ok else 1

    # Default: Run full suite: schema validation on sample, sanity check eval, fault injection, scenario specs
    print("=" * 60)
    print("Running Ghost Data Still Exists Evaluation Harness Suite")
    print("=" * 60)

    sample_csv = dataset_dir / "sample_output.csv"
    val_rep = validate_csv(sample_csv, expected_rows=32, valid_evidence_ids=known_ev_ids)
    print("\n1. Sample Output Schema Conformance:")
    print(val_rep.summary())

    sanity_rep = evaluate_predictions(sample_csv, sample_csv, is_sanity_check=True)
    print("\n2. Evaluator Harness Self-Check:")
    print(sanity_rep.to_markdown())

    # Fault injection tests
    faults_ok = run_fault_injection_tests(dataset_dir)

    # Scenarios specification check
    print("\n" + "=" * 60)
    print("3. Custom Edge-Case Scenarios Verification")
    print("=" * 60)
    scenario_spec_res = verify_scenario_spec_conformance()
    print(f"Total Scenarios Defined: {scenario_spec_res['total_scenarios']}")
    print(f"Scenario Specification Validity: {'PASS (100% Conforming)' if scenario_spec_res['spec_valid'] else 'FAIL'}")
    if scenario_spec_res["issues"]:
        for issue in scenario_spec_res["issues"]:
            print(f"  [ISSUE] {issue}")

    # Execution against prediction engine (currently None -> PENDING_IMPLEMENTATION)
    scenario_exec_res = execute_scenarios_against_engine(engine=None)
    print(f"Engine Status: {scenario_exec_res['status']} ({scenario_exec_res['message']})")

    # Generate complete report
    report_file = PROJECT_ROOT / "code" / "evaluation" / "evaluation_report.md"
    generate_evaluation_report(val_rep, sanity_rep, scenario_spec_res, scenario_exec_res, report_file)

    return 0 if (val_rep.is_valid and faults_ok and scenario_spec_res["spec_valid"]) else 1


if __name__ == "__main__":
    sys.exit(main())
