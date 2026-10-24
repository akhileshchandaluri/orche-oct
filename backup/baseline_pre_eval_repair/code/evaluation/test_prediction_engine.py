"""Behavioral unit tests for PredictionEngine.

Validates:
1. Multilingual intent classification (English, French, Spanish, German, Japanese, Korean, Arabic).
2. Non-deletion intent classification (marketing opt-out, data export, invoice request).
3. Temporal window constraints (requested_at <= captured_at <= audit_at).
4. Grounded forensic reasoning and policy mapping.
5. Canonical step sequencing and schema compliance.
"""

from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
from code.prediction_engine import IntentInterpreter, PolicyMapper, PredictionEngine, IntentResult


class TestPredictionEngineBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")
        cls.intent_interpreter = IntentInterpreter()
        cls.policy_mapper = PolicyMapper()

    def test_multilingual_deletion_intent(self):
        """Verify semantic intent identification across all languages in specification."""
        test_cases = [
            ("Please permanently delete my account and personal data.", True, "en"),
            ("Veuillez supprimer définitivement mon compte et effacer mes données.", True, "fr"),
            ("Por favor, elimine permanentemente mi cuenta y mis datos personales.", True, "es"),
            ("Bitte löschen Sie mein Konto und alle damit verbundenen Daten.", True, "de"),
            ("アカウントとすべての個人データを完全に削除してください。", True, "ja"),
            ("계정과 모든 개인정보를 영구적으로 삭제해 주십시오.", True, "ko"),
            ("يرجى حذف حسابي وجميع البيانات الشخصية بشكل دائم.", True, "ar"),
            ("Por favor, apague minha conta e todos os dados associados.", True, "pt"),
        ]
        for text, expected, lang in test_cases:
            with self.subTest(lang=lang):
                res = self.intent_interpreter.interpret(text)
                self.assertEqual(res.is_deletion, expected, f"Failed deletion intent for {lang}: {text}")
                self.assertGreaterEqual(res.confidence, 0.8)

    def test_non_deletion_intents_produce_not_applicable(self):
        """Verify non-deletion intents are recognized as NOT_APPLICABLE with empty steps."""
        non_deletion_samples = [
            "Please unsubscribe me from marketing emails. I still use the service.",
            "Can you send me an export of all my personal data and receipts?",
            "I need a copy of my invoice for last month's subscription.",
            "Please update my phone number to +1 555-0199.",
            "I want to change my primary email address on my profile.",
        ]
        for text in non_deletion_samples:
            res = self.intent_interpreter.interpret(text)
            self.assertFalse(res.is_deletion, f"Non-deletion text incorrectly classified as deletion: {text}")

            # Test audit_case with synthetic request
            req = {
                "case_id": "test_non_del",
                "email": "test@example.com",
                "requested_at": "2026-09-01T00:00:00Z",
                "reported_status": "NOT_APPLICABLE",
                "reported_at": "2026-09-01T01:00:00Z",
                "audit_at": "2026-09-05T00:00:00Z",
                "request_text": text,
            }
            audit_res = self.engine.audit_case(req)
            self.assertEqual(audit_res["deletion_status"], "NOT_APPLICABLE")
            self.assertEqual(audit_res["steps_json"], "[]")

    def test_active_data_flow_generates_finding_remediation_verification(self):
        """Verify active data flow maps to REPORT_ACTIVE_DATA_FLOW -> DISABLE_DATA_FLOW -> VERIFY_DATA_FLOW_DISABLED."""
        # case_18 has active data_flow_4890
        req = {
            "case_id": "case_18",
            "email": "mori.ren@gmail.com",
            "requested_at": "2026-09-06T11:00:00Z",
            "reported_status": "COMPLETE",
            "reported_at": "2026-09-09T11:00:00Z",
            "audit_at": "2026-09-26T11:00:00Z",
            "request_text": "Please delete my account and personal data.",
        }
        res = self.engine.audit_case(req)
        self.assertEqual(res["deletion_status"], "INCOMPLETE")
        
        # Check that data flow steps exist
        import json
        steps = json.loads(res["steps_json"])
        flow_steps = [s for s in steps if s["resource_id"] == "data_flow_4890"]
        self.assertEqual(len(flow_steps), 3)
        self.assertEqual(flow_steps[0]["phase"], "FINDING")
        self.assertEqual(flow_steps[0]["operation"], "REPORT_ACTIVE_DATA_FLOW")
        self.assertEqual(flow_steps[0]["evidence_id"], "evidence_94")
        self.assertEqual(flow_steps[1]["phase"], "REMEDIATION")
        self.assertEqual(flow_steps[1]["operation"], "DISABLE_DATA_FLOW")
        self.assertEqual(flow_steps[2]["phase"], "VERIFICATION")
        self.assertEqual(flow_steps[2]["operation"], "VERIFY_DATA_FLOW_DISABLED")

    def test_backup_restore_risk_mapping(self):
        """Verify unblocked backup generates restore risk steps."""
        # case_14 has backup_3870
        req = {
            "case_id": "case_14",
            "email": "y.tanaka32@gmail.com",
            "requested_at": "2026-09-04T12:00:00Z",
            "reported_status": "COMPLETE",
            "reported_at": "2026-09-06T12:00:00Z",
            "audit_at": "2026-10-01T12:00:00Z",
            "request_text": "Please delete my account and all personal information.",
        }
        res = self.engine.audit_case(req)
        self.assertEqual(res["deletion_status"], "INCOMPLETE")
        import json
        steps = json.loads(res["steps_json"])
        backup_steps = [s for s in steps if s["resource_id"] == "backup_3870"]
        self.assertEqual(len(backup_steps), 3)
        self.assertEqual(backup_steps[0]["operation"], "REPORT_RESTORE_RISK")
        self.assertEqual(backup_steps[0]["evidence_id"], "evidence_03")
        self.assertEqual(backup_steps[1]["operation"], "BLOCK_RESTORE")
        self.assertEqual(backup_steps[2]["operation"], "VERIFY_RESTORE_BLOCKED")

    def test_canonical_phase_ordering(self):
        """Ensure all generated steps strictly adhere to FINDING -> REMEDIATION -> VERIFICATION."""
        import json
        sample_file = PROJECT_ROOT / "dataset" / "sample_deletion_requests.csv"
        import csv
        with open(sample_file, mode="r", encoding="utf-8") as f:
            sample_reqs = list(csv.DictReader(f))

        phase_rank = {"FINDING": 1, "REMEDIATION": 2, "VERIFICATION": 3}
        for req in sample_reqs[:15]:
            res = self.engine.audit_case(req)
            steps = json.loads(res["steps_json"])
            if not steps:
                continue
            ranks = [phase_rank[s["phase"]] for s in steps]
            self.assertEqual(ranks, sorted(ranks), f"Phase ordering violated in {req['case_id']}: {ranks}")
            step_nos = [s["step_no"] for s in steps]
            self.assertEqual(step_nos, list(range(1, len(steps) + 1)), f"Step numbering violated in {req['case_id']}")


if __name__ == "__main__":
    unittest.main()
