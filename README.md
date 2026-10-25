# HackerRank Orchestrate - October 2026: Ghost Data Still Exists

An autonomous forensic compliance and deletion audit system for **Northstar Shop**. It determines whether user data was permanently eradicated across distributed systems or persists as **ghost data**, producing canonical remediation and verification steps strictly adhering to the competition contract.

---

## 1. System Architecture

The system uses an adversarial **Hybrid Forensic Pipeline** that pairs a fast, deterministic forensic engine with a token-efficient LLM reviewer agent:

```
                                  [ Deletion Request ]
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │   Deterministic Forensic Engine       │
                       │   - Intent Classification (Regex/NLP) │
                       │   - Identity Graph Resolution         │
                       │   - Evidence Indexing & SQL Forensics │
                       │   - Deletion Policy Rule Compilation  │
                       └───────────────────┬───────────────────┘
                                           │
                                           ▼
                                [ Engine Draft Dossier ]
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │       Uncertainty Router              │
                       │   Flags:                              │
                       │   - Multiple Candidate Accounts       │
                       │   - Historical Identity Changes       │
                       │   - Intent Confidence < 0.90          │
                       │   - Conflicting Evidence Signals      │
                       │   - Invariant Scan Violations         │
                       └───────┬───────────────────────┬───────┘
                               │ (Certain)             │ (Uncertain)
                               ▼                       ▼
                     [ Accept Draft ]      ┌───────────────────────┐
                                           │ ReviewerAgent (LLM)   │
                                           │ - In-Window Digest    │
                                           │ - Provenance Ledger   │
                                           │ - Tool Calling (1 rd) │
                                           │ - Ledger Verification │
                                           └───────────┬───────────┘
                                                       │
                                                       ▼
                                           [ Verified Canonical ]
                                           [ Output Steps CSV   ]
```

### Components
1. **Deterministic Forensic Engine (`code/prediction_engine.py`)**:
   - `IntentInterpreter`: Multilingual intent classifier with negative lookaheads preventing false deletions on portability/access requests.
   - `EvidenceForensicsEngine`: Reconstructs user timelines across 8 systems (`account_service`, `customer_service`, `search_service`, `analytics_service`, `marketing_service`, `security_service`, `integration_service`, `backup_service`).
   - `PolicyMapper`: Compiles findings, remediations, and verification checks conforming to `deletion_rules.csv` and canonical sorting tie-breakers.
2. **ReviewerAgent (`code/agent_loop.py`)**:
   - Gathers a compact context digest (<= 1500 tokens) containing engine drafts, identity profiles, and in-window evidence snippets.
   - Makes a single low-reasoning LLM call (JSON output) with at most 1 tool round (3 tools max, capped at 800 chars).
   - Validates all proposed amendments against the per-case `ProvenanceLedger`; hallucinated identifiers are automatically rejected and discarded.
3. **InvestigatorAgent (`code/agent_loop.py`)**:
   - Full 5-phase autonomous investigative agent (`Plan` -> `Investigate` -> `Dossier` -> `Auditor` -> `Step Proposal`) for deep autonomous investigation.
4. **Agent Tools (`code/agent_tools.py`)**:
   - 8 specialized tools: `resolve_identity`, `list_evidence_manifest`, `search_evidence`, `read_evidence`, `query_sql_snapshot`, `search_activity`, `get_deletion_rules`, `get_baseline_analysis`.

---

## 2. Security & Guardrails

- **Harness-Enforced Temporal Windows**: The harness strictly overwrites `audit_at` and `requested_at` arguments on all tool executions with the case's ground truth timestamps. The model cannot widen temporal windows or observe forward leakage.
- **ProvenanceLedger Validation**: Every cited `resource_id`, `system_id`, and `evidence_id` must be recorded in the case's ledger via tool execution or verified engine analysis. Hallucinations are rejected in pure code.
- **Untrusted User Request Isolation**: User request text is wrapped in `<user_request_text>` tags with system instructions to treat it strictly as inert data, preventing prompt-injection attacks.
- **Zero Secrets Policy**: API keys are read from the environment and scrubbed before writing any traces, caches, or logs (`[REDACTED_API_KEY]`).
- **Token Budget Protection**: Enforces an atomic daily budget (default: 140,000 tokens) persisted in `run_state.json`. At budget exhaustion or on a TPD 429 error, execution gracefully stops and falls back to verified engine drafts (`path_used="engine_budget"`).

---

## 3. Quick Start & Execution

### Installation
```bash
pip install -r requirements.txt
```

### Running the Pipeline (`code/main.py`)
```bash
# Default mode: Fast, offline, deterministic engine (0 API tokens, 100% contract compliant)
python code/main.py dataset output.csv

# Hybrid mode: Engine draft + ReviewerAgent for routed uncertain cases
python code/main.py dataset scratch/prod_hybrid_output.csv --mode hybrid

# Dry-run mode: Analyze routing breakdown and token estimates without calling APIs
python code/main.py dataset scratch/prod_dry_run.csv --mode hybrid --dry-run

# Filter by specific cases or set limit
python code/main.py dataset scratch/test_output.csv --mode hybrid --cases case_01,case_04,case_23 --limit 10
```

---

## 4. Verification & Quality Gates

Run all automated verification gates:
```bash
# 1. Run all 73 unit tests (including all security, temporal, and mock agent tests)
python -m unittest discover -s code/evaluation -p "test_*.py"

# 2. Run the regression gate (validates sample benchmark >= 29/32 and 100% status accuracy)
python scratch/regression_gate.py

# 3. Run strict contract schema validation (checks all 518 production rows)
python code/evaluation/schema_validator.py output.csv

# 4. Run invariant scan (checks temporal boundaries, ordering, and evidence validity)
python scratch/invariant_scan.py output.csv
```

---

## 5. Measured Benchmark Results

| Metric | Measured Result | Benchmark Scope |
|---|---|---|
| **Exact-Row Matches** | **29 / 32 (90.62%)** | 32 Public Cases (`sample_output.csv`) |
| **Case-Status Accuracy** | **32 / 32 (100.00%)** | 32 Public Cases (`sample_output.csv`) |
| **Step Precision** | **99.48%** | 32 Public Cases (`sample_output.csv`) |
| **Step Recall** | **98.45%** | 32 Public Cases (`sample_output.csv`) |
| **Step F1-Score** | **98.96%** | 32 Public Cases (`sample_output.csv`) |
| **Sequence Accuracy** | **100.00%** | Step multiset matched cases |
| **Production Row Count** | **518 / 518 cases** | Full Production Output |
| **Schema Validation Errors** | **0 errors (100% Pass)** | Full Production Output |
| **Invariant Violations** | **0 violations (100% Pass)** | Reduced from 155 in legacy baseline |
| **Unit Test Suite** | **73 / 73 passing** | `code/evaluation/test_*.py` |

---

## 6. Honest Limitations & Edge Cases

1. **Unresolvable Ground Truth in Public Samples**:
   - `case_18` and `case_20`: Reference citations cite `audit_record_6645` and `audit_record_5569`, which do not exist anywhere in participant evidence files.
   - `case_23`: Batch execution window contains 3 simultaneous deletion failure events (`account_7015`, `account_410`, `account_9155`) for the user.
2. **Rate Limit Throttling on Free Tiers**:
   - Free/developer Groq tiers enforce a strict 200k Tokens Per Day (TPD) limit. The hybrid pipeline handles this gracefully via budget tracking and deterministic fallbacks.
3. **SQLite Query Constraints**:
   - SQLite queries in `query_sql_snapshot` are bounded and read-only to prevent denial-of-service on large SQL dumps.
