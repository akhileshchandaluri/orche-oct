"""Unit tests for AgentTools and ProvenanceLedger in Ghost Data Still Exists.

Tests:
1. Temporal cutoff enforcement: post-audit_at evidence is NEVER returned.
2. Provenance ledger: every file_id, activity_id, audit_id, and resource_id is recorded.
3. Multi-format identity resolution (email, phone, user_id, hash).
4. SQL snapshot parameterized querying, SQL injection defense, and table validation.
5. Evidence reading size bounding and truncation flags.
6. Activity search temporal filtering.
7. Deletion rules retrieval.
8. Dynamic tool execution dispatching and structured error trapping.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code.agent_tools import AgentTools, ProvenanceLedger, get_tool_schemas


class TestAgentTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset_dir = PROJECT_ROOT / "dataset"
        cls.tools = AgentTools(cls.dataset_dir)

    def setUp(self):
        # Create a fresh ledger for each test to isolate provenance checks
        self.ledger = ProvenanceLedger(case_id="test_case")
        self.tools.ledger = self.ledger

    def test_tool_schemas_specification(self):
        """Verify all 8 tools have valid JSON schemas conforming to function-calling standards."""
        schemas = get_tool_schemas()
        self.assertEqual(len(schemas), 9)
        names = {s["function"]["name"] for s in schemas}
        expected_names = {
            "get_baseline_analysis",
            "resolve_identity",
            "list_evidence_manifest",
            "search_evidence",
            "read_evidence",
            "query_sql_snapshot",
            "search_activity",
            "get_deletion_rules",
            "check_temporal_window",
        }
        self.assertEqual(names, expected_names)

        for s in schemas:
            func = s["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            self.assertEqual(func["parameters"]["type"], "object")

    def test_post_audit_at_evidence_never_returned(self):
        """Hard Requirement 1: Evidence captured after audit_at is strictly withheld."""
        # 1. list_evidence_manifest: cutoff at 2026-08-01T00:00:00Z
        cutoff = "2026-08-01T00:00:00Z"
        manifest_items = self.tools.list_evidence_manifest(audit_at=cutoff)
        self.assertGreater(len(manifest_items), 0)
        for item in manifest_items:
            self.assertLessEqual(item["captured_at"], cutoff)

        # 2. read_evidence on a post-audit file (evidence_04 was captured on 2026-09-26)
        res = self.tools.read_evidence("evidence_04", audit_at=cutoff)
        self.assertIn("error", res)
        self.assertTrue(res.get("cutoff_enforced"))
        self.assertNotIn("content", res)

        # 3. query_sql_snapshot on a September SQL dump with an August cutoff
        # Find a September SQL file
        sep_sql_fid = None
        for fid, info in self.tools.manifest.items():
            if info["file_path"].endswith(".sql") and info["captured_at"] > cutoff:
                sep_sql_fid = fid
                break
        self.assertIsNotNone(sep_sql_fid)

        sql_res = self.tools.query_sql_snapshot(
            file_id=sep_sql_fid,
            table="customer_profiles_primary",
            where_column="user_id",
            where_value="user_01",
            audit_at=cutoff,
        )
        self.assertIn("error", sql_res)
        self.assertTrue(sql_res.get("cutoff_enforced"))
        self.assertNotIn("rows", sql_res)

        # 4. search_evidence with an August cutoff
        search_res = self.tools.search_evidence("account_", audit_at=cutoff, max_results=10)
        for item in search_res:
            self.assertLessEqual(item["captured_at"], cutoff)

        # 5. search_activity with an August cutoff
        act_res = self.tools.search_activity("user_05", audit_at=cutoff)
        for act in act_res["system_activity_matches"]:
            self.assertLessEqual(act["event_time"], cutoff)
        for aud in act_res["user_audit_matches"]:
            self.assertLessEqual(aud["event_time"], cutoff)

    def test_ledger_entries_match_tool_output(self):
        """Hard Requirement 2: Every returned file_id, activity_id, audit_id, and resource_id is in ProvenanceLedger."""
        self.assertEqual(len(self.ledger.file_ids), 0)
        self.assertEqual(len(self.ledger.resource_ids), 0)

        # 1. resolve_identity records user_id
        ident_res = self.tools.resolve_identity("leila.haddad@yahoo.com")
        self.assertTrue(ident_res["found"])
        self.assertIn("user_05", self.ledger.resource_ids)

        # 2. read_evidence records file_id and any discovered resource IDs
        read_res = self.tools.read_evidence("evidence_03")
        self.assertIn("evidence_03", self.ledger.file_ids)
        for rid in read_res.get("discovered_resource_ids", []):
            self.assertIn(rid, self.ledger.resource_ids)

        # 3. search_activity records activity_id and resource_id
        act_res = self.tools.search_activity("account_005")
        for act in act_res["system_activity_matches"]:
            self.assertIn(act["activity_id"], self.ledger.activity_ids)
            if act["resource_id"]:
                self.assertIn(act["resource_id"], self.ledger.resource_ids)

        # 4. check_temporal_window records file_id
        self.tools.check_temporal_window("evidence_01", "2026-09-01T00:00:00Z", "2026-09-30T00:00:00Z")
        self.assertIn("evidence_01", self.ledger.file_ids)

        # Summary check
        summary = self.ledger.summary()
        self.assertIn("evidence_03", summary["file_ids"])
        self.assertIn("evidence_01", summary["file_ids"])
        self.assertIn("user_05", summary["resource_ids"])
        self.assertGreater(summary["total_access_events"], 0)

    def test_resolve_identity_multimodal_keys(self):
        """Test identity resolution via email, user_id, phone, and hash."""
        # By current email
        p1 = self.tools.resolve_identity("leila.haddad@yahoo.com")
        self.assertTrue(p1["found"])
        self.assertEqual(p1["user_id"], "user_05")

        # By user_id
        p2 = self.tools.resolve_identity("user_05")
        self.assertTrue(p2["found"])
        self.assertEqual(p2["current_email"], "leila.haddad@yahoo.com")

        # By phone
        phone = p1["current_phone"]
        if phone:
            p3 = self.tools.resolve_identity(phone)
            self.assertTrue(p3["found"])
            self.assertEqual(p3["user_id"], "user_05")

        # Unknown identity
        p_unknown = self.tools.resolve_identity("nonexistent_user_999999@domain.org")
        self.assertFalse(p_unknown["found"])

        # Invalid empty string
        p_invalid = self.tools.resolve_identity("")
        self.assertIn("error", p_invalid)

    def test_query_sql_snapshot_parameterized_and_safety(self):
        """Test SQL snapshot query execution, row retrieval, and injection defense."""
        # Find customer_accounts_failover_replica_20260902.sql
        target_fid = None
        for fid, info in self.tools.manifest.items():
            if info["file_path"].endswith("customer_accounts_failover_replica_20260902.sql"):
                target_fid = fid
                break
        self.assertIsNotNone(target_fid)

        # Valid query
        res = self.tools.query_sql_snapshot(
            file_id=target_fid,
            table="customer_profiles_failover_replica",
            where_column="user_id",
            where_value="user_05",
        )
        self.assertNotIn("error", res)
        self.assertEqual(res["row_count"], 1)
        self.assertEqual(res["rows"][0]["resource_id"], "account_005")

        # SQL Injection attempt in table name rejected
        inj_res = self.tools.query_sql_snapshot(
            file_id=target_fid,
            table="customer_profiles_failover_replica; DROP TABLE users;--",
            where_column="user_id",
            where_value="user_05",
        )
        self.assertIn("error", inj_res)

        # Nonexistent table returns structured error
        bad_table = self.tools.query_sql_snapshot(
            file_id=target_fid,
            table="nonexistent_table_xyz",
            where_column="user_id",
            where_value="user_05",
        )
        self.assertIn("error", bad_table)
        self.assertIn("available_tables", bad_table)

    def test_read_evidence_bounded_and_locators(self):
        """Test bounded character limits and locator support in read_evidence."""
        res = self.tools.read_evidence("evidence_03", max_chars=100)
        self.assertNotIn("error", res)
        self.assertEqual(len(res["content"]), 100)
        self.assertTrue(res["truncated"])

        # Line locator
        loc_res = self.tools.read_evidence("evidence_03", locator="line:1-5")
        self.assertNotIn("error", loc_res)
        lines = loc_res["content"].splitlines()
        self.assertLessEqual(len(lines), 5)

    def test_get_deletion_rules(self):
        """Test retrieval and filtering of deletion_rules.csv."""
        # All 15 rules
        all_rules = self.tools.get_deletion_rules()
        self.assertEqual(len(all_rules), 15)

        # Specific category
        up_rules = self.tools.get_deletion_rules("USER_PROFILE")
        self.assertEqual(len(up_rules), 1)
        self.assertEqual(up_rules[0]["required_action"], "DELETE")

        tomb_rules = self.tools.get_deletion_rules("ACCOUNT_TOMBSTONE")
        self.assertEqual(len(tomb_rules), 1)
        self.assertEqual(tomb_rules[0]["required_action"], "REDACT")

    def test_check_temporal_window(self):
        """Test check_temporal_window accurately diagnoses in_window, pre_request, and post_audit."""
        # evidence_04 captured on 2026-09-26T11:00:00Z
        # 1. Post-audit
        w1 = self.tools.check_temporal_window(
            "evidence_04",
            requested_at="2026-09-01T00:00:00Z",
            audit_at="2026-09-15T00:00:00Z",
        )
        self.assertFalse(w1["in_window"])
        self.assertEqual(w1["temporal_status"], "post_audit")

        # 2. In-window
        w2 = self.tools.check_temporal_window(
            "evidence_04",
            requested_at="2026-09-20T00:00:00Z",
            audit_at="2026-09-30T00:00:00Z",
        )
        self.assertTrue(w2["in_window"])
        self.assertEqual(w2["temporal_status"], "in_window")

        # 3. Pre-request
        w3 = self.tools.check_temporal_window(
            "evidence_04",
            requested_at="2026-10-01T00:00:00Z",
            audit_at="2026-10-15T00:00:00Z",
        )
        self.assertFalse(w3["in_window"])
        self.assertEqual(w3["temporal_status"], "pre_request")

    def test_execute_tool_dispatcher(self):
        """Test dynamic tool dispatcher and unknown tool error trapping."""
        # Valid call via execute_tool
        res = self.tools.execute_tool("resolve_identity", {"identifier": "user_05"})
        self.assertTrue(res["found"])

        # Unknown tool name returns structured error
        err = self.tools.execute_tool("unknown_tool_xyz", {})
        self.assertIn("error", err)
        self.assertIn("available_tools", err)


if __name__ == "__main__":
    unittest.main()
