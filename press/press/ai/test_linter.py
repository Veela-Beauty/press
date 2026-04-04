"""Tests for AI response linter — Category 1 (hard block) and Category 2 (approval required).

Pure Python — no Frappe DB dependency. Runs standalone with unittest.
"""

import unittest


class TestCategory1HardBlock(unittest.TestCase):
    """Category 1: Dangerous patterns removed from AI response. Escalation triggered."""

    # --- Raw SQL destructive statements ---

    def test_blocks_delete_sql(self):
        from press.press.ai.linter import lint_response

        text = 'Try this:\n```python\nfrappe.db.sql("DELETE FROM tabPayment Entry WHERE status=\'Cancelled\'")\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertEqual(result.violations[0].category, 1)
        self.assertIn("DELETE", result.violations[0].pattern)
        self.assertNotIn("DELETE FROM", result.sanitized_text)

    def test_blocks_drop_table(self):
        from press.press.ai.linter import lint_response

        text = 'Run:\n```sql\nDROP TABLE tabCustom Field;\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertEqual(result.violations[0].category, 1)
        self.assertNotIn("DROP TABLE", result.sanitized_text)

    def test_blocks_truncate_table(self):
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.db.sql("TRUNCATE TABLE tabError Log")\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertNotIn("TRUNCATE", result.sanitized_text)

    def test_blocks_delete_case_insensitive(self):
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.db.sql("delete from tabSite")\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    def test_allows_select_sql(self):
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.db.sql("SELECT name FROM tabSite WHERE status=\'Active\'")\n```'
        result = lint_response(text)
        self.assertFalse(result.has_violations)
        self.assertIn("SELECT", result.sanitized_text)

    # --- Destructive shell commands ---

    def test_blocks_rm_rf(self):
        from press.press.ai.linter import lint_response

        text = "Clean up:\n```bash\nrm -rf /home/frappe/frappe-bench/apps/myapp\n```"
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertEqual(result.violations[0].category, 1)
        self.assertNotIn("rm -rf", result.sanitized_text)

    def test_blocks_shutil_rmtree(self):
        from press.press.ai.linter import lint_response

        text = '```python\nimport shutil\nshutil.rmtree("/home/frappe/frappe-bench")\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    # --- Bench destructive commands ---

    def test_blocks_bench_destroy(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nbench destroy\n```"
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertNotIn("bench destroy", result.sanitized_text)

    def test_blocks_bench_uninstall_app(self):
        from press.press.ai.linter import lint_response

        text = "Run:\n```bash\nbench uninstall-app myapp\n```"
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    def test_blocks_bench_drop_site(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nbench drop-site mysite.localhost\n```"
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    # --- Credential modification ---

    def test_blocks_site_config_db_password(self):
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.conf.db_password = "new_password"\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    def test_blocks_site_config_json_write(self):
        from press.press.ai.linter import lint_response

        text = """```python
import json
with open('sites/mysite/site_config.json', 'w') as f:
    json.dump(config, f)
```"""
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    # --- Sanitization preserves safe content ---

    def test_sanitized_keeps_safe_parts(self):
        from press.press.ai.linter import lint_response

        text = "Step 1: Query the data\n```python\nfrappe.db.sql('SELECT * FROM tabSite')\n```\nStep 2: Delete old ones\n```python\nfrappe.db.sql('DELETE FROM tabSite WHERE status=\"Archived\"')\n```\nStep 3: Done"
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertIn("Step 1", result.sanitized_text)
        self.assertIn("SELECT", result.sanitized_text)
        self.assertIn("Step 3", result.sanitized_text)

    # --- Multiple violations in one response ---

    def test_detects_multiple_violations(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nrm -rf /tmp/old\n```\n\n```python\nfrappe.db.sql('DROP TABLE tabOld')\n```"
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        self.assertGreaterEqual(len(result.violations), 2)

    # --- Edge cases: safe patterns that look dangerous ---

    def test_allows_frappe_delete_doc_single(self):
        """frappe.delete_doc() for a single doc is Category 3, not 1."""
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.delete_doc("ToDo", "TODO-001")\n```'
        result = lint_response(text)
        # Single delete_doc is NOT Category 1
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertEqual(len(cat1), 0)

    def test_allows_delete_in_english_text(self):
        """The word 'delete' in explanation text should not trigger."""
        from press.press.ai.linter import lint_response

        text = "You can delete the record using frappe.delete_doc(). This is safe for single documents."
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertEqual(len(cat1), 0)


class TestCategory2Approval(unittest.TestCase):
    """Category 2: Flagged in response, requires TL + Admin approval."""

    def test_flags_bulk_delete_doc_loop(self):
        from press.press.ai.linter import lint_response

        text = """```python
for doc in frappe.get_all("Payment Entry", {"status": "Cancelled"}, limit=200):
    frappe.delete_doc("Payment Entry", doc.name)
```"""
        result = lint_response(text)
        cat2 = [v for v in result.violations if v.category == 2]
        self.assertGreater(len(cat2), 0)
        # Category 2 is NOT removed — only flagged
        self.assertIn("delete_doc", result.sanitized_text)

    def test_flags_bench_migrate_staging(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nbench --site staging.example.com migrate\n```"
        result = lint_response(text)
        cat2 = [v for v in result.violations if v.category == 2]
        self.assertGreater(len(cat2), 0)

    def test_flags_permission_changes(self):
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.permissions.add_permission("Sales Invoice", "System Manager", 0)\n```'
        result = lint_response(text)
        cat2 = [v for v in result.violations if v.category == 2]
        self.assertGreater(len(cat2), 0)


class TestCategory3Warning(unittest.TestCase):
    """Category 3: Warning shown inline, user confirms."""

    def test_warns_bench_clear_cache(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nbench clear-cache\n```"
        result = lint_response(text)
        cat3 = [v for v in result.violations if v.category == 3]
        self.assertGreater(len(cat3), 0)
        # Category 3 is NOT removed
        self.assertIn("bench clear-cache", result.sanitized_text)

    def test_warns_single_delete_doc(self):
        from press.press.ai.linter import lint_response

        text = '```python\nfrappe.delete_doc("ToDo", "TODO-001")\n```'
        result = lint_response(text)
        cat3 = [v for v in result.violations if v.category == 3]
        self.assertGreater(len(cat3), 0)

    def test_warns_git_reset(self):
        from press.press.ai.linter import lint_response

        text = "```bash\ngit reset --hard HEAD~1\n```"
        result = lint_response(text)
        cat3 = [v for v in result.violations if v.category == 3]
        self.assertGreater(len(cat3), 0)


class TestLintResult(unittest.TestCase):
    """Test the LintResult data structure."""

    def test_clean_response_has_no_violations(self):
        from press.press.ai.linter import lint_response

        text = "Here's how to add a field:\n```python\nfrappe.get_doc('DocType', 'Site').append('fields', {...})\n```"
        result = lint_response(text)
        self.assertFalse(result.has_violations)
        self.assertEqual(len(result.violations), 0)
        self.assertEqual(result.sanitized_text, text)

    def test_result_has_max_category(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nrm -rf /tmp\n```\n```bash\nbench clear-cache\n```"
        result = lint_response(text)
        self.assertEqual(result.max_category, 1)

    def test_empty_input(self):
        from press.press.ai.linter import lint_response

        result = lint_response("")
        self.assertFalse(result.has_violations)
        self.assertEqual(result.sanitized_text, "")


class TestBypassPrevention(unittest.TestCase):
    """Tests for known bypass vectors identified in code review."""

    # --- HIGH: Prose/inline code bypass ---

    def test_blocks_rm_rf_in_prose(self):
        """Dangerous command in plain text (no code block) must still be caught."""
        from press.press.ai.linter import lint_response

        text = "Run this command: rm -rf /home/frappe to clean up."
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    def test_blocks_delete_sql_in_inline_code(self):
        """Dangerous SQL in single-backtick inline code must be caught."""
        from press.press.ai.linter import lint_response

        text = 'Use `frappe.db.sql("DELETE FROM tabSite")` to remove records.'
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    def test_blocks_bench_destroy_in_prose(self):
        from press.press.ai.linter import lint_response

        text = "You can clean up by running bench destroy in the terminal."
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    def test_blocks_drop_table_in_inline_code(self):
        from press.press.ai.linter import lint_response

        text = "Execute `DROP TABLE tabOldDoc;` to remove the table."
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    # --- HIGH: Backtick characters inside code blocks ---

    def test_blocks_delete_with_backtick_quoted_table(self):
        """MariaDB backtick-quoted table names must not break pattern matching."""
        from press.press.ai.linter import lint_response

        text = '```sql\nDELETE FROM `tabSite` WHERE status="Archived";\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    def test_blocks_drop_table_with_backtick_quotes(self):
        from press.press.ai.linter import lint_response

        text = "```sql\nDROP TABLE `tabCustom Field`;\n```"
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    # --- HIGH: Trailing space after fence language tag ---

    def test_blocks_delete_with_trailing_space_in_fence(self):
        """Trailing space after language tag must not bypass detection."""
        from press.press.ai.linter import lint_response

        text = '```python \nfrappe.db.sql("DELETE FROM tabSite")\n```'
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    def test_blocks_rm_rf_with_crlf_fence(self):
        """Windows CRLF line endings must not bypass detection."""
        from press.press.ai.linter import lint_response

        text = "```bash\r\nrm -rf /home/frappe\r\n```"
        result = lint_response(text)
        self.assertTrue(result.has_violations)

    # --- MEDIUM: rm variants ---

    def test_blocks_rm_r_f_separate_flags(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nrm -r -f /tmp/old\n```"
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    def test_blocks_rm_recursive_force(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nrm --recursive --force /tmp/old\n```"
        result = lint_response(text)
        cat1 = [v for v in result.violations if v.category == 1]
        self.assertGreater(len(cat1), 0)

    # --- MEDIUM: max_category renamed ---

    def test_most_severe_category(self):
        from press.press.ai.linter import lint_response

        text = "```bash\nrm -rf /tmp\n```\n```bash\nbench clear-cache\n```"
        result = lint_response(text)
        self.assertEqual(result.most_severe_category, 1)

    def test_most_severe_category_empty(self):
        from press.press.ai.linter import lint_response

        result = lint_response("safe text")
        self.assertEqual(result.most_severe_category, 0)


if __name__ == "__main__":
    unittest.main()
