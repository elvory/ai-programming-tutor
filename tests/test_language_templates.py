"""Public catalog/language behavior; fixtures never write the formal catalog."""
import json
import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.language_service import LANGUAGES, validate_language
from services.problem_service import CatalogError, get_learning_route, get_problem, load_problems, search_problems

ROOT = Path(__file__).resolve().parents[1]


class LanguageTemplateTests(unittest.TestCase):
    def test_language_ids_are_explicit_and_python_is_the_legacy_default(self):
        self.assertEqual(validate_language(), "python")
        self.assertEqual(set(LANGUAGES), {"python", "java", "c", "cpp"})
        for language in ("python", "java", "c", "cpp"):
            self.assertEqual(validate_language(language), language)
        for language in (None, "", "javascript", "Python", "c++", {}, 1):
            with self.subTest(language=language), self.assertRaisesRegex(ValueError, "不支持"):
                validate_language(language)

    def test_two_sum_exposes_distinct_language_interfaces_and_original_python(self):
        original = json.loads((ROOT / "data/problem_catalog.json").read_text(encoding="utf-8"))[0]
        problem = get_problem(1)
        self.assertEqual(set(problem["templates"]), {"python", "java", "c", "cpp"})
        self.assertEqual(problem["templates"]["python"], original["python_template"])
        self.assertIn("public int[] twoSum(int[] nums, int target)", problem["templates"]["java"])
        self.assertIn("int* twoSum(int* nums, int numsSize, int target, int* returnSize)", problem["templates"]["c"])
        self.assertIn("vector<int> twoSum(vector<int>& nums, int target)", problem["templates"]["cpp"])

    def test_all_32_exercises_have_four_templates_without_catalog_changes(self):
        originals = json.loads((ROOT / "data/problem_catalog.json").read_text(encoding="utf-8"))
        problems = load_problems()
        self.assertEqual(len(problems), 32)
        for original, problem in zip(originals, problems):
            with self.subTest(problem=original["id"]):
                self.assertEqual({key: problem[key] for key in original}, original)
                self.assertEqual(set(problem["templates"]), {"python", "java", "c", "cpp"})
                self.assertEqual(problem["templates"]["python"], original["python_template"])
                self.assertEqual(len(set(problem["templates"].values())), 4)
                ast.parse(problem["templates"]["python"])

    def test_nested_outputs_have_the_correct_c_shape_and_length_parameters(self):
        expected = {
            49: "char*** groupAnagrams(char** strs, int strsSize, int* returnSize, int** returnColumnSizes)",
            739: "int* dailyTemperatures(int* temperatures, int temperaturesSize, int* returnSize)",
            102: "int** levelOrder(struct TreeNode* root, int* returnSize, int** returnColumnSizes)",
            78: "int** subsets(int* nums, int numsSize, int* returnSize, int** returnColumnSizes)",
            46: "int** permute(int* nums, int numsSize, int* returnSize, int** returnColumnSizes)",
            56: "int** merge(int** intervals, int intervalsSize, int* intervalsColSize, int* returnSize, int** returnColumnSizes)",
        }
        for identity, signature in expected.items():
            with self.subTest(problem=identity):
                template = get_problem(identity)["templates"]["c"]
                self.assertIn(signature + " {", template)
                self.assertIn("*returnSize = 0;", template)
                self.assertIn("caller frees", template)
                if identity != 739:
                    self.assertIn("*returnColumnSizes = NULL;", template)

    def test_character_and_integer_grids_are_not_confused(self):
        islands = get_problem(200)["templates"]
        oranges = get_problem(994)["templates"]
        self.assertIn("numIslands(char[][] grid)", islands["java"])
        self.assertIn("numIslands(vector<vector<char>>& grid)", islands["cpp"])
        self.assertIn("numIslands(char** grid, int gridSize, int* gridColSize)", islands["c"])
        self.assertIn("orangesRotting(int[][] grid)", oranges["java"])
        self.assertIn("orangesRotting(vector<vector<int>>& grid)", oranges["cpp"])
        self.assertIn("orangesRotting(int** grid, int gridSize, int* gridColSize)", oranges["c"])

    def test_linked_list_and_tree_interfaces_include_judge_supplied_node_contracts(self):
        expected = {
            206: ("ListNode", "reverseList(ListNode head)", "reverseList(ListNode* head)", "reverseList(struct ListNode* head)"),
            21: ("ListNode", "mergeTwoLists(ListNode list1, ListNode list2)", "mergeTwoLists(ListNode* list1, ListNode* list2)", "mergeTwoLists(struct ListNode* list1, struct ListNode* list2)"),
            141: ("ListNode", "hasCycle(ListNode head)", "hasCycle(ListNode* head)", "hasCycle(struct ListNode* head)"),
            19: ("ListNode", "removeNthFromEnd(ListNode head, int n)", "removeNthFromEnd(ListNode* head, int n)", "removeNthFromEnd(struct ListNode* head, int n)"),
            104: ("TreeNode", "maxDepth(TreeNode root)", "maxDepth(TreeNode* root)", "maxDepth(struct TreeNode* root)"),
            226: ("TreeNode", "invertTree(TreeNode root)", "invertTree(TreeNode* root)", "invertTree(struct TreeNode* root)"),
            102: ("TreeNode", "levelOrder(TreeNode root)", "levelOrder(TreeNode* root)", "levelOrder(struct TreeNode* root, int* returnSize, int** returnColumnSizes)"),
            98: ("TreeNode", "isValidBST(TreeNode root)", "isValidBST(TreeNode* root)", "isValidBST(struct TreeNode* root)"),
        }
        for identity, (node, java, cpp, c) in expected.items():
            with self.subTest(problem=identity):
                templates = get_problem(identity)["templates"]
                for language, signature in (("java", java), ("cpp", cpp), ("c", c)):
                    self.assertIn(signature + " {", templates[language])
                    self.assertIn("LeetCode supplies this type", templates[language])
                self.assertIn("class " + node, templates["java"])
                self.assertIn("struct " + node, templates["c"])
                self.assertIn("struct " + node, templates["cpp"])

    def test_search_detail_and_route_return_independent_multilingual_copies(self):
        detail = get_problem(1)
        searched = search_problems("1")[0]
        routed = get_learning_route()[0]["problems"][0]
        self.assertEqual(detail["templates"], searched["templates"])
        self.assertEqual(detail["templates"], routed["templates"])
        detail["templates"]["java"] = "edited by caller"
        self.assertIn("twoSum", get_problem(1)["templates"]["java"])

    def test_unknown_exercises_never_inherit_a_signature_by_reused_id(self):
        catalog = json.loads((ROOT / "data/problem_catalog.json").read_text(encoding="utf-8"))[:1]
        catalog[0]["slug"] = "a-different-exercise"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with patch.dict(os.environ, {"AI_TUTOR_CATALOG_PATH": str(path)}):
                self.assertEqual(get_problem(1)["templates"], {"python": catalog[0]["python_template"]})

    def test_template_overlay_validation_is_read_only_and_path_override_refreshes(self):
        originals = json.loads((ROOT / "data/problem_templates.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "templates.json"
            bad = {"1": {**originals["1"], "java": ""}}
            path.write_text(json.dumps(bad), encoding="utf-8")
            before = path.read_bytes()
            with patch.dict(os.environ, {"AI_TUTOR_TEMPLATES_PATH": str(path)}):
                with self.assertRaisesRegex(CatalogError, "模板不完整"):
                    get_problem(1)
                self.assertEqual(path.read_bytes(), before)
            alternate = Path(directory) / "alternate.json"
            alternate.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"AI_TUTOR_TEMPLATES_PATH": str(alternate)}):
                self.assertEqual(set(get_problem(1)["templates"]), {"python"})
        self.assertEqual(set(get_problem(1)["templates"]), {"python", "java", "c", "cpp"})


if __name__ == "__main__":
    unittest.main()
