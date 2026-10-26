"""UI regressions use only temporary records and activities, never production data."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from streamlit.testing.v1 import AppTest

from services.activity_service import load_activities, mark_accepted, summarize_activity
from services.problem_service import load_problems
from services.record_service import load_records

ROOT = Path(__file__).resolve().parents[1]


class AppFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formal_hashes = {}
        for name in ("records.json", "activities.json", "problem_catalog.json"):
            path = ROOT / "data" / name
            cls.formal_hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    @classmethod
    def tearDownClass(cls):
        for path, original in cls.formal_hashes.items():
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            if actual != original:
                raise AssertionError(f"UI tests changed the production {path.name} file")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ai-tutor-ui-")
        self.addCleanup(self.directory.cleanup)
        self.records_path = Path(self.directory.name) / "records.json"
        self.activities_path = Path(self.directory.name) / "activities.json"
        self.records_path.write_text(json.dumps([{"question": "synthetic legacy record"}]), encoding="utf-8")
        self.env = patch.dict(os.environ, {
            "AI_TUTOR_RECORDS_PATH": str(self.records_path),
            "AI_TUTOR_ACTIVITIES_PATH": str(self.activities_path),
            "DEEPSEEK_API_KEY": "unit-test-key-never-real",
            "DEEPSEEK_MODEL": "deepseek-flash",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        # Block the real .env and HTTP boundary for every page flow.
        dotenv = patch("services.llm_service.load_dotenv", create=True)
        dotenv.start()
        self.addCleanup(dotenv.stop)
        http = patch("services.llm_service.urlopen", create=True)
        self.http = http.start()
        self.addCleanup(http.stop)
        self.http.side_effect = lambda *args, **kwargs: self.http_response()

    def http_response(self, content=None, status="completed"):
        if content is None:
            content = {"error_type": "返回值错误", "knowledge": "数组与哈希表",
                       "analysis": "当前代码没有按题目要求返回两个下标。",
                       "hints": ["先核对输出类型。", "观察返回值是否来自输入下标。", "用一个简单示例追踪返回值。"]}
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        response = {
            "id": "resp_test", "object": "response", "created_at": 0,
            "model": "deepseek-flash", "status": status,
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": content}]}],
        }
        return io.BytesIO(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    def app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def practice(self):
        app = self.app().switch_page("pages/practice.py").run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_dashboard_has_real_zero_metrics_and_eight_stages(self):
        app = self.app()
        self.assertEqual([metric.value for metric in app.metric], ["0", "0", "0", "第 1 阶段"])
        self.assertEqual(len(app.expander), 8)
        self.assertIn("数组与哈希表", app.expander[0].label)
        self.assertFalse(self.activities_path.exists())
        app.button(key="route_1").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox(key="problem_picker").value, 1)

    def test_search_filters_show_the_selected_statement(self):
        app = self.practice()
        app.text_input(key="problem_search").set_value("two sum").run()
        self.assertEqual(app.selectbox(key="problem_picker").value, 1)
        self.assertIn("两数之和", " ".join(header.value for header in app.subheader))
        self.assertTrue(any("练习示例" in item.value for item in app.markdown))
        app.selectbox(key="difficulty_filter").set_value("Hard").run()
        self.assertEqual(len(app.selectbox), 1)
        self.assertTrue(any("没有匹配" in item.value for item in app.info))
        self.assertEqual(len(app.exception), 0)

    def test_completed_route_recommends_review_in_the_last_stage(self):
        for problem in load_problems():
            mark_accepted(problem["id"], problem["title_zh"])
        app = self.app()
        self.assertEqual(app.metric[3].value, "第 8 阶段")
        app.button(key="start_recommended").click().run()
        self.assertEqual(app.selectbox(key="problem_picker").value, 70)

    def test_draft_survives_hint_rerun_problem_switch_and_navigation(self):
        app = self.practice()
        edited = "# synthetic first draft\nprint('first')"
        app.text_area(key="code_editor_1").set_value(edited).run()
        app.button(key="diagnose").click().run()
        self.assertEqual(app.text_area(key="code_editor_1").value, edited)
        app.button(key="next_hint").click().run()
        self.assertEqual(app.session_state["hint_level"], 2)
        self.assertEqual(app.text_area(key="code_editor_1").value, edited)
        self.assertEqual(load_records()[1]["hints_used"], [1, 2])
        app.selectbox(key="problem_picker").set_value(20).run()
        self.assertIsNone(app.session_state["diagnosis"])
        second = "# synthetic second draft\nprint('second')"
        app.text_area(key="code_editor_20").set_value(second).run()
        app.selectbox(key="problem_picker").set_value(1).run()
        self.assertEqual(app.text_area(key="code_editor_1").value, edited)
        self.assertIsNone(app.session_state["diagnosis"])
        app.switch_page("pages/history.py").run()
        self.assertEqual(len(app.exception), 0)
        app.switch_page("pages/practice.py").run()
        self.assertEqual(app.text_area(key="code_editor_1").value, edited)
        self.assertEqual(app.session_state["drafts"]["20"], second)
        self.assertEqual(len(app.exception), 0)

    def test_diagnosis_submission_and_acceptance_are_distinct(self):
        app = self.practice()
        app.text_area(key="code_editor_1").set_value("print('synthetic')").run()
        app.button(key="diagnose").click().run()
        self.assertEqual(load_activities(), [])
        self.assertEqual(load_records()[0], {"question": "synthetic legacy record"})
        app.button(key="record_submission").click().run()
        app.run()
        self.assertEqual(len(load_activities()), 1)
        app.button(key="record_submission").click().run()
        self.assertEqual(summarize_activity(load_activities(), load_problems())["total_submissions"], 2)
        self.assertTrue(app.button(key="record_accepted").disabled)
        app.checkbox(key="confirm_accepted_1").check().run()
        app.button(key="record_accepted").click().run()
        summary = summarize_activity(load_activities(), load_problems())
        self.assertEqual(summary["total_submissions"], 2)
        self.assertEqual(summary["completed_problems"], 1)
        self.assertTrue(app.button(key="record_accepted").disabled)
        self.assertEqual(len(app.exception), 0)
        dashboard = self.app()
        self.assertEqual([metric.value for metric in dashboard.metric][:3], ["2", "1", "1"])

    def test_catalog_failure_is_reported_without_traceback_on_dashboard_and_practice(self):
        catalog = Path(self.directory.name) / "problem_catalog.json"
        catalog.write_text("{broken", encoding="utf-8")
        before_records = self.records_path.read_bytes()
        with patch.dict(os.environ, {"AI_TUTOR_CATALOG_PATH": str(catalog)}):
            app = self.app()
            self.assertTrue(any("题库加载失败" in item.value for item in app.error))
            self.assertEqual(len(app.metric), 0)
            practice = app.switch_page("pages/practice.py").run()
            self.assertEqual(len(practice.exception), 0)
            self.assertTrue(any("题库加载失败" in item.value for item in practice.error))
        self.assertEqual(self.records_path.read_bytes(), before_records)
        self.assertFalse(self.activities_path.exists())

    def test_empty_recommended_stage_shows_notice_without_index_error(self):
        catalog = json.loads((ROOT / "data" / "problem_catalog.json").read_text(encoding="utf-8"))
        for problem in catalog:
            if problem["stage"] != 8:
                mark_accepted(problem["id"], problem["title_zh"])
        path = Path(self.directory.name) / "catalog_without_stage_8.json"
        path.write_text(json.dumps([problem for problem in catalog if problem["stage"] != 8],
                                   ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, {"AI_TUTOR_CATALOG_PATH": str(path)}):
            app = self.app()
        self.assertEqual(app.metric[3].value, "第 8 阶段")
        self.assertTrue(any("暂无题目" in item.value for item in app.info))
        self.assertFalse(any(button.key == "start_recommended" for button in app.button))
        self.assertEqual(len(app.expander), 8)

    def test_corrupted_activity_data_is_not_presented_as_zero_or_overwritten(self):
        self.activities_path.write_text("broken synthetic JSON", encoding="utf-8")
        before = self.activities_path.read_bytes()
        app = self.app()
        self.assertEqual(app.metric[0].value, "—")
        self.assertTrue(any("无法读取" in item.value for item in app.error))
        app.switch_page("pages/practice.py").run()
        app.button(key="record_submission").click().run()
        self.assertEqual(self.activities_path.read_bytes(), before)
        self.assertEqual(len(app.exception), 0)

    def test_deepseek_source_is_displayed_and_saved_with_three_progressive_hints(self):
        app = self.practice()
        edited = "# 中文虚构测试\nprint('synthetic')"
        app.text_area(key="code_editor_1").set_value(edited).run()
        app.button(key="diagnose").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.http.call_count, 1)
        diagnosis = app.session_state["diagnosis"]
        self.assertEqual(diagnosis["source"], "deepseek")
        self.assertIs(diagnosis["is_mock"], False)
        self.assertEqual(len(diagnosis["hints"]), 3)
        self.assertTrue(any("DeepSeek" in item.value for item in app.subheader))
        record = load_records()[-1]
        self.assertEqual(record["source"], "deepseek")
        self.assertIs(record["is_mock"], False)
        self.assertEqual(record["hints_used"], [1])
        self.assertEqual(len([item for item in app.info if item.value.startswith("Hint ")]), 1)

        app.button(key="next_hint").click().run()
        app.button(key="next_hint").click().run()
        self.assertEqual(app.session_state["hint_level"], 3)
        self.assertTrue(app.button(key="next_hint").disabled)
        self.assertEqual(load_records()[-1]["hints_used"], [1, 2, 3])
        self.assertEqual(len([item for item in app.info if item.value.startswith("Hint ")]), 3)
        app.button(key="diagnose").click().run()
        self.assertEqual(self.http.call_count, 2)
        self.assertEqual(app.session_state["hint_level"], 1)
        self.assertEqual(load_records()[-1]["hints_used"], [1])
        self.assertEqual(app.text_area(key="code_editor_1").value, edited)
        self.assertEqual(load_activities(), [])

    def test_deepseek_failures_keep_draft_without_saving_diagnosis_or_activity(self):
        app = self.practice()
        edited = "# 测试草稿\nprint('synthetic failure case')"
        app.text_area(key="code_editor_1").set_value(edited).run()
        app.button(key="diagnose").click().run()
        self.assertEqual(app.session_state["diagnosis"]["source"], "deepseek")
        baseline = self.records_path.read_bytes()
        cases = []
        for status in (401, 402, 429):
            cases.append((str(status), HTTPError("https://api.deepseek.com/responses",
                                                status, "synthetic", {}, io.BytesIO(b"{}")), str(status)))
        cases.extend([
            ("timeout", TimeoutError("synthetic timeout"), "超时"),
            ("incomplete", lambda *args, **kwargs: self.http_response(status="incomplete"), "未完整"),
            ("empty", lambda *args, **kwargs: self.http_response(""), "空"),
            ("invalid-json", lambda *args, **kwargs: self.http_response("not JSON"), "JSON"),
            ("missing-fields", lambda *args, **kwargs: self.http_response({"analysis": "缺失其他字段"}), "字段"),
        ])
        for label, effect, message in cases:
            with self.subTest(case=label):
                self.http.side_effect = effect
                app.button(key="diagnose").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any(message in item.value for item in app.error),
                                [item.value for item in app.error])
                self.assertEqual(self.records_path.read_bytes(), baseline)
                self.assertEqual(load_activities(), [])
                self.assertFalse(self.activities_path.exists())
                self.assertIsNone(app.session_state["diagnosis"])
                self.assertEqual(app.session_state["drafts"]["1"], edited)
                self.assertEqual(app.text_area(key="code_editor_1").value, edited)
                self.assertFalse(any(button.key == "next_hint" for button in app.button))

    def test_editing_code_removes_old_diagnosis_and_hint_controls(self):
        app = self.practice()
        app.text_area(key="code_editor_1").set_value("print('first')").run()
        app.button(key="diagnose").click().run()
        app.button(key="next_hint").click().run()
        baseline = self.records_path.read_bytes()
        app.text_area(key="code_editor_1").set_value("print('edited')").run()
        self.assertIsNone(app.session_state["diagnosis"])
        self.assertEqual(app.session_state["hint_level"], 1)
        self.assertFalse(any(button.key == "next_hint" for button in app.button))
        self.assertEqual(self.records_path.read_bytes(), baseline)
        self.assertEqual(self.http.call_count, 1)

    def test_response_for_changed_selection_or_editor_is_discarded_before_saving(self):
        # Simulate changes arriving while the HTTP request is in flight.
        cases = (("selected_problem_id", 20), ("problem_picker", 20),
                 ("code_editor_1", "print('changed while waiting')"))
        for key, value in cases:
            with self.subTest(changed=key):
                app = self.practice()
                app.text_area(key="code_editor_1").set_value("print('request snapshot')").run()
                baseline = self.records_path.read_bytes()

                def response_after_change(*args, **kwargs):
                    # Updating through the underlying state models an incoming
                    # widget update without setting an instantiated widget via
                    # Streamlit's public assignment API.
                    app.session_state._state._new_session_state[key] = value
                    return self.http_response()

                self.http.side_effect = response_after_change
                app.button(key="diagnose").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(self.records_path.read_bytes(), baseline)
                self.assertEqual(load_activities(), [])
                self.assertIsNone(app.session_state["diagnosis"])


if __name__ == "__main__":
    unittest.main()
