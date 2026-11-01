"""Unit tests for the Ace payload filtering used by the practice page."""

import unittest

from utils.editor import _event_text, widget_key


class EditorPayloadTests(unittest.TestCase):
    def test_default_and_selection_payloads_never_replace_the_draft(self):
        self.assertIsNone(_event_text(None))
        self.assertIsNone(_event_text({"type": "", "text": ""}))
        self.assertIsNone(_event_text({"type": "selection", "text": "selected fragment"}))
        self.assertIsNone(_event_text({"type": "blur", "text": None}))

    def test_change_blur_and_submit_keep_the_full_editor_text(self):
        self.assertEqual(_event_text({"type": "change", "text": "print(1)"}), "print(1)")
        self.assertEqual(_event_text({"type": "blur", "text": ""}), "")
        self.assertEqual(_event_text({"type": "submit", "text": "x"}), "x")

    def test_component_key_is_derived_from_the_canonical_draft_key(self):
        self.assertEqual(widget_key("code_editor_1"), "code_editor_1__ace")


if __name__ == "__main__":
    unittest.main()
