"""Compatibility export is explicit, lossless and never writes project data."""
import copy
import json
import unittest

from utils.draft_export import build_draft_export


class DraftExportTests(unittest.TestCase):
    def test_export_keeps_empty_unicode_and_latest_editor_buffer_without_mutation(self):
        state = {"drafts": {"1": "old", "20": "", "198": "# 中文草稿\npass"},
                 "code_editor_1": "canonical",
                 "code_editor_1__ace": {"type": "blur", "text": "# latest\nprint(1)"}}
        original = copy.deepcopy(state)
        exported = json.loads(build_draft_export(state))
        self.assertEqual(exported["schema_version"], 1)
        self.assertEqual(exported["drafts"], {"1": "# latest\nprint(1)", "20": "", "198": "# 中文草稿\npass"})
        self.assertIn("exported_at", exported)
        self.assertEqual(state, original)

    def test_unrelated_session_state_is_never_exported(self):
        state = {"drafts": {"1": "pass"}, "diagnosis": {"analysis": "private"},
                 "DEEPSEEK_API_KEY": "synthetic-never-real", "code_editor_1__ace": {"type": "selection", "text": "fragment"}}
        exported = build_draft_export(state)
        self.assertNotIn("synthetic-never-real", exported)
        self.assertNotIn("private", exported)
        self.assertEqual(json.loads(exported)["drafts"], {"1": "pass"})


if __name__ == "__main__":
    unittest.main()
