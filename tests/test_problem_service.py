import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services import problem_service
from services.problem_service import (
    CatalogError, get_learning_route, get_problem, load_problems, search_problems,
)

ROOT = Path(__file__).resolve().parents[1]


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


class CatalogValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "problem_catalog.json"
        self.environment = patch.dict(os.environ, {"AI_TUTOR_CATALOG_PATH": str(self.path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.catalog = json.loads((ROOT / "data" / "problem_catalog.json").read_text(encoding="utf-8"))
        self.stamp = 0

    def write_catalog(self, data=None, text=None):
        self.path.write_text(
            text if text is not None else json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )
        # Deterministic cache invalidation even on a coarse filesystem clock.
        self.stamp += 1_000_000
        marker = 1_700_000_000_000_000_000 + self.stamp
        os.utime(self.path, ns=(marker, marker))

    def test_missing_catalog_raises_a_clear_chinese_error(self):
        with self.assertRaisesRegex(CatalogError, "题库文件不存在"):
            load_problems()

    def test_corrupt_nonstandard_and_empty_json_are_rejected_without_rewriting(self):
        cases = (
            ("{broken", "解析失败"),
            ('{"problems": []}', "根节点"),
            ("[]", "不能为空"),
            ("[NaN]", "非法 JSON 数值"),
        )
        for text, message in cases:
            with self.subTest(text=text):
                self.write_catalog(text=text)
                before = self.path.read_bytes()
                with self.assertRaisesRegex(CatalogError, message):
                    load_problems()
                self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_problem_structure_is_rejected(self):
        def missing_field(problems):
            problems[0].pop("stage")

        def duplicate_id(problems):
            problems[1]["id"] = problems[0]["id"]

        def missing_example_input(problems):
            problems[0]["examples"][0].pop("input")

        def unsafe_url(problems):
            problems[0]["official_url"] = "javascript:alert(1)"

        cases = (
            ("缺少字段", missing_field, "缺少必填字段"),
            ("非正整数题号", lambda problems: problems[0].update(id=0), "id 必须是正整数"),
            ("难度非法", lambda problems: problems[0].update(difficulty="Unknown"), "difficulty"),
            ("阶段非法", lambda problems: problems[0].update(stage=9), "stage"),
            ("标签类型错误", lambda problems: problems[0].update(tags="数组"), "tags"),
            ("示例缺输出", lambda problems: problems[0]["examples"][0].update(output=None), "input 和 output"),
            ("缺示例输入", missing_example_input, "input 和 output"),
            ("重复题号", duplicate_id, "重复题号"),
            ("非对象条目", lambda problems: problems.append("bad"), "必须是 JSON 对象"),
            ("链接格式非法", unsafe_url, "official_url"),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                problems = copy.deepcopy(self.catalog)
                mutate(problems)
                self.write_catalog(problems)
                with self.assertRaisesRegex(CatalogError, message):
                    load_problems()

    def test_empty_stage_is_allowed_and_the_route_keeps_eight_stages(self):
        without_last_stage = [problem for problem in self.catalog if problem["stage"] != 8]
        self.write_catalog(without_last_stage)
        route = get_learning_route()
        self.assertEqual([stage["id"] for stage in route], list(range(1, 9)))
        self.assertEqual(route[-1]["problems"], [])
        self.assertEqual(len(load_problems()), len(without_last_stage))

    def test_catalog_is_read_once_per_file_version_and_refreshes_after_edit(self):
        self.write_catalog(self.catalog)
        reads = []
        original = problem_service._read_catalog_text

        def counting_reader(path):
            reads.append(path)
            return original(path)

        with patch.object(problem_service, "_read_catalog_text", side_effect=counting_reader):
            self.assertEqual(len(load_problems()), len(self.catalog))
            load_problems()
            get_problem(1)
            search_problems("two sum")
            get_learning_route()
            self.assertEqual(len(reads), 1)

            self.write_catalog([problem for problem in self.catalog if problem["id"] != 1])
            refreshed = load_problems()
            self.assertEqual(len(refreshed), len(self.catalog) - 1)
            self.assertEqual(len(reads), 2)

    def test_cached_catalog_is_not_shared_between_callers(self):
        self.write_catalog(self.catalog)
        first = load_problems()
        first[0]["tags"].append("意外修改")
        self.assertNotIn("意外修改", load_problems()[0]["tags"])


if __name__ == "__main__":
    unittest.main()
