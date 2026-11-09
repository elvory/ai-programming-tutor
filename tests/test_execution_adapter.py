"""Compare untrusted candidate values without executing submissions on the host."""
import unittest
import json

from backend.execution.adapters.python_adapter import RESULT_PREFIX, get_adapter, parse_result


class TwoSumAdapterTests(unittest.TestCase):
    def test_public_example_accepts_either_index_order_without_official_acceptance(self):
        adapter = get_adapter(1)
        for candidate in ([1, 2], [2, 1]):
            result = adapter.judge(candidate)
            self.assertTrue(result["all_passed"])
            self.assertEqual(result["scope"], "public_examples")
            self.assertEqual(result["passed"], 1)
            self.assertFalse(result["official_accepted"])

    def test_wrong_values_types_and_duplicate_indices_are_not_accepted(self):
        adapter = get_adapter(1)
        for candidate in (None, [], [0, 0], [0, 2], [-1, 2], [1, 3],
                          [True, 2], [1.0, 2], "[1, 2]", {"passed": True}):
            with self.subTest(candidate=candidate):
                self.assertFalse(adapter.judge(candidate)["all_passed"])

    def test_input_mutation_cannot_change_the_external_comparison(self):
        adapter = get_adapter(1)
        inputs = adapter.case_input
        inputs["nums"][:] = [0, 7]
        self.assertEqual(adapter.case_input, {"nums": [4, 1, 6], "target": 7})
        self.assertFalse(adapter.judge([0, 1])["all_passed"])

    def test_unexecuted_example_cannot_pass(self):
        result = get_adapter(1).not_run()
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["executed"], 0)
        self.assertEqual(result["cases"][0]["status"], "not_run")

    def test_other_problem_or_reused_id_with_wrong_slug_is_unsupported(self):
        for problem_id, slug in ((217, "contains-duplicate"), (1, "other")):
            with self.assertRaises(ValueError):
                get_adapter(problem_id, slug=slug)

    def test_untrusted_protocol_is_separate_from_visible_stdout(self):
        result = parse_result('hello\n' + RESULT_PREFIX + '{"kind":"return","value":[2,1]}\n', "", 0)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["candidate"], [2, 1])
        self.assertNotIn(RESULT_PREFIX, result["stdout"])
        self.assertIn("hello", result["stdout"])

    def test_missing_duplicate_malformed_and_abnormal_exit_never_succeed(self):
        valid = RESULT_PREFIX + '{"kind":"return","value":[1,2]}\n'
        for stdout, exit_code in (("", 0), (valid * 2, 0),
                                  (RESULT_PREFIX + '{bad}', 0), (valid, 1),
                                  (RESULT_PREFIX + '{"kind":"return","value":NaN}', 0)):
            self.assertEqual(parse_result(stdout, "", exit_code)["status"], "RUNTIME_ERROR")

    def test_python_syntax_and_runtime_errors_remain_distinct(self):
        for kind, status in (("compile_error", "COMPILE_ERROR"), ("runtime_error", "RUNTIME_ERROR")):
            result = parse_result(RESULT_PREFIX + '{"kind":"' + kind + '","message":"test"}\n', "", 1)
            self.assertEqual(result["status"], status)
            self.assertIn("test", result["stderr"])

    def test_deep_or_nonfinite_candidate_does_not_reach_response_serialization(self):
        candidate = 1
        for _ in range(40):
            candidate = [candidate]
        for raw in (json.dumps({"kind": "return", "value": candidate}),
                    '{"kind":"return","value":1e999}',
                    '{"kind":"return","kind":"return","value":[1,2]}'):
            self.assertEqual(parse_result(RESULT_PREFIX + raw, "", 0)["status"], "RUNTIME_ERROR")
