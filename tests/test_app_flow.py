"""UI regressions use only temporary records and activities, never production data."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.activity_service import load_activities, mark_accepted, summarize_activity
from services.problem_service import load_problems
from services.record_service import load_records

ROOT = Path(__file__).resolve().parents[1]


class AppFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formal = ROOT / "data" / "records.json"
        cls.formal_hash = hashlib.sha256(cls.formal.read_bytes()).hexdigest() if cls.formal.exists() else None

    @classmethod
    def tearDownClass(cls):
        actual = hashlib.sha256(cls.formal.read_bytes()).hexdigest() if cls.formal.exists() else None
        if actual != cls.formal_hash:
            raise AssertionError("UI tests changed the production records file")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ai-tutor-ui-")
        self.addCleanup(self.directory.cleanup)
        self.records_path = Path(self.directory.name) / "records.json"
        self.activities_path = Path(self.directory.name) / "activities.json"
        self.records_path.write_text(json.dumps([{"question": "synthetic legacy record"}]), encoding="utf-8")
        self.env = patch.dict(os.environ, {
            "AI_TUTOR_RECORDS_PATH": str(self.records_path),
            "AI_TUTOR_ACTIVITIES_PATH": str(self.activities_path),
        })
        self.env.start()
        self.addCleanup(self.env.stop)

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


if __name__ == "__main__":
    unittest.main()
