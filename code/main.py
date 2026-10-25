"""Main production pipeline entry point for Ghost Data Still Exists.

Executes engine, agent, or hybrid audit pipeline on deletion requests,
enforcing token budgets, provenance tracking, temporal windows, and schema validation.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code.agent_loop import InvestigatorAgent, ReviewerAgent
from code.evaluation.schema_validator import validate_csv
from code.identity_resolver import IdentityResolver, UserProfile
from code.prediction_engine import PredictionEngine

DEFAULT_DAILY_TOKEN_BUDGET = 140000
ESTIMATED_TOKENS_PER_ROUTED_CASE = 4000


class RunStateTracker:
    """Tracks and persists daily token usage across runs in run_state.json."""

    def __init__(self, state_file: Path, daily_budget: int = DEFAULT_DAILY_TOKEN_BUDGET):
        self.state_file = state_file
        self.daily_budget = daily_budget
        self.tokens_used_today = 0
        self.cases_reviewed_today = 0
        self.today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self._load_state()

    def _load_state(self) -> None:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("date") == self.today_str:
                    self.tokens_used_today = int(data.get("tokens_used_today", 0))
                    self.cases_reviewed_today = int(data.get("cases_reviewed_today", 0))
                    self.daily_budget = int(data.get("daily_budget", self.daily_budget))
                else:
                    # New day: reset usage
                    self.tokens_used_today = 0
                    self.cases_reviewed_today = 0
                    self._save_state()
            except Exception:
                self._save_state()
        else:
            self._save_state()

    def _save_state(self) -> None:
        payload = {
            "date": self.today_str,
            "daily_budget": self.daily_budget,
            "tokens_used_today": self.tokens_used_today,
            "cases_reviewed_today": self.cases_reviewed_today,
            "remaining_budget": max(0, self.daily_budget - self.tokens_used_today),
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def remaining_tokens(self) -> int:
        return max(0, self.daily_budget - self.tokens_used_today)

    def can_call(self) -> bool:
        return self.remaining_tokens() > 0

    def record_usage(self, tokens: int, case_id: Optional[str] = None) -> None:
        self.tokens_used_today += max(0, tokens)
        self.cases_reviewed_today += 1
        self._save_state()


class UncertaintyRouter:
    """Routes cases in hybrid mode based on 5 objective uncertainty criteria:

    1. Multiple candidate accounts (ambiguous account resolution)
    2. Historical-identity match (request email matches historical record)
    3. Intent confidence < 0.90 (ambiguous or non-deletion request)
    4. Conflicting evidence (recreation, active data flows, or contradictory records)
    5. Invariant-scan violations (draft output violates schema/policy rules)
    """

    def __init__(self, dataset_dir: Path, engine: PredictionEngine):
        self.dataset_dir = dataset_dir
        self.engine = engine
        self.resolver = IdentityResolver(dataset_dir)
        self.activities = engine.forensics_engine.system_activities
        self.indexer = engine.forensics_engine.indexer

    def evaluate_case(
        self,
        case_row: Dict[str, str],
        engine_draft: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        case_id = case_row.get("case_id", "").strip()
        email = case_row.get("email", "").strip().lower()
        requested_at = case_row.get("requested_at", "").strip()
        reported_at = case_row.get("reported_at", "").strip()
        audit_at = case_row.get("audit_at", "").strip()
        reported_status = case_row.get("reported_status", "").strip()
        request_text = case_row.get("request_text", "").strip()

        status = engine_draft.get("deletion_status", "")
        raw_steps = engine_draft.get("steps_json", "[]")
        try:
            steps = json.loads(raw_steps) if isinstance(raw_steps, str) else raw_steps
        except Exception:
            steps = []

        # 1. Multiple candidate accounts
        profile = engine_draft.get("profile") or self.resolver.resolve_by_email(email)
        intent = engine_draft.get("intent")
        resources = engine_draft.get("resources") or []

        uids = self.resolver.historical_email_to_user_ids.get(email, set())
        curr_uid = self.resolver.current_email_to_user_id.get(email)
        if curr_uid:
            uids = uids | {curr_uid}

        has_multi_accounts = False
        if len(uids) > 1:
            has_multi_accounts = True
        elif requested_at and reported_at:
            try:
                rep_dt = datetime.datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
                b_start = (rep_dt - datetime.timedelta(hours=2.5)).isoformat().replace("+00:00", "Z")
                b_end = (rep_dt + datetime.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
                window_acts = [
                    a for a in self.activities
                    if a["target_system"] == "account_service"
                    and a["event_type"] == "DELETE_RECORD"
                    and b_start <= a["event_time"] <= b_end
                ]
                valid_acts = [
                    a for a in window_acts
                    if a["resource_id"] not in self.indexer.known_other_accounts
                    or self.indexer.known_other_accounts[a["resource_id"]] == email
                ]
                status_matched = []
                if reported_status == "COMPLETE":
                    status_matched = [a for a in valid_acts if a.get("reported_result") == "SUCCESS"]
                elif reported_status == "NOT_STARTED":
                    status_matched = [a for a in valid_acts if a.get("reported_result") == "FAILED"]
                elif reported_status == "PARTIALLY_COMPLETE":
                    status_matched = [a for a in valid_acts if a.get("reported_result") == "PARTIAL"]

                candidate_pool = status_matched if status_matched else valid_acts
                ev_res_ids = {r.resource_id for r in resources if r.system_id == "account_service"}
                confirmed = [
                    a for a in candidate_pool
                    if a["resource_id"] in ev_res_ids
                    or a["resource_id"] in getattr(self.indexer, "grounded_account_ids", set())
                ]
                if len(candidate_pool) > 1 and not confirmed:
                    has_multi_accounts = True
            except Exception:
                pass

        if has_multi_accounts:
            reasons.append("multiple_candidate_accounts")

        # 2. Historical-identity match
        if profile and email in [e.lower() for e in profile.historical_emails] and email != profile.current_email.lower():
            reasons.append("historical_identity_match")

        # 3. Intent confidence < 0.90
        if not intent:
            intent = self.engine.intent_interpreter.interpret(request_text)
        if intent and intent.confidence < 0.90:
            reasons.append("intent_confidence_low")

        # 4. Conflicting evidence
        has_conflict = False
        for r in resources:
            if r.state in ("PRESENT", "ACTIVE") and r.system_id != "security_service":
                for a in self.activities:
                    if a.get("resource_id") == r.resource_id and a.get("reported_result") == "SUCCESS":
                        has_conflict = True
                        break
            if has_conflict:
                break
        if has_conflict:
            reasons.append("conflicting_evidence")

        # 5. Invariant-scan violations in draft
        has_inv_violation = False
        findings = [s for s in steps if s.get("phase") == "FINDING"]
        remediations = [s for s in steps if s.get("phase") == "REMEDIATION"]
        verifs = [s for s in steps if s.get("phase") == "VERIFICATION"]

        if status == "COMPLETE":
            if findings or remediations or not verifs:
                has_inv_violation = True
        elif status == "INCOMPLETE":
            if not findings:
                has_inv_violation = True
        elif status == "NOT_APPLICABLE":
            if steps:
                has_inv_violation = True

        if has_inv_violation:
            reasons.append("invariant_violation")

        return (len(reasons) > 0, reasons)


def parse_case_num(cid: str) -> int:
    parts = cid.split("_")
    return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 999999


def run_pipeline(
    dataset_dir: Path,
    output_file: Path,
    mode: str = "engine",
    dry_run: bool = False,
    limit: Optional[int] = None,
    cases_filter: Optional[Set[str]] = None,
    concurrency: int = 1,
    enable_groq: Optional[bool] = None,
    daily_budget: int = DEFAULT_DAILY_TOKEN_BUDGET,
) -> Dict[str, Any]:
    start_time = time.time()
    dataset_dir = Path(dataset_dir).resolve()
    output_file = Path(output_file).resolve()

    print("=" * 80)
    print("ORCHESTRATE: GHOST DATA STILL EXISTS - COMPLIANCE AUDIT PIPELINE")
    print("=" * 80)
    print(f"Timestamp:       {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print(f"Dataset root:    {dataset_dir}")
    print(f"Output target:   {output_file}")
    print(f"Execution Mode:  {mode.upper()}")
    print(f"Dry Run:         {dry_run}")
    print(f"Concurrency:     {concurrency}")
    print(f"Daily Budget:    {daily_budget:,} tokens")

    # Load deletion requests
    if dataset_dir.is_file():
        requests_path = dataset_dir
        dataset_dir = dataset_dir.parent
    else:
        requests_path = dataset_dir / "deletion_requests.csv"
        if not requests_path.exists():
            requests_path = dataset_dir / "sample_deletion_requests.csv"

    if not requests_path.exists():
        raise FileNotFoundError(f"Missing deletion requests file in {dataset_dir}")

    with open(requests_path, mode="r", encoding="utf-8") as f:
        all_requests = list(csv.DictReader(f))

    if cases_filter:
        requests = [r for r in all_requests if r.get("case_id") in cases_filter]
    else:
        requests = all_requests

    if limit is not None and limit > 0:
        requests = requests[:limit]

    print(f"Loaded {len(requests)} cases to evaluate.")

    # Initialize Engine
    engine = PredictionEngine(dataset_dir=dataset_dir, enable_groq=enable_groq)
    state_file = PROJECT_ROOT / "run_state.json"
    tracker = RunStateTracker(state_file, daily_budget=daily_budget)

    # Tracking metrics
    results: List[Dict[str, Any]] = []
    status_counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}
    routed_cases_info: List[Dict[str, Any]] = []
    reason_counts = {
        "multiple_candidate_accounts": 0,
        "historical_identity_match": 0,
        "intent_confidence_low": 0,
        "conflicting_evidence": 0,
        "invariant_violation": 0,
    }

    router = UncertaintyRouter(dataset_dir, engine)

    # ReviewerAgent initialization if needed
    reviewer: Optional[ReviewerAgent] = None
    if mode in ("agent", "hybrid") and not dry_run:
        reviewer = ReviewerAgent(
            dataset_dir=dataset_dir,
            cache_dir=PROJECT_ROOT / "agent_cache",
            traces_dir=PROJECT_ROOT / "agent_traces",
        )

    tpd_429_halt = False

    for idx, req in enumerate(requests, start=1):
        case_id = req.get("case_id", "").strip()

        # Step 1: Baseline engine draft
        draft = engine.audit_case(req)
        final_status = draft["deletion_status"]
        final_steps = draft["steps_json"]
        path_used = "engine"

        # Step 2: Routing evaluation (for hybrid or dry-run)
        is_uncertain, reasons = router.evaluate_case(req, draft)
        if is_uncertain:
            for r in reasons:
                reason_counts[r] = reason_counts.get(r, 0) + 1
            routed_cases_info.append({
                "case_id": case_id,
                "reasons": reasons,
                "draft_status": draft["deletion_status"],
            })

        # Step 3: Execution by mode
        if mode == "hybrid":
            if is_uncertain and not dry_run:
                if tpd_429_halt or not tracker.can_call():
                    path_used = "engine_budget"
                elif reviewer and reviewer.client:
                    rem_budget = tracker.remaining_tokens()
                    review_res = reviewer.review_case(
                        case_row=req,
                        engine_draft=draft,
                        daily_token_budget_remaining=rem_budget,
                    )
                    if review_res.path_used == "engine_budget_429":
                        tpd_429_halt = True
                        path_used = "engine_budget"
                    elif review_res.path_used == "engine_budget":
                        path_used = "engine_budget"
                    elif review_res.deletion_status is not None:
                        final_status = review_res.deletion_status
                        final_steps = json.dumps(review_res.steps, separators=(",", ":"))
                        path_used = review_res.path_used
                        tokens_used = review_res.metrics.get("tokens_used", 0)
                        tracker.record_usage(tokens_used, case_id=case_id)
                    else:
                        path_used = "engine_fallback"
                else:
                    path_used = "engine_offline"

        elif mode == "agent":
            if not dry_run and reviewer and reviewer.client and not tpd_429_halt:
                if not tracker.can_call():
                    path_used = "engine_budget"
                else:
                    review_res = reviewer.review_case(
                        case_row=req,
                        engine_draft=draft,
                        daily_token_budget_remaining=tracker.remaining_tokens(),
                    )
                    if review_res.path_used == "engine_budget_429":
                        tpd_429_halt = True
                        path_used = "engine_budget"
                    elif review_res.deletion_status is not None:
                        final_status = review_res.deletion_status
                        final_steps = json.dumps(review_res.steps, separators=(",", ":"))
                        path_used = review_res.path_used
                        tracker.record_usage(review_res.metrics.get("tokens_used", 0), case_id=case_id)
            else:
                path_used = "engine_fallback"

        results.append({
            "case_id": case_id,
            "deletion_status": final_status,
            "steps_json": final_steps,
            "path_used": path_used,
        })
        status_counts[final_status] = status_counts.get(final_status, 0) + 1

        # Checkpoint partial CSV every 25 cases
        if idx % 25 == 0 and not dry_run:
            partial_path = PROJECT_ROOT / "scratch" / "output_partial.csv"
            partial_path.parent.mkdir(parents=True, exist_ok=True)
            with open(partial_path, "w", encoding="utf-8", newline="") as pf:
                writer = csv.DictWriter(pf, fieldnames=["case_id", "deletion_status", "steps_json"])
                writer.writeheader()
                for r in results:
                    writer.writerow({
                        "case_id": r["case_id"],
                        "deletion_status": r["deletion_status"],
                        "steps_json": r["steps_json"],
                    })

        if idx % 50 == 0 or idx == len(requests):
            print(f"Processed {idx:3d} / {len(requests)} cases (Status: {final_status}, Path: {path_used})")

    # Sort results canonically
    results.sort(key=lambda r: parse_case_num(r["case_id"]))

    elapsed = time.time() - start_time

    # Report Routing Analysis
    print("\n" + "=" * 80)
    print("ROUTING AND UNCERTAINTY ANALYSIS REPORT")
    print("=" * 80)
    print(f"Total Cases Analyzed:   {len(requests)}")
    print(f"Total Cases Routed:     {len(routed_cases_info)} ({(len(routed_cases_info)/max(1, len(requests)))*100:.1f}%)")
    print("\nRouted Breakdown by Uncertainty Reason:")
    for reason, count in reason_counts.items():
        print(f"  - {reason:32s}: {count:4d}")
    est_tokens = len(routed_cases_info) * ESTIMATED_TOKENS_PER_ROUTED_CASE
    print(f"\nEstimated Tokens Required: {est_tokens:,} tokens (routed x 4,000)")
    print(f"Current Daily Token Budget: {tracker.daily_budget:,} (Remaining Today: {tracker.remaining_tokens():,})")

    # If dry run, finish here without touching files
    if dry_run:
        print("\n[DRY RUN COMPLETE] Zero API tokens invoked, no output files modified.")
        return {
            "total_cases": len(requests),
            "routed_count": len(routed_cases_info),
            "reason_counts": reason_counts,
            "estimated_tokens": est_tokens,
            "remaining_budget": tracker.remaining_tokens(),
            "results": results,
        }

    # Write output to temporary file first, validate schema, then replace
    temp_output = output_file.with_name(f"{output_file.stem}_temp{output_file.suffix}")
    temp_output.parent.mkdir(parents=True, exist_ok=True)

    with open(temp_output, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "case_id": r["case_id"],
                "deletion_status": r["deletion_status"],
                "steps_json": r["steps_json"],
            })

    # Validate output schema
    print("\nExecuting strict schema validation before committing output...")
    val_report = validate_csv(temp_output, expected_rows=len(results))
    print(val_report.summary())

    if not val_report.is_valid:
        print(f"SCHEMA VALIDATION FAILED with {len(val_report.errors)} errors! Aborting overwrite.")
        for err in val_report.errors[:10]:
            print(f"  - Case {err.case_id} [Step {err.step_no}]: {err.message}")
        if temp_output.exists():
            temp_output.unlink()
        sys.exit(1)

    # Atomic rename/replace
    if temp_output.exists():
        if output_file.exists():
            output_file.unlink()
        temp_output.rename(output_file)

    print(f"\nWrote {len(results)} verified rows to {output_file} in {elapsed:.2f} seconds.")
    print("\nFinal Status Distribution:")
    for status, count in status_counts.items():
        pct = (count / len(results)) * 100
        print(f"  {status:15s}: {count:4d} ({pct:5.1f}%)")

    return {
        "total_cases": len(results),
        "routed_count": len(routed_cases_info),
        "reason_counts": reason_counts,
        "estimated_tokens": est_tokens,
        "remaining_budget": tracker.remaining_tokens(),
        "output_file": str(output_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Prediction & Audit Pipeline")
    parser.add_argument("pos_dataset_dir", nargs="?", default=None, help="Dataset directory path")
    parser.add_argument("pos_output_file", nargs="?", default=None, help="Target output CSV file path")
    parser.add_argument("--dataset-dir", "--dataset", dest="dataset_dir", default=None, help="Path to dataset directory")
    parser.add_argument("--output-file", "--output", dest="output_file", default=None, help="Path to target output CSV file")
    parser.add_argument("--mode", choices=["engine", "agent", "hybrid"], default="engine", help="Pipeline execution mode (default: engine)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze routing and tokens without calling LLM or overwriting output")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to process")
    parser.add_argument("--cases", default=None, help="Comma-separated list of case_ids to audit")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrency level")
    parser.add_argument("--disable-groq", action="store_true", help="Force disable Groq reasoning (offline deterministic)")
    parser.add_argument("--groq", action="store_true", help="Enable Groq reasoning assistant")
    parser.add_argument("--budget", type=int, default=None, help="Override daily token budget")

    args, unknown = parser.parse_known_args()

    enable_groq = False if args.disable_groq else (True if args.groq else None)
    ds_path = args.dataset_dir or args.pos_dataset_dir or (PROJECT_ROOT / "dataset")
    out_path = args.output_file or args.pos_output_file or (PROJECT_ROOT / "output.csv")
    dataset_dir = Path(ds_path).resolve()
    output_file = Path(out_path).resolve()

    cases_filter = set(args.cases.split(",")) if args.cases else None
    daily_budget = args.budget or int(os.environ.get("AGENT_DAILY_TOKEN_BUDGET", DEFAULT_DAILY_TOKEN_BUDGET))

    run_pipeline(
        dataset_dir=dataset_dir,
        output_file=output_file,
        mode=args.mode,
        dry_run=args.dry_run,
        limit=args.limit,
        cases_filter=cases_filter,
        concurrency=args.concurrency,
        enable_groq=enable_groq,
        daily_budget=daily_budget,
    )


if __name__ == "__main__":
    main()
