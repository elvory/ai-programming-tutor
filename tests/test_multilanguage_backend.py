"""Language contracts: fake credentials, mocked transport and temporary data."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from services.llm_service import DIAGNOSIS_SCHEMA, DiagnosisError, analyze_code, analyze_code_rules
from services.practice_service import (begin_diagnosis, diagnosis_request_is_current,
                                       save_draft, select_problem)
from services.activity_service import load_activities, mark_accepted, record_submission, summarize_activity
from services.history_service import build_activity_rows, build_history_rows


DIAGNOSIS = {
    "error_type": "实现不完整", "knowledge": "返回值与边界条件",
    "analysis": "当前函数仍需补充返回值。",
    "hints": ["检查返回类型。", "试着推演空输入。", "明确局部不变量。"],
}


def response(content=None):
    body = {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(content or DIAGNOSIS, ensure_ascii=False)}]}]}
    return io.BytesIO(json.dumps(body, ensure_ascii=False).encode("utf-8"))


class MultilanguageModelTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake-phase3-key", "DEEPSEEK_MODEL": "deepseek-flash"})
        env.start()
        self.addCleanup(env.stop)
        dotenv = patch("services.llm_service.load_dotenv")
        self.dotenv = dotenv.start()
        self.addCleanup(dotenv.stop)
        network = patch("services.llm_service.urlopen", side_effect=lambda *args, **kwargs: response())
        self.network = network.start()
        self.addCleanup(network.stop)

    def test_each_language_reaches_model_with_specific_static_review_context(self):
        for language, code, focus in (
            ("python", "def solve(): pass", "缩进"),
            ("java", "class Solution {}", "泛型"),
            ("c", "int solve(int* a) { return 0; }", "越界"),
            ("cpp", "class Solution {};", "迭代器"),
        ):
            with self.subTest(language=language):
                result = analyze_code(code, {"id": 1, "title_en": "Two Sum"}, language=language)
                payload = json.loads(self.network.call_args.args[0].data)
                context = json.loads(payload["input"])
                self.assertEqual(context["language"], language)
                self.assertEqual(context["code"], code)
                self.assertIn(focus, context["language_review"])
                self.assertEqual(payload["text"]["format"]["schema"], DIAGNOSIS_SCHEMA)
                self.assertEqual(payload["reasoning"], {"effort": "none"})
                self.assertEqual(result["hints"], DIAGNOSIS["hints"])

    def test_legacy_model_call_defaults_to_python_and_invalid_language_never_loads_credentials(self):
        analyze_code("pass")
        context = json.loads(json.loads(self.network.call_args.args[0].data)["input"])
        self.assertEqual(context["language"], "python")
        self.network.reset_mock()
        self.dotenv.reset_mock()
        with self.assertRaises(DiagnosisError):
            analyze_code("source", language="javascript")
        self.network.assert_not_called()
        self.dotenv.assert_not_called()

    def test_non_python_rules_never_parse_foreign_language_as_python(self):
        with patch("services.llm_service.ast.parse") as parser:
            for language in ("java", "c", "cpp"):
                with self.assertRaises(DiagnosisError):
                    analyze_code_rules("class Solution {}", language=language)
            parser.assert_not_called()
        self.network.assert_not_called()

    def test_every_language_keeps_exact_three_hint_validation_without_repair(self):
        for language in ("python", "java", "c", "cpp"):
            for hints in (["one"], ["one", "two", ""], ["one", "two", "three", "four"]):
                with self.subTest(language=language, hints=hints):
                    self.network.side_effect = lambda *args, **kwargs: response({**DIAGNOSIS, "hints": hints})
                    with self.assertRaises(DiagnosisError):
                        analyze_code("incomplete source", language=language)


class MultilanguagePracticeTests(unittest.TestCase):
    def test_language_drafts_restore_independently_and_legacy_python_draft_survives(self):
        state = {"drafts": {"1": "legacy Python"}}
        first = {"id": 1, "python_template": "pass", "templates": {
            "python": "pass", "java": "class Solution {}", "c": "void solve() {}", "cpp": "class Solution {};"}}
        for language in ("python", "java", "c", "cpp"):
            initial = select_problem(state, first, language=language)
            self.assertEqual(initial, "legacy Python" if language == "python" else first["templates"][language])
            save_draft(state, 1, "" if language == "c" else f"draft {language}", language=language)
        select_problem(state, {**first, "id": 20}, language="java")
        for language in ("cpp", "c", "java", "python"):
            self.assertEqual(select_problem(state, first, language=language),
                             "" if language == "c" else f"draft {language}")

    def test_switch_language_and_restore_same_code_cannot_revive_pending_diagnosis(self):
        state = {}
        problem = {"id": 1, "python_template": "same", "templates": {"java": "same"}}
        select_problem(state, problem)
        pending = begin_diagnosis(state, 1, "same")
        select_problem(state, problem, language="java")
        select_problem(state, problem)
        self.assertFalse(diagnosis_request_is_current(state, pending))


class MultilanguageActivityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="phase3-activity-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "activities.json"
        env = patch.dict(os.environ, {"AI_TUTOR_ACTIVITIES_PATH": str(self.path)})
        env.start()
        self.addCleanup(env.stop)

    def test_known_language_completions_are_separate_while_overall_ids_remain_unique(self):
        legacy = {"kind": "accepted", "problem_id": 20, "title": "legacy", "timestamp": "2020-01-01T12:00:00+08:00", "event_id": "old"}
        self.path.write_text(json.dumps([legacy]), encoding="utf-8")
        for language in ("python", "java", "c", "cpp"):
            record_submission(1, "Two Sum", language=language)
            mark_accepted(1, "Two Sum", language=language)
        events = load_activities()
        summary = summarize_activity(events, [])
        self.assertEqual(summary["completed_ids"], {1, 20})
        self.assertEqual(summary["completed_problems"], 2)
        self.assertEqual(summary["total_submissions"], 4)
        self.assertEqual(summary["completed_by_language"], {"python": [1], "java": [1], "c": [1], "cpp": [1]})
        rows = build_activity_rows(events)
        self.assertEqual(rows[0]["语言"], "未记录")
        self.assertEqual(rows[1]["语言"], "Python 3")
        self.assertEqual(rows[3]["语言"], "Java")
        self.assertEqual(events[0], legacy)

    def test_reusing_event_identity_in_another_language_is_rejected_without_overwrite(self):
        record_submission(1, "Two Sum", language="python", submission_id="same-id")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            record_submission(1, "Two Sum", language="java", submission_id="same-id")
        self.assertEqual(self.path.read_bytes(), before)

    def test_python_acceptance_does_not_mark_java_history_as_passed(self):
        mark_accepted(1, "Two Sum", language="python")
        base = {"question": "sample", "error_type": "e", "knowledge": "k", "hint_level": 1, "problem_id": 1}
        records = [{**base, "language": "python"}, {**base, "language": "java"}, base]
        rows = build_history_rows(records, load_activities())
        self.assertEqual(rows[0]["本地完成状态"], "用户自报本语言已通过（非官方同步）")
        self.assertEqual(rows[1]["本地完成状态"], "题目已通过，当前语言未确认")
        self.assertEqual(rows[2]["语言"], "未记录")
        self.assertNotIn("language", records[2])

    def test_retrying_legacy_event_preserves_unknown_language_without_rewriting_it(self):
        legacy = {"kind": "submission", "problem_id": 1, "title": "old",
                  "timestamp": "2020-01-01T12:00:00+08:00", "submission_id": "legacy-id"}
        self.path.write_text(json.dumps([legacy]), encoding="utf-8")
        before = self.path.read_bytes()
        result = record_submission(1, "old", submission_id="legacy-id")
        self.assertEqual(result, legacy)
        self.assertEqual(self.path.read_bytes(), before)


class MultilanguageApiTests(unittest.TestCase):
    def setUp(self):
        from backend.app import create_app
        self.directory = tempfile.TemporaryDirectory(prefix="phase3-api-")
        self.addCleanup(self.directory.cleanup)
        self.records = Path(self.directory.name) / "records.json"
        self.activities = Path(self.directory.name) / "activities.json"
        env = patch.dict(os.environ, {"AI_TUTOR_RECORDS_PATH": str(self.records),
                                     "AI_TUTOR_ACTIVITIES_PATH": str(self.activities),
                                     "DEEPSEEK_API_KEY": "fake-phase3-key", "DEEPSEEK_MODEL": "deepseek-flash"})
        env.start()
        self.addCleanup(env.stop)
        dotenv = patch("services.llm_service.load_dotenv")
        dotenv.start()
        self.addCleanup(dotenv.stop)
        network = patch("services.llm_service.urlopen", side_effect=lambda *args, **kwargs: response())
        self.network = network.start()
        self.addCleanup(network.stop)
        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)
        self.workspace_id = str(uuid4())

    def context(self, language="python", revision=1, code="same source"):
        return {"workspace_id": self.workspace_id, "problem_id": 1,
                "language": language, "revision": revision, "code": code}

    def post(self, path, body, status=200):
        result = self.client.post(path, json=body)
        self.assertEqual(result.status_code, status, result.text)
        return result.json()

    def diagnose(self, context):
        candidate = self.post("/api/diagnoses", context)
        return self.post("/api/diagnoses/accept", {
            "workspace_id": self.workspace_id, "request_id": candidate["request_id"],
            "revision": context["revision"]})

    def test_each_language_diagnosis_hint_and_submission_keep_provenance_without_auto_submission(self):
        for revision, language in enumerate(("python", "java", "c", "cpp"), 1):
            with self.subTest(language=language):
                context = self.context(language=language, revision=revision)
                result = self.diagnose(context)
                self.assertEqual(result["language"], language)
                self.assertEqual(result["diagnosis"]["hints"], DIAGNOSIS["hints"][:1])
                summary = self.client.get("/api/bootstrap").json()["summary"]
                self.assertEqual(summary["total_submissions"], revision - 1)
                hint = {"workspace_id": self.workspace_id, "revision": revision,
                        "diagnosis_id": result["diagnosis_id"], "expected_hint_level": 1}
                second = self.post("/api/hints", hint)
                self.assertEqual(self.post("/api/hints", hint), second)
                third = self.post("/api/hints", {**hint, "expected_hint_level": 2})
                self.assertEqual(third["diagnosis"]["hints"], DIAGNOSIS["hints"])
                self.post("/api/submissions", {**context, "submission_id": str(uuid4())})
        records = json.loads(self.records.read_text(encoding="utf-8"))
        activities = json.loads(self.activities.read_text(encoding="utf-8"))
        self.assertEqual([record["language"] for record in records], ["python", "java", "c", "cpp"])
        self.assertEqual([event["language"] for event in activities], ["python", "java", "c", "cpp"])
        self.assertTrue(all(event["hints_used"] == [1, 2, 3] for event in activities))
        self.assertTrue(all(event["diagnosis"]["source"] == "deepseek" for event in activities))
        self.assertEqual(self.network.call_count, 4)

    def test_old_python_client_defaults_to_python_and_unsupported_languages_are_rejected(self):
        context = self.context()
        del context["language"]
        result = self.diagnose(context)
        self.assertEqual(result["language"], "python")
        self.network.reset_mock()
        before = self.records.read_bytes()
        for invalid in ("javascript", "Python", "", None, [], True):
            self.post("/api/diagnoses", {**context, "language": invalid}, 422)
            self.post("/api/submissions", {**context, "language": invalid, "submission_id": str(uuid4())}, 422)
            self.post("/api/accepted", {"problem_id": 1, "language": invalid, "confirmed": True, "event_id": str(uuid4())}, 422)
        self.network.assert_not_called()
        self.assertEqual(self.records.read_bytes(), before)
        self.assertFalse(self.activities.exists())

    def test_language_switch_rejects_same_revision_and_discards_old_candidate_and_hints(self):
        python = self.context()
        candidate = self.post("/api/diagnoses", python)
        self.post("/api/workspace/sync", self.context(language="java"), 409)
        self.post("/api/workspace/sync", self.context(language="java", revision=2))
        self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                  "request_id": candidate["request_id"], "revision": 2}, 409)
        self.assertFalse(self.records.exists())
        accepted = self.diagnose(self.context(language="java", revision=2))
        self.post("/api/workspace/sync", self.context(language="cpp", revision=3))
        self.post("/api/hints", {"workspace_id": self.workspace_id, "revision": 3,
                  "diagnosis_id": accepted["diagnosis_id"]}, 409)
        self.post("/api/submissions", {**self.context(language="cpp", revision=3), "submission_id": str(uuid4())})
        event = json.loads(self.activities.read_text(encoding="utf-8"))[0]
        self.assertNotIn("diagnosis", event)
        self.assertEqual(event["hints_used"], [])

    def test_language_change_during_model_request_never_saves_stale_result(self):
        def change_language(*args, **kwargs):
            self.post("/api/workspace/sync", self.context(language="java", revision=2))
            return response()
        self.network.side_effect = change_language
        self.post("/api/diagnoses", self.context(), 409)
        self.assertFalse(self.records.exists())
        self.assertFalse(self.activities.exists())

    def test_multilanguage_acceptance_deduplicates_overall_completion_and_exposes_profile(self):
        for language in ("python", "java", "c", "cpp"):
            self.post("/api/accepted", {"problem_id": 1, "language": language,
                      "confirmed": True, "event_id": str(uuid4())})
        boot = self.client.get("/api/bootstrap").json()
        self.assertEqual(boot["summary"]["completed_ids"], [1])
        self.assertEqual(boot["summary"]["completed_problems"], 1)
        self.assertEqual(boot["summary"]["completed_by_language"], {"python": [1], "java": [1], "c": [1], "cpp": [1]})
        self.assertEqual(self.client.get("/api/capabilities").json(), boot["capability"])

    def test_custom_catalog_without_foreign_template_rejects_without_network_or_state_mutation(self):
        from services.problem_service import get_problem
        problem = {**get_problem(1), "slug": "custom-exercise-without-extension"}
        catalog = Path(self.directory.name) / "catalog.json"
        catalog.write_text(json.dumps([problem], ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, {"AI_TUTOR_CATALOG_PATH": str(catalog)}):
            accepted = self.diagnose(self.context())
            before = self.records.read_bytes()
            self.network.reset_mock()
            for language in ("java", "c", "cpp"):
                context = self.context(language=language, revision=2)
                self.post("/api/workspace/sync", context, 422)
                self.post("/api/diagnoses", context, 422)
                self.post("/api/submissions", {**context, "submission_id": str(uuid4())}, 422)
            self.network.assert_not_called()
            self.assertEqual(self.records.read_bytes(), before)
            self.assertFalse(self.activities.exists())
            restored = self.post("/api/hints", {"workspace_id": self.workspace_id,
                                 "revision": 1, "diagnosis_id": accepted["diagnosis_id"]})
            self.assertEqual(restored["hint_level"], 2)


if __name__ == "__main__":
    unittest.main()
