# Ghost Data Still Exists — Token Usage and Cost Analysis

## 1. Accounting Policy & Transparency Standard

This report tracks model calls, token consumption, and cost estimates for the Northstar Shop deletion audit system across both offline deterministic and Groq-assisted execution modes.

> [!IMPORTANT]
> **Strict Verification Standard**:
> - **Production Pipeline Status**: Full 518-Case Production Run Completed.
> - **Dual-Mode Capability**: 100% offline executable by default with seamless selective Groq reasoning when credentials (`GROQ_API_KEY`) and network access are available.
> - **Selective Invocations**: Groq is gated by explicit confidence thresholds (invoked only when deterministic regex confidence < 0.85). On clean high-confidence datasets, zero unnecessary API calls are made.
> - **Tested Live API Execution**: Verified with real Groq API call using `openai/gpt-oss-120b` (1 live test call: 450 total tokens).
> - **Unit Test Mocking**: All 9 automated Groq unit tests in `test_groq_integration.py` use deterministic mocks and consume 0 tokens.
> - **Cost**: $0.0000 total incurred.

---

## 2. Token Usage & Cost Ledger Across Modes

| Execution Mode | Scope | Total Cases | Model Calls | Prompt Tokens | Completion Tokens | Total Tokens | Avg Tokens / Case | Total Cost (USD) | Wall Clock Time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Mode 1: Deterministic (Groq Disabled)** | 32 Benchmark Cases | 32 | 0 | 0 | 0 | 0 | 0.0 | $0.0000 | 0.67s |
| **Mode 1: Deterministic (Full Production)** | Full Dataset | 518 | 0 | 0 | 0 | 0 | 0.0 | $0.0000 | 9.21s |
| **Mode 2: Groq Enabled (Public Benchmark)** | 32 Benchmark Cases | 32 | 0 | 0 | 0 | 0 | 0.0 | $0.0000 | 0.70s |
| **Mode 2: Groq Enabled (Full Production)** | Full Dataset | 518 | 0 | 0 | 0 | 0 | 0.0 | $0.0000 | 11.16s |
| **Live Ambiguous Intent Verification** | Live API Test | 1 | 1 | 301 | 149 | 450 | 450.0 | $0.0000 | 2.74s |
| **Automated Mock Test Suite** | 9 Unit Tests | 9 | 0 (Mocked) | 0 | 0 | 0 | 0.0 | $0.0000 | 1.22s |

---

## 3. Modular Architecture (Zero-Waste & Safe Fallback Strategy)

1. **Deterministic Subsystems (0 External Model Tokens)**:
   - Schema enforcement, row validation, step ordering, and JSON formatting.
   - Identity graph expansion: Joins across `user_identities.csv` and `user_audit_log.csv`.
   - SQL snapshot execution and table scanning (`sqlite3`).
   - Log parsing, grep/regex extraction of user IDs, phone numbers, and hashes.
   - Deletion policy rule matching (`deletion_rules.csv`).
   - Audit window enforcement: `requested_at <= captured_at <= audit_at`.

2. **Selective Groq Reasoning Assistant (`code/groq_reasoner.py`)**:
   - **Gated Invocation**: Only triggers when natural-language deletion intent is ambiguous (`confidence < 0.85`), avoiding high latency and rate limits on standard requests.
   - **Configurable Model**: Configured via `GROQ_MODEL` (default: `openai/gpt-oss-120b`).
   - **Strict Schema Enforcement**: Rejects malformed JSON, out-of-bounds confidence values, or ungrounded evidence proposals.
   - **Prompt Injection Defense**: Isolates user request text inside `<user_request_text>` XML tags with explicit system directives forbidding instruction obedience.
   - **Zero Secrets**: Reads `GROQ_API_KEY` from environment; never logs authorization headers or keys.
   - **Deterministic Fallback**: Automatically and transparently reverts to deterministic rules if credentials are missing, network times out, or rate limits occur.

---

## 4. Rate Cards & Cost Computation Formula

- **Model**: `openai/gpt-oss-120b` on Groq Cloud.
- **Incurred API Cost**: Free contest / developer tier ($0.0000 total).
- **Network Resilience**: 100% functional offline without network access.
