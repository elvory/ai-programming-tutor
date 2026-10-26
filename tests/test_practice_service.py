import unittest

from services.practice_service import (
    begin_diagnosis, diagnosis_request_is_current, reveal_next_hint,
    save_draft, select_problem, set_diagnosis,
)


class PracticeStateTests(unittest.TestCase):
    def test_switching_problem_restores_its_draft_and_clears_diagnosis(self):
        state = {}
        first = {"id": 1, "python_template": "first template"}
        second = {"id": 20, "python_template": "second template"}
        self.assertEqual(select_problem(state, first), "first template")
        save_draft(state, 1, "student edited first")
        set_diagnosis(state, 1, "student edited first", {"hints": ["one", "two", "three"]}, "record-1")
        self.assertEqual(select_problem(state, second), "second template")
        self.assertIsNone(state["diagnosis"])
        save_draft(state, 20, "student edited second")
        self.assertEqual(select_problem(state, first), "student edited first")
        self.assertEqual(state["drafts"]["20"], "student edited second")

    def test_hints_and_repeat_selection_keep_the_edited_code(self):
        state = {}
        problem = {"id": 1, "python_template": "template"}
        select_problem(state, problem)
        save_draft(state, 1, "edited")
        set_diagnosis(state, 1, "edited", {"hints": ["one", "two", "three"]})
        self.assertEqual(reveal_next_hint(state), 2)
        self.assertEqual(reveal_next_hint(state), 3)
        self.assertEqual(reveal_next_hint(state), 3)
        self.assertEqual(select_problem(state, problem), "edited")
        self.assertEqual(state["hint_level"], 3)
        self.assertIsNotNone(state["diagnosis"])

    def test_a_new_diagnosis_resets_only_hint_progress(self):
        state = {}
        problem = {"id": 1, "python_template": "template"}
        select_problem(state, problem)
        save_draft(state, 1, "new code")
        set_diagnosis(state, 1, "old code", {"hints": ["one", "two", "three"]})
        reveal_next_hint(state)
        set_diagnosis(state, 1, "new code", {"hints": ["new hint"]}, "new-record")
        self.assertEqual(state["hint_level"], 1)
        self.assertEqual(state["drafts"]["1"], "new code")
        self.assertEqual(state["diagnosed_code"], "new code")
        self.assertEqual(state["diagnosis_record_id"], "new-record")

    def test_editing_code_clears_previous_diagnosis_and_hint_progress(self):
        state = {}
        problem = {"id": 1, "python_template": "template"}
        select_problem(state, problem)
        save_draft(state, 1, "old code")
        set_diagnosis(state, 1, "old code", {"hints": ["one", "two", "three"]}, "old-record")
        reveal_next_hint(state)
        save_draft(state, 1, "new code")
        self.assertIsNone(state["diagnosis"])
        self.assertIsNone(state["diagnosis_record_id"])
        self.assertEqual(state["hint_level"], 1)
        self.assertEqual(state["drafts"]["1"], "new code")

    def test_begin_diagnosis_replaces_old_result_and_success_clears_pending(self):
        state = {}
        problem = {"id": 1, "python_template": "code"}
        select_problem(state, problem)
        set_diagnosis(state, 1, "code", {"hints": ["old"]}, "old-record")
        request = begin_diagnosis(state, 1, "code")
        self.assertTrue(request["request_id"])
        self.assertEqual(request["problem_id"], 1)
        self.assertEqual(request["code"], "code")
        self.assertIsNone(state["diagnosis"])
        self.assertIsNone(state["diagnosis_record_id"])
        self.assertEqual(state["hint_level"], 1)
        self.assertTrue(diagnosis_request_is_current(state, request))
        set_diagnosis(state, 1, "code", {"hints": ["new"]}, "new-record")
        self.assertIsNone(state["pending_diagnosis"])
        self.assertFalse(diagnosis_request_is_current(state, request))

    def test_editing_during_request_invalidates_it_even_if_code_is_restored(self):
        state = {}
        select_problem(state, {"id": 1, "python_template": "code A"})
        request = begin_diagnosis(state, 1, "code A")
        save_draft(state, 1, "code B")
        self.assertIsNone(state["pending_diagnosis"])
        save_draft(state, 1, "code A")
        self.assertFalse(diagnosis_request_is_current(state, request))

    def test_switching_away_and_back_does_not_revive_old_request(self):
        state = {}
        first = {"id": 1, "python_template": "first code"}
        second = {"id": 20, "python_template": "second code"}
        select_problem(state, first)
        request = begin_diagnosis(state, 1, "first code")
        select_problem(state, second)
        self.assertIsNone(state["pending_diagnosis"])
        self.assertFalse(diagnosis_request_is_current(state, request))
        select_problem(state, first)
        self.assertFalse(diagnosis_request_is_current(state, request))

    def test_only_latest_of_rapid_requests_can_be_applied(self):
        state = {}
        select_problem(state, {"id": 1, "python_template": "code"})
        first = begin_diagnosis(state, 1, "code")
        latest = begin_diagnosis(state, 1, "code")
        self.assertNotEqual(first["request_id"], latest["request_id"])
        self.assertFalse(diagnosis_request_is_current(state, first))
        self.assertTrue(diagnosis_request_is_current(state, latest))

    def test_widget_changes_reject_request_before_callbacks_save_the_draft(self):
        state = {}
        select_problem(state, {"id": 1, "python_template": "code"})
        request = begin_diagnosis(state, 1, "code")
        self.assertTrue(diagnosis_request_is_current(state, request))
        state["problem_picker"] = 20
        self.assertFalse(diagnosis_request_is_current(state, request))
        state["problem_picker"] = 1
        state["code_editor_1"] = "edited"
        self.assertFalse(diagnosis_request_is_current(state, request))

    def test_saving_an_unrelated_or_unchanged_draft_preserves_current_result(self):
        state = {}
        select_problem(state, {"id": 1, "python_template": "code"})
        request = begin_diagnosis(state, 1, "code")
        save_draft(state, 20, "another problem")
        save_draft(state, 1, "code")
        self.assertTrue(diagnosis_request_is_current(state, request))
        set_diagnosis(state, 1, "code", {"hints": ["one", "two", "three"]})
        reveal_next_hint(state)
        save_draft(state, 20, "changed another problem")
        save_draft(state, 1, "code")
        self.assertEqual(state["hint_level"], 2)
        self.assertIsNotNone(state["diagnosis"])


if __name__ == "__main__":
    unittest.main()
