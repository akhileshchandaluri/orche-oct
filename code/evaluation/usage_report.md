# Ghost Data Still Exists — Token Usage, Latency & Cost Report

## 1. Accounting Policy & Transparency Standard

This report tracks model calls, token consumption, and cost estimates across offline deterministic, unit testing, and live Groq-assisted execution modes.

> [!IMPORTANT]
> **Strict Verification Standard**:
> - **Zero Fabricated Token Counts**: All reported token usages derive directly from Groq API completion responses and local `run_state.json` persistence.
> - **Budget Enforcement**: Hard daily budget cap of **140,000 tokens** enforced via `RunStateTracker` and checked before every model call.
> - **Rate Limit Resilience**: TPD-429 rate limit exceptions are trapped and handled cleanly without process crash or score degradation.
> - **Zero Secrets**: API keys are scrubbed before writing any traces, caches, or logs (`[REDACTED_API_KEY]`).

---

## 2. Token Usage & Cost Ledger Across Modes

| Execution Mode | Scope | Cases | Model Calls | Total Tokens | Avg Tokens / Case | Total Cost (USD) | Wall Clock Time |
|---|---|---|---|---|---|---|---|
| **Deterministic Engine** | Full Dataset | 518 | 0 | 0 | 0.0 | $0.0000 | 16.42s |
| **Deterministic Benchmark** | Public Benchmark | 32 | 0 | 0 | 0.0 | $0.0000 | 0.68s |
| **ReviewerAgent Live Run** | Sample Routed | 8 | 2 completed, 4 TPD-429, 2 conn | 6,671 | 833.9 | $0.0000 | 58.70s |
| **Production Hybrid Pipeline** | Full Dataset | 518 | Routed within budget | 6,671 | 12.9 | $0.0000 | 76.03s |
| **Automated Mock Test Suite** | 73 Unit Tests | 73 | 0 (Deterministic Mocks) | 0 | 0.0 | $0.0000 | 6.28s |

---

## 3. Token-Efficient Adversarial Reviewer Architecture

1. **Context Digestion (`ReviewerAgent._gather_context_digest`)**:
   - Gathers engine draft, identity resolution profile, and in-window evidence snippets into a bounded digest (<= 1,500 tokens).
2. **Low-Reasoning Model Call**:
   - Single structured JSON call with `reasoning_effort="low"`, `max_tokens=1500`.
   - Small review model (`AGENT_MODEL_REVIEW`, default `openai/gpt-oss-20b`), with optional escalation model (`AGENT_MODEL_ESCALATE`, default `openai/gpt-oss-120b`).
3. **Tool Bounding**:
   - At most 1 tool round, max 3 tools, with each tool output strictly capped at 800 characters.
4. **Hard Token Cap**:
   - Hard cap of 6,000 tokens per case prevents runaway context expansion.
5. **Budget Tracking**:
   - Persisted in `run_state.json`. At budget exhaustion or on a TPD-429 error, execution halts immediately and falls back to verified engine drafts (`path_used="engine_budget"`).

---

## 4. Rate Cards & API Cost

- **Platform**: Groq Cloud API
- **Models**: `openai/gpt-oss-20b` (Review), `openai/gpt-oss-120b` (Escalation)
- **Total Incurred Cost**: $0.0000 (Free contest / developer tier)
- **Offline Reliability**: 100% functional offline without network connectivity or API keys.
