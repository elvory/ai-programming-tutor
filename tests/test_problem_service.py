import ast
import copy
import unittest

from services.problem_service import get_learning_route, get_problem, load_problems, search_problems


class ProblemSearchTests(unittest.TestCase):
    def test_search_problem_by_number_chinese_and_english(self):
        self.assertEqual(search_problems("1")[0]["title_en"], "Two Sum")
        self.assertEqual(search_problems("两数之和")[0]["id"], 1)
        self.assertEqual(search_problems("two sum")[0]["id"], 1)
        self.assertEqual(get_problem("1")["id"], 1)
        self.assertIsNone(get_problem(999999))

    def test_filters_can_be_combined_and_number_search_is_exact(self):
        matches = search_problems(difficulty="Easy", tags=["数组", "哈希表"])
        self.assertIn(1, [problem["id"] for problem in matches])
        self.assertTrue(all(problem["difficulty"] == "Easy" for problem in matches))
        self.assertEqual([p["id"] for p in search_problems("1")], [1])
        self.assertEqual(search_problems("two sum", difficulty="Hard"), [])
        self.assertEqual(search_problems(tags="不存在的标签"), [])
        self.assertEqual(search_problems("不属于题库的题目"), [])

    def test_complete_catalog_has_templates_examples_and_eight_route_stages(self):
        catalog = load_problems()
        self.assertGreaterEqual(len(catalog), 24)
        self.assertEqual(len({p["id"] for p in catalog}), len(catalog))
        for problem in catalog:
            with self.subTest(problem=problem["id"]):
                self.assertIn(problem["difficulty"], {"Easy", "Medium", "Hard"})
                self.assertTrue(problem["title_zh"] and problem["title_en"])
                self.assertTrue(problem["summary"] and problem["constraints"] and problem["examples"])
                self.assertTrue(problem["tags"] and problem["source_note"])
                self.assertEqual(problem["official_url"], "https://leetcode.cn/problems/" + problem["slug"] + "/")
                self.assertIn("class Solution", problem["python_template"])
                ast.parse(problem["python_template"])
        route = get_learning_route()
        self.assertEqual([stage["id"] for stage in route], list(range(1, 9)))
        self.assertEqual(route[0]["title"], "数组与哈希表")
        self.assertEqual(route[-1]["title"], "动态规划")
        self.assertTrue(all(stage["problems"] for stage in route))
        self.assertEqual(sorted(p["id"] for s in route for p in s["problems"]), sorted(p["id"] for p in catalog))
        self.assertEqual(get_problem(102)["difficulty"], "Medium")

    def test_callers_cannot_mutate_catalog_and_working_directory_is_irrelevant(self):
        import os
        import tempfile
        before = copy.deepcopy(get_problem(1))
        edited = get_problem(1)
        edited["tags"].append("意外修改")
        self.assertEqual(get_problem(1), before)
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(get_problem(1), before)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
