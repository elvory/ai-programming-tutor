"""Completion coverage is computed from isolated events, never diagnosis guesses."""
import unittest

from services.capability_service import build_capability_profile
from services.problem_service import load_problems


def accepted(problem_id, identity, language=None):
    event = {"kind": "accepted", "problem_id": problem_id, "title": "fixture",
             "event_id": identity, "timestamp": "2026-10-25T12:00:00+08:00"}
    if language is not None:
        event["language"] = language
    return event


class CapabilityProfileTests(unittest.TestCase):
    def test_catalog_has_six_exclusive_dimensions_and_no_data_is_not_zero_ability(self):
        result = build_capability_profile([], load_problems(), today="2026-11-02")
        self.assertEqual([r["total"] for r in result["dimensions"]], [4, 4, 4, 8, 4, 8])
        ids = [pid for row in result["dimensions"] for pid in row["problem_ids"]]
        self.assertEqual(len(ids), 32)
        self.assertEqual(len(set(ids)), 32)
        self.assertEqual(result["completed_unique"], 0)
        self.assertEqual(result["sample_status"], "empty")
        self.assertEqual(result["strongest"], [])
        self.assertEqual(result["unclassified_problem_ids"], [])
        self.assertIn("不代表", result["recommendation"])

    def test_same_problem_in_multiple_languages_counts_once_and_legacy_acceptance_counts(self):
        events = [accepted(1, "p", "python"), accepted(1, "j", "java"),
                  accepted(1, "c", "c"), accepted(1, "cpp", "cpp"), accepted(217, "old")]
        result = build_capability_profile(events, load_problems(), today="2026-11-02")
        self.assertEqual(result["completed_unique"], 2)
        self.assertEqual(result["sample_status"], "insufficient")
        self.assertEqual(result["dimensions"][0]["completed_ids"], [1, 217])
        self.assertEqual(result["dimensions"][0]["percentage"], 50.0)
        self.assertEqual(result["strongest"], [])

    def test_submissions_diagnosis_hints_future_and_invalid_events_do_not_imply_pass(self):
        submission = {"kind": "submission", "problem_id": 1, "title": "fixture",
                      "submission_id": "submit", "timestamp": "2026-10-25T12:00:00+08:00",
                      "hints_used": [1, 2, 3], "diagnosis": {"source": "deepseek"}}
        events = [submission, dict(submission, submission_id="second"),
                  accepted(1, "future") | {"timestamp": "2027-01-01T00:00:00+08:00"},
                  {"kind": "accepted", "problem_id": 217}, None]
        result = build_capability_profile(events, load_problems(), today="2026-11-02")
        self.assertEqual(result["completed_unique"], 0)
        self.assertTrue(all(r["percentage"] == 0 for r in result["dimensions"]))

    def test_unknown_stages_and_duplicate_catalog_ids_are_safe_and_do_not_inflate_totals(self):
        problems = [{"id": 1, "stage": 1}, {"id": 1, "stage": 2},
                    {"id": 999, "stage": 99}, {"id": 1000}, None]
        result = build_capability_profile([accepted(999, "unknown"), accepted(1, "known")],
                                          problems, today="2026-11-02")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["completed_unique"], 1)
        self.assertEqual(result["unclassified_problem_ids"], [999, 1000])
        self.assertEqual(result["dimensions"][1]["total"], 0)
        self.assertEqual(result["dimensions"][1]["percentage"], 0)

    def test_summary_uses_coverage_with_ties_and_suggests_an_uncompleted_problem(self):
        events = [accepted(1, "a"), accepted(217, "b"), accepted(125, "c")]
        result = build_capability_profile(events, load_problems(), today="2026-11-02")
        self.assertEqual(result["sample_status"], "available")
        self.assertEqual(result["strongest"], ["数组与哈希表"])
        self.assertIn("栈、队列与二分查找", result["needs_attention"])
        self.assertEqual(result["recommended_problem_id"], 20)
        self.assertEqual(result["dimensions"][0]["sample_status"], "insufficient")


if __name__ == "__main__":
    unittest.main()
