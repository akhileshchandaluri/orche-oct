"""Regression tests for concurrent execution windows and temporal cutoff handling.

Ensures that:
1. Accounts in concurrent windows are disambiguated using explicit identity exclusions
   (e.g., account_3610 belongs to n.masuku60@gmail.com, not mori.ren@gmail.com).
2. Account selection prioritizes evidence-corroborated records over temporal proximity.
3. Temporal cutoff properly filters mutable snapshots while preserving immutable audit logs.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code.prediction_engine import PredictionEngine
from code.evidence_indexer import EvidenceIndexer


class TestRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")
        cls.indexer = cls.engine.forensics_engine.indexer

    def test_concurrent_window_account_disambiguation(self):
        """Case 18 (mori.ren@gmail.com) must resolve to account_5521, not account_3610."""
        profile = self.engine.forensics_engine.resolver.resolve_by_email("mori.ren@gmail.com")
        self.assertIsNotNone(profile)
        # account_3610 is known to belong to n.masuku60@gmail.com
        self.assertIn("account_3610", self.indexer.known_other_accounts)
        self.assertEqual(self.indexer.known_other_accounts["account_3610"], "n.masuku60@gmail.com")

        acc_id, ev_id = self.engine.forensics_engine.resolve_primary_account_id(
            profile=profile,
            req_email="mori.ren@gmail.com",
            requested_at="2026-09-06T11:00:00Z",
            reported_at="2026-09-09T11:00:00Z",
            audit_at="2026-09-20T11:00:00Z",
            evidence_items=[],
            reported_status="COMPLETE",
        )
        self.assertEqual(acc_id, "account_5521")

    def test_account_corroboration_over_proximity(self):
        """Case 28 (smartinez6461@gmail.com) must select evidence-corroborated account_5482 over account_7012."""
        profile = self.engine.forensics_engine.resolver.resolve_by_email("smartinez6461@gmail.com")
        self.assertIsNotNone(profile)
        self.assertIn("account_5482", self.indexer.grounded_account_ids)
        self.assertNotIn("account_7012", self.indexer.grounded_account_ids)

        acc_id, _ = self.engine.forensics_engine.resolve_primary_account_id(
            profile=profile,
            req_email="smartinez6461@gmail.com",
            requested_at="2026-08-28T12:00:00Z",
            reported_at="2026-08-30T12:00:00Z",
            audit_at="2026-09-15T12:00:00Z",
            evidence_items=[],
            reported_status="NOT_STARTED",
        )
        self.assertEqual(acc_id, "account_5482")

    def test_temporal_cutoff_security_audit_preservation(self):
        """Case 23 (thandiwe.m6866@zoho.com) must ground audit_record_4128 via security service snapshot."""
        profile = self.engine.forensics_engine.resolver.resolve_by_email("thandiwe.m6866@zoho.com")
        self.assertIsNotNone(profile)
        evidence_items = self.indexer.find_evidence_for_user(
            profile=profile,
            audit_at="2026-09-15T12:00:00Z",
            requested_at="2026-09-02T12:00:00Z",
        )
        audit_res_ids = {it.resource_id for it in evidence_items if it.system_id == "security_service"}
        self.assertIn("audit_record_4128", audit_res_ids)


if __name__ == "__main__":
    unittest.main()
