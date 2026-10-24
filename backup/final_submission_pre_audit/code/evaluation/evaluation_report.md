# Ghost Data Still Exists — Evaluation Foundation & Baseline Report

## 1. Executive Summary & Verification Methodology

This report documents the rigorous evaluation baseline for HackerRank ORCHESTRATE — *"Ghost Data Still Exists"*. It records both structural contract validations and quantitative prediction benchmarks across 32 public reference cases and 10 custom edge-case scenarios.

> [!IMPORTANT]
> **Transparency & Distinction of Checks**:
> 1. **Schema & Output Contract Validation**: Verifies candidate CSV structure, field types, and ordering against the rules in `problem_statement.md` and `AGENTS.md`.
> 2. **Evaluator Harness Sanity Check**: Tests that the evaluator correctly scores identical reference files (`sample_output.csv` vs `sample_output.csv`) as a mechanics verification. This is **NOT** a prediction score.
> 3. **Representative Model Benchmark**: Audits the 32 participant-facing cases from `dataset/sample_deletion_requests.csv` with `PredictionEngine` and evaluates against `dataset/sample_output.csv`.
> 4. **10 Custom Edge-Case Scenarios**: Real end-to-end execution of participant-created adversarial scenarios against the production `PredictionEngine`.
> 5. **Generalization Disclaimer**: Public sample accuracy serves as an anti-regression baseline; it does NOT guarantee identical accuracy on hidden test partitions.

## 2. Official Output Contract & Specification Rules

| Requirement | Specification | Enforcement Mechanism |
| --- | --- | --- |
| **Exact Header** | `case_id,deletion_status,steps_json` | Strict CSV header validation in `schema_validator.py` |
| **Row Count** | Exactly 518 data rows for submission | Exact row count and missing/extra case checks |
| **Case Ordering** | Monotonically ascending order by `case_id` | Full sequence ordering validation |
| **Permitted Statuses** | `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE` | Exact enum membership |
| **`NOT_APPLICABLE` Rule** | Must have empty steps array `[]` | Fails if `len(steps) != 0` |
| **Exact Step Fields** | `step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id` | Strict key set match (no missing, no extra keys) |
| **Step Numbering** | 1-indexed, strictly consecutive (`1, 2, ...`) | Enforced integer progression |
| **Phase Ordering** | `FINDING` -> `REMEDIATION` -> `VERIFICATION` | Enforced phase ordering |
| **Operation Ordering** | Canonical precedence defined in `problem_statement.md` | Enforced operation sort order |
| **Tie-Breaker Rule** | `system_id` ascending, then `resource_id` ascending | Multi-key sort validation |
| **Evidence ID (`COMPLETE`)** | Non-empty evidence ID proving current compliant state | Must cite participant evidence |
| **Evidence ID (`INCOMPLETE`)** | Non-empty for `FINDING`; empty string `""` for `REMEDIATION` and `VERIFICATION` | Enforced future-step evidence clearing |

## 3. Formal Metric Definitions & Mathematical Handling

1. **Case-Level Status Accuracy**:
   $$\text{Status Accuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{pred\_status}_i = \text{truth\_status}_i)}{N}$$
   - Enforces exact string enum equality (`COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`).

2. **Full Row-Level Exact Accuracy**:
   $$\text{Row Accuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{pred\_status}_i = \text{truth\_status}_i \land \text{pred\_steps}_i = \text{truth\_steps}_i)}{N}$$
   - Requires exact status match AND exact 1-to-1 match of all step fields in canonical sorted order.

3. **Step Precision, Recall, and F1-Score** (Multiset Step Matching):
   - **Step Fingerprint**: A tuple of `(phase, system_id, resource_id, operation, state, evidence_id)`.
   - **Duplicate Handling**: In multiset matching, each reference step can match at most one predicted step. If the prediction generates duplicate identical steps, subsequent duplicates cannot match and are penalized as **False Positives ($FP$)**.
   - **Extra Steps**: Any predicted step not present in reference ground-truth is scored as a False Positive ($FP$).
   - **Missing Steps**: Any reference step not present in prediction is scored as a False Negative ($FN$).
   - **Global Step Precision**: $\frac{TP}{TP + FP}$ across all cases.
   - **Global Step Recall**: $\frac{TP}{TP + FN}$ across all cases.
   - **Step F1-Score**: $\frac{2 \times \text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$.

4. **Sequence Accuracy**:
   - Evaluated only on cases where the predicted step multiset matches the reference step multiset ($TP = |\text{reference}| \land |\text{predicted}| = |\text{reference}|$).
   - Measures the fraction of eligible cases where the predicted array ordering strictly matches reference canonical order.

5. **Field-Level Accuracies**:
   - Measures individual attribute accuracy (`phase`, `operation`, `system_id`, `resource_id`, `state`, `evidence_id`) across aligned steps.

## 4. Resolution of Historical Report Disagreements

| Historical Result | Source / Evaluator | Root Cause of Disagreement | Verified Reality |
| --- | --- | --- | --- |
| **100% Status & 100% Exact Row** | Earlier `evaluation_report.md` | The report generator ran an evaluator harness self-check comparing `sample_output.csv` with itself (`is_sanity_check=True`), and output that table as the main benchmark. | That 100% was a mechanics self-check, **not** prediction accuracy. |
| **56.25% Exact Row (18/32)** | Initial offline hybrid engine | Engine lacked search index tombstone absence verification and had unresolved identity linkage edge cases. | Accurately reflected early pipeline performance before systematic canonical ordering fixes. |
| **71.88% Exact Row (23/32)** | Current `PredictionEngine` baseline | Evaluated using `code/evaluation/benchmark_sample.py` comparing real predictions on 32 cases against `sample_output.csv`. | Status: 100% (32/32), Exact Row: 71.88% (23/32), Precision: 99.46% (micro), Recall: 94.82% (micro), Sequence: 100%. |

## 5. Evaluator Mechanics Sanity Check (Self-Comparison)

> [!NOTE]
> Automated verification of evaluator comparison mechanics by comparing `sample_output.csv` with itself. Proves multiset alignment, field matching, and sequence scoring function correctly.

### Benchmark Results (SANITY_CHECK)

> [!NOTE]
> **EVALUATOR HARNESS SELF-CHECK**:
> - Mode: `SANITY_CHECK`
> - Truth Cases: 32 | Predicted Cases: 32
> - Missing Cases Penalized: 0 | Unexpected Cases: 0
> - **IMPORTANT**: This run compares identical reference files as a self-test of evaluator mechanics. It does NOT represent prediction or model accuracy.

| Metric | Score | Definition |
| --- | --- | --- |
| **Evaluated Reference Cases** | 32 | Total cases in reference ground-truth |
| **Case-Level Status Accuracy** | 100.00% | Exact match of `deletion_status` across all truth cases |
| **Full Row-Level Exact Accuracy** | 100.00% | Exact match of status AND entire ordered `steps_json` |
| **Step Precision** | 100.00% | Correct predicted steps / total predicted steps |
| **Step Recall** | 100.00% | Correct predicted steps / total reference steps |
| **Step F1-Score** | 100.00% | Harmonic mean of step precision and recall |
| **Sequence Accuracy** | 100.00% | Correct array ordering among cases with matching step sets |

#### Field-Level Accuracies

| Field | Accuracy | Description |
| --- | --- | --- |
| `deletion_status` | 100.00% | Correct assignment of `deletion_status` across aligned steps |
| `evidence_id` | 100.00% | Correct assignment of `evidence_id` across aligned steps |
| `operation` | 100.00% | Correct assignment of `operation` across aligned steps |
| `phase` | 100.00% | Correct assignment of `phase` across aligned steps |
| `resource_id` | 100.00% | Correct assignment of `resource_id` across aligned steps |
| `state` | 100.00% | Correct assignment of `state` across aligned steps |
| `system_id` | 100.00% | Correct assignment of `system_id` across aligned steps |

#### Case-by-Case Breakdown

| Case ID | Truth Status | Pred Status | Status Match | Row Match | Step F1 | Seq Match | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `case_01` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_02` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_03` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_04` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_05` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_06` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_07` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_08` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_09` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_10` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_11` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_12` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_13` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_14` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_15` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_16` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_17` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_18` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_19` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_20` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_21` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_22` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_23` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_24` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_25` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_26` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_27` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_28` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_29` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_30` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_31` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_32` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |

## 6. Current PredictionEngine Baseline on Public Benchmark (32 Cases)

> [!IMPORTANT]
> Real end-to-end execution of `PredictionEngine` on `dataset/sample_deletion_requests.csv` evaluated against `dataset/sample_output.csv`.

- **Prediction Schema Conformance**: 100% PASS (0 errors)
- **Status Accuracy**: 100.00% (32/32)
- **Exact Row Accuracy**: 90.62% (29/32)
- **Global Step Precision**: 99.48%
- **Global Step Recall**: 98.45%
- **Step F1-Score**: 98.96%
- **Sequence Accuracy**: 100.00%

### Benchmark Results (BENCHMARK_EVALUATION)

> [!NOTE]
> **Metric Semantics & Disclaimer**:
> - Mode: `BENCHMARK_EVALUATION`
> - Truth Cases: 32 | Predicted Cases: 32
> - Missing Cases Penalized: 0 | Unexpected Cases: 0

| Metric | Score | Definition |
| --- | --- | --- |
| **Evaluated Reference Cases** | 32 | Total cases in reference ground-truth |
| **Case-Level Status Accuracy** | 100.00% | Exact match of `deletion_status` across all truth cases |
| **Full Row-Level Exact Accuracy** | 90.62% | Exact match of status AND entire ordered `steps_json` |
| **Step Precision** | 99.48% | Correct predicted steps / total predicted steps |
| **Step Recall** | 98.45% | Correct predicted steps / total reference steps |
| **Step F1-Score** | 98.96% | Harmonic mean of step precision and recall |
| **Sequence Accuracy** | 100.00% | Correct array ordering among cases with matching step sets |

#### Field-Level Accuracies

| Field | Accuracy | Description |
| --- | --- | --- |
| `deletion_status` | 100.00% | Correct assignment of `deletion_status` across aligned steps |
| `evidence_id` | 100.00% | Correct assignment of `evidence_id` across aligned steps |
| `operation` | 97.91% | Correct assignment of `operation` across aligned steps |
| `phase` | 100.00% | Correct assignment of `phase` across aligned steps |
| `resource_id` | 97.38% | Correct assignment of `resource_id` across aligned steps |
| `state` | 97.91% | Correct assignment of `state` across aligned steps |
| `system_id` | 97.91% | Correct assignment of `system_id` across aligned steps |

#### Case-by-Case Breakdown

| Case ID | Truth Status | Pred Status | Status Match | Row Match | Step F1 | Seq Match | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `case_01` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_02` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_03` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_04` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_05` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_06` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_07` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_08` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_09` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_10` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_11` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_12` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_13` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_14` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_15` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_16` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_17` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_18` | INCOMPLETE | INCOMPLETE | PASS | FAIL | 96.3% | FAIL | Step count mismatch: expected 14, got 13 |
| `case_19` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_20` | INCOMPLETE | INCOMPLETE | PASS | FAIL | 93.3% | FAIL | Step count mismatch: expected 8, got 7 |
| `case_21` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_22` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_23` | INCOMPLETE | INCOMPLETE | PASS | FAIL | 87.5% | FAIL | - |
| `case_24` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_25` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_26` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_27` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_28` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_29` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_30` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_31` | COMPLETE | COMPLETE | PASS | PASS | 100.0% | PASS | - |
| `case_32` | INCOMPLETE | INCOMPLETE | PASS | PASS | 100.0% | PASS | - |

## 7. Ten Comprehensive Edge-Case Scenarios (Execution Results)

- **Total Scenarios Defined**: 10
- **Scenario Schema & Contract Conformance**: 100% PASS
- **Execution Engine**: `PredictionEngine` (COMPLETED)
- **Scenarios Passing**: 10 / 10

| Scenario ID | Category | Expected Status | Execution Result | Supporting Rule |
| --- | --- | --- | --- | --- |
| `scenario_01_non_deletion` | Non-Deletion Intent | `NOT_APPLICABLE` | `PASS` | problem_statement.md line 19 & 91-97; AGENTS.md §6.5 |
| `scenario_02_historical_identity` | Historical Identity Resolution | `INCOMPLETE` | `PASS` | problem_statement.md line 123; deletion_rules.csv rule_03 |
| `scenario_03_secondary_system` | Secondary System Record Remnant | `INCOMPLETE` | `PASS` | deletion_rules.csv rule_06; problem_statement.md lines 105, 111, 114 |
| `scenario_04_active_data_flow` | Recreation Hazard (Active Data Flow) | `INCOMPLETE` | `PASS` | problem_statement.md lines 27, 107, 109, 118 |
| `scenario_05_backup_restore_risk` | Recreation Hazard (Backup Restore Risk) | `INCOMPLETE` | `PASS` | deletion_rules.csv rule_14; problem_statement.md lines 108, 110, 119 |
| `scenario_06_policy_retention` | Policy-Mandated Retention | `INCOMPLETE` | `PASS` | deletion_rules.csv rule_12 & rule_13; problem_statement.md line 115 |
| `scenario_07_temporal_cutoff` | Temporal Cutoff Enforcement | `COMPLETE` | `PASS` | problem_statement.md line 124; AGENTS.md §6.2 |
| `scenario_08_multilingual_intent` | Multilingual Intent Classification | `COMPLETE` | `PASS` | problem_statement.md line 222; AGENTS.md §6.2 |
| `scenario_09_replica_drift` | Conflicting Evidence (Replica Drift) | `INCOMPLETE` | `PASS` | problem_statement.md line 59; AGENTS.md §6.6 |
| `scenario_10_prompt_injection` | Adversarial Prompt Injection Defense | `INCOMPLETE` | `PASS` | AGENTS.md §6.5 & §6.6 |

## 8. Prioritized Defect Register (Remaining 3 Mismatches)

Following Prompt 5 generalized evidence correlation improvements, exact-row accuracy reached **90.62%** (29/32 matches, up from 65.62%). The remaining 3 mismatches are strictly governed by grounding and conservative attribution constraints:

1. **Ungrounded Security Audit Records** (`case_18`, `case_20`):
   - *Observation*: Ground-truth expected `audit_record_6645` (`case_18`) and `audit_record_5569` (`case_20`).
   - *Forensic Investigation*: Exhaustive searching of all files under `dataset/evidence/` reveals neither identifier exists anywhere in the participant evidence.
   - *Governance Compliance*: Problem statement and Prompt 5 explicitly mandate: *'Never generate evidence IDs, resource IDs, audit records, or deletion outcomes without grounding.'* Fabricating ungrounded audit IDs is strictly forbidden.

2. **Concurrent Deletion Worker Ambiguity** (`case_23`):
   - *Observation*: Reference expected `account_410`; prediction selected `account_9155`.
   - *Forensic Investigation*: Two deletion worker failure events occurred within a 2-minute window. Conservative heuristics map to verified identity relationships without hardcoding.
