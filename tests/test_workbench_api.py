"""HTTP adapter tests; fake credentials, mocked network and temporary data only."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import create_app


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSIS = {
    "error_type": "边界条件错误", "knowledge": "列表索引",
    "analysis": "最后一次循环访问了不存在的下一项。",
    "hints": ["先检查循环末尾。", "代入只有一个元素的输入。", "让下一项索引小于列表长度。"],
}


def response(content=None, status="completed"):
    if content is None:
        content = DIAGNOSIS
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)
    body = {"status": status, "output": [{"type": "message", "content": [
        {"type": "output_text", "text": content}]}]}
    return io.BytesIO(json.dumps(body, ensure_ascii=False).encode("utf-8"))


class WorkbenchApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formal_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (ROOT / "data").rglob("*") if path.is_file()}

    @classmethod
    def tearDownClass(cls):
        actual = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (ROOT / "data").rglob("*") if path.is_file()}
        if actual != cls.formal_hashes:
            raise AssertionError("API tests changed production data")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ai-tutor-api-")
        self.addCleanup(self.directory.cleanup)
        self.records = Path(self.directory.name) / "records.json"
        self.activities = Path(self.directory.name) / "activities.json"
        self.records.write_text('[{"question":"synthetic legacy"},null]', encoding="utf-8")
        env = patch.dict(os.environ, {"AI_TUTOR_RECORDS_PATH": str(self.records),
                                     "AI_TUTOR_ACTIVITIES_PATH": str(self.activities),
                                     "DEEPSEEK_API_KEY": "fake-api-key", "DEEPSEEK_MODEL": "deepseek-flash"})
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

    def context(self, *, revision=1, problem_id=1, code="print(nums[i + 1])"):
        return {"workspace_id": self.workspace_id, "revision": revision,
                "problem_id": problem_id, "code": code}

    def post(self, path, body, expected=200):
        result = self.client.post(path, json=body)
        self.assertEqual(result.status_code, expected, result.text)
        return result.json()

    def accepted_diagnosis(self, **changes):
        context = self.context(**changes)
        candidate = self.post("/api/diagnoses", context)
        accepted = self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                             "request_id": candidate["request_id"], "revision": context["revision"]})
        return context, accepted

    def test_read_endpoints_use_catalog_and_existing_history_without_writing(self):
        before = self.records.read_bytes()
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        boot = self.client.get("/api/bootstrap").json()
        self.assertEqual(len(boot["problems"]), 32)
        self.assertEqual(len(boot["route"]), 8)
        self.assertEqual(boot["summary"]["total_submissions"], 0)
        self.assertEqual(len(boot["heatmap"]), 365)
        found = self.client.get("/api/problems", params={"query": "two sum"}).json()
        self.assertEqual([p["id"] for p in found["problems"]], [1])
        rows = self.client.get("/api/history").json()
        self.assertEqual([row["原始索引"] for row in rows["records"]], ["0", "1"])
        self.assertEqual(rows["records"][1]["状态"], "记录异常")
        self.assertEqual(rows["activities"], [])
        self.assertEqual(self.records.read_bytes(), before)
        self.assertFalse(self.activities.exists())
        self.network.assert_not_called()

    def test_diagnosis_is_saved_only_after_acceptance_and_repeated_accept_is_idempotent(self):
        before = self.records.read_bytes()
        context = self.context()
        candidate = self.post("/api/diagnoses", context)
        self.assertEqual(candidate["revision"], 1)
        self.assertEqual(self.records.read_bytes(), before)
        self.assertNotIn("diagnosis", candidate)
        accept = {"workspace_id": self.workspace_id, "request_id": candidate["request_id"], "revision": 1}
        result = self.post("/api/diagnoses/accept", accept)
        self.assertEqual(result["diagnosis"]["hints"], DIAGNOSIS["hints"][:1])
        self.assertEqual(result["hint_level"], 1)
        self.assertEqual(result["hint_count"], 3)
        self.assertEqual(result["diagnosis"]["source"], "deepseek")
        self.assertIs(result["diagnosis"]["is_mock"], False)
        rows = json.loads(self.records.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"question": "synthetic legacy"})
        self.assertIsNone(rows[1])
        self.assertEqual(rows[2]["hints_used"], [1])
        self.assertEqual(rows[2]["source"], "deepseek")
        self.assertEqual(rows[2]["record_id"], result["record_id"])
        self.assertEqual(self.post("/api/diagnoses/accept", accept), result)
        self.assertEqual(len(json.loads(self.records.read_text(encoding="utf-8"))), 3)
        self.network.assert_called_once()
        request = self.network.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/responses")
        model_input = json.loads(json.loads(request.data)["input"])
        self.assertEqual(model_input["code"], context["code"])
        self.assertEqual(model_input["problem"]["id"], 1)

    def test_hint_progress_is_persisted_capped_at_three_and_new_diagnosis_resets_it(self):
        context, accepted = self.accepted_diagnosis()
        hint = {"workspace_id": self.workspace_id, "revision": 1,
                "diagnosis_id": accepted["diagnosis_id"]}
        second = self.post("/api/hints", hint)
        self.assertEqual(second["hint_level"], 2)
        self.assertEqual(second["diagnosis"]["hints"], DIAGNOSIS["hints"][:2])
        third = self.post("/api/hints", hint)
        self.assertEqual(third["hint_level"], 3)
        self.assertEqual(third["diagnosis"]["hints"], DIAGNOSIS["hints"])
        self.assertEqual(self.post("/api/hints", hint)["hint_level"], 3)
        rows = json.loads(self.records.read_text(encoding="utf-8"))
        self.assertEqual(rows[-1]["hints_used"], [1, 2, 3])
        self.assertEqual(rows[-1]["hint_level"], 3)
        self.assertEqual(len(rows), 3)
        self.network.assert_called_once()
        _, fresh = self.accepted_diagnosis()
        self.assertEqual(fresh["hint_level"], 1)
        self.assertNotEqual(fresh["diagnosis_id"], accepted["diagnosis_id"])
        self.post("/api/hints", hint, 409)

    def test_diagnosis_submission_and_self_reported_acceptance_stay_independent(self):
        context, accepted = self.accepted_diagnosis()
        self.assertFalse(self.activities.exists())
        submission = {**context, "submission_id": str(uuid4())}
        self.post("/api/submissions", submission)
        self.post("/api/submissions", submission)
        activity = json.loads(self.activities.read_text(encoding="utf-8"))
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0]["hints_used"], [1])
        self.assertEqual(activity[0]["diagnosis"]["source"], "deepseek")
        boot = self.client.get("/api/bootstrap").json()
        self.assertEqual(boot["summary"]["total_submissions"], 1)
        self.assertEqual(boot["summary"]["completed_problems"], 0)
        event = {"problem_id": 1, "confirmed": False, "event_id": str(uuid4())}
        self.post("/api/accepted", event, 422)
        event["confirmed"] = True
        self.post("/api/accepted", event)
        self.post("/api/accepted", event)
        boot = self.client.get("/api/bootstrap").json()
        self.assertEqual(boot["summary"]["total_submissions"], 1)
        self.assertEqual(boot["summary"]["completed_problems"], 1)
        history = self.client.get("/api/history", params={"problem_id": 1}).json()
        self.assertEqual(history["records"][0]["原始索引"], "2")
        self.assertEqual(len(history["activities"]), 2)

    def test_submission_after_edit_omits_stale_diagnosis_snapshot(self):
        self.accepted_diagnosis()
        submission = {**self.context(revision=2, code="new source"), "submission_id": str(uuid4())}
        self.post("/api/submissions", submission)
        activity = json.loads(self.activities.read_text(encoding="utf-8"))[0]
        self.assertNotIn("diagnosis", activity)
        self.assertEqual(activity["hints_used"], [])

    def test_higher_revision_invalidates_an_accepted_diagnosis_even_when_code_matches(self):
        # A -> B -> A can arrive as rev3(A), rev2(B). Matching final source does
        # not make the diagnosis for rev1 current again.
        _, accepted = self.accepted_diagnosis()
        self.post("/api/workspace/sync", self.context(revision=3))
        self.post("/api/workspace/sync", self.context(revision=2, code="intermediate B"), 409)
        self.post("/api/hints", {"workspace_id": self.workspace_id, "revision": 3,
                  "diagnosis_id": accepted["diagnosis_id"]}, 409)
        self.post("/api/submissions", {**self.context(revision=3), "submission_id": str(uuid4())})
        activity = json.loads(self.activities.read_text(encoding="utf-8"))[0]
        self.assertNotIn("diagnosis", activity)
        self.assertEqual(activity["hints_used"], [])

    def test_hint_retries_with_expected_level_do_not_skip_the_next_hint(self):
        _, accepted = self.accepted_diagnosis()
        hint = {"workspace_id": self.workspace_id, "revision": 1,
                "diagnosis_id": accepted["diagnosis_id"], "expected_hint_level": 1}
        second = self.post("/api/hints", hint)
        self.assertEqual(second["hint_level"], 2)
        self.assertEqual(self.post("/api/hints", hint), second)
        hint["expected_hint_level"] = 3
        self.post("/api/hints", hint, 409)
        hint["expected_hint_level"] = 2
        third = self.post("/api/hints", hint)
        self.assertEqual(third["hint_level"], 3)
        self.assertEqual(self.post("/api/hints", hint), third)
        rows = json.loads(self.records.read_text(encoding="utf-8"))
        self.assertEqual(rows[-1]["hints_used"], [1, 2, 3])

    def test_edit_and_restore_invalidates_candidate_and_stale_sync_cannot_roll_back_draft(self):
        candidate = self.post("/api/diagnoses", self.context())
        changed = self.context(revision=2, code="changed source")
        self.post("/api/workspace/sync", changed)
        self.post("/api/workspace/sync", self.context(), 409)
        self.post("/api/workspace/sync", self.context(revision=3))
        self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                  "revision": 1, "request_id": candidate["request_id"]}, 409)
        self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                  "revision": 3, "request_id": candidate["request_id"]}, 409)
        self.assertEqual(len(json.loads(self.records.read_text(encoding="utf-8"))), 2)

    def test_switching_problem_and_editing_clear_old_hint_controls(self):
        for change in ({"problem_id": 20}, {"code": "changed"}):
            with self.subTest(change=change):
                self.workspace_id = str(uuid4())
                _, accepted = self.accepted_diagnosis()
                self.post("/api/workspace/sync", self.context(revision=2, **change))
                self.post("/api/hints", {"workspace_id": self.workspace_id, "revision": 2,
                          "diagnosis_id": accepted["diagnosis_id"]}, 409)

    def test_same_revision_cannot_describe_different_code_and_problem(self):
        self.post("/api/workspace/sync", self.context())
        self.post("/api/workspace/sync", self.context(code="changed"), 409)
        self.post("/api/workspace/sync", self.context(problem_id=20), 409)
        self.post("/api/workspace/sync", self.context())

    def test_response_is_discarded_when_editor_changes_during_the_network_request(self):
        before = self.records.read_bytes()
        def edit_during_request(*args, **kwargs):
            self.post("/api/workspace/sync", self.context(revision=2, code="new code"))
            return response()
        self.network.side_effect = edit_during_request
        self.post("/api/diagnoses", self.context(), 409)
        self.assertEqual(self.records.read_bytes(), before)

    def test_only_latest_of_rapid_same_code_requests_can_be_accepted(self):
        candidate = {}
        def newer_during_request(*args, **kwargs):
            self.network.side_effect = lambda *args, **kwargs: response()
            candidate.update(self.post("/api/diagnoses", self.context()))
            return response()
        self.network.side_effect = newer_during_request
        self.post("/api/diagnoses", self.context(), 409)
        accepted = self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                             "revision": 1, "request_id": candidate["request_id"]})
        self.assertEqual(accepted["hint_level"], 1)
        self.assertEqual(len(json.loads(self.records.read_text(encoding="utf-8"))), 3)
        self.assertEqual(self.network.call_count, 2)

    def test_candidate_replaced_before_acceptance_cannot_create_an_extra_record(self):
        first = self.post("/api/diagnoses", self.context())
        second = self.post("/api/diagnoses", self.context())
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                  "revision": 1, "request_id": first["request_id"]}, 409)
        self.post("/api/diagnoses/accept", {"workspace_id": self.workspace_id,
                  "revision": 1, "request_id": second["request_id"]})
        self.assertEqual(len(json.loads(self.records.read_text(encoding="utf-8"))), 3)

    def test_failures_never_create_successful_records_and_errors_are_safe(self):
        cases = [
            (lambda: (_ for _ in ()).throw(HTTPError("https://example.test", 401, "fake-api-key", {}, io.BytesIO())), "401"),
            (lambda: (_ for _ in ()).throw(HTTPError("https://example.test", 402, "fake-api-key", {}, io.BytesIO())), "402"),
            (lambda: (_ for _ in ()).throw(HTTPError("https://example.test", 429, "fake-api-key", {}, io.BytesIO())), "429"),
            (lambda: (_ for _ in ()).throw(TimeoutError("fake-api-key")), "超时"),
            (lambda: (_ for _ in ()).throw(URLError("fake-api-key")), "连接"),
            (lambda: response(""), "空响应"),
            (lambda: response("bad JSON"), "JSON"),
            (lambda: response({"analysis": "missing fields"}), "缺字段"),
            (lambda: response({**DIAGNOSIS, "hints": ["one"]}), "三级"),
            (lambda: response(status="incomplete"), "完整"),
        ]
        before = self.records.read_bytes()
        for callback, expected in cases:
            with self.subTest(expected=expected):
                self.network.side_effect = lambda *args, **kwargs: callback()
                error = self.post("/api/diagnoses", self.context(), 502)
                self.assertIn(expected, error["detail"])
                self.assertNotIn("fake-api-key", error["detail"])
                self.assertEqual(self.records.read_bytes(), before)
                self.assertFalse(self.activities.exists())

    def test_invalid_inputs_do_not_call_the_model_or_write_data(self):
        for body in (self.context(code=" "), self.context(problem_id=999999),
                     {**self.context(), "workspace_id": "not-a-uuid"},
                     self.context(revision=-1), {**self.context(), "revision": True}):
            with self.subTest(body=body):
                result = self.client.post("/api/diagnoses", json=body)
                self.assertIn(result.status_code, (404, 422))
                self.assertIsInstance(result.json()["detail"], str)
        self.network.assert_not_called()
        self.assertFalse(self.activities.exists())

    def test_corrupted_local_data_is_reported_without_overwrite(self):
        self.activities.write_text("not JSON", encoding="utf-8")
        before = self.activities.read_bytes()
        result = self.client.get("/api/bootstrap")
        self.assertEqual(result.status_code, 503)
        self.post("/api/submissions", {**self.context(), "submission_id": str(uuid4())}, 503)
        self.assertEqual(self.activities.read_bytes(), before)
        self.records.write_text("not JSON", encoding="utf-8")
        self.assertEqual(self.client.get("/api/history").status_code, 503)

    def test_record_save_failure_keeps_diagnosis_visible_but_warns_and_preserves_data(self):
        self.records.write_text("broken JSON", encoding="utf-8")
        before = self.records.read_bytes()
        _, accepted = self.accepted_diagnosis()
        self.assertIsNone(accepted["record_id"])
        self.assertIn("保存失败", accepted["warning"])
        self.assertEqual(self.records.read_bytes(), before)
        self.assertEqual(accepted["diagnosis"]["hints"], DIAGNOSIS["hints"][:1])

    def test_workspace_limit_never_evicts_an_inflight_request(self):
        with TestClient(create_app(workspace_limit=1)) as client:
            other_id = str(uuid4())
            def other_workspace_during_request(*args, **kwargs):
                result = client.post("/api/workspace/sync", json={**self.context(), "workspace_id": other_id})
                self.assertEqual(result.status_code, 503)
                return response()
            self.network.side_effect = other_workspace_during_request
            candidate = client.post("/api/diagnoses", json=self.context())
            self.assertEqual(candidate.status_code, 200)
            accepted = client.post("/api/diagnoses/accept", json={"workspace_id": self.workspace_id,
                                   "revision": 1, "request_id": candidate.json()["request_id"]})
            self.assertEqual(accepted.status_code, 200)


if __name__ == "__main__":
    unittest.main()
