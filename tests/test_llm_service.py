import unittest
from unittest.mock import patch

from services.llm_service import analyze_code_rules as analyze_code
from services.problem_service import get_problem


class DiagnosisTests(unittest.TestCase):
    def test_original_boundary_rule_still_works_and_is_labeled_mock(self):
        result = analyze_code("for i in range(len(nums)):\n    print(nums[i + 1])")
        self.assertEqual(result["error_type"], "可能存在边界条件错误")
        self.assertEqual(result["knowledge"], "列表索引")
        self.assertEqual(len(result["hints"]), 3)
        self.assertIs(result.get("is_mock"), True)

    def test_selected_problem_context_is_used_without_claiming_correctness(self):
        result = analyze_code("class Solution:\n    pass", get_problem(1))
        self.assertIn("两数之和", result["analysis"])
        self.assertIn("数组", result["analysis"])
        self.assertIn("目标值", result["analysis"])
        self.assertIn("模拟", result["analysis"])
        self.assertIn("不代表", result["analysis"])
        self.assertEqual(len(result["hints"]), 3)

    def test_syntax_errors_are_detected_but_student_code_is_never_executed(self):
        result = analyze_code("def broken(:\n    pass", get_problem(20))
        self.assertIn("语法", result["error_type"])
        self.assertIn("1", result["analysis"])
        with patch("builtins.print", side_effect=AssertionError("student code was executed")):
            result = analyze_code("print('this is student code')", get_problem(1))
        self.assertEqual(result["error_type"], "未匹配到已知问题")
        self.assertEqual(analyze_code("")["error_type"], "未提供代码")

    def test_normalization_retains_legacy_defaults_and_mock_status(self):
        from services.llm_service import normalize_diagnosis
        self.assertIsNone(normalize_diagnosis(None))
        self.assertIsNone(normalize_diagnosis({}))
        self.assertIsNone(normalize_diagnosis({"hints": [None, "  "]}))
        result = normalize_diagnosis({"analysis": " 有效说明 ", "hints": [None, " 提示 ", ""]})
        self.assertEqual(result["analysis"], "有效说明")
        self.assertEqual(result["error_type"], "未知")
        self.assertEqual(result["knowledge"], "未知")
        self.assertEqual(result["hints"], ["提示"])
        self.assertIs(result["is_mock"], True)
        self.assertEqual(normalize_diagnosis({"knowledge": "数组"})["hints"], ["暂未提供提示，请结合问题分析检查代码。"])


if __name__ == "__main__":
    unittest.main()
