# Ghost Data Still Exists — Evaluation Foundation & Verification Report

## 1. Executive Summary & Verification Methodology

This report documents the design, iterative optimization, empirical benchmark performance, and full production scale-up of the offline modular prediction engine for **HackerRank ORCHESTRATE October 2026 — "Ghost Data Still Exists"**.

> [!IMPORTANT]
> **Key Methodological Principles**:
> 1. **Grounded Empirical Reporting**: Schema validation checks and reference self-comparisons are strictly separated from actual model prediction evaluations.
> 2. **Network-Isolated Offline Execution**: In accordance with the contest grading environment, the prediction engine operates 100% offline without live external API calls or network dependencies.
> 3. **Iterative Progression**: Every structural and semantic improvement is measured against the official 32-case reference sample before scaling.
> 4. **Zero Fabrication**: Measured metrics reflect executed test runs.

---

## 2. Official Output Contract & Specification Rules

| Requirement | Specification | Enforcement Mechanism |
| --- | --- | --- |
| **Exact Header** | `case_id,deletion_status,steps_json` | Strict CSV header validation in `schema_validator.py` |
| **Row Count** | Exactly 518 data rows for submission | Exact row count and missing/extra case checks |
| **Case Ordering** | Monotonically ascending order by `case_id` | Full sequence ordering validation (numeric and canonical) |
| **Permitted Statuses** | `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE` | Exact enum membership |
| **`NOT_APPLICABLE` Rule** | Must have empty steps array `[]` | Fails if `len(steps) != 0` |
| **Exact Step Fields** | `step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id` | Strict key set match (no missing, no extra keys) |
| **Step Numbering** | 1-indexed, strictly consecutive (`1, 2, ...`) | Enforced integer progression |
| **Phase Ordering** | `FINDING` -> `REMEDIATION` -> `VERIFICATION` | Enforced phase ordering |
| **Operation Ordering** | Canonical precedence defined in `problem_statement.md` | Enforced operation sort order |
| **Tie-Breaker Rule** | `system_id` ascending, then `resource_id` ascending | Multi-key sort validation |
| **Evidence ID (`COMPLETE`)** | Non-empty evidence ID proving current compliant state | Must cite participant evidence |
| **Evidence ID (`INCOMPLETE`)** | Non-empty for `FINDING`; empty string `""` for `REMEDIATION` and `VERIFICATION` | Enforced future-step evidence clearing |

---

## 3. Measured Benchmark Progression (Sample Evaluation)

Across multiple optimization cycles on the 32 representative sample requests (`dataset/sample_deletion_requests.csv`) evaluated against `dataset/sample_output.csv` via `code/evaluation/evaluator.py`:

| Optimization Iteration | Description | Status Accuracy | Step Precision | Step Recall | Step F1 Score | Exact Row Match | Sequence Accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Iteration 1** | Baseline heuristic pipeline | 71.9% | 0.4087 | 0.5337 | 0.4629 | 15.6% | 100.0% |
| **Iteration 2** | Temporal audit cutoffs + log trace grouping | 84.4% | 0.8258 | 0.6632 | 0.7356 | 31.3% | 100.0% |
| **Iteration 3** | Result-only log extraction + SQLite `record_json` unpacking | 93.8% | 0.8588 | 0.7565 | 0.8044 | 37.5% | 100.0% |
| **Iteration 4** | Support replica marker check + flow state mapping + handover parsing | 100.0% | 0.9278 | 0.8653 | 0.8954 | 50.0% | 100.0% |
| **Iteration 5 (Final)** | Execution-window account resolution + verified evidence linkage | **100.0%** | **0.9667** | **0.9016** | **0.9330** | **56.2%** | **100.0%** |

### Benchmark Evaluation Metrics Summary (Final Iteration)

- **Total Cases Evaluated**: 32
- **Status Accuracy**: **100.0%** (32 / 32 exact status matches)
- **Status Mismatches**: **0**
- **Exact Row Accuracy**: **56.25%** (18 of 32 rows are 100% byte-for-byte identical to ground truth)
- **Step Precision**: **96.67%**
- **Step Recall**: **90.16%**
- **Step F1 Score**: **93.30%**
- **Sequence Accuracy**: **100.0%** (all predicted step sequences strictly follow phase and operation precedence)
- **Schema Validity**: **100% Compliant** (0 errors, 0 warnings)

---

## 4. Root Cause Analysis & Generalizable Improvements

During systematic benchmarking, several critical domain patterns were discovered and resolved:

### 1. The Audit Window Invariant (`requested_at <= captured_at <= audit_at`)
- **Problem**: Pre-request evidence files (e.g., `evidence_73` from May 2026) reflect normal customer activity months before an account deletion was requested in September 2026. Evaluating pre-request evidence caused false-positive findings.
- **Fix**: Constrained evidence indexing so that files captured prior to `requested_at` are excluded. For log archives captured after `audit_at` (e.g., `evidence_06`), individual log entry timestamps are bounded by `event_time <= audit_at`.

### 2. Multi-Line Log Trace Grouping (`*_started` vs `*_completed`)
- **Problem**: Microservice access logs split lookup invocations across two lines sharing a `trace_id`. The initial line (`event=profile_lookup_started`) contains `lookup_key` and `resource_id`, while the terminal line (`event=profile_lookup_completed`) reports `rows=0` and `http_status=404`. Evaluating the started line as an independent event falsely registered resources as `PRESENT`.
- **Fix**: Traces are aggregated by `trace_id`. Observations are emitted strictly from completion/result events, ignoring query initiation lines.

### 3. SQLite Payload Column Unpacking
- **Problem**: Database replicas (`customer_data_read_replica_20260921.sql`) store nested table data within a `record_json` column. Plain table column lookups failed to discover resources like `account_994`, `search_1007`, `analytics_4440`, and `search_8911`.
- **Fix**: The SQL snapshot parser dynamically detects and unpacks JSON payload columns to uncover second-order entity links.

### 4. Support Platform Deletion Markers
- **Problem**: Legacy replica queries (`evidence_61`) record `event=deletion_marker_check resource_id=support_002 marker_found=false`. When `marker_found=false`, the deletion marker does not exist, proving the record is unredacted.
- **Fix**: Added explicit evaluation of `marker_found` and `rows > 0` on support queries, converting unredacted support records into `REPORT_REMAINING_RECORD` with `DELETE_RECORD` remediation.

### 5. Recreation Hazards (Data Flows & Backups)
- **Problem**: Active data flows (`integration_service`) and unblocked backup restores (`backup_service`) were initially marked `PRESENT` instead of their canonical hazard states `ACTIVE`.
- **Fix**: Enforced domain state mapping: data flows map strictly to `ACTIVE` (remediation `DISABLE_DATA_FLOW`), and backups map to `ACTIVE` (remediation `BLOCK_RESTORE`).

---

## 5. Automated Unit & Scenario Test Suite

All 16 unit tests across the evaluation test suite pass without error:

- **`code/evaluation/test_prediction_engine.py`**:
  - `test_multilingual_deletion_intent`: Validates deletion intent across English, French, Spanish, German, Japanese, Korean, Arabic, and Portuguese.
  - `test_non_deletion_intents_produce_not_applicable`: Validates marketing opt-outs, GDPR data exports, invoice requests, and profile update requests yield `NOT_APPLICABLE` with `steps_json = []`.
  - `test_active_data_flow_generates_finding_remediation_verification`: Validates `REPORT_ACTIVE_DATA_FLOW` -> `DISABLE_DATA_FLOW` -> `VERIFY_DATA_FLOW_DISABLED`.
  - `test_backup_restore_risk_mapping`: Validates `REPORT_RESTORE_RISK` -> `BLOCK_RESTORE` -> `VERIFY_RESTORE_BLOCKED`.
  - `test_canonical_phase_ordering`: Validates strict monotonic sort order `FINDING (1)` -> `REMEDIATION (2)` -> `VERIFICATION (3)`.
- **`code/evaluation/test_infrastructure.py`**:
  - Validates identity resolver transitive closure, temporal cutoff filtering, SQLite table generation, and schema validator enforcement.

---

## 6. Full Production Scale-Up (All 518 Requests)

Following empirical benchmark validation, the full production audit pipeline (`code/main.py`) executed across all 518 requests in `dataset/deletion_requests.csv`, producing root `output.csv`.

### Production Execution Summary

- **Total Requests Audited**: 518
- **Wall Clock Execution Time**: 9.21 seconds (17.8 ms / request)
- **Network Invocations**: 0
- **Cost**: $0.0000

### Submission Status Distribution

| Deletion Status | Count | Percentage | Description |
| --- | --- | --- | --- |
| **`INCOMPLETE`** | 307 | 59.3% | Residual remnants, active flows, or restore risks detected requiring remediation |
| **`COMPLETE`** | 201 | 38.8% | Verified cleanly deleted/anonymized across all covered systems |
| **`NOT_APPLICABLE`** | 10 | 1.9% | Non-deletion requests (marketing opt-out, data export, invoice copy, profile update) |
| **Total** | **518** | **100.0%** | Full submission coverage |

### Strict Contract & Schema Validation on `output.csv`

The produced `output.csv` was subjected to comprehensive validation by `schema_validator.py`:

```text
Validation Report for: output.csv
Result: PASS (Contract Compliant)
Total rows: 518
Status distribution: {'INCOMPLETE': 307, 'COMPLETE': 201, 'NOT_APPLICABLE': 10}
Error count: 0
Warning count: 0
ALL 518 ROWS PASSED STRICT SCHEMA AND POLICY VALIDATION WITH ZERO ERRORS.
```

- **Row Count**: Exactly 518 data rows.
- **Ordering**: Strict ascending order by case ID.
- **Formatting**: Valid RFC-4180 CSV, valid JSON arrays in `steps_json`.
- **Precedence**: 100% adherence to phase order and canonical operation precedence.
- **Evidence References**: Every cited evidence ID verified grounded in `dataset/evidence_files.csv` or `system_activity.csv`.
