"""Service behavior through fake runner; submissions never execute on the host."""
from dataclasses import replace
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from backend.execution.adapters.python_adapter import RESULT_PREFIX
from backend.execution.config import ExecutionConfig
from backend.execution.schemas import ExecutionRequest
from backend.execution.service import ExecutionRejected, ExecutionService
from backend.execution.exceptions import ExecutionBusy


def sandbox_result(**changes):
    fields = dict(status="SUCCESS", stdout=RESULT_PREFIX + '{"kind":"return","value":[1,2]}\n',
                  stderr="", exit_code=0, execution_time_ms=24.0, error_message=None,
                  error_code=None, cleanup_confirmed=True, limits={"memory_mb": 128})
    fields.update(changes)
    return SimpleNamespace(**fields)


class ExecutionServiceTests(unittest.TestCase):
    def setUp(self):
        self.runner = Mock()
        self.runner.run.return_value = sandbox_result()
        self.config = ExecutionConfig(enabled=True)
        self.service = ExecutionService(config=self.config, runner=self.runner)
        self.request = ExecutionRequest(problem_id=1, language="python", code="class Solution: pass")

    def test_wrong_answer_is_distinct_from_execution_failure(self):
        self.runner.run.return_value = sandbox_result(stdout=RESULT_PREFIX + '{"kind":"return","value":[]}\n')
        result = self.service.run(self.request)
        self.assertEqual(result.status, "SUCCESS")
        self.assertFalse(result.judge["all_passed"])
        self.assertEqual(result.judge["cases"][0]["error_type"], "invalid_index_count")

    def test_syntax_and_runtime_protocol_errors_are_reported(self):
        for kind, status in (("compile_error", "COMPILE_ERROR"), ("runtime_error", "RUNTIME_ERROR")):
            with self.subTest(kind=kind):
                self.runner.run.return_value = sandbox_result(status="RUNTIME_ERROR", exit_code=1,
                    stdout=RESULT_PREFIX + '{"kind":"' + kind + '","message":"test"}\n')
                result = self.service.run(self.request)
                self.assertEqual(result.status, status)
                self.assertEqual(result.judge["executed"], 0)
                self.assertFalse(result.judge["all_passed"])

    def test_external_limit_and_system_outcomes_cannot_be_overridden_by_student_protocol(self):
        for status in ("TIME_LIMIT_EXCEEDED", "OUTPUT_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED", "SYSTEM_ERROR"):
            with self.subTest(status=status):
                self.runner.run.return_value = sandbox_result(status=status)
                result = self.service.run(self.request)
                self.assertEqual(result.status, status)
                self.assertFalse(result.judge["all_passed"])
                self.assertEqual(result.judge["executed"], 0)

    def test_cross_process_busy_is_a_retryable_http_rejection(self):
        self.runner.run.side_effect = ExecutionBusy()
        with self.assertRaises(ExecutionRejected) as error:
            self.service.run(self.request)
        self.assertEqual(error.exception.status_code, 429)
        self.runner.run.side_effect = None
        self.assertEqual(self.service.run(self.request).status, "SUCCESS")

    def test_parser_diagnostics_obey_configured_utf8_stderr_budget(self):
        import json
        service = ExecutionService(config=replace(self.config, stderr_limit=128), runner=self.runner)
        self.runner.run.return_value = sandbox_result(status="RUNTIME_ERROR", exit_code=1,
            stdout=RESULT_PREFIX + json.dumps({"kind": "runtime_error", "message": "中" * 1000}))
        result = service.run(self.request)
        self.assertEqual(result.status, "RUNTIME_ERROR")
        self.assertLessEqual(len(result.stderr.encode("utf-8")), 128)

    def test_cleanup_uncertainty_disables_further_execution(self):
        self.runner.run.return_value = sandbox_result(cleanup_confirmed=False)
        result = self.service.run(self.request)
        self.assertEqual(result.status, "SYSTEM_ERROR")
        self.assertFalse(result.cleanup_confirmed)
        with self.assertRaises(ExecutionRejected) as error:
            self.service.run(self.request)
        self.assertEqual(error.exception.error_code, "CLEANUP_UNCONFIRMED")
        self.assertEqual(self.runner.run.call_count, 1)

    def test_unexpected_system_exception_is_sanitized_and_fails_closed(self):
        self.runner.run.side_effect = RuntimeError("D:\\secret\\key.txt SECRET_VALUE")
        result = self.service.run(self.request)
        self.assertEqual(result.status, "SYSTEM_ERROR")
        self.assertNotIn("secret", result.model_dump_json().lower())
        self.assertNotIn("SECRET_VALUE", result.model_dump_json())
        with self.assertRaises(ExecutionRejected):
            self.service.run(self.request)

    def test_busy_requests_are_rejected_and_slot_is_released_after_completion(self):
        entered, release = Event(), Event()
        def blocking_run(*_args):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test worker timed out")
            return sandbox_result()
        self.runner.run.side_effect = blocking_run
        completed = []
        worker = Thread(target=lambda: completed.append(self.service.run(self.request)))
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaises(ExecutionRejected) as error:
                self.service.run(self.request)
            self.assertEqual(error.exception.status_code, 429)
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(completed[0].status, "SUCCESS")
        self.runner.run.side_effect = None
        self.assertEqual(self.service.run(self.request).status, "SUCCESS")

    def test_configured_code_limit_cannot_be_overridden(self):
        service = ExecutionService(config=replace(self.config, code_limit=128), runner=self.runner)
        request = self.request.model_copy(update={"code": "#" + "x" * 129})
        with self.assertRaises(ExecutionRejected) as error:
            service.run(request)
        self.assertEqual(error.exception.status_code, 413)
        self.runner.run.assert_not_called()
