"""Execution HTTP boundary: fake Docker only, never write learning data."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.execution.config import ExecutionConfig
from backend.execution.service import ExecutionService
from backend.execution.adapters.python_adapter import RESULT_PREFIX


ROOT = Path(__file__).resolve().parents[1]


class ExecutionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (ROOT / "data").rglob("*") if path.is_file()}

    @classmethod
    def tearDownClass(cls):
        actual = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (ROOT / "data").rglob("*") if path.is_file()}
        if actual != cls.hashes:
            raise AssertionError("Execution tests changed production data")

    def setUp(self):
        self.runner = Mock()
        self.config = ExecutionConfig(enabled=True)
        self.service = ExecutionService(config=self.config, runner=self.runner)
        self.client = TestClient(create_app(execution_service=self.service),
                                 base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
        self.addCleanup(self.client.close)
        self.request = {"problem_id": 1, "language": "python", "code": "class Solution: pass"}

    def token(self):
        response = self.client.get("/api/execution/session")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()["token"]

    def test_session_is_local_only_and_run_requires_execution_token(self):
        token = self.token()
        self.assertGreaterEqual(len(token), 32)
        for headers in ({}, {"X-Execution-Token": "wrong"}):
            response = self.client.post("/api/execution/run", json=self.request, headers=headers)
            self.assertEqual(response.status_code, 403)
        self.runner.run.assert_not_called()

    def test_valid_run_compares_public_example_without_writing_learning_activity(self):
        self.runner.run.return_value = SimpleNamespace(
            status="SUCCESS", stdout=RESULT_PREFIX + '{"kind":"return","value":[2,1]}\n',
            stderr="", exit_code=0, execution_time_ms=42.5, error_message=None,
            error_code=None, cleanup_confirmed=True, limits={})
        with patch("backend.app.analyze_code") as model, patch("backend.app.clear_diagnosis") as clear, \
                patch("backend.app.save_record") as records, \
                patch("backend.app.record_submission") as submissions, patch("backend.app.mark_accepted") as accepted:
            response = self.client.post("/api/execution/run", json=self.request,
                                        headers={"X-Execution-Token": self.token()})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["execution_time_ms"], 42.5)
        self.assertTrue(data["judge"]["all_passed"])
        self.assertEqual(data["judge"]["scope"], "public_examples")
        self.assertFalse(data["judge"]["official_accepted"])
        self.assertNotIn("Accepted", response.text)
        self.assertNotIn(RESULT_PREFIX, data["stdout"])
        model.assert_not_called()
        clear.assert_not_called()
        records.assert_not_called()
        submissions.assert_not_called()
        accepted.assert_not_called()
        self.assertEqual(self.runner.run.call_args.args[1], {"nums": [4, 1, 6], "target": 7})

    def test_host_origin_remote_clients_and_cross_site_access_are_denied(self):
        for headers in ({"Host": "attacker.example:8000"}, {"Origin": "https://attacker.example"},
                        {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                response = self.client.get("/api/execution/session", headers=headers)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("token", response.json())
        remote = TestClient(create_app(execution_service=self.service), base_url="http://127.0.0.1:8000",
                            client=("192.0.2.10", 50000))
        self.addCleanup(remote.close)
        self.assertEqual(remote.get("/api/execution/session").status_code, 403)
        self.assertEqual(self.client.get("/api/execution/session", headers={"Origin": "http://localhost:5173"}).status_code, 200)
        self.runner.run.assert_not_called()

    def test_invalid_source_language_fields_and_client_test_overrides_are_rejected(self):
        token = self.token()
        variants = [
            {"language": "java"}, {"problem_id": True}, {"problem_id": "1"},
            {"code": " "}, {"code": "\x00"}, {"code": "中" * 21846},
            {"input": {"nums": [1, 2], "target": 3}}, {"memory_mb": 8192},
            {"image": "other"}, {"request_id": "not-a-uuid"},
        ]
        for changes in variants:
            with self.subTest(changes=list(changes)):
                response = self.client.post("/api/execution/run", json={**self.request, **changes},
                                            headers={"X-Execution-Token": token})
                self.assertEqual(response.status_code, 422, response.text)
        self.runner.run.assert_not_called()

    def test_unsupported_problem_and_disabled_engine_are_explicit(self):
        token = self.token()
        for problem_id, expected, code in ((217, 422, "PROBLEM_NOT_SUPPORTED"),
                                           (999999, 404, "PROBLEM_NOT_FOUND")):
            response = self.client.post("/api/execution/run", json={**self.request, "problem_id": problem_id},
                                        headers={"X-Execution-Token": token})
            self.assertEqual(response.status_code, expected, response.text)
            self.assertEqual(response.json()["error_code"], code)
        disabled = ExecutionService(config=replace(self.config, enabled=False), runner=self.runner)
        client = TestClient(create_app(execution_service=disabled), base_url="http://127.0.0.1:8000",
                            client=("127.0.0.1", 50000))
        self.addCleanup(client.close)
        token = client.get("/api/execution/session").json()["token"]
        response = client.post("/api/execution/run", json=self.request, headers={"X-Execution-Token": token})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error_code"], "EXECUTION_DISABLED")
        self.runner.run.assert_not_called()

    def test_body_is_bounded_before_json_and_content_length_is_not_trusted(self):
        import asyncio
        from backend.execution.routes import ExecutionBoundaryMiddleware

        called = []
        sent = []
        chunks = iter([b"x" * 300000, b"x" * 300000])

        async def application(scope, receive, send):
            called.append(True)

        async def receive():
            return {"type": "http.request", "body": next(chunks), "more_body": True}

        async def send(message):
            sent.append(message)

        middleware = ExecutionBoundaryMiddleware(application, self.service, "token")
        scope = {"type": "http", "method": "POST", "path": "/api/execution/run",
                 "client": ("127.0.0.1", 50000), "headers": [
                     (b"host", b"127.0.0.1:8000"), (b"content-type", b"application/json"),
                     (b"x-execution-token", b"token"), (b"content-length", b"1")]}
        asyncio.run(middleware(scope, receive, send))
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(called, [])
        self.runner.run.assert_not_called()

    def test_non_json_and_oversized_declared_body_are_rejected(self):
        token = self.token()
        response = self.client.post("/api/execution/run", content="{}",
                                    headers={"X-Execution-Token": token, "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 415)
        response = self.client.post("/api/execution/run", content="{}", headers={
            "X-Execution-Token": token, "Content-Type": "application/json", "Content-Length": "999999"})
        self.assertEqual(response.status_code, 413)
        self.runner.run.assert_not_called()

    def test_execution_configuration_error_does_not_break_existing_health_endpoint(self):
        with patch.dict("os.environ", {"AI_TUTOR_EXECUTION_ENABLED": "invalid"}):
            client = TestClient(create_app(), base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
        self.addCleanup(client.close)
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        session = client.get("/api/execution/session").json()
        self.assertFalse(session["capabilities"]["enabled"])
        self.assertFalse(session["capabilities"]["configuration_valid"])
        response = client.post("/api/execution/run", json=self.request,
                               headers={"X-Execution-Token": session["token"]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error_code"], "EXECUTION_CONFIG_INVALID")


if __name__ == "__main__":
    unittest.main()
