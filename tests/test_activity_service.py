from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services import activity_service


class ActivityServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "activities.json"
        self.environment = patch.dict(os.environ, {"AI_TUTOR_ACTIVITIES_PATH": str(self.path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_submission_and_self_reported_acceptance_are_separate_idempotent_events(self):
        self.assertEqual(activity_service.load_activities(), [])
        first = activity_service.record_submission(1, "sample", submission_id="s1",
                                                   timestamp="2026-10-19T16:30:00+00:00")
        again = activity_service.record_submission(1, "sample", submission_id="s1")
        accepted = activity_service.mark_accepted(1, "sample", event_id="a1",
                                                  timestamp="2026-10-20T01:00:00+08:00")
        self.assertEqual(first, again)
        self.assertEqual(first["timestamp"], "2026-10-20T00:30:00+08:00")
        self.assertEqual(accepted["kind"], "accepted")
        self.assertEqual(activity_service.load_activities(), [first, accepted])

    def test_summary_counts_submissions_completions_and_yesterday_streak_separately(self):
        activities = [
            {"kind": "submission", "problem_id": 1, "title": "sample", "submission_id": "s1", "timestamp": "2026-10-20T15:00:00Z"},
            {"kind": "submission", "problem_id": 1, "title": "sample", "submission_id": "s2", "timestamp": "2026-10-21T00:30:00+08:00"},
            {"kind": "accepted", "problem_id": 1, "title": "sample", "event_id": "a1", "timestamp": "2026-10-21T01:00:00+08:00"},
            {"kind": "accepted", "problem_id": 1, "title": "sample", "event_id": "a2", "timestamp": "2026-10-21T01:01:00+08:00"},
            {"kind": "submission", "problem_id": 2, "title": "sample", "submission_id": "future", "timestamp": "2026-10-23T00:00:00+08:00"},
            {"kind": "accepted", "problem_id": 2, "title": "sample", "event_id": "future", "timestamp": "2026-10-23T00:00:00+08:00"},
            {"kind": "submission", "problem_id": 2, "title": "bad"}, None,
        ]
        problems = [{"id": 1, "stage": 1}, {"id": 2, "stage": 2}, {"id": 3, "stage": 2}]
        self.assertEqual(activity_service.summarize_activity(activities, problems, today=date(2026, 10, 22)), {
            "total_submissions": 2, "completed_problems": 1, "streak_days": 2,
            "recommended_stage": 2, "completed_ids": {1},
            "counts_by_day": {"2026-10-20": 1, "2026-10-21": 1},
        })
        self.assertEqual(activity_service.summarize_activity([], problems, today="2026-10-22")["recommended_stage"], 1)

    def test_heatmap_has_365_shanghai_dates_including_today_and_only_counts_submissions(self):
        activities = []
        for index in range(5):
            activities.append({"kind": "submission", "problem_id": 1, "title": "sample",
                               "submission_id": str(index), "timestamp": "2026-10-21T16:01:00Z"})
        activities.extend([
            {"kind": "submission", "problem_id": 1, "title": "sample", "submission_id": "old", "timestamp": "2025-10-22T12:00:00+08:00"},
            {"kind": "accepted", "problem_id": 1, "title": "sample", "event_id": "a1", "timestamp": "2026-10-22T01:00:00+08:00"},
        ])
        heatmap = activity_service.build_heatmap(activities, today="2026-10-22")
        self.assertEqual(len(heatmap), 365)
        self.assertEqual(heatmap[0], {"date": "2025-10-23", "count": 0, "level": 0})
        self.assertEqual(heatmap[-1], {"date": "2026-10-22", "count": 5, "level": 4})
        self.assertEqual(sum(day["count"] for day in heatmap), 5)

    def test_problem_status_ignores_other_problems_and_future_acceptance(self):
        activity_service.record_submission(1, "sample", submission_id="s1", timestamp="2026-10-20T16:01:00Z")
        activity_service.mark_accepted(2, "another", timestamp="2026-10-21T01:00:00+08:00")
        activity_service.mark_accepted(1, "sample", timestamp="2026-10-23T01:00:00+08:00")
        self.assertEqual(activity_service.problem_status(activity_service.load_activities(), 1, today="2026-10-22"), {
            "problem_id": 1, "accepted": False, "submission_count": 1,
            "last_submission_at": "2026-10-21T00:01:00+08:00",
        })

    def test_corrupt_or_non_list_file_is_not_overwritten(self):
        for content in ("{broken", '{"activities": []}', '[NaN]'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                before = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    activity_service.load_activities()
                with self.assertRaises(ValueError):
                    activity_service.record_submission(1, "sample")
                self.assertEqual(self.path.read_bytes(), before)

    def test_bad_legacy_entries_survive_append_but_do_not_count(self):
        legacy = [None, {"kind": "submission", "problem_id": True, "title": "bad",
                         "submission_id": "bad", "timestamp": "2026-10-22T01:00:00+08:00"},
                  {"kind": "accepted", "problem_id": 1, "title": "missing timestamp", "event_id": "bad"}]
        self.path.write_text(json.dumps(legacy), encoding="utf-8")
        added = activity_service.record_submission(1, "sample", timestamp="2026-10-22T01:00:00+08:00")
        self.assertEqual(activity_service.load_activities(), [*legacy, added])
        summary = activity_service.summarize_activity(activity_service.load_activities(), [], today="2026-10-22")
        self.assertEqual(summary["total_submissions"], 1)
        self.assertEqual(summary["completed_ids"], set())

    def test_invalid_new_events_and_snapshots_never_create_a_file(self):
        invalid = [
            {"problem_id": True}, {"problem_id": 0}, {"title": " "},
            {"timestamp": "2026-10-22T10:00:00"}, {"submission_id": ""},
            {"diagnosis": {"score": float("nan")}}, {"diagnosis": "bad"},
            {"hints_used": [True]}, {"hints_used": [1, 1]},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                activity_service.record_submission(**{"problem_id": 1, "title": "sample", **changes})
        self.assertFalse(self.path.exists())

    def test_concurrent_submissions_do_not_lose_updates_and_same_id_is_idempotent(self):
        def submit(index):
            return activity_service.record_submission(1, "sample", submission_id=f"s{index % 20}",
                                                       timestamp="2026-10-22T01:00:00+08:00")
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(submit, range(60)))
        events = activity_service.load_activities()
        self.assertEqual(len(events), 20)
        self.assertEqual(activity_service.summarize_activity(events, [], today="2026-10-22")["total_submissions"], 20)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            activity_service.record_submission(2, "other", submission_id="s1")
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_atomic_replacement_preserves_file_and_removes_temporary_file(self):
        activity_service.record_submission(1, "sample")
        before = self.path.read_bytes()
        with patch("services.activity_service.os.replace", side_effect=OSError("blocked")):
            with self.assertRaises(OSError):
                activity_service.mark_accepted(1, "sample")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(".activities-*.tmp")), [])

    def test_completed_stages_and_gap_in_streak_have_literal_results(self):
        activities = [
            {"kind": "submission", "problem_id": 1, "title": "sample", "submission_id": "s1", "timestamp": "2026-10-19T01:00:00+08:00"},
            {"kind": "accepted", "problem_id": 1, "title": "sample", "event_id": "a1", "timestamp": "2026-10-22T01:00:00+08:00"},
            {"kind": "accepted", "problem_id": 2, "title": "sample", "event_id": "a2", "timestamp": "2026-10-22T01:00:00+08:00"},
        ]
        summary = activity_service.summarize_activity(activities, [{"id": 1, "stage": 1}, {"id": 2, "stage": 8}], today="2026-10-22")
        self.assertEqual(summary["completed_problems"], 2)
        self.assertEqual(summary["recommended_stage"], 8)
        self.assertEqual(summary["streak_days"], 0)
        self.assertEqual(summary["total_submissions"], 1)

    def test_duplicate_loaded_submission_id_counts_once_and_heatmap_validates_days(self):
        event = activity_service.record_submission(1, "sample", timestamp="2026-10-22T01:00:00+08:00")
        self.assertEqual(activity_service.summarize_activity([event, event], [], today="2026-10-22")["total_submissions"], 1)
        self.assertEqual(len(activity_service.build_heatmap([event], today="2026-10-22", days=7)), 7)
        for days in (0, -1, True, 1.5):
            with self.subTest(days=days), self.assertRaises(ValueError):
                activity_service.build_heatmap([], today="2026-10-22", days=days)

    def test_transient_replace_permission_error_retries_but_persistent_error_preserves_data(self):
        activity_service.record_submission(1, "sample")
        replace = os.replace
        attempts = []
        def temporarily_locked(source, target):
            attempts.append(target)
            if len(attempts) < 3:
                raise PermissionError("file temporarily busy")
            return replace(source, target)
        with patch("services.activity_service.os.replace", side_effect=temporarily_locked):
            activity_service.mark_accepted(1, "sample")
        self.assertEqual(len(activity_service.load_activities()), 2)
        self.assertEqual(len(attempts), 3)
        before = self.path.read_bytes()
        with patch("services.activity_service.os.replace", side_effect=PermissionError("still busy")):
            with self.assertRaises(PermissionError):
                activity_service.record_submission(1, "sample")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(".activities-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
