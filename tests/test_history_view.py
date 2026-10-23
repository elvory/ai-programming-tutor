import copy
from datetime import date, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.history_service import build_activity_rows, build_history_rows, display_value


class HistoryViewTests(unittest.TestCase):
    def test_legacy_and_malformed_records_keep_original_positions_and_values(self):
        records = [{"question": "legacy"}, None, {"question": 0, "error_type": False,
                   "knowledge": "  ", "hint_level": None}]
        original = copy.deepcopy(records)
        rows = build_history_rows(records, [])
        self.assertEqual([row["原始索引"] for row in rows], ["0", "1", "2"])
        self.assertEqual(rows[0]["状态"], "记录不完整")
        self.assertEqual(rows[0]["错误类型"], "未记录")
        self.assertEqual(rows[1]["状态"], "记录异常")
        self.assertIn("NoneType", rows[1]["异常说明"])
        self.assertEqual(rows[2]["题目"], "0")
        self.assertEqual(rows[2]["错误类型"], "False")
        self.assertIn("空白字符串", rows[2]["知识点"])
        self.assertEqual(rows[2]["Hint 等级"], "空值（null）")
        self.assertEqual(records, original)

    def test_display_value_keeps_distinct_missing_and_empty_states(self):
        self.assertEqual(display_value({}, "x"), "未记录")
        self.assertEqual(display_value({"x": None}, "x"), "空值（null）")
        self.assertEqual(display_value({"x": ""}, "x"), '空字符串（""）')
        self.assertEqual(display_value({"x": False}, "x"), "False")

    def test_new_metadata_separates_submissions_and_user_reported_acceptance(self):
        record = {"question": "Two Sum", "error_type": "index", "knowledge": "array",
                  "hint_level": 2, "leetcode_id": 1, "title": "两数之和",
                  "created_at": "2020-01-01T10:00:00+08:00", "hints_used": [1, 2]}
        submission = {"kind": "submission", "problem_id": 1, "title": "两数之和",
                      "timestamp": "2020-01-01T10:00:00+08:00", "submission_id": "s1"}
        accepted = {"kind": "accepted", "problem_id": 1, "title": "两数之和",
                    "timestamp": "2020-01-01T10:01:00+08:00", "event_id": "a1"}
        not_accepted = build_history_rows([record], [submission])[0]
        self.assertEqual(not_accepted["本地完成状态"], "未确认通过")
        row = build_history_rows([record], [submission, accepted])[0]
        self.assertEqual(row["LeetCode 题号"], "1")
        self.assertEqual(row["题目名称"], "两数之和")
        self.assertEqual(row["提交日期"], "2020-01-01T10:00:00+08:00")
        self.assertEqual(row["Hint 使用情况"], "Hint 1、2")
        self.assertEqual(row["本地完成状态"], "用户自报已通过（非官方同步）")

    def test_invalid_or_future_acceptance_never_marks_history_completed(self):
        record = {"question": "sample", "error_type": "e", "knowledge": "k",
                  "hint_level": 1, "problem_id": 1}
        activities = [None, {"kind": "accepted", "problem_id": 1},
                      {"kind": "accepted", "problem_id": 1, "title": "sample",
                       "timestamp": "2999-01-01T10:00:00+08:00", "event_id": "future"}]
        self.assertEqual(build_history_rows([record], activities)[0]["本地完成状态"],
                         "未确认通过")

    def test_activity_table_keeps_anomalies_and_original_indices(self):
        activities = ["legacy", {"kind": "submission", "problem_id": 1,
                      "title": "sample", "timestamp": "2020-01-01T10:00:00+08:00",
                      "submission_id": "s1", "hints_used": [],
                      "diagnosis": {"error_type": "sample error"}}]
        original = copy.deepcopy(activities)
        rows = build_activity_rows(activities)
        self.assertEqual([row["原始索引"] for row in rows], ["0", "1"])
        self.assertEqual(rows[0]["状态"], "记录异常")
        self.assertIn("str", rows[0]["异常说明"])
        self.assertEqual(rows[1]["活动类型"], "本地刷题提交")
        self.assertEqual(rows[1]["错误类型"], "sample error")
        self.assertEqual(rows[1]["Hint 使用情况"], "未使用")
        self.assertEqual(activities, original)

    def test_utc_z_acceptance_is_a_valid_self_report(self):
        activities = [{"kind": "accepted", "problem_id": 1, "title": "sample",
                       "timestamp": "2020-01-01T00:00:00Z", "event_id": "utc"}]
        row = build_history_rows([{"problem_id": 1}], activities)[0]
        self.assertEqual(row["本地完成状态"], "用户自报已通过（非官方同步）")

    def test_malformed_field_types_remain_visible_without_crashing_the_table(self):
        activities = [{"kind": ["accepted"], "problem_id": "9" * 5000,
                       "title": None, "hints_used": "not a list"}]
        row = build_activity_rows(activities)[0]
        self.assertEqual(row["状态"], "记录异常")
        self.assertEqual(row["活动类型"], "['accepted']")
        self.assertEqual(row["题目名称"], "空值（null）")
        self.assertEqual(row["本地完成状态"], "未记录题号")


class HeatmapTests(unittest.TestCase):
    def test_365_real_dates_have_hover_counts_and_padding_has_no_dates(self):
        from utils.ui import build_heatmap_html

        first = date(2025, 1, 1)
        cells = [{"date": (first + timedelta(days=index)).isoformat(), "count": 0, "level": 0}
                 for index in range(365)]
        cells[0].update(count=3, level=2)
        html = build_heatmap_html(cells)
        self.assertEqual(html.count('class="tutor-day level-'), 365)
        self.assertEqual(html.count('class="tutor-day empty"'), 6)
        self.assertIn('title="2025-01-01：3 次本地刷题提交"', html)
        self.assertIn("2025-01-01 至 2025-12-31 · 3 次本地刷题提交", html)
        self.assertIn("tutor-legend", html)
        self.assertIn("4 次及以上", html)

    def test_untrusted_html_cannot_become_a_heatmap_attribute(self):
        from utils.ui import build_heatmap_html

        html = build_heatmap_html([
            {"date": '<script>alert(1)</script>', "count": 1, "level": 1},
            {"date": "2025-12-31", "count": '<img src=x>', "level": '" onclick="x'},
            {"date": "2026-01-01", "count": 1, "level": 1},
        ])
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("onclick", html)
        self.assertIn('title="2025-12-31：0 次本地刷题提交"', html)
        self.assertIn("2025-12-31 至 2026-01-01", html)

    def test_partial_start_month_does_not_overlap_the_next_month_label(self):
        from utils.ui import build_heatmap_html

        first = date(2025, 10, 24)
        cells = [{"date": (first + timedelta(days=index)).isoformat(), "count": 0, "level": 0}
                 for index in range(365)]
        html = build_heatmap_html(cells)
        self.assertNotIn('title="2025年10月"', html)
        self.assertIn('title="2025年11月"', html)
        self.assertIn(">11月</span>", html)
        self.assertIn('title="2026年1月"', html)
        self.assertIn(">2026年1月</span>", html)


class HistoryPageTests(unittest.TestCase):
    def test_history_tabs_isolate_read_errors_and_do_not_write_data(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as directory:
            records = Path(directory) / "records.json"
            activities = Path(directory) / "activities.json"
            records.write_text('[{"question":"legacy"},null]', encoding="utf-8")
            activities.write_text('{broken', encoding="utf-8")
            before = (records.read_bytes(), activities.read_bytes())
            with patch.dict(os.environ, {"AI_TUTOR_RECORDS_PATH": str(records),
                                         "AI_TUTOR_ACTIVITIES_PATH": str(activities)}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages/history.py"))
                app.run(timeout=15)
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.dataframe), 1)
                self.assertEqual(len(app.dataframe[0].value), 2)
                self.assertIn("活动", app.error[0].value)
                self.assertIn("暂不可用", str(app.dataframe[0].value.iloc[0]["本地完成状态"]))
                self.assertEqual(before, (records.read_bytes(), activities.read_bytes()))

                records.write_text('{broken', encoding="utf-8")
                activities.write_text('[]', encoding="utf-8")
                app.run(timeout=15)
                self.assertEqual(len(app.exception), 0)
                self.assertIn("学习记录", app.error[0].value)
                self.assertIn("暂无刷题活动", app.info[0].value)


if __name__ == "__main__":
    unittest.main()
