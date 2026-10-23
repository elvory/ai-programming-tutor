import unittest

from services.practice_service import reveal_next_hint, save_draft, select_problem, set_diagnosis


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


if __name__ == "__main__":
    unittest.main()
